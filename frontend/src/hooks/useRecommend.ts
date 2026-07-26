/**
 * Recommendation hooks — TanStack Query based
 * 추천 관련 훅 — TanStack Query 기반
 *
 * v2 → v3:
 *   - DEFAULT_PREFERENCES: 6개 분산 → 매일 다른 테마 순환
 *   - 테마 5개 (서사/아늑/전략/분위기/숨겨진 보석)
 *   - 각 테마는 핵심 3개 지표만 → 변별력 ↑
 */
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { recommendByGame, recommendByPreference, getVibes, recommendByVibe } from '@/lib/api';

// ==================== 매일 순환 테마 / Daily Rotating Themes ====================

/**
 * Daily rotating recommendation themes for cold-start users.
 * 신규 유저용 매일 순환 추천 테마.
 *
 * 각 테마는 핵심 3개 지표만 → 변별력 강화.
 * (이전 6개 분산 방식은 액션-어드벤처에 유리하게 작동하는 문제 있었음)
 */
export interface DailyTheme {
  readonly name:  string;
  readonly label: string;
  readonly prefs: Record<string, number>;
}

const DAILY_THEMES: readonly DailyTheme[] = [
  {
    name:  'narrative',
    label: '서사 깊은',
    prefs: {
      narrative_depth:    10,
      lore_richness:       9,
      choice_consequence:  8,
    },
  },
  {
    name:  'cozy',
    label: '아늑한',
    prefs: {
      cozy_factor:    9,
      time_pressure:  1,
      humor_rating:   7,
    },
  },
  {
    name:  'strategic',
    label: '뇌지컬',
    prefs: {
      strategic_depth:       10,
      management_complexity:  8,
      learning_curve:         7,
    },
  },
  {
    name:  'atmospheric',
    label: '분위기 깊은',
    prefs: {
      environmental_storytelling: 9,
      soundtrack_impact:          9,
      melancholy:                 7,
    },
  },
  {
    name:  'hidden_gem',
    label: '숨겨진 보석',
    prefs: {
      art_style_uniqueness: 9,
      audio_design:         8,
      replay_value:         8,
    },
  },
] as const;

/**
 * Get today's theme by UTC day-of-year.
 * Korean: UTC 기준 연중 일수로 오늘의 테마 결정.
 *   SSR(Vercel 미국) ≠ CSR(한국) 시간대 불일치(#418) 방지 위해 UTC 고정.
 */
function getTodaysTheme(): DailyTheme {
  const now = new Date();
  // UTC 기준 통일 — 서버/브라우저 어디서든 같은 날짜
  const startUTC = Date.UTC(now.getUTCFullYear(), 0, 0);
  const dayOfYear = Math.floor((now.getTime() - startUTC) / 86400000);
  return DAILY_THEMES[dayOfYear % DAILY_THEMES.length];
}

const todaysTheme = getTodaysTheme();


/** 오늘의 테마 선호도 / Today's theme preferences */
export const DEFAULT_PREFERENCES = todaysTheme.prefs;

/** 오늘의 테마 라벨 / Today's theme label (UI 표시용) */
export const DEFAULT_THEME_LABEL = todaysTheme.label;

/** 오늘의 테마 이름 / Today's theme name (analytics용) */
export const DEFAULT_THEME_NAME = todaysTheme.name;

// ==================== Query Hooks ====================

/**
 * Default AI recommendations for home page (auto-cached, no useEffect needed).
 * 메인 페이지 기본 추천 — 자동 캐싱, useEffect 불필요.
 *
 * staleTime 30분: 같은 기기에서 새로고침해도 재요청 없음
 */
export function useDefaultRecommendations(count: number = 9) {
  return useQuery({
    queryKey: ['recommend', 'default', DEFAULT_THEME_NAME, count],
    queryFn:  () => recommendByPreference({ ...DEFAULT_PREFERENCES }, count),
    staleTime:          1000 * 60 * 30,  // 30분 fresh
    gcTime:             1000 * 60 * 60,  // 1시간 캐시 유지
    refetchOnWindowFocus: false,
    refetchOnMount:       false,
    retry: 1,
  });
}

/**
 * Recommend similar games by reference game ID (game detail page).
 * 특정 게임 기반 유사 게임 추천 (게임 상세 페이지).
 */
export function useRecommendByGame(appId: number | null, count: number = 6) {
  return useQuery({
    queryKey: ['recommend', 'by-game', appId, count],
    queryFn:  () => recommendByGame(appId as number, count),
    enabled:  appId !== null && !Number.isNaN(appId),
    staleTime: 1000 * 60 * 15,
    gcTime:    1000 * 60 * 30,
    retry: 1,
  });
}

/**
 * Recommend by genre preferences (ranking page).
 * 장르별 선호도 추천 (랭킹 페이지).
 */
export function useRecommendByGenre(
  genrePrefs: Record<string, number> | null,
  count: number = 10
) {
  return useQuery({
    queryKey: ['recommend', 'genre', genrePrefs, count],
    queryFn:  () => recommendByPreference(genrePrefs!, count),
    enabled:  !!genrePrefs && Object.keys(genrePrefs).length > 0,
    staleTime: 1000 * 60 * 30,
    gcTime:    1000 * 60 * 60,
    retry: 1,
  });
}

// ==================== Mutation Hooks ====================

/**
 * Custom preference recommendation — mutation (search/page.tsx 취향 분석).
 * 사용자 정의 선호도 추천 — mutation (제출 버튼 클릭 시).
 *
 * 매번 다른 선호도라 캐싱 실익 없음.
 */
export function useRecommendByPreference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      preferences,
      count = 12,
    }: {
      preferences: Record<string, number>;
      count?: number;
    }) => recommendByPreference(preferences, count),
    onSuccess: (data, variables) => {
      // 동일 선호도 재요청 시 캐시에서 즉시 반환
      queryClient.setQueryData(
        ['recommend', 'preference', variables.preferences, variables.count],
        data
      );
    },
  });
}

// ==================== Vibe Cluster Hooks ====================

/**
 * Fetch vibe chip list (cached long — rarely changes).
 * Korean: Vibe 칩 목록 조회. 거의 안 바뀌니 길게 캐싱.
 */
export function useVibes() {
  return useQuery({
    queryKey: ['vibes', 'list'],
    queryFn:  getVibes,
    staleTime: 1000 * 60 * 60,      // 1시간 fresh
    gcTime:    1000 * 60 * 60 * 24, // 24시간 캐시
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

/**
 * Recommend games by selected vibe chip.
 * Korean: 선택된 Vibe 칩으로 추천. vibeKey가 null이면 비활성.
 */
export function useRecommendByVibe(vibeKey: string | null, count: number = 12) {
  return useQuery({
    queryKey: ['recommend', 'vibe', vibeKey, count],
    queryFn:  () => recommendByVibe(vibeKey as string, count),
    enabled:  vibeKey !== null,
    staleTime: 1000 * 60 * 30,
    gcTime:    1000 * 60 * 60,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}