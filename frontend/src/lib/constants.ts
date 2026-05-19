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