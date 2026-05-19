/**
 * Similar games recommendation list
 * 유사 게임 추천 리스트
 */
'use client';

import { useRecommendByGame } from '@/hooks/useRecommend';
import { GameGrid } from './GameGrid';

interface RecommendListProps {
  appId: number;
  count?: number;
}

/**
 * Render recommended games based on a base game
 * 기준 게임 기반 추천 게임 렌더링
 */
export function RecommendList({ appId, count = 6 }: RecommendListProps) {
  const { data, isLoading } = useRecommendByGame(appId, count);

  return (
    <section className="mt-12">
      <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
        이 게임과 비슷한 게임
      </h2>
      <GameGrid
        games={data?.recommendations ?? []}
        loading={isLoading}
        emptyMessage="비슷한 게임을 찾지 못했어요."
      />
    </section>
  );
}
