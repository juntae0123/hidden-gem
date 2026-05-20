"""
Hidden Gem 추천 엔진 v3 (Hybrid Recommendation Engine)

하이브리드 유사도 알고리즘:
    - 49차원 지표 벡터: 코사인(35%) + 유클리드(35%)
    - 1536차원 임베딩 벡터: OpenAI text-embedding-3-small 코사인(30%)
    - 임베딩 없을 경우: 지표 코사인(50%) + 유클리드(50%) 폴백

추천 방식:
    1. by-game       : 특정 게임과 유사한 게임 추천 (임베딩 포함 하이브리드)
    2. by-preference : 원하는 지표 값을 직접 입력하여 맞춤 추천 (지표만)
    3. semantic      : 자연어 쿼리 → GPT 번역/지표 추출 → pgvector 유사도 검색

Hidden Gem 보너스:
    - gem_potential 점수와 낮은 리뷰 수(< 1,000)를 조합해 숨겨진 명작 우대
"""

import json

# 지표 한국어 라벨 / Korean metric labels for match reasons
METRIC_LABELS_KO: dict = {
    "cozy_factor": "아늑함", "horror_factor": "공포", "gore_level": "고어",
    "humor_rating": "유머", "dark_fantasy_vibe": "다크판타지", "epic_scale": "스케일",
    "melancholy": "멜랑콜리", "reflex_demand": "반응속도", "strategic_depth": "전략깊이",
    "grind_factor": "노가다", "time_pressure": "시간압박", "learning_curve": "학습곡선",
    "freedom_level": "자유도", "action_pacing": "액션템포", "rng_dependency": "RNG의존도",
    "growth_reward": "성장보상", "exploration_reward": "탐험보상",
    "management_complexity": "관리복잡도", "stealth_importance": "스텔스",
    "session_length": "세션길이", "narrative_linearity": "서사선형성",
    "puzzle_complexity": "퍼즐복잡도", "platforming_precision": "플랫폼정밀도",
    "coop_synergy": "협동시너지", "competitive_stress": "경쟁스트레스",
    "npc_interaction": "NPC상호작용", "user_creation": "유저창작",
    "multiplayer_scale": "멀티규모", "lore_richness": "세계관밀도",
    "choice_consequence": "선택결과", "visual_spectacle": "시각연출",
    "environmental_storytelling": "환경서사", "soundtrack_impact": "사운드트랙",
    "build_variety": "빌드다양성", "progression_clarity": "진행명확성",
    "save_flexibility": "저장유연성", "difficulty_accessibility": "난이도접근성",
    "tutorial_quality": "튜토리얼", "ui_ux_polish": "UI/UX완성도",
    "modding_support": "모딩지원", "art_style_uniqueness": "아트독창성",
    "audio_design": "오디오디자인", "animation_quality": "애니메이션",
    "world_reactivity": "세계반응성", "community_dependency": "커뮤니티의존",
    "narrative_depth": "서사깊이", "replay_value": "리플레이",
    "endgame_content": "엔드게임", "monetization_fairness": "과금공정성",
}
import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from openai import AsyncOpenAI

from models.game import (
    Game, GameMetric,
    NUMERIC_METRIC_FIELDS, BOOLEAN_TAG_FIELDS
)
from schemas.game import RecommendedGame
from config import settings


class GameRecommender:
    """
    49차원 지표 + 1536차원 임베딩 하이브리드 게임 추천 엔진
    Hybrid game recommender using 49D metric vectors + 1536D embeddings.
    """

    def __init__(self):
        # 수치 지표 차원 수 / Number of numeric metric dimensions
        self.dimension = len(NUMERIC_METRIC_FIELDS)  # 49
        self.neutral_value = 5.0
        # 실제 게임 간 거리 분포 기준 정규화 값 / Normalization factor for euclidean distance
        self.max_distance = 30.0
        # OpenAI 비동기 클라이언트 / Async OpenAI client for embedding generation
        self._openai: Optional[AsyncOpenAI] = None

    def _get_openai(self) -> AsyncOpenAI:
        """
        OpenAI 클라이언트 싱글톤 반환 (Lazy OpenAI Client Initialization)
        최초 호출 시에만 인스턴스 생성, 이후 재사용.
        """
        if self._openai is None:
            self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai

    # ==================== 벡터 변환 / Vector Conversion ====================

    def _metric_to_vector(
        self,
        metric: GameMetric,
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """
        GameMetric → 49차원 numpy 벡터 변환 (Metric to 49D Vector)
        가중치 딕셔너리가 주어지면 각 지표에 가중치를 곱해 벡터 생성.

        Args:
            metric: GameMetric ORM 인스턴스
            weights: 지표별 가중치 딕셔너리 (없으면 모두 1.0)
        Returns:
            np.ndarray: 49차원 float32 벡터
        """
        vector = np.empty(self.dimension, dtype=np.float32)
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            value = getattr(metric, field, None)
            if value is None:
                value = self.neutral_value  # null → 중립값 5.0 / Replace null with neutral
            w = weights.get(field, 1.0) if weights else 1.0
            vector[i] = value * w
        return vector

    def _parse_embedding(self, metric: GameMetric) -> Optional[np.ndarray]:
        """
        GameMetric.embedding → numpy 배열 변환 (Parse Stored Embedding)
        DB에 JSON 문자열 또는 벡터로 저장된 임베딩을 numpy 배열로 파싱.

        Returns:
            np.ndarray: 1536차원 float32 벡터, 실패 시 None
        """
        emb = getattr(metric, "embedding", None)
        if emb is None:
            return None
        try:
            if isinstance(emb, str):
                emb = json.loads(emb)
            arr = np.array(emb, dtype=np.float32)
            if arr.shape[0] == 1536:
                return arr
        except Exception:
            pass
        return None

    # ==================== 유사도 계산 / Similarity Calculation ====================

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        코사인 유사도 계산 (Cosine Similarity)
        두 벡터의 방향 유사도를 0~1 범위로 반환.
        """
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        sim = float(np.dot(v1, v2) / (n1 * n2))
        return max(0.0, min(sim, 1.0))

    def _euclidean_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        유클리드 거리 기반 유사도 (Euclidean Similarity)
        max_distance=30 기준 정규화 → 0~1 범위.
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
        49차원 지표 + 1536차원 임베딩 하이브리드 유사도 (Hybrid Similarity Score)
        임베딩이 없으면 지표 코사인/유클리드 5:5 폴백.
        """
        cosine = self._cosine_similarity(target_vec, cand_vec)
        euclidean = self._euclidean_similarity(target_vec, cand_vec)
        if target_emb is not None and cand_emb is not None:
            emb_sim = self._cosine_similarity(target_emb, cand_emb)
            return cosine * cosine_w + euclidean * euclidean_w + emb_sim * embedding_w
        else:
            return cosine * 0.5 + euclidean * 0.5

    # ==================== 필터링 / Filtering ====================

    def _check_tags(
        self,
        metric: GameMetric,
        required: List[str],
        excluded: List[str]
    ) -> bool:
        """
        Boolean 태그 조건 필터 (Tag Filter)
        required 태그는 모두 True, excluded 태그는 모두 False여야 통과.
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

    # ==================== Hidden Gem 보너스 / Gem Bonus ====================

    def _calculate_gem_bonus(self, game: Game, metric: GameMetric) -> float:
        """
        Hidden Gem 보너스 계산 (Hidden Gem Bonus Score)
        gem_percentile 기반으로 보너스 계산 (없으면 gem_potential 폴백).
        리뷰 1,000개 미만 게임 우대 → 최대 0.15 보너스.
        """
        # gem_percentile 우선 사용, 없으면 gem_potential 폴백
        # Use gem_percentile first, fallback to gem_potential
        gem = metric.gem_percentile if metric.gem_percentile is not None \
            else (metric.gem_potential if metric.gem_potential is not None else 50.0)
        confidence = metric.confidence_score if metric.confidence_score is not None else 0.5
        reviews = game.review_count or 0

        # 리뷰 1,000개 미만 게임 우대 / Boost games with fewer reviews
        if reviews < 1000:
            review_bonus = 0.05 * (1.0 - reviews / 1000.0)
        else:
            review_bonus = 0.0

        # gem 0~100 → 0~0.10 정규화 / Normalize gem to 0~0.10
        gem_bonus = (gem / 100.0) * 0.10

        return (gem_bonus + review_bonus) * confidence

    # ==================== 추천 이유 생성 / Match Reason Generation ====================

    def _generate_match_reasons_from_preferences(
        self,
        candidate_vec: np.ndarray,
        preferences: Dict[str, float]
    ) -> List[str]:
        """
        선호도 기반 추천 이유 생성 (Preference-based Match Reasons)
        유저가 지정한 지표와 후보 게임의 실제 값 비교 → 차이 ≤ 2.0이면 이유 포함.
        """
        reasons = []
        for field, target_value in preferences.items():
            if field not in NUMERIC_METRIC_FIELDS:
                continue
            idx = NUMERIC_METRIC_FIELDS.index(field)
            actual_value = float(candidate_vec[idx])
            diff = abs(actual_value - target_value)
            if diff <= 2.0:
                if target_value >= 7:
                    reasons.append(f"✓ {METRIC_LABELS_KO.get(field, field)} 높음 ({actual_value:.1f})")
                elif target_value <= 3:
                    reasons.append(f"✓ {METRIC_LABELS_KO.get(field, field)} 낮음 ({actual_value:.1f})")
                else:
                    reasons.append(f"✓ {METRIC_LABELS_KO.get(field, field)} 적절 ({actual_value:.1f})")
        return reasons[:5]

    def _generate_match_reasons_from_target(
        self,
        target_vec: np.ndarray,
        candidate_vec: np.ndarray,
    ) -> List[str]:
        """
        기준 게임과의 공통 특징 추출 (Target-based Match Reasons)
        두 게임 모두 극단값이고 차이가 1.5 이하인 지표를 공통 특징으로 추출.
        """
        common_features = []
        for i, field in enumerate(NUMERIC_METRIC_FIELDS):
            target = float(target_vec[i])
            cand = float(candidate_vec[i])
            if abs(target - cand) <= 1.5:
                if target >= 7 and cand >= 7:
                    common_features.append((field, "공통적으로 높음", cand))
                elif target <= 3 and cand <= 3:
                    common_features.append((field, "공통적으로 낮음", cand))
        reasons = []
        for field, desc, value in common_features[:5]:
            reasons.append(f"✓ {METRIC_LABELS_KO.get(field, field)} {desc} ({value:.1f})")
        return reasons

    def _get_key_metrics(self, metric: GameMetric) -> Dict[str, float]:
        """
        핵심 지표 5개 추출 (Key Metrics Extraction)
        극단값(≤2 or ≥8) 우선, priority 목록 순으로 최대 5개 반환.
        """
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

    # ==================== 시맨틱 검색 / Semantic Search ====================

    async def analyze_query(self, query: str) -> Dict:
        """
        자연어 쿼리 분석 (Query Analysis via GPT)
        GPT-4.1-mini로 검색어를 영어 번역 + 지표 힌트 추출.

        Returns:
            {
                "english_query": "relaxing solo strategy game",
                "metric_hints": {"cozy_factor": 8, "strategic_depth": 7},
                "excluded_metrics": {"horror_factor": 0, "multiplayer_scale": 0}
            }
        """
        client = self._get_openai()

        # 유효한 지표 목록 전달 / Pass valid metric names to GPT
        valid_metrics = NUMERIC_METRIC_FIELDS[:20]  # 주요 20개만 / Top 20 for token efficiency

        prompt = f"""You are a game recommendation assistant. Analyze this Korean game search query and return JSON.

Query: "{query}"

Return ONLY valid JSON with these fields:
{{
  "english_query": "translate to English, focus on game feel/atmosphere",
  "metric_hints": {{"metric_name": score_0_to_10}},
  "reasoning": "brief explanation"
}}

Valid metric names (use only these): {valid_metrics}

Examples:
- "혼자 조용히 즐기는 힐링 게임" → {{"english_query": "cozy relaxing solo healing game peaceful", "metric_hints": {{"cozy_factor": 9, "horror_factor": 0, "multiplayer_scale": 0, "action_pacing": 2}}}}
- "전략적이고 어려운 로그라이크" → {{"english_query": "strategic challenging roguelike permadeath", "metric_hints": {{"strategic_depth": 9, "learning_curve": 8, "replay_value": 9}}}}
- "공포스럽고 분위기 있는 게임" → {{"english_query": "horror atmospheric dark scary game", "metric_hints": {{"horror_factor": 9, "dark_fantasy_vibe": 8, "cozy_factor": 0}}}}
"""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception:
            # GPT 실패 시 원본 쿼리 그대로 사용 / Fallback to original query
            return {"english_query": query, "metric_hints": {}}

    async def embed_query(self, query: str) -> np.ndarray:
        """
        텍스트를 1536차원 임베딩으로 변환 (Query Embedding)
        OpenAI text-embedding-3-small 모델 사용.

        Args:
            query: 영어로 번역된 검색어 (영어일수록 품질 좋음)
        Returns:
            np.ndarray: 1536차원 float32 임베딩 벡터
        """
        client = self._get_openai()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def _normalize_scores(
        self,
        scored: List[Tuple],
        score_idx: int = 2
    ) -> List[Tuple]:
        """
        점수 정규화 - 1위를 1.0으로 상대 정규화 (Score Normalization)
        검색 결과 중 최고점을 1.0으로 두고 나머지를 상대적으로 변환.
        변별력 있는 매치율 표시를 위해 사용.

        Args:
            scored: (game, metric, score, ...) 튜플 리스트
            score_idx: 점수가 위치한 인덱스
        Returns:
            정규화된 점수로 교체된 동일 구조 리스트
        """
        if not scored:
            return scored

        scores = [item[score_idx] for item in scored]
        max_score = max(scores)
        min_score = min(scores)
        score_range = max_score - min_score

        if score_range == 0:
            return scored

        normalized = []
        for item in scored:
            raw_score = item[score_idx]
            # min-max 정규화 후 0.5~1.0 범위로 스케일 / Scale to 0.5~1.0 range
            norm = (raw_score - min_score) / score_range
            scaled = 0.5 + norm * 0.5
            normalized.append(item[:score_idx] + (round(scaled, 4),) + item[score_idx+1:])

        return normalized

    async def semantic_search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 12,
        min_gem_potential: float = 0.0,
    ) -> List[Tuple[Game, GameMetric, float]]:
        """
        자연어 시맨틱 검색 v2 (Enhanced Natural Language Semantic Search)

        흐름:
        1. GPT-4.1-mini로 쿼리 분석 (영어 번역 + 지표 힌트 추출)
        2. 영어 쿼리로 임베딩 생성 (품질 향상)
        3. pgvector 코사인 유사도 검색
        4. 지표 힌트로 추가 필터링/정렬
        5. FINAL SCORE = 임베딩 유사도(60%) + gem_percentile(40%)
        6. 상대 정규화 (1위=1.0)

        Args:
            query: 자연어 검색어 (한국어/영어 모두 가능)
            limit: 반환할 최대 게임 수
            min_gem_potential: 최소 gem_potential 필터
        Returns:
            [(Game, GameMetric, normalized_score), ...]
        """
        # 1. GPT로 쿼리 분석 / Analyze query with GPT
        analysis = await self.analyze_query(query)
        english_query = analysis.get("english_query", query)
        metric_hints = analysis.get("metric_hints", {})

        # 2. 영어 쿼리로 임베딩 생성 / Generate embedding from English query
        query_vec = await self.embed_query(english_query)
        query_vec_str = str(query_vec.tolist())

        # 3. pgvector 코사인 유사도 검색 / pgvector cosine similarity search
        # 여유롭게 2배 가져와서 지표 힌트 필터링 후 limit 적용
        # Fetch 2x limit to allow metric hint filtering
        sql = text("""
            SELECT
                g.id AS game_id,
                g.app_id,
                1 - (gm.embedding <=> :query_vec ::vector) AS emb_similarity,
                COALESCE(gm.gem_percentile, gm.gem_potential, 50) AS gem_score
            FROM game_metrics gm
            JOIN games g ON g.id = gm.game_id
            WHERE g.is_active = true
              AND g.is_analyzed = true
              AND gm.embedding IS NOT NULL
              AND (:min_gem = 0 OR gm.gem_potential >= :min_gem)
            ORDER BY gm.embedding <=> :query_vec ::vector
            LIMIT :limit
        """)

        result = await db.execute(sql, {
            "query_vec": query_vec_str,
            "min_gem": min_gem_potential,
            "limit": limit * 2,
        })
        rows = result.fetchall()

        if not rows:
            return []

        # 4. FINAL SCORE 계산 / Compute final score
        # = 임베딩 유사도 60% + gem_percentile 40%
        # Embedding similarity 60% + gem_percentile 40%
        scored_rows = []
        for row in rows:
            emb_sim = float(row.emb_similarity)
            gem_score = float(row.gem_score) / 100.0  # 0~100 → 0~1 정규화
            final_score = emb_sim * 0.6 + gem_score * 0.4
            scored_rows.append((row.game_id, row.app_id, final_score))

        # 5. 지표 힌트로 필터링 / Apply metric hint filtering
        # 힌트와 크게 다른 게임 페널티 적용 / Penalize games far from metric hints
        game_ids = [r[0] for r in scored_rows]
        sim_map = {r[0]: r[2] for r in scored_rows}

        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.id.in_(game_ids))
        )
        games_result = await db.execute(stmt)
        games = games_result.scalars().all()
        games_map = {g.id: g for g in games}

        final_scored = []
        for game_id, app_id, base_score in scored_rows:
            game = games_map.get(game_id)
            if not game or not game.metrics:
                continue

            score = base_score

            # 지표 힌트 패널티/보너스 / Metric hint penalty/bonus
            if metric_hints:
                hint_match = 0.0
                for metric_name, target_val in metric_hints.items():
                    if metric_name not in NUMERIC_METRIC_FIELDS:
                        continue
                    actual = getattr(game.metrics, metric_name, None)
                    if actual is None:
                        continue
                    diff = abs(float(actual) - float(target_val))
                    # 차이가 적을수록 보너스 / Smaller diff = more bonus
                    hint_match += max(0, 1.0 - diff / 10.0)

                if metric_hints:
                    hint_score = hint_match / len(metric_hints)
                    # 지표 힌트 10% 반영 / Apply 10% metric hint weight
                    score = score * 0.9 + hint_score * 0.1

            final_scored.append((game, game.metrics, score))

        # 6. 정렬 후 limit 적용 / Sort and apply limit
        final_scored.sort(key=lambda x: x[2], reverse=True)
        final_scored = final_scored[:limit]

        # 7. 상대 정규화 (1위=1.0, 최하위=0.5) / Relative normalization
        final_scored = self._normalize_scores(final_scored, score_idx=2)

        return final_scored

    # ==================== 추천 메인 로직 / Main Recommendation Logic ====================

    async def recommend_by_game(
        self,
        db: AsyncSession,
        app_id: int,
        count: int = 5,
        exclude_same_developer: bool = False
    ) -> Tuple[Optional[Game], List[Tuple[Game, GameMetric, float, np.ndarray]]]:
        """
        특정 게임 기반 유사 게임 추천 (Game-based Recommendation)
        기준 게임의 지표 벡터 + 임베딩을 활용한 하이브리드 유사도 계산.

        Returns:
            (기준 게임, [(후보 게임, 지표, 유사도 점수, 기준 벡터), ...])
        """
        # 기준 게임 조회 / Fetch target game
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

        # 후보 게임 조회 / Fetch candidate games
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

        # 하이브리드 점수 계산 / Compute hybrid scores
        scored = []
        for game in candidates:
            if not game.metrics:
                continue
            cand_vec = self._metric_to_vector(game.metrics)
            cand_emb = self._parse_embedding(game.metrics)

            base_score = self._hybrid_score(target_vec, cand_vec, target_emb, cand_emb)
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
        """
        유저 선호도 기반 맞춤 추천 (Preference-based Recommendation)
        지정한 지표에 2.5배 가중치를 부여해 선호도 벡터 생성 후 유사도 계산.
        """
        required_tags = required_tags or []
        excluded_tags = excluded_tags or []

        # 목표 벡터 생성 / Build target preference vector
        target_vec = np.full(self.dimension, self.neutral_value, dtype=np.float32)
        weights = {field: 1.0 for field in NUMERIC_METRIC_FIELDS}

        for field, value in preferences.items():
            if field in NUMERIC_METRIC_FIELDS:
                idx = NUMERIC_METRIC_FIELDS.index(field)
                target_vec[idx] = value
                weights[field] = 2.5  # 지정 지표 가중치 강화 / Boost specified metrics

        weight_array = np.array(
            [weights[f] for f in NUMERIC_METRIC_FIELDS],
            dtype=np.float32
        )
        target_weighted = target_vec * weight_array

        # 후보 게임 조회 / Fetch candidates
        stmt = (
            select(Game)
            .options(selectinload(Game.metrics))
            .where(Game.is_active == True)
            .where(Game.is_analyzed == True)
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        # 점수 계산 / Compute scores
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

    # ==================== 응답 포맷팅 / Response Formatting ====================

    def format_semantic_results(
        self,
        results: List[Tuple[Game, GameMetric, float]],
    ) -> List[RecommendedGame]:
        """
        시맨틱 검색 결과 포맷 (Format Semantic Search Results)
        정규화된 similarity_score를 매치율로 사용.
        """
        formatted = []
        for game, metric, score in results:
            formatted.append(RecommendedGame(
                app_id=game.app_id,
                name=game.name or "",
                genres=game.genres or "",
                header_image=game.header_image or "",
                one_line_summary=game.one_line_summary or "",
                marketing_hook=game.marketing_hook or "",
                similarity_score=round(score, 4),
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=[],
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted

    def format_recommendations_by_preference(
        self,
        results: List[Tuple[Game, GameMetric, float]],
        preferences: Dict[str, float]
    ) -> List[RecommendedGame]:
        """
        선호도 기반 추천 결과 포맷 (Format Preference-based Results)
        match_reasons에 선호도와 일치하는 지표 설명 포함.
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
                gem_potential=metric.gem_percentile or metric.gem_potential,
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
        게임 기반 추천 결과 포맷 (Format Game-based Results)
        match_reasons에 기준 게임과의 공통 특징 포함.
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
                gem_potential=metric.gem_percentile or metric.gem_potential,
                match_reasons=self._generate_match_reasons_from_target(
                    target_vec, cand_vec
                ),
                key_metrics=self._get_key_metrics(metric),
            ))
        return formatted


# 싱글톤 인스턴스 / Singleton instance
recommender = GameRecommender()