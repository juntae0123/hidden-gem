/**
 * Score utilities for Hidden Gem recommendation system v5
 * Hidden Gem 추천 시스템 v5 점수 유틸리티
 *
 * 점수 체계:
 *   similarity_score: 0~99 (절대 점수)
 *   기준 게임 (by-game reference): 100 (앵커)
 *   gem_potential: 0~100 (백분위 기반)
 */

// ==================== 등급 상수 / Tier Constants ====================

/** Gem Tier — gem_potential 기준 등급 */
export const GEM_TIERS = {
  LEGENDARY: 90,  // (legacy, LLM gem_potential 스케일) 전설급 명작
  EPIC:      80,  // (legacy) 숨겨진 보석
  RARE:      70,  // (legacy) 주목할 만함
} as const;

/**
 * R-3 리뷰 실측 발굴 지수(gem_evidence, 0~100) 등급. 실측 최대가 ≈77 이라 70/80/90 은 도달 불가 (D-13).
 * 히든젬 ≥ 60 / 주목 45~60. 리뷰 30건 이상은 서버 랭킹 조건이고, 카드 뱃지는 값만 본다.
 */
export const GEM_EVIDENCE_TIERS = {
  HIDDEN_GEM: 60,
  NOTABLE:    45,
} as const;

export type GemEvidenceTier = 'hidden_gem' | 'notable' | 'none';

export function getGemEvidenceTier(score: number | null | undefined): GemEvidenceTier {
  if (score === null || score === undefined) return 'none';
  if (score >= GEM_EVIDENCE_TIERS.HIDDEN_GEM) return 'hidden_gem';
  if (score >= GEM_EVIDENCE_TIERS.NOTABLE)    return 'notable';
  return 'none';
}

/** Match Score Tier — similarity_score 기준 등급 */
export const MATCH_TIERS = {
  EXCELLENT: 85,  // 강한 매치
  GOOD:      70,  // 추천
  FAIR:      50,  // 무난
  WEAK:      30,  // 약함
} as const;

// ==================== 등급 판별 / Tier Detection ====================

export type GemTier = 'legendary' | 'epic' | 'rare' | 'common';

/**
 * Get gem tier from score.
 * gem_potential 점수로 등급 반환.
 */
export function getGemTier(score: number): GemTier {
  if (score >= GEM_TIERS.LEGENDARY) return 'legendary';
  if (score >= GEM_TIERS.EPIC)      return 'epic';
  if (score >= GEM_TIERS.RARE)      return 'rare';
  return 'common';
}

/**
 * Get bar gradient class by match score.
 * 매치 점수에 따른 바 그라데이션 클래스.
 */
export function getScoreGradient(score: number): string {
  if (score >= MATCH_TIERS.EXCELLENT) return 'from-purple-500 to-pink-500';
  if (score >= MATCH_TIERS.GOOD)      return 'from-purple-500 to-purple-600';
  if (score >= MATCH_TIERS.FAIR)      return 'from-blue-500 to-purple-500';
  if (score >= MATCH_TIERS.WEAK)      return 'from-zinc-400 to-blue-400';
  return 'from-zinc-300 to-zinc-400';
}

// ==================== 점수 변환 / Score Conversion ====================

/**
 * Check if score is anchor (reference game = 100).
 * 기준 게임 앵커 점수(100) 여부 확인.
 */
export function isAnchorScore(score: number): boolean {
  return score >= 100;
}

/**
 * Clamp score to 0~100 for width percent.
 * 바 너비 계산용 0~100 클램프.
 */
export function scoreToWidthPercent(score: number): number {
  return Math.max(0, Math.min(100, score));
}

// ==================== 라벨 / Labels ====================

/**
 * Human-readable match label.
 * 매치 점수 한글 라벨.
 */
export function getMatchLabel(score: number): string {
  if (isAnchorScore(score))           return '기준 게임';
  if (score >= MATCH_TIERS.EXCELLENT) return '강한 매치';
  if (score >= MATCH_TIERS.GOOD)      return '추천';
  if (score >= MATCH_TIERS.FAIR)      return '무난';
  return '참고';
}

/**
 * Human-readable gem tier label.
 * gem 등급 한글 라벨.
 */
export function getGemLabel(score: number): string {
  const tier = getGemTier(score);
  const map: Record<GemTier, string> = {
    legendary: '전설급 명작',
    epic:      '숨겨진 보석',
    rare:      '주목할 만함',
    common:    '',
  };
  return map[tier];
}

// ==================== score_breakdown 타입 / Score Breakdown ====================

export interface ScoreBreakdown {
  metric_score:    number;  // 지표 매치 점수 (0~100 스케일)
  embedding_score: number;  // 임베딩 유사도 점수 (0~100 스케일)
  gem_bonus:       number;  // Hidden Gem 보너스 (0~5)
  final_score:     number;  // 최종 점수 (0~99)
}

/**
 * Normalize partial breakdown to full shape.
 * 부분적 breakdown을 전체 형태로 정규화.
 */
export function normalizeBreakdown(
  breakdown: Partial<ScoreBreakdown> | null | undefined
): ScoreBreakdown {
  return {
    metric_score:    breakdown?.metric_score    ?? 0,
    embedding_score: breakdown?.embedding_score ?? 0,
    gem_bonus:       breakdown?.gem_bonus       ?? 0,
    final_score:     breakdown?.final_score     ?? 0,
  };
}