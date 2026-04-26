# fastapi_app/services/retriever.py
"""
Hidden Gem - Two-Tower ANN 검색기

핵심 설계:
1. DB에는 pure_embedding (가중치 없는 정규화 벡터) 저장
2. 검색 시 유저 쿼리에 개인화 가중치 적용
3. HNSW 인덱스로 0.005초 내 1000개 추출

Two-Tower 구조:
- Tower 1 (Game): pure_embedding (33차원, 정규화)
- Tower 2 (User): weighted_query (33차원, 개인화 가중치 적용)
"""

import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.constants import ALL_NUMERIC_METRICS, CATEGORY_METRICS
from core.metrics_config import CATEGORY_BASE_WEIGHTS, get_metric_config
from schemas.search import MetricPreference, TagPreference, PreferenceType

@dataclass
class RetrieverConfig:
    """검색기 설정"""
    top_k: int = 1000
    timeout_seconds: float = 5.0
    pre_filter_margin: float = 2.0

@dataclass
class GameCandidate:
    """검색 후보"""
    app_id: int
    name: str
    genres: str
    description: str
    header_image: Optional[str]
    
    # 지표
    metrics: Dict[str, float]
    tags: Dict[str, bool]
    
    # AI 콘텐츠
    ai_curation_summary: Optional[str] = None
    marketing_hook: Optional[str] = None
    
    # 품질 데이터
    steam_positive_ratio: Optional[float] = None
    review_count: Optional[int] = None
    gem_potential: Optional[float] = None
    is_indie: bool = True
    
    # 검색 메타
    l2_distance: float = 0.0
    analysis_method: str = "gpt5.4_batch"

class TwoTowerRetriever:
    """
    Two-Tower ANN 검색기
    
    Pipeline:
    1. 유저 선호도 → 가중 쿼리 벡터 생성
    2. Pre-Filter (Tags, AVOID)
    3. HNSW ANN 검색 (L2 거리)
    4. Top K 반환
    """
    
    def __init__(self, config: Optional[RetrieverConfig] = None):
        self.config = config or RetrieverConfig()
        
        # 지표 순서 (벡터 인덱스 매핑)
        self.metric_order = ALL_NUMERIC_METRICS
        self.metric_to_idx = {m: i for i, m in enumerate(self.metric_order)}
    
    async def retrieve(
        self,
        db: AsyncSession,
        user_metrics: Dict[str, MetricPreference],
        user_tags: Optional[Dict[str, TagPreference]] = None,
        personal_bias: Optional[Dict[str, Any]] = None,
        exclude_app_ids: Optional[List[int]] = None,
    ) -> List[GameCandidate]:
        """
        Two-Tower ANN 검색
        """
        user_tags = user_tags or {}
        personal_bias = personal_bias or {}
        exclude_app_ids = exclude_app_ids or []
        
        # 1. 가중 쿼리 벡터 생성 (Tower 2)
        query_vector = self._build_weighted_query_vector(
            user_metrics=user_metrics,
            personal_bias=personal_bias,
        )
        
        # 2. Pre-Filter SQL 조건 생성
        pre_filter = self._build_pre_filter(
            user_metrics=user_metrics,
            user_tags=user_tags,
            exclude_app_ids=exclude_app_ids,
        )
        
        # 3. HNSW ANN 검색 실행
        candidates = await self._execute_ann_search(
            db=db,
            query_vector=query_vector,
            pre_filter=pre_filter,
        )
        
        return candidates
    
    async def get_game_by_app_id(
        self,
        db: AsyncSession,
        app_id: int,
    ) -> Optional[GameCandidate]:
        """App ID로 게임 조회"""
        query = """
        SELECT 
            g.app_id, g.name, g.genres, g.description, g.header_image,
            g.steam_positive_ratio, g.review_count, g.is_indie,
            g.analysis_method, g.ai_curation_summary, g.marketing_hook,
            m.cozy_factor, m.horror_factor, m.gore_level, m.humor_rating,
            m.dark_fantasy_vibe, m.epic_scale, m.melancholy,
            m.reflex_demand, m.strategic_depth, m.grind_factor,
            m.time_pressure, m.learning_curve,
            m.freedom_level, m.action_pacing, m.rng_dependency,
            m.growth_reward, m.exploration_reward, m.management_complexity,
            m.stealth_importance, m.session_length, m.narrative_linearity,
            m.puzzle_complexity, m.platforming_precision,
            m.coop_synergy, m.competitive_stress, m.npc_interaction,
            m.user_creation, m.multiplayer_scale,
            m.lore_richness, m.choice_consequence, m.visual_spectacle,
            m.environmental_storytelling, m.soundtrack_impact,
            m.is_turn_based, m.is_real_time, m.is_first_person, m.is_third_person,
            m.has_permadeath, m.has_base_building, m.has_crafting,
            m.is_anime_style, m.is_retro_aesthetic,
            m.gem_potential
        FROM games g
        JOIN game_metrics m ON g.id = m.game_id
        WHERE g.app_id = :app_id
        LIMIT 1
        """
        try:
            result = await db.execute(text(query), {"app_id": app_id})
            row = result.fetchone()
            if row:
                return self._row_to_candidate(row)
            return None
        except Exception as e:
            print(f"get_game_by_app_id error: {e}")
            return None
    
    async def search_game_by_name(
        self,
        db: AsyncSession,
        name: str,
    ) -> Optional[GameCandidate]:
        """이름으로 게임 검색 (Fuzzy)"""
        # 정확 매칭
        query_exact = """
        SELECT 
            g.app_id, g.name, g.genres, g.description, g.header_image,
            g.steam_positive_ratio, g.review_count, g.is_indie,
            g.analysis_method, g.ai_curation_summary, g.marketing_hook,
            m.cozy_factor, m.horror_factor, m.gore_level, m.humor_rating,
            m.dark_fantasy_vibe, m.epic_scale, m.melancholy,
            m.reflex_demand, m.strategic_depth, m.grind_factor,
            m.time_pressure, m.learning_curve,
            m.freedom_level, m.action_pacing, m.rng_dependency,
            m.growth_reward, m.exploration_reward, m.management_complexity,
            m.stealth_importance, m.session_length, m.narrative_linearity,
            m.puzzle_complexity, m.platforming_precision,
            m.coop_synergy, m.competitive_stress, m.npc_interaction,
            m.user_creation, m.multiplayer_scale,
            m.lore_richness, m.choice_consequence, m.visual_spectacle,
            m.environmental_storytelling, m.soundtrack_impact,
            m.is_turn_based, m.is_real_time, m.is_first_person, m.is_third_person,
            m.has_permadeath, m.has_base_building, m.has_crafting,
            m.is_anime_style, m.is_retro_aesthetic,
            m.gem_potential
        FROM games g
        JOIN game_metrics m ON g.id = m.game_id
        WHERE LOWER(g.name) = LOWER(:name)
        LIMIT 1
        """
        try:
            result = await db.execute(text(query_exact), {"name": name})
            row = result.fetchone()
            if row:
                return self._row_to_candidate(row)
            
            # 부분 매칭
            query_like = """
            SELECT 
                g.app_id, g.name, g.genres, g.description, g.header_image,
                g.steam_positive_ratio, g.review_count, g.is_indie,
                g.analysis_method, g.ai_curation_summary, g.marketing_hook,
                m.cozy_factor, m.horror_factor, m.gore_level, m.humor_rating,
                m.dark_fantasy_vibe, m.epic_scale, m.melancholy,
                m.reflex_demand, m.strategic_depth, m.grind_factor,
                m.time_pressure, m.learning_curve,
                m.freedom_level, m.action_pacing, m.rng_dependency,
                m.growth_reward, m.exploration_reward, m.management_complexity,
                m.stealth_importance, m.session_length, m.narrative_linearity,
                m.puzzle_complexity, m.platforming_precision,
                m.coop_synergy, m.competitive_stress, m.npc_interaction,
                m.user_creation, m.multiplayer_scale,
                m.lore_richness, m.choice_consequence, m.visual_spectacle,
                m.environmental_storytelling, m.soundtrack_impact,
                m.is_turn_based, m.is_real_time, m.is_first_person, m.is_third_person,
                m.has_permadeath, m.has_base_building, m.has_crafting,
                m.is_anime_style, m.is_retro_aesthetic,
                m.gem_potential
            FROM games g
            JOIN game_metrics m ON g.id = m.game_id
            WHERE LOWER(g.name) LIKE LOWER(:pattern)
            ORDER BY LENGTH(g.name) ASC
            LIMIT 1
            """
            result = await db.execute(text(query_like), {"pattern": f"%{name}%"})
            row = result.fetchone()
            if row:
                return self._row_to_candidate(row)
            return None
        except Exception as e:
            print(f"search_game_by_name error: {e}")
            return None
    
    def game_to_user_preferences(self, game: GameCandidate) -> Dict[str, MetricPreference]:
        """게임 지표 → 유저 선호도로 변환 (유사 게임 검색용)"""
        preferences = {}
        for metric_name, value in game.metrics.items():
            if value is not None:
                preferences[metric_name] = MetricPreference(
                    value=value,
                    type=PreferenceType.MUST_EXACT,
                    confidence=0.9,
                )
        return preferences
    
    def _build_weighted_query_vector(self, user_metrics: Dict[str, MetricPreference], personal_bias: Dict[str, Any]) -> np.ndarray:
        """가중치가 적용된 쿼리 벡터 생성"""
        vector = np.full(len(self.metric_order), 5.0, dtype=np.float32)
        weights = np.ones(len(self.metric_order), dtype=np.float32)
        category_boosts = personal_bias.get("category_boosts", {})
        
        for metric_name, pref in user_metrics.items():
            if pref.type == PreferenceType.NEUTRAL or pref.value is None:
                continue
            idx = self.metric_to_idx.get(metric_name)
            if idx is None:
                continue
            
            vector[idx] = pref.value
            config = get_metric_config(metric_name)
            category = self._find_category(metric_name)
            category_weight = CATEGORY_BASE_WEIGHTS.get(category, 0.2)
            personal_boost = category_boosts.get(category, 1.0)
            
            final_weight = np.sqrt(category_weight * config.weight * personal_boost)
            weights[idx] = final_weight
        
        weighted_vector = vector * weights
        norm = np.linalg.norm(weighted_vector)
        if norm > 0:
            weighted_vector = weighted_vector / norm
        return weighted_vector
    
    def _build_pre_filter(self, user_metrics: Dict[str, MetricPreference], user_tags: Dict[str, TagPreference], exclude_app_ids: List[int]) -> Dict[str, Any]:
        """Pre-Filter SQL 조건"""
        conditions = ["g.is_analyzed = true"]
        params = {}
        
        if exclude_app_ids:
            placeholders = ", ".join([f":exclude_{i}" for i in range(len(exclude_app_ids))])
            conditions.append(f"g.app_id NOT IN ({placeholders})")
            for i, app_id in enumerate(exclude_app_ids):
                params[f"exclude_{i}"] = app_id
        
        for tag_name, tag_pref in user_tags.items():
            if tag_pref.type == "MUST" and tag_pref.value is not None:
                conditions.append(f"m.{tag_name} = :tag_{tag_name}")
                params[f"tag_{tag_name}"] = tag_pref.value
            elif tag_pref.type == "EXCLUDE" and tag_pref.value is not None:
                conditions.append(f"m.{tag_name} != :tag_{tag_name}")
                params[f"tag_{tag_name}"] = tag_pref.value
        
        for metric_name, pref in user_metrics.items():
            if pref.type == PreferenceType.MUST_LOW and pref.value is not None:
                config = get_metric_config(metric_name)
                margin = self.config.pre_filter_margin
                if config.is_sensitive:
                    margin = margin * 0.5
                threshold = min(10, pref.value + margin)
                conditions.append(f"m.{metric_name} <= :avoid_{metric_name}")
                params[f"avoid_{metric_name}"] = threshold
        
        return {"where": " AND ".join(conditions), "params": params}
    
    async def _execute_ann_search(self, db: AsyncSession, query_vector: np.ndarray, pre_filter: Dict[str, Any]) -> List[GameCandidate]:
        """HNSW ANN 검색 실행"""
        vector_str = "[" + ",".join(map(str, query_vector.tolist())) + "]"
        
        query = f"""
        SELECT 
            g.app_id, g.name, g.genres, g.description, g.header_image,
            g.steam_positive_ratio, g.review_count, g.is_indie,
            g.analysis_method, g.ai_curation_summary, g.marketing_hook,
            m.cozy_factor, m.horror_factor, m.gore_level, m.humor_rating,
            m.dark_fantasy_vibe, m.epic_scale, m.melancholy,
            m.reflex_demand, m.strategic_depth, m.grind_factor,
            m.time_pressure, m.learning_curve,
            m.freedom_level, m.action_pacing, m.rng_dependency,
            m.growth_reward, m.exploration_reward, m.management_complexity,
            m.stealth_importance, m.session_length, m.narrative_linearity,
            m.puzzle_complexity, m.platforming_precision,
            m.coop_synergy, m.competitive_stress, m.npc_interaction,
            m.user_creation, m.multiplayer_scale,
            m.lore_richness, m.choice_consequence, m.visual_spectacle,
            m.environmental_storytelling, m.soundtrack_impact,
            m.is_turn_based, m.is_real_time, m.is_first_person, m.is_third_person,
            m.has_permadeath, m.has_base_building, m.has_crafting,
            m.is_anime_style, m.is_retro_aesthetic,
            m.gem_potential,
            m.pure_embedding <-> :query_vector::vector AS l2_distance
        FROM games g
        JOIN game_metrics m ON g.id = m.game_id
        WHERE {pre_filter['where']}
        ORDER BY l2_distance ASC
        LIMIT :top_k
        """
        
        params = {**pre_filter["params"], "query_vector": vector_str, "top_k": self.config.top_k}
        
        try:
            result = await asyncio.wait_for(db.execute(text(query), params), timeout=self.config.timeout_seconds)
            rows = result.fetchall()
        except asyncio.TimeoutError:
            print("ANN search timeout")
            return []
        except Exception as e:
            print(f"ANN search error: {e}")
            return []
        
        candidates = []
        for row in rows:
            candidates.append(self._row_to_candidate(row))
        return candidates
    
    def _row_to_candidate(self, row) -> GameCandidate:
        """DB Row → GameCandidate"""
        if hasattr(row, '_mapping'):
            row_dict = dict(row._mapping)
        else:
            row_dict = row._asdict() if hasattr(row, '_asdict') else {}
        
        metrics = {}
        for metric_name in ALL_NUMERIC_METRICS:
            value = row_dict.get(metric_name) if row_dict else getattr(row, metric_name, None)
            if value is not None:
                metrics[metric_name] = float(value)
        
        tags = {}
        tag_names = [
            "is_turn_based", "is_real_time", "is_first_person", "is_third_person",
            "has_permadeath", "has_base_building", "has_crafting",
            "is_anime_style", "is_retro_aesthetic"
        ]
        for tag_name in tag_names:
            value = row_dict.get(tag_name) if row_dict else getattr(row, tag_name, None)
            if value is not None:
                tags[tag_name] = bool(value)
        
        def get_val(key, default=None):
            if row_dict:
                return row_dict.get(key, default)
            return getattr(row, key, default)
        
        return GameCandidate(
            app_id=get_val("app_id"),
            name=get_val("name", ""),
            genres=get_val("genres", ""),
            description=get_val("description", ""),
            header_image=get_val("header_image"),
            metrics=metrics,
            tags=tags,
            ai_curation_summary=get_val("ai_curation_summary"),
            marketing_hook=get_val("marketing_hook"),
            steam_positive_ratio=get_val("steam_positive_ratio"),
            review_count=get_val("review_count"),
            gem_potential=get_val("gem_potential"),
            is_indie=get_val("is_indie", True),
            l2_distance=get_val("l2_distance", 0.0),
            analysis_method=get_val("analysis_method", "gpt5.4_batch"),
        )
    
    def _find_category(self, metric_name: str) -> Optional[str]:
        """지표 카테고리 찾기"""
        for category, metrics in CATEGORY_METRICS.items():
            if metric_name in metrics:
                return category
        return None

# 싱글톤
retriever = TwoTowerRetriever()