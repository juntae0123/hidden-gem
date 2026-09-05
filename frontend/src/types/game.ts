/**
 * Game-related TypeScript type definitions.
 * 게임 관련 TypeScript 타입 정의.
 */

// ==================== Base ====================

export interface Game {
  app_id: number;
  name: string;
  genres: string;
  header_image: string;
  one_line_summary: string;
  marketing_hook: string;
  gem_potential: number | null;
  steam_positive_ratio: number | null;
  review_count: number;
}

// ==================== Metrics ====================

export interface GameMetrics {
  // VIBE (7)
  cozy_factor: number | null;
  horror_factor: number | null;
  gore_level: number | null;
  humor_rating: number | null;
  dark_fantasy_vibe: number | null;
  epic_scale: number | null;
  melancholy: number | null;
  // DEMANDS (5)
  reflex_demand: number | null;
  strategic_depth: number | null;
  grind_factor: number | null;
  time_pressure: number | null;
  learning_curve: number | null;
  // MECHANICS (11)
  freedom_level: number | null;
  action_pacing: number | null;
  rng_dependency: number | null;
  growth_reward: number | null;
  exploration_reward: number | null;
  management_complexity: number | null;
  stealth_importance: number | null;
  session_length: number | null;
  narrative_linearity: number | null;
  puzzle_complexity: number | null;
  platforming_precision: number | null;
  // SOCIAL (5)
  coop_synergy: number | null;
  competitive_stress: number | null;
  npc_interaction: number | null;
  user_creation: number | null;
  multiplayer_scale: number | null;
  // PRESENTATION (5)
  lore_richness: number | null;
  choice_consequence: number | null;
  visual_spectacle: number | null;
  environmental_storytelling: number | null;
  soundtrack_impact: number | null;
  // SYSTEM/UX (7)
  build_variety: number | null;
  progression_clarity: number | null;
  save_flexibility: number | null;
  difficulty_accessibility: number | null;
  tutorial_quality: number | null;
  ui_ux_polish: number | null;
  modding_support: number | null;
  // ART/AUDIO (3)
  art_style_uniqueness: number | null;
  audio_design: number | null;
  animation_quality: number | null;
  // OTHER (2)
  world_reactivity: number | null;
  community_dependency: number | null;
  // NEW (4)
  narrative_depth: number | null;
  replay_value: number | null;
  endgame_content: number | null;
  monetization_fairness: number | null;
  // TAGS (9 boolean)
  is_turn_based: boolean;
  is_real_time: boolean;
  is_first_person: boolean;
  is_third_person: boolean;
  has_permadeath: boolean;
  has_base_building: boolean;
  has_crafting: boolean;
  is_anime_style: boolean;
  is_retro_aesthetic: boolean;
  // EVAL (2)
  gem_potential: number | null;
  confidence_score: number | null;
}

// ==================== Detail ====================

export interface GameDetail extends Game {
  developer: string;
  publisher: string;
  description: string;
  short_description: string;
  release_date: string | null;
  price: number | null;
  is_free: boolean;
  is_indie: boolean;
  is_early_access: boolean;
  target_personas: Persona[];
  similar_games: SimilarGame[];
  unique_selling_points: string[];
  is_analyzed: boolean;
  metrics: GameMetrics;
}

export interface Persona {
  persona_id: string;
  persona_name: string;
  description: string;
  fit_reason: string;
}

export interface SimilarGame {
  name: string;
  similarity_reason: string;
}

// ==================== Recommendation ====================

/**
 * Score breakdown for explainability (v5).
 * 점수 분해 — 추천 근거 투명성 (v5 신규).
 */
export interface ScoreBreakdown {
  metric_score:    number;  // 지표 매치 점수 (0~100 스케일)
  embedding_score: number;  // 임베딩 유사도 점수 (0~100 스케일)
  gem_bonus:       number;  // Hidden Gem 보너스 (0~5)
  final_score:     number;  // 최종 점수 (0~99)
}

export interface RecommendedGame {
  app_id: number;
  name: string;
  genres: string;
  header_image: string;
  one_line_summary: string;
  marketing_hook: string;
  /** 절대 점수 0~99 (기준 게임 앵커는 100) */
  similarity_score: number;
  gem_potential: number | null;
  match_reasons: string[];
  key_metrics: Record<string, number>;
  /** v5 신규 — 점수 분해 (선택적) */
  score_breakdown?: ScoreBreakdown | null;
  /** R-3 리뷰 실측 발굴 지수 0~100. null = 근거 없음(0 과 다르다). undefined = 서버가 legacy 모드 */
  gem_evidence?: number | null;
  gem_evidence_status?: 'ok' | 'too_new' | 'famous' | 'insufficient' | 'no_reviews' | 'upcoming' | null;
  /** R-11 생애주기: 신작(출시 ≤180일) / 정착 / 유명(리뷰 2만+). 신작은 발굴 판단 보류 */
  lifecycle?: Lifecycle;
  /** 인지도 축 — 나이 축과 별개. 8.7만 리뷰 신작은 new + is_famous */
  is_famous?: boolean;
  days_since_release?: number | null;
  review_count?: number | null;
}

export type Lifecycle = 'new' | 'established' | 'famous' | 'upcoming' | '';

/** GET /games/ranking 응답 한 줄 (R-12) */
export interface RankingItem {
  rank: number;
  app_id: number;
  name: string;
  genres: string;
  header_image: string;
  one_line_summary: string;
  review_count: number | null;
  positive_ratio: number | null;
  wilson_lower: number | null;
  lifecycle: Lifecycle;
  is_famous: boolean;
  days_since_release: number | null;
  gem_evidence: number | null;       // steady
  velocity_per_day: number | null;   // new
  delta_30d: number | null;          // rising
  growth_30d_pct: number | null;     // rising
  badge: string;
}

export type RankingType = 'steady' | 'rising' | 'new' | 'new_quiet';

export interface RankingResponse {
  type: RankingType;
  genre: string | null;
  total: number;
  status: 'ok' | 'collecting';
  note: string;
  items: RankingItem[];
}

export interface RecommendationResponse {
  query_type: string;
  reference_game: string | null;
  total_candidates: number;
  recommendations: RecommendedGame[];
}

export interface RankingGame {
  app_id: number;
  name: string;
  genres: string;
  header_image: string;
  one_line_summary: string;
  gem_potential: number | null;
  steam_positive_ratio: number | null;
  review_count: number;
}