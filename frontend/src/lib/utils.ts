/**
 * Utility functions for Hidden Gem frontend.
 * Hidden Gem 프론트엔드 유틸리티 함수.
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// ==================== Class Utility ====================

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ==================== Percentage Helper ====================

/** Convert 0~1 to 0~100 percentage */
export function toPercent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

// ==================== Metric Labels ====================

export const METRIC_LABELS: Record<string, string> = {
  cozy_factor: '아늑함', horror_factor: '공포', gore_level: '고어',
  humor_rating: '유머', dark_fantasy_vibe: '다크판타지', epic_scale: '스케일',
  melancholy: '멜랑콜리', reflex_demand: '반응속도', strategic_depth: '전략깊이',
  grind_factor: '노가다', time_pressure: '시간압박', learning_curve: '학습곡선',
  freedom_level: '자유도', action_pacing: '액션템포', rng_dependency: 'RNG의존도',
  growth_reward: '성장보상', exploration_reward: '탐험보상',
  management_complexity: '관리복잡도', stealth_importance: '스텔스',
  session_length: '세션길이', narrative_linearity: '서사선형성',
  puzzle_complexity: '퍼즐복잡도', platforming_precision: '플랫폼정밀도',
  coop_synergy: '협동시너지', competitive_stress: '경쟁스트레스',
  npc_interaction: 'NPC상호작용', user_creation: '유저창작',
  multiplayer_scale: '멀티규모', lore_richness: '세계관밀도',
  choice_consequence: '선택결과', visual_spectacle: '시각연출',
  environmental_storytelling: '환경서사', soundtrack_impact: '사운드트랙',
  build_variety: '빌드다양성', progression_clarity: '진행명확성',
  save_flexibility: '저장유연성', difficulty_accessibility: '난이도접근성',
  tutorial_quality: '튜토리얼', ui_ux_polish: 'UI/UX완성도',
  modding_support: '모딩지원', art_style_uniqueness: '아트독창성',
  audio_design: '오디오디자인', animation_quality: '애니메이션',
  world_reactivity: '세계반응성', community_dependency: '커뮤니티의존',
  narrative_depth: '서사깊이', replay_value: '리플레이',
  endgame_content: '엔드게임', monetization_fairness: '과금공정성',
};

export const NUMERIC_METRIC_FIELDS = Object.keys(METRIC_LABELS);

// ==================== Distinctive Metrics ====================

export interface DistinctiveMetric {
  key: string;
  value: number;
  /** 평균(5)에서 떨어진 정도 */
  deviation: number;
  /** high(8+) / low(2-) / normal */
  category: 'high' | 'low' | 'normal';
}

/**
 * Get most distinctive metrics for a game (deviation from neutral 5).
 * 게임의 가장 특징적인 지표 N개 — 평균(5)에서 편차 큰 순.
 *
 * 기존 getTopMetrics(값 큰 순)의 문제:
 *   - 모든 게임이 비슷한 "높은 지표"를 가질 수 있음
 *   - 진짜 이 게임만의 특징을 못 잡음
 *
 * 개선: 편차 기반 → "이 게임은 다른 게임과 뭐가 다른가"
 */
export function getDistinctiveMetrics(
  metrics: Record<string, number | boolean | null | undefined>,
  n: number = 6
): DistinctiveMetric[] {
  const result: DistinctiveMetric[] = [];

  for (const key of NUMERIC_METRIC_FIELDS) {
    const value = metrics[key];
    if (typeof value !== 'number') continue;

    const deviation = Math.abs(value - 5);
    result.push({
      key,
      value,
      deviation,
      category: value >= 8 ? 'high' : value <= 2 ? 'low' : 'normal',
    });
  }

  return result.sort((a, b) => b.deviation - a.deviation).slice(0, n);
}

/**
 * Legacy — top metrics by value.
 * 레거시 — 값 기준 상위 지표 (하위 호환).
 * @deprecated Use getDistinctiveMetrics instead.
 */
export function getTopMetrics(
  metrics: Record<string, number | boolean | null>,
  n = 6
): { key: string; value: number; label: string }[] {
  return Object.entries(metrics)
    .filter(([k, v]) => typeof v === 'number' && v !== null && METRIC_LABELS[k])
    .map(([k, v]) => ({ key: k, value: v as number, label: METRIC_LABELS[k] }))
    .sort((a, b) => b.value - a.value)
    .slice(0, n);
}

// ==================== Misc Helpers ====================

export function getGemColor(gem: number | null): string {
  if (!gem) return 'text-gray-400';
  if (gem >= 90) return 'text-purple-500';
  if (gem >= 75) return 'text-blue-500';
  if (gem >= 60) return 'text-teal-500';
  return 'text-gray-400';
}

export function getHeaderImage(url: string | null): string {
  if (!url || url === '') return '/placeholder-game.png';
  return url;
}

export function parseGenres(genres: string): string[] {
  return genres.split(',').map(g => g.trim()).filter(Boolean);
}