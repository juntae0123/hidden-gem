/**
 * Recommendation hooks — TanStack Query based
 * 추천 관련 훅 — TanStack Query 기반
 *
 * v1 → v2 변경사항:
 *   - useDefaultRecommendations: useEffect+mutation → useQuery (30분 캐싱)
 *   - useRecommendByGenre: 신규 (랭킹 페이지용)
 *   - useRecommendByGame: 기존 유지
 *   - useRecommendByPreference: mutation 유지 (취향 분석 제출용)
 */
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { recommendByGame, recommendByPreference } from '@/lib/api';

// ==================== Cold Start 기본 선호도 ====================

/** 신규 유저용 기본 선호도 — 다양한 감성 게임 */
export const DEFAULT_PREFERENCES = {
  narrative_depth:     8,
  lore_richness:       7,
  art_style_uniqueness:7,
  replay_value:        6,
  exploration_reward:  7,
  soundtrack_impact:   7,
} as const;

// ==================== Query Hooks ====================

/**
 * Default AI recommendations for home page (auto-cached, no useEffect needed).
 * 메인 페이지 기본 추천 — 자동 캐싱, useEffect 불필요.
 *
 * staleTime 30분: 같은 기기에서 새로고침해도 재요청 없음
 */
export function useDefaultRecommendations(count: number = 9) {
  return useQuery({
    queryKey: ['recommend', 'default', count],
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