# fastapi_app/services/recommender.py
"""
🎯 Hidden Gem 추천 엔진 - 49차원 지표 기반 유사도 계산

알고리즘:
1. 벡터 유사도: 49개 수치 지표 → 코사인 + 유클리드 하이브리드
2. 태그 필터링: 9개 Boolean 태그로 필수/제외 조건
3. 가중치 시스템: 유저 지정 지표에 2배 가중치
4. Hidden Gem 보정: gem_potential 높고 review_count 낮은 게임 우대
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.game import Game, GameMetric, NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS
from schemas.game import RecommendedGame


class GameRecommender:
    """49차원 게임 추천 엔진"""
    
    def __init__(self):
        self.dimension = len(NUMERIC_METRIC_FIELDS)  # 49차원
        self.default_weights = {field: 1.0 for field in NUMERIC_METRIC_FIELDS}
    
    def _metric_to_vector(
        self, 
        metric: GameMetric, 
        weights: Dict[str, float] = None
    ) -> np.ndarray:
        """
        GameMetric → 49차원 벡터 변환
        - None 값은 5.0 (중립값)으로 대체
        - 가중치 적용 가능
        """
        if weights is None:
            weights = self.default_weights
        
        vector = []
        for field in NUMERIC_METRIC_FIELDS:
            value = getattr(metric, field, None)
            value = value if value is not None else 5.0
            weight = weights.get(field, 1.0)
            vector.append(value * weight)
        
        return np.array(vector, dtype=np.float32)
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """코사인 유사도 (0~1)"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
    
    def _euclidean_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """유클리드 거리 기반 유사도 (0~1)"""
        distance = np.linalg.norm(vec1 - vec2)
        # 최대 거리: sqrt(49 * 100) ≈ 70
        max_distance = 70.0
        return float(1 - min(distance / max_distance, 1.0))
    
    def _check_tags(
        self, 
        metric: GameMetric, 
        required: List[str], 
        excluded: List[str]
    ) -> bool:
        """태그 조건 확인"""
        for tag in required:
            if tag in BOOLEAN_TAG_FIELDS:
                if not getattr(metric, tag, False):
                    return False
        
        for tag in excluded:
            if tag in BOOLEAN_TAG_FIELDS:
                if getattr(metric, tag, False):
                    return False
        
        return True
    
    def _calculate_gem_bonus(self, game: Game, metric: GameMetric) -> float:
        """
        Hidden Gem 보너스
        - gem_potential 높을수록 보너스
        - review_count 적을수록 보너스 (진짜 숨겨진 보석)
        """
        gem = metric.gem_potential or 5.0
        confidence = metric.confidence_score or 0.5
        reviews = game.review_count or 0
        
        # 리뷰 1000개 이하면 보너스
        review_bonus = 0.1 * (1 - min(reviews / 1000, 1.0)) if reviews < 1000 else 0
        
        # gem_potential을 0~0.2 범위로
        gem_bonus = (gem / 10) * 0.2
        
        return (gem_bonus + review_bonus) * confidence
    
    def _generate_match_reasons(
        self,
        candidate_vec: np.ndarray,
        preferences: Dict[str, float] = None
    ) -> List[str]:
        """추천 이유 생성"""
        reasons = []
        
        if preferences:
            for field, target_value in preferences.items():
                if field in NUMERIC_METRIC_FIELDS:
                    idx = NUMERIC_METRIC_FIELDS.index(field)
                    actual_value = candidate_vec[idx]
                    diff = abs(actual_value - target_value)
                    
                    if diff <= 2:
                        if target_value >= 7:
                            reasons.append(f"✓ {field} 높음 ({actual_value:.1f})")
                        elif target_value <= 3:
                            reasons.append(f"✓ {field} 낮음 ({actual_value:.1f})")
                        else:
                            reasons.append(f"✓ {field} 적절 ({actual_value:.1f})")
        
        return reasons[:5]
    
    def _get_key_metrics(self, metric: GameMetric) -> Dict[str, float]:
        """핵심 지표 5개 추출 (극단값 우선)"""
        metrics_dict = {}
        
        for field in NUMERIC_METRIC_FIELDS:
            value = getattr(metric, field, None)
            if value is not None:
                metrics_dict[field] = value
        
        # 극단값 (0~2 또는 8~10) 우선
        extreme = {k: v for k, v in metrics_dict.items() if v <= 2 or v >= 8}
        
        priority = ['cozy_factor', 'strategic_depth', 'freedom_level', 
                   'horror_factor', 'narrative_depth']
        
        result = {}
        for p in priority:
            if p in extreme:
                result[p] = extreme[p]
            if len(result) >= 5:
                break
        
        for k, v in extreme.items():
            if k not in result:
                result[k] = v
            if len(result) >= 5:
                break
        
        if len(result) < 5:
            for field in priority:
                if field not in result and field in metrics_dict:
                    result[field] = metrics_dict[field]
                if len(result) >= 5:
                    break
        
        return result
    
    async def recommend_by_game(
        self,
        db: AsyncSession,
        app_id: int,
        count: int = 5,
        exclude_same_developer: bool = False
    ) -> Tuple[Optional[Game], List[Tuple[Game, GameMetric, float]]]:
        """특정 게임 기반 유사 게임 추천"""
        
        # 기준 게임 조회
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.app_id == app_id)
        )
        result = await db.execute(stmt)
        target_game = result.scalar_one_or_none()
        
        if not target_game or not target_game.metrics:
            return None, []
        
        target_vector = self._metric_to_vector(target_game.metrics)
        
        # 전체 게임 조회
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
            .where(Game.app_id != app_id)
        )
        
        if exclude_same_developer and target_game.developer:
            stmt = stmt.where(Game.developer != target_game.developer)
        
        result = await db.execute(stmt)
        candidates = result.scalars().all()
        
        # 유사도 계산
        scored = []
        for game in candidates:
            if not game.metrics:
                continue
            
            candidate_vector = self._metric_to_vector(game.metrics)
            
            # 하이브리드 유사도
            cosine = self._cosine_similarity(target_vector, candidate_vector)
            euclidean = self._euclidean_similarity(target_vector, candidate_vector)
            base_score = cosine * 0.6 + euclidean * 0.4
            
            # Hidden Gem 보너스
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            
            final_score = min(base_score + gem_bonus, 1.0)
            scored.append((game, game.metrics, final_score))
        
        scored.sort(key=lambda x: x[2], reverse=True)
        return target_game, scored[:count]
    
    async def recommend_by_preference(
        self,
        db: AsyncSession,
        preferences: Dict[str, float],
        required_tags: List[str] = None,
        excluded_tags: List[str] = None,
        count: int = 5,
        min_gem_potential: float = 0
    ) -> List[Tuple[Game, GameMetric, float]]:
        """유저 선호도 기반 추천"""
        required_tags = required_tags or []
        excluded_tags = excluded_tags or []
        
        # 선호도 벡터 생성
        target_vector = np.full(self.dimension, 5.0, dtype=np.float32)
        weights = {field: 1.0 for field in NUMERIC_METRIC_FIELDS}
        
        for field, value in preferences.items():
            if field in NUMERIC_METRIC_FIELDS:
                idx = NUMERIC_METRIC_FIELDS.index(field)
                target_vector[idx] = value
                weights[field] = 2.0  # 지정 지표 가중치 상승
        
        target_vector_weighted = target_vector * np.array(
            [weights[f] for f in NUMERIC_METRIC_FIELDS]
        )
        
        # 전체 게임 조회
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()
        
        # 필터링 및 점수 계산
        scored = []
        for game in candidates:
            if not game.metrics:
                continue
            
            # 태그 필터
            if not self._check_tags(game.metrics, required_tags, excluded_tags):
                continue
            
            # gem_potential 최소값 필터
            if min_gem_potential > 0:
                gp = game.metrics.gem_potential or 0
                if gp < min_gem_potential:
                    continue
            
            candidate_vector = self._metric_to_vector(game.metrics, weights)
            
            # 유클리드 위주 (선호도 매칭)
            euclidean = self._euclidean_similarity(target_vector_weighted, candidate_vector)
            cosine = self._cosine_similarity(target_vector_weighted, candidate_vector)
            base_score = euclidean * 0.7 + cosine * 0.3
            
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            final_score = min(base_score + gem_bonus, 1.0)
            
            scored.append((game, game.metrics, final_score))
        
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:count]
    
    def format_recommendations(
        self,
        results: List[Tuple[Game, GameMetric, float]],
        target_vector: np.ndarray = None,
        preferences: Dict[str, float] = None
    ) -> List[RecommendedGame]:
        """추천 결과를 응답 스키마로 변환"""
        formatted = []
        
        for game, metric, score in results:
            candidate_vec = self._metric_to_vector(metric)
            
            rec = RecommendedGame(
                app_id=game.app_id,
                name=game.name,
                genres=game.genres,
                header_image=game.header_image,
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_potential,
                match_reasons=self._generate_match_reasons(candidate_vec, preferences),
                key_metrics=self._get_key_metrics(metric)
            )
            formatted.append(rec)
        
        return formatted


# 싱글톤 인스턴스
recommender = GameRecommender()
