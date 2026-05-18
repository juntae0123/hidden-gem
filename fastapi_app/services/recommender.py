"""
Hidden Gem 추천 엔진 v3 (Hybrid Recommendation Engine)

하이브리드 유사도 알고리즘:
    - 49차원 지표 벡터: 코사인(35%) + 유클리드(35%)
    - 1536차원 임베딩 벡터: OpenAI text-embedding-3-small 코사인(30%)
    - 임베딩 없을 경우: 지표 코사인(50%) + 유클리드(50%) 폴백

추천 방식:
    1. by-game   : 특정 게임과 유사한 게임 추천 (임베딩 포함 하이브리드)
    2. by-preference : 원하는 지표 값을 직접 입력하여 맞춤 추천 (지표만)

Hidden Gem 보너스:
    - gem_potential 점수와 낮은 리뷰 수(< 1,000)를 조합해 숨겨진 명작 우대
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.game import (
    Game, GameMetric,
    NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS
)
from schemas.game import RecommendedGame
from config import settings


class GameRecommender:
    """
    하이브리드 게임 추천 엔진 (Hybrid Game Recommendation Engine)

    49차원 지표 벡터와 1536차원 임베딩을 결합한 유사도 계산으로
    정량적 특성(지표) + 의미적 유사성(임베딩)을 모두 반영.

    Attributes:
        dimension (int): 수치 지표 벡터 차원 수 (49)
        neutral_value (float): 지표 기본값 - None 필드 대체 (0~10 스케일 중간값)
        max_distance (float): 유클리드 거리 정규화 기준값 (이 거리를 유사도 0으로 처리)
    """

    def __init__(self):
        self.dimension = len(NUMERIC_METRIC_FIELDS)  # 49차원 고정
        self.neutral_value = 5.0   # null 지표를 중립값으로 대체 (0~10 중간)
        self.max_distance = 30.0   # 유클리드 거리 → 유사도 변환 시 최대 기준값

    # ==================== 벡터 변환 ====================

    def _metric_to_vector(
        self,
        metric: GameMetric,
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """
        GameMetric ORM 객체를 49차원 numpy 벡터로 변환 (Metric → Vector)

        NUMERIC_METRIC_FIELDS 순서대로 값을 추출하고, None 필드는
        neutral_value(5.0)로 대체. weights 가중치가 있으면 각 차원에 곱함.

        Args:
            metric: GameMetric ORM 인스턴스
            weights: {필드명: 가중치} 딕셔너리 (by-preference에서 강조 지표에 2.5 부여)

        Returns:
            shape=(49,) float32 numpy 배열
        """
        vector = np.empty(self.dimension, dtype=np.float32)
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            value = getattr(metric, field, None)
            if value is None:
                value = self.neutral_value  # null → 중립값 5.0 으로 폴백
            w = weights.get(field, 1.0) if weights else 1.0
            vector[i] = value * w
        return vector

    def _parse_embedding(self, metric: GameMetric) -> Optional[np.ndarray]:
        """
        GameMetric.embedding 필드를 1536차원 numpy 배열로 파싱 (Embedding Parser)

        pgvector 컬럼은 문자열 또는 리스트로 올 수 있어 두 경우 모두 처리.
        1536차원 불일치 시 None 반환하여 하이브리드 계산에서 폴백 처리.

        Args:
            metric: GameMetric ORM 인스턴스

        Returns:
            shape=(1536,) float32 배열 또는 None (임베딩 없거나 파싱 실패 시)
        """
        emb = getattr(metric, "embedding", None)
        if emb is None:
            return None
        try:
            if isinstance(emb, str):
                import json
                emb = json.loads(emb)  # pgvector가 문자열로 반환하는 경우 파싱
            arr = np.array(emb, dtype=np.float32)
            if arr.shape[0] == 1536:  # text-embedding-3-small 차원 검증
                return arr
        except Exception:
            pass
        return None

    # ==================== 유사도 계산 ====================

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        코사인 유사도 계산 (Cosine Similarity)

        두 벡터 간 방향 유사도를 0~1 범위로 반환.
        영벡터(all-zero) 입력 시 0.0 반환하여 ZeroDivision 방지.
        """
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        # np.clip 대신 max/min으로 부동소수점 오차 보정
        return float(max(0.0, min(np.dot(v1, v2) / (n1 * n2), 1.0)))

    def _euclidean_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        유클리드 거리 기반 유사도 계산 (Euclidean Similarity)

        거리를 0~1 유사도로 정규화: sim = 1 - min(dist / max_distance, 1.0)
        max_distance(30.0)는 49차원 지표 공간에서 실험적으로 결정된 기준값.
        """
        distance = float(np.linalg.norm(v1 - v2))
        return max(0.0, 1.0 - min(distance / self.max_distance, 1.0))

    def _hybrid_score(
        self,
        target_vec: np.ndarray,
        cand_vec: np.ndarray,
        target_emb: Optional[np.ndarray],
        cand_emb: Optional[np.ndarray],
        cosine_w: float = 0.35,
        euclidean_w: float = 0.35,
        embedding_w: float = 0.30,
    ) -> float:
        """
        49차원 지표 + 1536차원 임베딩 하이브리드 유사도 계산 (Hybrid Score)

        임베딩이 양쪽 모두 존재할 때: 코사인(35%) + 유클리드(35%) + 임베딩(30%)
        임베딩 없을 때: 코사인(50%) + 유클리드(50%) 폴백

        Args:
            target_vec: 기준 게임 49차원 지표 벡터
            cand_vec: 후보 게임 49차원 지표 벡터
            target_emb: 기준 게임 1536차원 임베딩 (없으면 None)
            cand_emb: 후보 게임 1536차원 임베딩 (없으면 None)

        Returns:
            0.0 ~ 1.0 사이의 최종 유사도 점수
        """
        cosine = self._cosine_similarity(target_vec, cand_vec)
        euclidean = self._euclidean_similarity(target_vec, cand_vec)

        # 임베딩 유사도 - 양쪽 모두 있을 때만 반영
        if target_emb is not None and cand_emb is not None:
            emb_sim = self._cosine_similarity(target_emb, cand_emb)
            score = cosine * cosine_w + euclidean * euclidean_w + emb_sim * embedding_w
        else:
            # 임베딩 없으면 지표만 5:5 (가중치 재분배)
            score = cosine * 0.5 + euclidean * 0.5

        return score

    # ==================== 필터링 ====================

    def _check_tags(
        self,
        metric: GameMetric,
        required: List[str],
        excluded: List[str]
    ) -> bool:
        """
        Boolean 태그 필터 검사 (Tag Filter Check)

        required_tags는 모두 True여야 통과, excluded_tags는 하나라도 True면 탈락.
        BOOLEAN_TAG_FIELDS에 없는 태그명은 조용히 무시 (API 레이어에서 사전 검증).

        Args:
            metric: 검사할 GameMetric
            required: 반드시 있어야 하는 태그 목록 (예: ["has_crafting"])
            excluded: 없어야 하는 태그 목록 (예: ["has_permadeath"])

        Returns:
            True = 필터 통과, False = 탈락
        """
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
        """
        Hidden Gem 보너스 점수 계산 (Gem Bonus Score)

        리뷰가 적은 숨겨진 명작에 우대 점수를 부여하여 추천 상위에 노출.
        - gem_potential: AI가 평가한 잠재 가치 (0~100 스케일)
        - review_bonus: 1,000개 미만 리뷰에 최대 0.05 부여 (리뷰 적을수록 큰 보너스)
        - confidence_score: 분석 신뢰도로 보너스 전체를 스케일 조정

        Returns:
            0.0 ~ ~0.15 범위의 보너스 (최종 점수에 더해짐)
        """
        gem = metric.gem_potential if metric.gem_potential is not None else 50.0
        confidence = metric.confidence_score if metric.confidence_score is not None else 0.5
        reviews = game.review_count or 0

        # 리뷰 수 1,000 미만인 게임에 역비례 보너스 (숨겨진 명작 발굴)
        if reviews < 1000:
            review_bonus = 0.05 * (1.0 - reviews / 1000.0)
        else:
            review_bonus = 0.0  # 충분히 알려진 게임에는 보너스 없음

        gem_bonus = (gem / settings.GEM_POTENTIAL_SCALE) * 0.10  # gem_potential → 최대 0.10
        return (gem_bonus + review_bonus) * confidence

    # ==================== 추천 이유 생성 ====================

    def _generate_match_reasons_from_preferences(
        self,
        candidate_vec: np.ndarray,
        preferences: Dict[str, float]
    ) -> List[str]:
        """
        선호도 기반 추천의 매칭 이유 생성 (Match Reasons for Preference-Based)

        유저가 요청한 선호 지표와 후보 게임의 실제 지표 값이
        오차 2.0 이내일 때 '매칭 이유'로 포함.

        Args:
            candidate_vec: 후보 게임 49차원 지표 벡터
            preferences: 유저 선호 지표 {필드명: 목표값}

        Returns:
            최대 5개의 한국어 매칭 이유 문자열 리스트
        """
        reasons = []
        for field, target_value in preferences.items():
            if field not in NUMERIC_METRIC_FIELDS:
                continue
            idx = NUMERIC_METRIC_FIELDS.index(field)
            actual_value = float(candidate_vec[idx])
            diff = abs(actual_value - target_value)
            if diff <= 2.0:  # 오차 ±2.0 이내를 '매칭'으로 판단
                if target_value >= 7:
                    reasons.append(f"✓ {field} 높음 ({actual_value:.1f})")
                elif target_value <= 3:
                    reasons.append(f"✓ {field} 낮음 ({actual_value:.1f})")
                else:
                    reasons.append(f"✓ {field} 적절 ({actual_value:.1f})")
        return reasons[:5]  # UI 표시용 최대 5개

    def _generate_match_reasons_from_target(
        self,
        target_vec: np.ndarray,
        candidate_vec: np.ndarray,
    ) -> List[str]:
        """
        게임 기반 추천의 매칭 이유 생성 (Match Reasons for Game-Based)

        기준 게임과 후보 게임이 공통으로 높거나 낮은 특성을 추출.
        두 벡터 간 차이가 1.5 이하이고, 동시에 극단값(≥7 or ≤3)인 경우만 포함.

        Args:
            target_vec: 기준 게임 49차원 벡터
            candidate_vec: 후보 게임 49차원 벡터

        Returns:
            최대 5개의 공통 특성 설명 문자열 리스트
        """
        common_features = []
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            target = float(target_vec[i])
            cand = float(candidate_vec[i])
            if abs(target - cand) <= 1.5:  # 두 게임이 유사한 값을 가질 때
                if target >= 7 and cand >= 7:
                    common_features.append((field, "공통적으로 높음", cand))
                elif target <= 3 and cand <= 3:
                    common_features.append((field, "공통적으로 낮음", cand))
        reasons = []
        for field, desc, value in common_features[:5]:
            reasons.append(f"✓ {field} {desc} ({value:.1f})")
        return reasons

    def _get_key_metrics(self, metric: GameMetric) -> Dict[str, float]:
        """
        게임의 특징적인 핵심 지표 추출 (Key Metric Extraction)

        UI에 표시할 대표 지표 5개를 우선순위 기반으로 선택.
        선택 우선순위:
            1) 극단값(≤2 or ≥8) 중 우선순위 필드
            2) 그 외 극단값 필드
            3) 극단값이 부족하면 우선순위 필드의 일반값으로 보완

        Args:
            metric: GameMetric ORM 인스턴스

        Returns:
            {지표명: 값} 딕셔너리 (최대 5개)
        """
        all_metrics = {}
        for field in NUMERIC_METRIC_FIELDS:
            v = getattr(metric, field, None)
            if v is not None:
                all_metrics[field] = float(v)

        # 극단값 필드 추출 (게임의 개성이 뚜렷한 지표)
        extreme = {k: v for k, v in all_metrics.items() if v <= 2 or v >= 8}

        # 게임 개성을 잘 나타내는 우선순위 필드 목록
        priority = [
            'cozy_factor', 'strategic_depth', 'horror_factor',
            'narrative_depth', 'freedom_level', 'action_pacing',
            'lore_richness', 'replay_value'
        ]

        result = {}
        # 1순위: 극단값 중 우선순위 필드
        for p in priority:
            if p in extreme and len(result) < 5:
                result[p] = extreme[p]
        # 2순위: 나머지 극단값
        for k, v in extreme.items():
            if len(result) >= 5:
                break
            if k not in result:
                result[k] = v
        # 3순위: 5개 미달 시 우선순위 필드의 일반값으로 보완
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
        """
        특정 게임 기반 유사 게임 추천 (Game-Based Recommendation)

        기준 게임의 49D 지표 + 1536D 임베딩을 사용한 하이브리드 유사도 계산.
        Hidden Gem 보너스 점수를 더해 숨겨진 명작을 상위에 노출.

        Args:
            db: 비동기 DB 세션
            app_id: 기준 게임의 Steam App ID
            count: 반환할 추천 게임 수 (기본 5)
            exclude_same_developer: True면 동일 개발사 게임 제외

        Returns:
            (기준 게임, [(게임, 지표, 최종점수, 기준벡터), ...]) 튜플
            기준 게임이 없으면 (None, []) 반환
        """
        # 기준 게임 조회 - metrics 관계를 함께 로드 (N+1 방지)
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
        target_emb = self._parse_embedding(target_game.metrics)

        # 후보 게임 조회 (활성화 + 분석 완료 + 기준 게임 제외)
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
            .where(Game.app_id != app_id)
        )
        if exclude_same_developer and target_game.developer:
            # 개발사 제외 옵션 - 같은 시리즈 추천 방지
            stmt = stmt.where(Game.developer != target_game.developer)

        result = await db.execute(stmt)
        candidates = result.scalars().all()

        # 전체 후보에 대해 하이브리드 점수 계산 후 정렬
        scored = []
        for game in candidates:
            if not game.metrics:
                continue

            cand_vec = self._metric_to_vector(game.metrics)
            cand_emb = self._parse_embedding(game.metrics)

            base_score = self._hybrid_score(target_vec, cand_vec, target_emb, cand_emb)
            gem_bonus = self._calculate_gem_bonus(game, game.metrics)
            final_score = min(base_score + gem_bonus, 1.0)  # 최대 1.0으로 클리핑

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
        """
        유저 선호도 기반 맞춤 추천 (Preference-Based Recommendation)

        유저가 직접 원하는 지표 값을 지정하면 해당 특성에 가중치(2.5)를 부여한
        목표 벡터를 생성하고, 지표 유사도로만 추천 (임베딩 미사용).

        가중치 전략:
            - 명시된 선호 지표: 2.5배 가중치 (강조)
            - 나머지 지표: 1.0배 (균등)
            - 유클리드(60%) + 코사인(40%) 조합으로 절대 거리 강조

        Args:
            db: 비동기 DB 세션
            preferences: {지표명: 원하는 값(0~10)} - 명시된 지표만 강조
            required_tags: 반드시 포함해야 할 Boolean 태그 목록
            excluded_tags: 제외할 Boolean 태그 목록
            count: 반환할 추천 수
            min_gem_potential: 최소 gem_potential 필터 (0이면 비활성)

        Returns:
            [(게임, 지표, 최종점수), ...] 내림차순 정렬
        """
        required_tags = required_tags or []
        excluded_tags = excluded_tags or []

        # 목표 벡터: 미지정 차원은 중립값(5.0), 지정 차원은 선호값으로 설정
        target_vec = np.full(self.dimension, self.neutral_value, dtype=np.float32)
        weights = {field: 1.0 for field in NUMERIC_METRIC_FIELDS}

        for field, value in preferences.items():
            if field in NUMERIC_METRIC_FIELDS:
                idx = NUMERIC_METRIC_FIELDS.index(field)
                target_vec[idx] = value
                weights[field] = 2.5  # 선호 지표에 2.5배 가중치로 매칭 강조

        # 가중치 배열로 목표 벡터를 스케일링 (후보 벡터도 동일 가중치로 계산해야 비교 가능)
        weight_array = np.array(
            [weights[f] for f in NUMERIC_METRIC_FIELDS],
            dtype=np.float32
        )
        target_weighted = target_vec * weight_array

        # 후보 게임 전체 조회
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        # 태그 필터링 + 점수 계산 (by-preference는 임베딩 없이 지표만 사용)
        scored = []
        for game in candidates:
            if not game.metrics:
                continue
            if not self._check_tags(game.metrics, required_tags, excluded_tags):
                continue  # 태그 조건 불만족 게임 제외
            if min_gem_potential > 0:
                gp = game.metrics.gem_potential
                if gp is None or gp < min_gem_potential:
                    continue  # 최소 gem_potential 미달 게임 제외

            cand_vec = self._metric_to_vector(game.metrics, weights)
            euclidean = self._euclidean_similarity(target_weighted, cand_vec)
            cosine = self._cosine_similarity(target_weighted, cand_vec)
            # 선호도 추천은 절대 거리(유클리드)를 더 강조 (by-game보다 유클리드 비중 높음)
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
        """
        선호도 추천 결과를 API 응답 스키마로 포맷 (Format Preference Results)

        Args:
            results: recommend_by_preference()의 반환값
            preferences: 유저가 입력한 선호 지표 (매칭 이유 생성에 사용)

        Returns:
            RecommendedGame Pydantic 모델 리스트
        """
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
        """
        게임 기반 추천 결과를 API 응답 스키마로 포맷 (Format Game Results)

        기준 게임의 target_vec와 비교해 공통 특성을 match_reasons로 생성.

        Args:
            results: recommend_by_game()의 반환값 (target_vec 포함)

        Returns:
            RecommendedGame Pydantic 모델 리스트
        """
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


# 앱 전역 싱글톤 인스턴스 - 임포트해서 사용 (from services.recommender import recommender)
recommender = GameRecommender()