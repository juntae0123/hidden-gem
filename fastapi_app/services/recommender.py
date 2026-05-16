"""
🎯 Hidden Gem 추천 엔진 v2 - 점수 변별력 강화

개선 사항:
1. 유클리드 거리 정규화 개선 (실제 거리 분포 반영)
2. 점수 변별력 강화 (round 정밀도 ↑, 가중치 재조정)
3. by-game에서도 match_reasons 생성 (공통 특징 분석)
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.game import (
    Game, GameMetric, 
    NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS
)
from schemas.game import RecommendedGame
from config import settings


class GameRecommender:
    """49차원 게임 추천 엔진"""
    
    def __init__(self):
        self.dimension = len(NUMERIC_METRIC_FIELDS)  # 49
        self.neutral_value = 5.0
        # 실제 게임 간 거리는 보통 10~30 범위 → 30을 1.0으로 정규화
        # (max_distance=70은 너무 커서 모든 점수가 1에 수렴함)
        self.max_distance = 30.0
    
    # ==================== 벡터 변환 ====================
    
    def _metric_to_vector(
        self, 
        metric: GameMetric, 
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """GameMetric → 49차원 벡터"""
        vector = np.empty(self.dimension, dtype=np.float32)
        
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            value = getattr(metric, field, None)
            if value is None:
                value = self.neutral_value
            
            w = weights.get(field, 1.0) if weights else 1.0
            vector[i] = value * w
        
        return vector
    
    # ==================== 유사도 계산 ====================
    
    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """코사인 유사도 (0~1)"""
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        
        if n1 == 0 or n2 == 0:
            return 0.0
        
        sim = float(np.dot(v1, v2) / (n1 * n2))
        return max(0.0, min(sim, 1.0))
    
    def _euclidean_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """유클리드 거리 기반 유사도 (0~1)
        
        max_distance=30으로 정규화 → 변별력 강화
        - 거리 0 → 1.0 (완전 일치)
        - 거리 15 → 0.5 (보통)
        - 거리 30+ → 0.0 (완전 다름)
        """
        distance = float(np.linalg.norm(v1 - v2))
        return max(0.0, 1.0 - min(distance / self.max_distance, 1.0))
    
    # ==================== 필터링 ====================
    
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
    
    # ==================== Hidden Gem 보너스 ====================
    
    def _calculate_gem_bonus(self, game: Game, metric: GameMetric) -> float:
        """Hidden Gem 보너스 (0~0.15) - 보너스 영향 축소"""
        gem = metric.gem_potential if metric.gem_potential is not None else 50.0
        confidence = metric.confidence_score if metric.confidence_score is not None else 0.5
        reviews = game.review_count or 0
        
        # 리뷰 적을수록 보너스 (1000개 이하 기준)
        if reviews < 1000:
            review_bonus = 0.05 * (1.0 - reviews / 1000.0)
        else:
            review_bonus = 0.0
        
        # gem_potential 정규화 (0~100 → 0~0.10)
        gem_bonus = (gem / settings.GEM_POTENTIAL_SCALE) * 0.10
        
        return (gem_bonus + review_bonus) * confidence
    
    # ==================== 추천 이유 생성 ====================
    
    def _generate_match_reasons_from_preferences(
        self,
        candidate_vec: np.ndarray,
        preferences: Dict[str, float]
    ) -> List[str]:
        """선호도 기반 추천 이유"""
        reasons = []
        
        for field, target_value in preferences.items():
            if field not in NUMERIC_METRIC_FIELDS:
                continue
            
            idx = NUMERIC_METRIC_FIELDS.index(field)
            actual_value = float(candidate_vec[idx])
            diff = abs(actual_value - target_value)
            
            if diff <= 2.0:
                if target_value >= 7:
                    reasons.append(f"✓ {field} 높음 ({actual_value:.1f})")
                elif target_value <= 3:
                    reasons.append(f"✓ {field} 낮음 ({actual_value:.1f})")
                else:
                    reasons.append(f"✓ {field} 적절 ({actual_value:.1f})")
        
        return reasons[:5]
    
    def _generate_match_reasons_from_target(
        self,
        target_vec: np.ndarray,
        candidate_vec: np.ndarray,
    ) -> List[str]:
        """기준 게임과 비교한 공통 특징"""
        reasons = []
        common_features = []
        
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            target = float(target_vec[i])
            cand = float(candidate_vec[i])
            
            # 둘 다 극단값이고 차이 작으면 공통 특징
            if abs(target - cand) <= 1.5:
                # 둘 다 높음 (7+)
                if target >= 7 and cand >= 7:
                    common_features.append((field, "공통적으로 높음", cand))
                # 둘 다 낮음 (≤3)
                elif target <= 3 and cand <= 3:
                    common_features.append((field, "공통적으로 낮음", cand))
        
        # 차이가 큰 정도순으로 정렬해서 상위 5개
        for field, desc, value in common_features[:5]:
            reasons.append(f"✓ {field} {desc} ({value:.1f})")
        
        return reasons
    
    def _get_key_metrics(self, metric: GameMetric) -> Dict[str, float]:
        """핵심 지표 5개 추출 (극단값 우선)"""
        all_metrics = {}
        for field in NUMERIC_METRIC_FIELDS:
            v = getattr(metric, field, None)
            if v is not None:
                all_metrics[field] = float(v)
        
        extreme = {k: v for k, v in all_metrics.items() if v <= 2 or v >= 8}
        
        priority = [
            'cozy_factor', 'strategic_depth', 'horror_factor',
            'narrative_depth', 'freedom_level', 'action_pacing',
            'lore_richness', 'replay_value'
        ]
        
        result = {}
        for p in priority:
            if p in extreme and len(result) < 5:
                result[p] = extreme[p]
        
        for k, v in extreme.items():
            if len(result) >= 5:
                break
            if k not in result:
                result[k] = v
        
        if len(result) < 5:
            for p in priority:
                if len(result) >= 5:
                    break
                if p not in result and p in all_metrics:
                    result[p] = all_metrics[p]
        
        return result
    
    # ==================== 추천 메인 로직 ====================
    
    async def recommend_by_game(
        self,
        db: AsyncSession,
        app_id: int,
        count: int = 5,
        exclude_same_developer: bool = False
    ) -> Tuple[Optional[Game], List[Tuple[Game, GameMetric, float, np.ndarray]]]:
        """특정 게임 기반 유사 게임 추천
        
        Returns:
            (기준 게임, [(게임, 지표, 점수, target_vec), ...])
            target_vec 추가 → format에서 match_reasons 생성용
        """
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
        
        target_vec = self._metric_to_vector(target_game.metrics)
        
        # 후보 조회
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
        
        # 점수 계산
        scored = []
        for game in candidates:
            if not game.metrics:
                continue
            
            cand_vec = self._metric_to_vector(game.metrics)
            
            cosine = self._cosine_similarity(target_vec, cand_vec)
            euclidean = self._euclidean_similarity(target_vec, cand_vec)
            base_score = cosine * 0.5 + euclidean * 0.5  # 5:5 균형
            
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            final_score = min(base_score + gem_bonus, 1.0)
            
            scored.append((game, game.metrics, final_score, target_vec))
        
        scored.sort(key=lambda x: x[2], reverse=True)
        return target_game, scored[:count]
    
    async def recommend_by_preference(
        self,
        db: AsyncSession,
        preferences: Dict[str, float],
        required_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        count: int = 5,
        min_gem_potential: float = 0.0
    ) -> List[Tuple[Game, GameMetric, float]]:
        """유저 선호도 기반 추천"""
        required_tags = required_tags or []
        excluded_tags = excluded_tags or []
        
        # 목표 벡터
        target_vec = np.full(self.dimension, self.neutral_value, dtype=np.float32)
        weights = {field: 1.0 for field in NUMERIC_METRIC_FIELDS}
        
        for field, value in preferences.items():
            if field in NUMERIC_METRIC_FIELDS:
                idx = NUMERIC_METRIC_FIELDS.index(field)
                target_vec[idx] = value
                weights[field] = 2.5  # 지정 지표 가중치 강화
        
        weight_array = np.array(
            [weights[f] for f in NUMERIC_METRIC_FIELDS],
            dtype=np.float32
        )
        target_weighted = target_vec * weight_array
        
        # 후보 조회
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()
        
        # 점수 계산
        scored = []
        for game in candidates:
            if not game.metrics:
                continue
            
            if not self._check_tags(game.metrics, required_tags, excluded_tags):
                continue
            
            if min_gem_potential > 0:
                gp = game.metrics.gem_potential
                if gp is None or gp < min_gem_potential:
                    continue
            
            cand_vec = self._metric_to_vector(game.metrics, weights)
            
            euclidean = self._euclidean_similarity(target_weighted, cand_vec)
            cosine = self._cosine_similarity(target_weighted, cand_vec)
            base_score = euclidean * 0.6 + cosine * 0.4
            
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            final_score = min(base_score + gem_bonus, 1.0)
            
            scored.append((game, game.metrics, final_score))
        
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:count]
    
    # ==================== 응답 포맷팅 ====================
    
    def format_recommendations_by_preference(
        self,
        results: List[Tuple[Game, GameMetric, float]],
        preferences: Dict[str, float]
    ) -> List[RecommendedGame]:
        """선호도 기반 추천 결과 포맷"""
        formatted = []
        
        for game, metric, score in results:
            cand_vec = self._metric_to_vector(metric)
            
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_potential,
                match_reasons=self._generate_match_reasons_from_preferences(
                    cand_vec, preferences
                ),
                key_metrics=self._get_key_metrics(metric),
            ))
        
        return formatted
    
    def format_recommendations_by_game(
        self,
        results: List[Tuple[Game, GameMetric, float, np.ndarray]]
    ) -> List[RecommendedGame]:
        """게임 기반 추천 결과 포맷 (공통 특징 분석)"""
        formatted = []
        
        for game, metric, score, target_vec in results:
            cand_vec = self._metric_to_vector(metric)
            
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_potential,
                match_reasons=self._generate_match_reasons_from_target(
                    target_vec, cand_vec
                ),
                key_metrics=self._get_key_metrics(metric),
            ))
        
        return formatted


# 싱글톤 인스턴스
recommender = GameRecommender()
