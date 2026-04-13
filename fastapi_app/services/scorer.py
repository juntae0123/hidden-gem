# fastapi_app/services/scorer.py
"""
Hidden Gem - 최종 점수 계산기

핵심:
1. Bayesian Smoothing: 리뷰 0개인 신작도 공정하게 평가
2. Personal Bias: 취향 DNA 반영
3. Discovery Bonus: 숨겨진 명작 보상
4. AI Curation Summary: 한 줄 평 가공
"""

import math
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from services.reranker import RerankedResult
from core.metrics_config import get_metric_config


@dataclass
class ScorerConfig:
    """점수 계산 설정"""
    
    # 최대 점수
    max_final_score: float = 120.0
    
    # Quality Bonus
    max_quality_bonus: float = 0.20
    quality_steam_weight: float = 0.5
    quality_gem_weight: float = 0.5
    
    # Bayesian Smoothing
    bayesian_prior_mean: float = 0.75  # 사전 평균 (75% 긍정)
    bayesian_prior_strength: float = 10  # 사전 강도 (가상 리뷰 10개)
    
    # 인기도 보정
    popularity_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "viral": 500000,
        "popular": 100000,
        "known": 50000,
        "indie": 10000,
    })
    
    # Discovery Bonus
    discovery_bonus_max: float = 0.08
    discovery_min_score: float = 85.0


@dataclass
class QualityBonus:
    """품질 보너스 상세"""
    steam_positive_ratio: Optional[float] = None
    bayesian_score: float = 0.0  # Bayesian Smoothing 적용 후
    gem_potential: Optional[float] = None
    review_count: Optional[int] = None
    popularity_modifier: float = 1.0
    discovery_bonus: float = 0.0
    final_multiplier: float = 1.0


@dataclass
class PersonalBiasAdjustment:
    """개인화 조정"""
    taste_similarity: float = 0.0  # 취향 DNA 유사도
    history_boost: float = 0.0     # 플레이 이력 기반
    total_adjustment: float = 0.0


@dataclass
class FinalScore:
    """최종 점수"""
    base_match_score: float
    quality_bonus: QualityBonus
    personal_bias: PersonalBiasAdjustment
    final_match_score: float
    
    # AI 큐레이션
    ai_summary: Optional[str] = None
    match_summary: str = ""


@dataclass
class ScoredCandidate:
    """최종 점수 후보"""
    reranked: RerankedResult
    final_score: FinalScore
    match_reasons: List[str] = field(default_factory=list)
    caution_reasons: List[str] = field(default_factory=list)


class BayesianScorer:
    """
    Bayesian Smoothing 적용 점수 계산기
    
    핵심 수식:
    bayesian_score = (prior_mean × prior_strength + actual_ratio × review_count) 
                     / (prior_strength + review_count)
    
    이렇게 하면:
    - 리뷰 0개: prior_mean (75%) 반환
    - 리뷰 10개: 실제와 사전의 중간
    - 리뷰 1000개+: 거의 실제 값
    """
    
    def __init__(self, config: Optional[ScorerConfig] = None):
        self.config = config or ScorerConfig()
    
    def score_all(
        self,
        reranked: List[RerankedResult],
        user_taste_dna: Optional[np.ndarray] = None,
    ) -> List[ScoredCandidate]:
        """
        모든 후보에 최종 점수 계산
        """
        
        scored = []
        
        for item in reranked:
            final_score = self._calculate_final_score(
                item=item,
                user_taste_dna=user_taste_dna,
            )
            
            match_reasons, caution_reasons = self._generate_reasons(item, final_score)
            
            scored.append(ScoredCandidate(
                reranked=item,
                final_score=final_score,
                match_reasons=match_reasons,
                caution_reasons=caution_reasons,
            ))
        
        # 점수순 정렬
        scored.sort(key=lambda x: x.final_score.final_match_score, reverse=True)
        
        return scored
    
    def _calculate_final_score(
        self,
        item: RerankedResult,
        user_taste_dna: Optional[np.ndarray],
    ) -> FinalScore:
        """단일 후보 최종 점수 계산"""
        
        candidate = item.candidate
        base_score = item.base_match_score
        
        # ========== 1. Bayesian Smoothing ==========
        bayesian_score = self._bayesian_smooth(
            actual_ratio=candidate.steam_positive_ratio,
            review_count=candidate.review_count or 0,
        )
        
        # ========== 2. Quality Bonus 계산 ==========
        quality_bonus = self._calculate_quality_bonus(
            bayesian_score=bayesian_score,
            gem_potential=candidate.gem_potential,
            review_count=candidate.review_count,
            is_indie=candidate.is_indie,
            base_score=base_score,
        )
        
        # ========== 3. Personal Bias 계산 ==========
        personal_bias = self._calculate_personal_bias(
            candidate_metrics=candidate.metrics,
            user_taste_dna=user_taste_dna,
        )
        
        # ========== 4. 최종 점수 ==========
        score_after_quality = base_score * quality_bonus.final_multiplier
        final_score = score_after_quality + personal_bias.total_adjustment
        final_score = min(self.config.max_final_score, max(0, final_score))
        
        # ========== 5. AI Summary 가공 ==========
        ai_summary = self._generate_ai_summary(candidate)
        
        # ========== 6. Match Summary ==========
        match_summary = self._generate_match_summary(base_score, final_score)
        
        return FinalScore(
            base_match_score=round(base_score, 2),
            quality_bonus=quality_bonus,
            personal_bias=personal_bias,
            final_match_score=round(final_score, 2),
            ai_summary=ai_summary,
            match_summary=match_summary,
        )
    
    def _bayesian_smooth(
        self,
        actual_ratio: Optional[float],
        review_count: int,
    ) -> float:
        """
        Bayesian Smoothing
        
        리뷰 적은 게임도 공정하게 평가
        """
        
        if actual_ratio is None:
            actual_ratio = self.config.bayesian_prior_mean
        
        prior_mean = self.config.bayesian_prior_mean
        prior_strength = self.config.bayesian_prior_strength
        
        # Bayesian 평균
        # (prior_mean × prior_strength + actual_ratio × review_count) / (prior_strength + review_count)
        bayesian = (
            (prior_mean * prior_strength + actual_ratio * review_count) /
            (prior_strength + review_count)
        )
        
        return bayesian
    
    def _calculate_quality_bonus(
        self,
        bayesian_score: float,
        gem_potential: Optional[float],
        review_count: Optional[int],
        is_indie: bool,
        base_score: float,
    ) -> QualityBonus:
        """Quality Bonus 계산"""
        
        gem = gem_potential or 5.0
        reviews = review_count or 0
        
        # 정규화
        normalized_bayesian = max(0, min(1, (bayesian_score - 0.6) / 0.35))
        normalized_gem = gem / 10.0
        
        # 가중 평균
        raw_quality = (
            normalized_bayesian * self.config.quality_steam_weight +
            normalized_gem * self.config.quality_gem_weight
        )
        
        # 인기도 보정
        popularity_modifier = self._get_popularity_modifier(reviews)
        
        # Discovery Bonus
        discovery_bonus = self._calculate_discovery_bonus(
            review_count=reviews,
            base_score=base_score,
            is_indie=is_indie,
        )
        
        # 최종 보너스
        base_bonus = math.log(1 + raw_quality) * self.config.max_quality_bonus
        adjusted_bonus = base_bonus * popularity_modifier + discovery_bonus
        final_bonus = min(self.config.max_quality_bonus + self.config.discovery_bonus_max, adjusted_bonus)
        
        return QualityBonus(
            steam_positive_ratio=None,  # 원본은 별도 저장
            bayesian_score=round(bayesian_score, 4),
            gem_potential=gem,
            review_count=reviews,
            popularity_modifier=round(popularity_modifier, 4),
            discovery_bonus=round(discovery_bonus, 4),
            final_multiplier=round(1.0 + final_bonus, 4),
        )
    
    def _get_popularity_modifier(self, review_count: int) -> float:
        """인기도 보정"""
        thresholds = self.config.popularity_thresholds
        
        if review_count >= thresholds["viral"]:
            return 0.5
        elif review_count >= thresholds["popular"]:
            return 0.7
        elif review_count >= thresholds["known"]:
            return 0.85
        elif review_count >= thresholds["indie"]:
            return 1.0
        else:
            return 1.0
    
    def _calculate_discovery_bonus(
        self,
        review_count: int,
        base_score: float,
        is_indie: bool,
    ) -> float:
        """발견의 기쁨 보너스"""
        
        if review_count >= self.config.popularity_thresholds["indie"]:
            return 0.0
        
        if base_score < self.config.discovery_min_score:
            return 0.0
        
        # 매칭 점수에 비례
        match_factor = (base_score - self.config.discovery_min_score) / 15
        match_factor = min(1.0, match_factor)
        
        # 인디 부스트
        indie_boost = 1.2 if is_indie else 1.0
        
        # 리뷰 적을수록 보너스
        if review_count < 1000:
            rarity_boost = 1.5
        elif review_count < 5000:
            rarity_boost = 1.2
        else:
            rarity_boost = 1.0
        
        bonus = self.config.discovery_bonus_max * match_factor * indie_boost * rarity_boost
        
        return min(self.config.discovery_bonus_max * 1.5, bonus)
    
    def _calculate_personal_bias(
        self,
        candidate_metrics: Dict[str, float],
        user_taste_dna: Optional[np.ndarray],
    ) -> PersonalBiasAdjustment:
        """Personal Bias 계산"""
        
        if user_taste_dna is None:
            return PersonalBiasAdjustment()
        
        # 게임 벡터
        from core.constants import ALL_NUMERIC_METRICS
        game_vector = np.array([
            candidate_metrics.get(m, 5.0) for m in ALL_NUMERIC_METRICS
        ], dtype=np.float32)
        
        # 정규화
        game_norm = np.linalg.norm(game_vector)
        dna_norm = np.linalg.norm(user_taste_dna)
        
        if game_norm > 0 and dna_norm > 0:
            # 코사인 유사도
            similarity = np.dot(game_vector, user_taste_dna) / (game_norm * dna_norm)
            similarity = float(similarity)
        else:
            similarity = 0.0
        
        # 유사도 → 점수 조정 (최대 ±5점)
        adjustment = (similarity - 0.5) * 10  # 0.5 기준, 위아래로 ±5
        
        return PersonalBiasAdjustment(
            taste_similarity=round(similarity, 4),
            history_boost=0.0,  # TODO: 플레이 이력 기반
            total_adjustment=round(adjustment, 2),
        )
    
    def _generate_ai_summary(self, candidate) -> Optional[str]:
        """AI 큐레이션 요약 생성"""
        
        # 우선순위: ai_curation_summary > marketing_hook > one_line_summary
        if candidate.ai_curation_summary:
            return candidate.ai_curation_summary
        
        if candidate.marketing_hook:
            return candidate.marketing_hook
        
        # 없으면 자동 생성
        if candidate.gem_potential and candidate.gem_potential >= 7:
            return f"✨ 숨겨진 명작! {candidate.genres} 장르의 걸작"
        
        return None
    
    def _generate_match_summary(self, base_score: float, final_score: float) -> str:
        """매칭 요약"""
        
        if final_score >= 110:
            return "💎 숨겨진 명작! 당신을 위한 게임!"
        elif final_score >= 100:
            return "🌟 완벽에 가까운 매칭!"
        elif final_score >= 90:
            return "✨ 매우 잘 맞아요!"
        elif final_score >= 80:
            return "👍 꽤 잘 맞아요!"
        elif final_score >= 70:
            return "🤔 괜찮아 보여요"
        else:
            return "🤷 취향에는 안 맞을 수도"
    
    def _generate_reasons(
        self,
        item: RerankedResult,
        final_score: FinalScore,
    ) -> Tuple[List[str], List[str]]:
        """매칭 이유 생성"""
        
        match_reasons = []
        caution_reasons = []
        
        # 잘 맞은 지표
        if item.matched_metrics:
            descriptions = [get_metric_config(m).description for m in item.matched_metrics[:3]]
            match_reasons.append(f"✅ {', '.join(descriptions)}이(가) 딱 맞아요!")
        
        # 카테고리 우수
        if item.category_scores:
            best_cat = max(item.category_scores.items(), key=lambda x: x[1])
            if best_cat[1] >= 8:
                match_reasons.append(f"🎯 {best_cat[0].upper()} 영역 매칭 우수!")
        
        # 발견의 기쁨
        if final_score.quality_bonus.discovery_bonus > 0.02:
            match_reasons.append("💎 숨겨진 명작! 놓치지 마세요!")
        
        # AI 평가 높음
        if final_score.quality_bonus.gem_potential and final_score.quality_bonus.gem_potential >= 8:
            match_reasons.append("⭐ AI가 극찬한 게임!")
        
        # 주의사항
        if item.mismatched_metrics:
            desc = get_metric_config(item.mismatched_metrics[0]).description
            caution_reasons.append(f"⚠️ {desc}은(는) 기대와 다를 수 있어요")
        
        return match_reasons[:3], caution_reasons[:2]


# 싱글톤
scorer = BayesianScorer()
