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
from models.user import User


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
        
        Args:
            db: DB 세션
            user_metrics: 유저 지표 선호도
            user_tags: 유저 태그 선호도
            personal_bias: 개인화 바이어스 (취향 DNA)
            exclude_app_ids: 제외할 게임 ID
            
        Returns:
            Top K 후보 게임
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
    
    def _build_weighted_query_vector(
        self,
        user_metrics: Dict[str, MetricPreference],
        personal_bias: Dict[str, Any],
    ) -> np.ndarray:
        """
        개인화 가중치가 적용된 쿼리 벡터 생성
        
        수식:
        weighted_query[i] = user_value[i] × sqrt(category_weight × metric_weight × personal_boost)
        
        sqrt를 쓰는 이유: L2 거리에서 가중치 효과가 제곱되므로
        """
        
        # 기본 벡터 (중립값 5.0)
        vector = np.full(len(self.metric_order), 5.0, dtype=np.float32)
        weights = np.ones(len(self.metric_order), dtype=np.float32)
        
        # 개인화 부스트
        category_boosts = personal_bias.get("category_boosts", {})
        
        for metric_name, pref in user_metrics.items():
            if pref.type == PreferenceType.NEUTRAL or pref.value is None:
                continue
            
            idx = self.metric_to_idx.get(metric_name)
            if idx is None:
                continue
            
            # 유저 값 설정
            vector[idx] = pref.value
            
            # 가중치 계산
            config = get_metric_config(metric_name)
            category = self._find_category(metric_name)
            
            category_weight = CATEGORY_BASE_WEIGHTS.get(category, 0.2)
            personal_boost = category_boosts.get(category, 1.0)
            
            # 최종 가중치
            final_weight = np.sqrt(category_weight * config.weight * personal_boost)
            weights[idx] = final_weight
        
        # 가중 벡터 생성
        weighted_vector = vector * weights
        
        # L2 정규화
        norm = np.linalg.norm(weighted_vector)
        if norm > 0:
            weighted_vector = weighted_vector / norm
        
        return weighted_vector
    
    def _build_pre_filter(
        self,
        user_metrics: Dict[str, MetricPreference],
        user_tags: Dict[str, TagPreference],
        exclude_app_ids: List[int],
    ) -> Dict[str, Any]:
        """Pre-Filter SQL 조건"""
        
        conditions = ["g.is_analyzed = true"]
        params = {}
        
        # 제외 게임
        if exclude_app_ids:
            conditions.append("g.app_id NOT IN :exclude_ids")
            params["exclude_ids"] = tuple(exclude_app_ids)
        
        # Tags Hard Filter
        for tag_name, tag_pref in user_tags.items():
            if tag_pref.type == "MUST" and tag_pref.value is not None:
                conditions.append(f"m.{tag_name} = :tag_{tag_name}")
                params[f"tag_{tag_name}"] = tag_pref.value
            elif tag_pref.type == "EXCLUDE" and tag_pref.value is not None:
                conditions.append(f"m.{tag_name} != :tag_{tag_name}")
                params[f"tag_{tag_name}"] = tag_pref.value
        
        # AVOID Pre-Filter
        for metric_name, pref in user_metrics.items():
            if pref.type == PreferenceType.MUST_LOW and pref.value is not None:
                config = get_metric_config(metric_name)
                margin = self.config.pre_filter_margin
                
                if config.is_sensitive:
                    margin = margin * 0.5  # 민감 지표는 마진 줄임
                
                threshold = min(10, pref.value + margin)
                conditions.append(f"m.{metric_name} <= :avoid_{metric_name}")
                params[f"avoid_{metric_name}"] = threshold
        
        return {
            "where": " AND ".join(conditions),
            "params": params,
        }
    
    async def _execute_ann_search(
        self,
        db: AsyncSession,
        query_vector: np.ndarray,
        pre_filter: Dict[str, Any],
    ) -> List[GameCandidate]:
        """HNSW ANN 검색 실행"""
        
        # 벡터를 PostgreSQL 형식으로
        vector_str = "[" + ",".join(map(str, query_vector.tolist())) + "]"
        
        query = f"""
        SELECT 
            g.app_id,
            g.name,
            g.genres,
            g.description,
            g.header_image,
            g.steam_positive_ratio,
            g.review_count,
            g.is_indie,
            g.analysis_method,
            g.ai_curation_summary,
            g.marketing_hook,
            m.*,
            m.pure_embedding <-> :query_vector::vector AS l2_distance
        FROM games g
        JOIN game_metrics m ON g.id = m.game_id
        WHERE {pre_filter['where']}
        ORDER BY l2_distance ASC
        LIMIT :top_k
        """
        
        params = {
            **pre_filter["params"],
            "query_vector": vector_str,
            "top_k": self.config.top_k,
        }
        
        try:
            result = await asyncio.wait_for(
                db.execute(text(query), params),
                timeout=self.config.timeout_seconds,
            )
            rows = result.fetchall()
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            print(f"ANN search error: {e}")
            return []
        
        # 결과 변환
        candidates = []
        for row in rows:
            candidate = self._row_to_candidate(row)
            candidates.append(candidate)
        
        return candidates
    
    def _row_to_candidate(self, row) -> GameCandidate:
        """DB Row → GameCandidate"""
        
        metrics = {}
        for metric_name in ALL_NUMERIC_METRICS:
            value = getattr(row, metric_name, None)
            if value is not None:
                metrics[metric_name] = float(value)
        
        tags = {}
        for tag_name in ["is_turn_based", "is_real_time", "is_first_person", "is_third_person",
                         "has_permadeath", "has_base_building", "has_crafting",
                         "is_anime_style", "is_retro_aesthetic"]:
            value = getattr(row, tag_name, None)
            if value is not None:
                tags[tag_name] = bool(value)
        
        return GameCandidate(
            app_id=row.app_id,
            name=row.name,
            genres=row.genres or "",
            description=row.description or "",
            header_image=getattr(row, "header_image", None),
            metrics=metrics,
            tags=tags,
            ai_curation_summary=getattr(row, "ai_curation_summary", None),
            marketing_hook=getattr(row, "marketing_hook", None),
            steam_positive_ratio=getattr(row, "steam_positive_ratio", None),
            review_count=getattr(row, "review_count", None),
            gem_potential=getattr(row, "gem_potential", None),
            is_indie=getattr(row, "is_indie", True),
            l2_distance=getattr(row, "l2_distance", 0.0),
            analysis_method=getattr(row, "analysis_method", "gpt5.4_batch"),
        )
    
    def _find_category(self, metric_name: str) -> Optional[str]:
        """지표 카테고리 찾기"""
        for category, metrics in CATEGORY_METRICS.items():
            if metric_name in metrics:
                return category
        return None


# 싱글톤
retriever = TwoTowerRetriever()
