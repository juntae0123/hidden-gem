// types/index.ts - v4.2

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

export interface IntentObject {
  id: string;
  name: string;
}

export interface GameResult {
  app_id: string;
  name: string;
  genres: string;
  developer: string;
  description: string;
  final_score: number;
  status: string;
  similarity: number;
  is_genre_match: boolean;
  is_exact_match: boolean;
  matched_intents: IntentObject[];
  scores: GameScores;
  is_fallback?: boolean;
}

export interface SearchResponse {
  success: boolean;
  is_game_search: boolean;
  query: string;
  summary_query?: string;
  intents: IntentObject[];
  core_genres?: string[];
  main_results: GameResult[];
  alternative_results: GameResult[];
  total_found: number;
  algorithm_version: string;
  error?: string;
  rejection_reason?: string;
  suggestion?: string;
}

export const METRIC_LABELS: Record<string, string> = {
  mania_score: "마니아",
  story_depth: "스토리",
  originality: "독창성",
  difficulty: "난이도",
  art_style: "아트",
  replay_value: "리플레이",
  indie_spirit: "인디",
  character_appeal: "캐릭터",
  user_friendliness: "접근성",
  addictiveness: "중독성",
  emotional_impact: "감정",
  atmosphere_intensity: "분위기",
  soundtrack_prominence: "음악",
  gem_potential: "명작도",
};

export const STATUS_COLORS: Record<string, string> = {
  LEGENDARY: "#FF4444",
  MYTHIC: "#FF6B6B",
  EPIC: "#A855F7",
  RARE: "#3B82F6",
  UNCOMMON: "#22C55E",
  COMMON: "#9CA3AF",
};
