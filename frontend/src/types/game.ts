/**
 * Game-related TypeScript type definitions.
 * 게임 관련 TypeScript 타입 정의 모음.
 */

export interface Game {
  app_id: number
  name: string
  genres: string
  header_image: string
  one_line_summary: string
  marketing_hook: string
  gem_potential: number | null
  steam_positive_ratio: number | null
  review_count: number
}

export interface GameMetrics {
  // VIBE
  cozy_factor: number | null
  horror_factor: number | null
  gore_level: number | null
  humor_rating: number | null
  dark_fantasy_vibe: number | null
  epic_scale: number | null
  melancholy: number | null
  // DEMANDS
  reflex_demand: number | null
  strategic_depth: number | null
  grind_factor: number | null
  time_pressure: number | null
  learning_curve: number | null
  // MECHANICS
  freedom_level: number | null
  action_pacing: number | null
  rng_dependency: number | null
  growth_reward: number | null
  exploration_reward: number | null
  management_complexity: number | null
  stealth_importance: number | null
  session_length: number | null
  narrative_linearity: number | null
  puzzle_complexity: number | null
  platforming_precision: number | null
  // SOCIAL
  coop_synergy: number | null
  competitive_stress: number | null
  npc_interaction: number | null
  user_creation: number | null
  multiplayer_scale: number | null
  // PRESENTATION
  lore_richness: number | null
  choice_consequence: number | null
  visual_spectacle: number | null
  environmental_storytelling: number | null
  soundtrack_impact: number | null
  // SYSTEM/UX
  build_variety: number | null
  progression_clarity: number | null
  save_flexibility: number | null
  difficulty_accessibility: number | null
  tutorial_quality: number | null
  ui_ux_polish: number | null
  modding_support: number | null
  // ART/AUDIO
  art_style_uniqueness: number | null
  audio_design: number | null
  animation_quality: number | null
  // OTHER
  world_reactivity: number | null
  community_dependency: number | null
  // NEW
  narrative_depth: number | null
  replay_value: number | null
  endgame_content: number | null
  monetization_fairness: number | null
  // TAGS
  is_turn_based: boolean
  is_real_time: boolean
  is_first_person: boolean
  is_third_person: boolean
  has_permadeath: boolean
  has_base_building: boolean
  has_crafting: boolean
  is_anime_style: boolean
  is_retro_aesthetic: boolean
  // EVAL
  gem_potential: number | null
  confidence_score: number | null
}

export interface GameDetail extends Game {
  developer: string
  publisher: string
  description: string
  short_description: string
  release_date: string | null
  price: number | null
  is_free: boolean
  is_indie: boolean
  is_early_access: boolean
  target_personas: Persona[]
  similar_games: SimilarGame[]
  unique_selling_points: string[]
  is_analyzed: boolean
  metrics: GameMetrics
}

export interface Persona {
  persona_id: string
  persona_name: string
  description: string
  fit_reason: string
}

export interface SimilarGame {
  name: string
  similarity_reason: string
}

export interface RecommendedGame {
  app_id: number
  name: string
  genres: string
  header_image: string
  one_line_summary: string
  marketing_hook: string
  similarity_score: number
  gem_potential: number | null
  match_reasons: string[]
  key_metrics: Record<string, number>
}

export interface RecommendationResponse {
  query_type: string
  reference_game: string | null
  total_candidates: number
  recommendations: RecommendedGame[]
}

export interface RankingGame {
  app_id: number
  name: string
  genres: string
  header_image: string
  one_line_summary: string
  gem_potential: number | null
  steam_positive_ratio: number | null
  review_count: number
}