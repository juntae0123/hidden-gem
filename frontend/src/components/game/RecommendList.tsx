/**
 * Similar games recommendation list.
 * 유사 게임 추천 리스트.
 *
 * v1 → v2:
 *   - 에러 처리 추가 (ErrorState + 재시도)
 *   - 로딩 개선 (GameGridSkeleton)
 *   - 빈 결과 명확한 메시지
 *   - 4가지 상태 분기 (error / loading / empty / success)
 */
'use client';

import { useRecommendByGame } from '@/hooks/useRecommend';
import { GameGrid } from './GameGrid';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameGridSkeleton } from '@/components/ui/LoadingSkeleton';

interface RecommendListProps {
  appId: number;
  count?: number;
}

/**
 * Render similar games based on reference game.
 * 기준 게임 기반 유사 게임 렌더링.
 */
export function RecommendList({ appId, count = 6 }: RecommendListProps) {
  const { data, isLoading, error, refetch } = useRecommendByGame(appId, count);
  const games = data?.recommendations ?? [];

  return (
    <section className="mt-12">
      <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
        이 게임과 비슷한 게임
      </h2>

      {/* 에러 상태 */}
      {error && (
        <ErrorState
          error={error as Error}
          onRetry={() => refetch()}
          variant="inline"
          title="비슷한 게임을 불러올 수 없어요"
        />
      )}

      {/* 로딩 상태 */}
      {isLoading && !error && <GameGridSkeleton count={count} />}

      {/* 빈 결과 */}
      {!isLoading && !error && games.length === 0 && (
        <ErrorState
          type="not-found"
          variant="inline"
          title="비슷한 게임을 찾지 못했어요"
          description="이 게임은 매우 독특한 특성을 가지고 있나봐요"
        />
      )}

      {/* 정상 결과 */}
      {!isLoading && !error && games.length > 0 && <GameGrid games={games} />}
    </section>
  );
}
