/**
 * Utility functions for Hidden Gem frontend.
 * Hidden Gem 프론트엔드 유틸리티 함수 모음.
 */

import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

// Tailwind 클래스 병합 / Merge Tailwind classes
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// gem potential 색상 반환 / Get gem potential color class
export function getGemColor(gem: number | null): string {
  if (!gem) return 'text-gray-400'
  if (gem >= 90) return 'text-purple-500'
  if (gem >= 75) return 'text-blue-500'
  if (gem >= 60) return 'text-teal-500'
  return 'text-gray-400'
}

// 매치율 퍼센트 변환 / Convert similarity score to percentage
export function toPercent(score: number): number {
  return Math.round(score * 100)
}

// 지표 한국어 라벨 / Korean labels for metrics
export const METRIC_LABELS: Record<string, string> = {
  cozy_factor: '아늑함',
  horror_factor: '공포',
  gore_level: '고어',
  humor_rating: '유머',
  dark_fantasy_vibe: '다크판타지',
  epic_scale: '스케일',
  melancholy: '멜랑콜리',
  reflex_demand: '반응속도',
  strategic_depth: '전략깊이',
  grind_factor: '노가다',
  time_pressure: '시간압박',
  learning_curve: '학습곡선',
  freedom_level: '자유도',
  action_pacing: '액션템포',
  rng_dependency: 'RNG의존도',
  growth_reward: '성장보상',
  exploration_reward: '탐험보상',
  management_complexity: '관리복잡도',
  stealth_importance: '스텔스',
  session_length: '세션길이',
  narrative_linearity: '서사선형성',
  puzzle_complexity: '퍼즐복잡도',
  platforming_precision: '플랫폼정밀도',
  coop_synergy: '협동시너지',
  competitive_stress: '경쟁스트레스',
  npc_interaction: 'NPC상호작용',
  user_creation: '유저창작',
  multiplayer_scale: '멀티규모',
  lore_richness: '세계관밀도',
  choice_consequence: '선택결과',
  visual_spectacle: '시각연출',
  environmental_storytelling: '환경서사',
  soundtrack_impact: '사운드트랙',
  build_variety: '빌드다양성',
  progression_clarity: '진행명확성',
  save_flexibility: '저장유연성',
  difficulty_accessibility: '난이도접근성',
  tutorial_quality: '튜토리얼',
  ui_ux_polish: 'UI/UX완성도',
  modding_support: '모딩지원',
  art_style_uniqueness: '아트독창성',
  audio_design: '오디오디자인',
  animation_quality: '애니메이션',
  world_reactivity: '세계반응성',
  community_dependency: '커뮤니티의존',
  narrative_depth: '서사깊이',
  replay_value: '리플레이',
  endgame_content: '엔드게임',
  monetization_fairness: '과금공정성',
}

// 상위 N개 지표 추출 / Extract top N metrics by value
export function getTopMetrics(
  metrics: Record<string, number | boolean | null>,
  n = 6
): { key: string; value: number; label: string }[] {
  return Object.entries(metrics)
    .filter(([k, v]) => typeof v === 'number' && v !== null && METRIC_LABELS[k])
    .map(([k, v]) => ({ key: k, value: v as number, label: METRIC_LABELS[k] || k }))
    .sort((a, b) => b.value - a.value)
    .slice(0, n)
}

// 헤더 이미지 fallback / Header image with fallback
export function getHeaderImage(url: string | null): string {
  if (!url || url === '') return '/placeholder-game.png'
  return url
}

// 장르 배열 변환 / Parse genres string to array
export function parseGenres(genres: string): string[] {
  return genres.split(',').map(g => g.trim()).filter(Boolean)
}