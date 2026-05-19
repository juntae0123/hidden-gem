/**
 * Recommendation hooks
 * 추천 관련 훅 모음
 */
'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { recommendByGame, recommendByPreference } from '@/lib/api';

/**
 * Recommend similar games by appId
 * 특정 게임 기준 유사 게임 추천 훅
 */
export function useRecommendByGame(appId: number | null, count: number = 6) {
  return useQuery({
    queryKey: ['recommend', 'by-game', appId, count],
    queryFn: () => recommendByGame(appId as number, count),
    enabled: appId !== null && !Number.isNaN(appId),
    staleTime: 1000 * 60 * 5,
  });
}

/**
 * Recommend games by preference vector
 * 선호도 벡터 기반 추천 (mutation)
 */
export function useRecommendByPreference() {
  return useMutation({
    mutationFn: ({
      preferences,
      count = 12,
    }: {
      preferences: Record<string, number>;
      count?: number;
    }) => recommendByPreference(preferences, count),
  });
}
