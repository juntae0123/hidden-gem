/**
 * App-wide constants for Hidden Gem.
 * Hidden Gem 앱 전역 상수 정의.
 */

// 검색 플레이스홀더 예시 / Search placeholder examples
export const SEARCH_PLACEHOLDERS = [
  "예: '혼자 조용히 즐기는 전략 게임'",
  "예: 'Stardew Valley 같은 힐링겜'",
  "예: '죽으면 처음부터인데 중독되는 게임'",
  "예: 'Dark Souls 분위기인데 좀 쉬운 거'",
  "예: '커피 마시면서 30분 정도 할 만한 게임'",
  "예: '스토리가 강렬한 인디 RPG'",
]

// 검색 힌트 칩 / Search hint chips
export const SEARCH_CHIPS = [
  { label: '아늑한 힐링겜', query: '스트레스 없이 편하게 즐길 수 있는 힐링 게임' },
  { label: '뇌지컬 전략', query: '깊은 전략과 복잡한 시스템을 가진 게임' },
  { label: '서사 몰입', query: '스토리와 세계관이 깊고 몰입감 있는 게임' },
  { label: '공포 분위기', query: '공포스럽고 긴장감 있는 분위기의 게임' },
  { label: '로그라이크', query: '죽으면 처음부터 시작하는 로그라이크 게임' },
  { label: '픽셀 인디', query: '픽셀 아트 스타일의 인디 게임' },
]

// 장르 목록 / Genre list
export const GENRES = [
  '전체', 'RPG', '액션', '전략', '시뮬레이션',
  '어드벤처', '인디', '로그라이크', '공포', '퍼즐',
]

// 정렬 옵션 / Sort options
export const SORT_OPTIONS = [
  { value: 'match', label: '매치율 높은 순' },
  { value: 'gem', label: 'Gem Potential 순' },
  { value: 'review', label: '리뷰 많은 순' },
]

// API 기본 URL / API base URL
export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// 지표별 설명 / Metric descriptions for tooltip
export const METRIC_DESCRIPTIONS: Record<string, string> = {
  cozy_factor: '게임이 얼마나 아늑하고 편안한 분위기인지 나타냅니다. 높을수록 힐링/휴식 느낌이 강합니다.',
  horror_factor: '공포 요소의 강도입니다. 높을수록 무섭고 긴장되는 분위기입니다.',
  gore_level: '폭력적/잔인한 표현의 수위입니다. 높을수록 그래픽한 장면이 많습니다.',
  humor_rating: '유머와 재미 요소입니다. 높을수록 웃기고 가벼운 분위기입니다.',
  dark_fantasy_vibe: '다크 판타지 분위기입니다. 높을수록 어둡고 무거운 세계관입니다.',
  epic_scale: '게임의 스케일과 장대함입니다. 높을수록 영웅적이고 거대한 이야기입니다.',
  melancholy: '우울하고 쓸쓸한 감성입니다. 높을수록 감성적이고 여운이 남습니다.',
  reflex_demand: '반응속도 요구량입니다. 높을수록 빠른 손놀림이 필요합니다.',
  strategic_depth: '전략적 깊이입니다. 높을수록 깊이 생각하고 계획해야 합니다.',
  grind_factor: '반복 파밍/노가다 비중입니다. 높을수록 같은 행동을 많이 반복합니다.',
  time_pressure: '시간 압박감입니다. 높을수록 빠르게 결정하고 행동해야 합니다.',
  learning_curve: '학습 난이도입니다. 높을수록 익히기 어렵고 진입장벽이 높습니다.',
  freedom_level: '플레이 자유도입니다. 높을수록 내 방식대로 즐길 수 있습니다.',
  action_pacing: '액션 템포입니다. 높을수록 빠르고 역동적인 전투가 많습니다.',
  rng_dependency: '랜덤 요소 의존도입니다. 높을수록 운이 결과에 큰 영향을 줍니다.',
  growth_reward: '성장 보상감입니다. 높을수록 캐릭터/장비 성장이 뚜렷하게 느껴집니다.',
  exploration_reward: '탐험 보상감입니다. 높을수록 새 지역 발견의 재미가 큽니다.',
  management_complexity: '관리 복잡도입니다. 높을수록 여러 요소를 동시에 관리해야 합니다.',
  stealth_importance: '스텔스 비중입니다. 높을수록 숨어서 조용히 진행하는 플레이가 많습니다.',
  session_length: '한 세션 길이입니다. 높을수록 한 번 플레이에 오랜 시간이 걸립니다.',
  narrative_linearity: '서사 선형성입니다. 높을수록 정해진 이야기를 따라가는 구조입니다.',
  puzzle_complexity: '퍼즐 복잡도입니다. 높을수록 두뇌를 많이 써야 하는 퍼즐이 많습니다.',
  platforming_precision: '플랫폼 정밀도입니다. 높을수록 정확한 점프/이동이 필요합니다.',
  coop_synergy: '협동 플레이 재미입니다. 높을수록 친구와 함께할 때 더 재밌습니다.',
  competitive_stress: '경쟁 스트레스입니다. 높을수록 다른 플레이어와 치열하게 경쟁합니다.',
  npc_interaction: 'NPC 상호작용입니다. 높을수록 다양한 캐릭터와 깊이 교류합니다.',
  user_creation: '유저 창작 요소입니다. 높을수록 직접 콘텐츠를 만들고 공유할 수 있습니다.',
  multiplayer_scale: '멀티플레이 규모입니다. 높을수록 많은 사람이 함께 즐깁니다.',
  lore_richness: '세계관 밀도입니다. 높을수록 깊고 풍부한 설정과 역사가 있습니다.',
  choice_consequence: '선택의 결과입니다. 높을수록 내 선택이 이야기에 크게 영향을 줍니다.',
  visual_spectacle: '시각적 연출입니다. 높을수록 화려하고 인상적인 비주얼이 많습니다.',
  environmental_storytelling: '환경 서사입니다. 높을수록 배경 자체가 이야기를 전달합니다.',
  soundtrack_impact: '사운드트랙 임팩트입니다. 높을수록 음악이 분위기를 강하게 이끕니다.',
  build_variety: '빌드 다양성입니다. 높을수록 다양한 플레이 스타일로 즐길 수 있습니다.',
  progression_clarity: '진행 명확성입니다. 높을수록 다음에 뭘 해야 할지 명확합니다.',
  save_flexibility: '저장 유연성입니다. 높을수록 언제든 자유롭게 저장할 수 있습니다.',
  difficulty_accessibility: '난이도 접근성입니다. 높을수록 다양한 실력의 플레이어가 즐길 수 있습니다.',
  tutorial_quality: '튜토리얼 품질입니다. 높을수록 게임 시작이 친절하고 쉽습니다.',
  ui_ux_polish: 'UI/UX 완성도입니다. 높을수록 인터페이스가 직관적이고 세련됐습니다.',
  modding_support: '모딩 지원입니다. 높을수록 유저가 직접 콘텐츠를 추가할 수 있습니다.',
  art_style_uniqueness: '아트 독창성입니다. 높을수록 남다르고 개성 있는 비주얼입니다.',
  audio_design: '오디오 디자인입니다. 높을수록 효과음과 환경음이 몰입감을 높입니다.',
  animation_quality: '애니메이션 품질입니다. 높을수록 움직임이 자연스럽고 역동적입니다.',
  world_reactivity: '세계 반응성입니다. 높을수록 내 행동에 세계가 풍부하게 반응합니다.',
  community_dependency: '커뮤니티 의존도입니다. 높을수록 공략/커뮤니티 참여가 중요합니다.',
  narrative_depth: '서사 깊이입니다. 높을수록 이야기가 문학적이고 감동적입니다.',
  replay_value: '리플레이 가치입니다. 높을수록 여러 번 해도 새로운 재미가 있습니다.',
  endgame_content: '엔드게임 콘텐츠입니다. 높을수록 클리어 후에도 즐길 거리가 많습니다.',
  monetization_fairness: '과금 공정성입니다. 높을수록 돈 안 써도 충분히 즐길 수 있습니다.',
}

// 지표 카테고리 (한국어) / Metric categories in Korean
export const METRIC_CATEGORIES_KO: Record<string, { label: string; metrics: string[] }> = {
  vibe: {
    label: '🎭 분위기',
    metrics: ['cozy_factor', 'horror_factor', 'gore_level', 'humor_rating', 'dark_fantasy_vibe', 'epic_scale', 'melancholy'],
  },
  demands: {
    label: '⚡ 난이도/요구사항',
    metrics: ['reflex_demand', 'strategic_depth', 'grind_factor', 'time_pressure', 'learning_curve'],
  },
  mechanics: {
    label: '🎮 게임 메카닉',
    metrics: ['freedom_level', 'action_pacing', 'rng_dependency', 'growth_reward', 'exploration_reward', 'management_complexity', 'stealth_importance', 'session_length', 'narrative_linearity', 'puzzle_complexity', 'platforming_precision'],
  },
  social: {
    label: '👥 소셜/멀티',
    metrics: ['coop_synergy', 'competitive_stress', 'npc_interaction', 'user_creation', 'multiplayer_scale'],
  },
  presentation: {
    label: '📖 연출/스토리',
    metrics: ['lore_richness', 'choice_consequence', 'visual_spectacle', 'environmental_storytelling', 'soundtrack_impact'],
  },
  system: {
    label: '⚙️ 시스템/UX',
    metrics: ['build_variety', 'progression_clarity', 'save_flexibility', 'difficulty_accessibility', 'tutorial_quality', 'ui_ux_polish', 'modding_support'],
  },
  art: {
    label: '🎨 아트/오디오',
    metrics: ['art_style_uniqueness', 'audio_design', 'animation_quality'],
  },
  other: {
    label: '✨ 기타',
    metrics: ['world_reactivity', 'community_dependency', 'narrative_depth', 'replay_value', 'endgame_content', 'monetization_fairness'],
  },
}