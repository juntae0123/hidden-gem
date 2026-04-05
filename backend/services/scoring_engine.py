"""
Hidden Gem - Scoring Engine Service
====================================
게임 점수 계산 및 상태 분류
"""

from typing import Dict, List, Tuple, Any, Optional

from backend.config import (
    ALL_METRICS, GENRE_WEIGHTS,
    SCORE_S_TIER, SCORE_A_TIER, SCORE_B_TIER, SCORE_DEFAULT,
    SIMILARITY_WEIGHT, METRIC_WEIGHT,
    GENRE_MISMATCH_PENALTY, GENRE_MIN_MULTIPLIER,
    INTENT_BASE_WEIGHT, BOOST_CAP, MAX_TOTAL_WEIGHT,
    DROP_THRESHOLD, MANIAC_AVG_THRESHOLD, MANIAC_S_TIER_THRESHOLD,
    METRIC_KOREAN
)
from backend.services.intent_extractor import ExtractedIntent

# ============== 장르 DNA 점수 생성 ==============
def generate_scores_from_genres(genres: str) -> Dict[str, int]:
    """장르 텍스트를 분석하여 14개 감성 지표 점수 동적 생성"""
    scores: Dict[str, int] = {metric: SCORE_DEFAULT for metric in ALL_METRICS}
    
    if not genres:
        return scores
    
    genre_list = [g.strip() for g in genres.split(",")]
    
    for genre in genre_list:
        genre_lower = genre.lower()
        
        for genre_key, tier_config in GENRE_WEIGHTS.items():
            if genre_key.lower() in genre_lower or genre_lower in genre_key.lower():
                for metric in tier_config.get("S", []):
                    scores[metric] = max(scores[metric], SCORE_S_TIER)
                for metric in tier_config.get("A", []):
                    scores[metric] = max(scores[metric], SCORE_A_TIER)
                for metric in tier_config.get("B", []):
                    scores[metric] = max(scores[metric], SCORE_B_TIER)
    
    # 추가 키워드 보정
    genre_lower = genres.lower()
    if "indie" in genre_lower:
        scores["indie_spirit"] = max(scores["indie_spirit"], SCORE_S_TIER)
        scores["gem_potential"] = max(scores["gem_potential"], SCORE_A_TIER)
    if "story rich" in genre_lower:
        scores["story_depth"] = max(scores["story_depth"], SCORE_S_TIER)
    if "atmospheric" in genre_lower:
        scores["atmosphere_intensity"] = max(scores["atmosphere_intensity"], SCORE_S_TIER)
    
    return scores

# ============== 가중치 맵 생성 ==============
def get_genre_weight_map(genres: str) -> Dict[str, float]:
    weight_map = {m: 1.0 for m in ALL_METRICS}
    
    for genre in [g.strip() for g in genres.split(",")]:
        for genre_key, tier_config in GENRE_WEIGHTS.items():
            if genre_key.lower() in genre.lower():
                for metric in tier_config.get("S", []):
                    weight_map[metric] = max(weight_map[metric], 1.5)
                for metric in tier_config.get("A", []):
                    weight_map[metric] = max(weight_map[metric], 1.3)
                for metric in tier_config.get("B", []):
                    weight_map[metric] = max(weight_map[metric], 1.1)
    
    return weight_map

# ============== S티어 지표 추출 ==============
def get_s_tier_metrics(genres: str) -> List[str]:
    s_tier = set()
    for genre in [g.strip() for g in genres.split(",")]:
        for genre_key, tier_config in GENRE_WEIGHTS.items():
            if genre_key.lower() in genre.lower():
                s_tier.update(tier_config.get("S", []))
    return list(s_tier)

# ============== 장르 매칭 점수 ==============
def calculate_genre_match_score(
    game_genres: str,
    intent: ExtractedIntent
) -> Tuple[float, str, float]:
    if not intent.required_genres:
        return 1.0, "", 0.0
    
    game_genre_lower = game_genres.lower()
    
    match_count = sum(1 for g in intent.required_genres if g.lower() in game_genre_lower)
    match_ratio = match_count / len(intent.required_genres) if intent.required_genres else 1.0
    
    negative_count = sum(1 for g in intent.negative_genres if g.lower() in game_genre_lower)
    
    base_multiplier = GENRE_MIN_MULTIPLIER + (match_ratio * 0.5)
    if negative_count > 0:
        base_multiplier -= 0.05 * negative_count
    
    final_multiplier = max(GENRE_MIN_MULTIPLIER, min(1.2, base_multiplier))
    
    static_penalty = 0.0
    if match_ratio < 0.1 and len(intent.required_genres) > 3:
        static_penalty = GENRE_MISMATCH_PENALTY
    
    if match_ratio >= 0.3:
        reason = "🎯 장르 매칭!"
    elif negative_count > 0:
        reason = "⚡ 일부 장르 차이"
    else:
        reason = ""
    
    return final_multiplier, reason, static_penalty

# ============== 동적 부스팅 ==============
def apply_dynamic_boosting(
    scores: Dict[str, int],
    weight_map: Dict[str, float],
    user_intents: List[str]
) -> Tuple[Dict[str, float], Dict[str, Any], Optional[str]]:
    boost_details = {}
    boost_reason = None
    
    if not user_intents:
        return weight_map, boost_details, boost_reason
    
    boosted_map = weight_map.copy()
    max_boost_metric, max_boost_value = None, 0
    
    for metric in user_intents:
        if metric in boosted_map:
            original = weight_map.get(metric, 1.0)
            boosted_map[metric] = original * INTENT_BASE_WEIGHT
            boost_details[metric] = {
                "original": round(original, 2),
                "after_base": round(boosted_map[metric], 2)
            }
    
    group_a = [m for m in user_intents if m in scores]
    group_b = [m for m in ALL_METRICS if m not in user_intents and m in scores]
    
    if group_a and len(group_b) >= 2:
        group_a_avg = sum(scores[m] * boosted_map[m] for m in group_a) / len(group_a)
        group_b_sorted = sorted([scores[m] * boosted_map[m] for m in group_b], reverse=True)
        group_b_2nd = group_b_sorted[1] if len(group_b_sorted) > 1 else group_b_sorted[0]
        
        if group_a_avg < group_b_2nd and group_a_avg > 0:
            additional_boost = min(BOOST_CAP, max(1.0, group_b_2nd / group_a_avg))
            for metric in group_a:
                final_weight = min(MAX_TOTAL_WEIGHT, boosted_map[metric] * additional_boost)
                boosted_map[metric] = final_weight
                boost_details[metric]["additional_boost"] = round(additional_boost, 2)
                boost_details[metric]["final_weight"] = round(final_weight, 2)
                if final_weight > max_boost_value:
                    max_boost_value = final_weight
                    max_boost_metric = metric
    
    if max_boost_metric and max_boost_value > 1.5:
        metric_name = METRIC_KOREAN.get(max_boost_metric, max_boost_metric)
        boost_reason = f"🚀 [{metric_name}] 취향 집중 (x{max_boost_value:.2f})"
    
    return boosted_map, boost_details, boost_reason

# ============== 최종 점수 계산 ==============
def calculate_final_score(
    scores: Dict[str, int],
    genres: str,
    intent: ExtractedIntent,
    similarity: float,
    drop_threshold: int = DROP_THRESHOLD
) -> Tuple[float, str, Dict, Optional[str], float, str]:
    
    weight_map = get_genre_weight_map(genres)
    boosted_map, boost_details, boost_reason = apply_dynamic_boosting(
        scores, weight_map, intent.metrics
    )
    
    genre_multiplier, genre_reason, genre_penalty = calculate_genre_match_score(genres, intent)
    
    # 메트릭 점수 계산
    weighted_scores = []
    total_weight = 0
    for metric in ALL_METRICS:
        if metric in scores:
            w = boosted_map.get(metric, 1.0)
            weighted_scores.append(scores[metric] * w)
            total_weight += w
    
    metric_base_score = sum(weighted_scores) / total_weight if total_weight > 0 else 50
    metric_adjusted_score = metric_base_score * genre_multiplier
    
    # 유사도 점수 결합
    similarity_score = similarity * 100
    combined_score = (similarity_score * SIMILARITY_WEIGHT) + (metric_adjusted_score * METRIC_WEIGHT)
    
    # 시너지 보너스
    synergy_bonus = 0
    
    s_tier_metrics = get_s_tier_metrics(genres)
    if s_tier_metrics:
        s_tier_scores = [scores.get(m, 0) for m in s_tier_metrics]
        if s_tier_scores and all(s >= MANIAC_S_TIER_THRESHOLD for s in s_tier_scores):
            synergy_bonus += 5
    
    if intent.metrics:
        intent_scores = [scores.get(m, 0) for m in intent.metrics]
        if intent_scores and all(s >= 75 for s in intent_scores):
            synergy_bonus += len(intent.metrics) * 2
    
    if genre_multiplier >= 1.0:
        synergy_bonus += 3
    
    if similarity >= 0.8:
        synergy_bonus += 8
    elif similarity >= 0.6:
        synergy_bonus += 4
    
    final_score = combined_score + synergy_bonus + genre_penalty
    
    # 상태 분류
    if final_score < drop_threshold:
        if s_tier_metrics:
            s_tier_scores = [scores.get(m, 0) for m in s_tier_metrics]
            plain_avg = sum(scores.values()) / len(scores) if scores else 0
            if s_tier_scores and all(s >= MANIAC_S_TIER_THRESHOLD for s in s_tier_scores) and plain_avg < MANIAC_AVG_THRESHOLD:
                status = "MANIAC"
            else:
                status = "DROP"
        else:
            status = "DROP"
    else:
        status = "GEM"
    
    return final_score, status, boost_details, boost_reason, genre_multiplier, genre_reason
