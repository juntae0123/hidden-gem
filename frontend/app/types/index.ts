// types/index.ts

export interface GameScores {
  mania_score: number;
  story_depth: number;
  originality: number;
  difficulty: number;
  art_style: number;
  replay_value: number;
  indie_spirit: number;
  character_appeal: number;
  user_friendliness: number;
  addictiveness: number;
  emotional_impact: number;
  atmosphere_intensity: number;
  soundtrack_prominence: number;
  gem_potential: number;
}

export interface BoostInfo {
  original?: number;
  after_base?: number;
  additional_boost?: number;
  final_weight?: number;
}

export interface Game {
  app_id: string;
  name: string;
  genres: string;
  developer: string;
  description: string;
  final_score: number;
  status: "GEM" | "MANIAC" | "DROP";
  similarity: number;
  matched_intents: string[];
  boost_reason: string | null;
  boost_info: Record<string, BoostInfo>;
  scores: GameScores;
  fallback_rescued?: boolean;
}

export interface SearchResponse {
  query: string;
  intents: string[];
  gems: Game[];
  maniacs: Game[];
  total_candidates: number;
  algorithm_version: string;
  fallback_activated: boolean;
  fallback_message: string | null;
}

export type TierType = "legendary" | "mythic" | "epic" | "rare" | "uncommon" | "solid" | "maniac";

export interface TierConfig {
  label: string;
  color: string;
}
