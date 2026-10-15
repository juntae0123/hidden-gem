/**
 * React Query hooks for game data fetching
 * 게임 데이터 조회용 React Query 훅 모음
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import {
  getGameDetail,
  getStatsOverview,
  getMetricsList,
} from '@/lib/api';
import type { GameDetail } from '@/types/game';

/**
 * Fetch game detail by appId
 * appId로 게임 상세 정보 조회 훅
 */
export function useGameDetail(appId: number | null, initialData?: GameDetail) {
  return useQuery({
    queryKey: ['game', appId],
    queryFn: () => getGameDetail(appId as number),
    enabled: appId !== null && !Number.isNaN(appId),
    initialData,   // 서버 컴포넌트가 받은 상세 (SEO 2026-10-14) — 첫 HTML 에 본문이 실린다
    staleTime: 1000 * 60 * 5, // 5분 / 5 min
  });
}

/**
 * Fetch stats overview
 * 전체 통계 조회 훅
 */
export function useStatsOverview() {
  return useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: getStatsOverview,
    staleTime: 1000 * 60 * 30,
  });
}

/**
 * Fetch available metrics list
 * 지표 목록 조회 훅
 */
export function useMetricsList() {
  return useQuery({
    queryKey: ['metrics', 'list'],
    queryFn: getMetricsList,
    staleTime: Infinity,
  });
}
