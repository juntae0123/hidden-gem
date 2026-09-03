/**
 * Utility functions for Hidden Gem frontend.
 * Hidden Gem 프론트엔드 유틸리티 함수.
 *
 * v3 → v4: 장르별 핵심지표 (getGenreCoreMetrics) 추가
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
  multiplayer_scale: '멀티규모', lore_richness: '세계관',
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

// ==================== Genre Core Metrics ====================
// juntae 철학: "장르마다 핵심지표가 다름, 9점 자랑 X 정체성 O"

export const GENRE_CORE_METRICS: Record<string, string[]> = {
  RPG: [
    'narrative_depth',      // 서사깊이
    'growth_reward',        // 성장보상
    'choice_consequence',   // 선택결과
    'lore_richness',        // 세계관
    'exploration_reward',   // 탐험보상
    'freedom_level',        // 자유도
  ],
  액션: [
    'action_pacing',        // 액션템포
    'reflex_demand',        // 반응속도
    'visual_spectacle',     // 시각연출
    'animation_quality',    // 애니메이션
    'replay_value',         // 리플레이
    'difficulty_accessibility', // 난이도접근성
  ],
  전략: [
    'strategic_depth',      // 전략깊이
    'management_complexity',// 관리복잡도
    'replay_value',         // 리플레이
    'learning_curve',       // 학습곡선
    'rng_dependency',       // RNG의존도
    'build_variety',        // 빌드다양성
  ],
  시뮬레이션: [
    'management_complexity',
    'freedom_level',
    'replay_value',
    'progression_clarity',
    'user_creation',
    'session_length',
  ],
  어드벤처: [
    'exploration_reward',
    'narrative_depth',
    'environmental_storytelling',
    'world_reactivity',
    'puzzle_complexity',
    'lore_richness',
  ],
  인디: [
    'art_style_uniqueness',
    'narrative_depth',
    'audio_design',
    'soundtrack_impact',
    'melancholy',
    'replay_value',
  ],
  로그라이크: [
    'replay_value',
    'rng_dependency',
    'learning_curve',
    'build_variety',
    'grind_factor',
    'reflex_demand',
  ],
  공포: [
    'horror_factor',
    'melancholy',
    'dark_fantasy_vibe',
    'environmental_storytelling',
    'soundtrack_impact',
    'narrative_depth',
  ],
  퍼즐: [
    'puzzle_complexity',
    'strategic_depth',
    'learning_curve',
    'progression_clarity',
    'art_style_uniqueness',
    'difficulty_accessibility',
  ],
};

export const DEFAULT_CORE_METRICS = [
  'narrative_depth',
  'replay_value',
  'art_style_uniqueness',
  'audio_design',
  'exploration_reward',
  'visual_spectacle',
];

// ==================== Distinctive Metric Type ====================

export interface DistinctiveMetric {
  key: string;
  value: number;
  deviation: number;
  category: 'high' | 'low' | 'normal';
}

/**
 * Get genre-core metrics for a game.
 * 게임의 장르 핵심 6대 지표 (정체성 표시).
 *
 * juntae 철학:
 *   - "9점 자랑" X (과금공정성 같은 무관 지표 제외)
 *   - "이 게임이 어떤 RPG/액션인가" 정체성
 *   - 낮은 점수도 정체성 (성장5 = 서사중심 RPG)
 *
 * @param metrics - 게임 지표
 * @param genres - 장르 문자열 (예: "RPG")
 * @param n - 표시 개수 (기본 6)
 */
export function getGenreCoreMetrics(
  metrics: Record<string, number | boolean | null | undefined>,
  genres: string,
  n: number = 6
): DistinctiveMetric[] {
  // 1. 장르 파싱 (첫 매칭 우선)
  const genreList = genres
    .split(',')
    .map((g) => g.trim())
    .filter(Boolean);

  let coreFields: string[] = DEFAULT_CORE_METRICS;
  for (const genre of genreList) {
    if (GENRE_CORE_METRICS[genre]) {
      coreFields = GENRE_CORE_METRICS[genre];
      break;
    }
  }

  // 2. 핵심지표 값 추출
  const result: DistinctiveMetric[] = [];
  for (const key of coreFields) {
    const value = metrics[key];
    if (typeof value !== 'number') continue;
    result.push({
      key,
      value,
      deviation: value - 5,
      category: value >= 8 ? 'high' : value >= 5 ? 'normal' : 'low',
    });
  }

  // 3. 6개 미만이면 강점으로 보충
  if (result.length < n) {
    const usedKeys = new Set(result.map((r) => r.key));
    const supplements: DistinctiveMetric[] = [];
    for (const key of NUMERIC_METRIC_FIELDS) {
      if (usedKeys.has(key)) continue;
      const value = metrics[key];
      if (typeof value !== 'number' || value < 6) continue;
      supplements.push({
        key,
        value,
        deviation: value - 5,
        category: value >= 8 ? 'high' : 'normal',
      });
    }
    supplements.sort((a, b) => b.value - a.value);
    result.push(...supplements.slice(0, n - result.length));
  }

  return result.slice(0, n);
}

/**
 * Legacy — 높은 값 우선 (검색 의도 카드용).
 * @deprecated 게임 상세는 getGenreCoreMetrics 사용.
 */
export function getDistinctiveMetrics(
  metrics: Record<string, number | boolean | null | undefined>,
  n: number = 6
): DistinctiveMetric[] {
  const result: DistinctiveMetric[] = [];
  for (const key of NUMERIC_METRIC_FIELDS) {
    const value = metrics[key];
    if (typeof value !== 'number') continue;
    if (value < 5) continue;
    result.push({
      key,
      value,
      deviation: value - 5,
      category: value >= 8 ? 'high' : value >= 6 ? 'normal' : 'low',
    });
  }
  result.sort((a, b) => b.value - a.value);
  return result.slice(0, n);
}

/**
 * Legacy — top metrics by value.
 * @deprecated
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
