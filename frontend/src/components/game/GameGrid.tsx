/**
 * Grid of game cards
 * 게임 카드 그리드 컴포넌트
 */
'use client';

import { GameCard } from '@/components/ui/GameCard';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { cn } from '@/lib/utils';
import type { RecommendedGame } from '@/types/game';

interface GameGridProps {
  games: RecommendedGame[];
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
}

/**
 * Responsive grid of GameCard
 * 반응형 게임 카드 그리드
 */
export function GameGrid({
  games,
  loading = false,
  emptyMessage = '추천할 게임이 없어요.',
  className,
}: GameGridProps) {
  if (loading) {
    return (
      <div className="py-20">
        <LoadingSpinner label="게임을 찾는 중..." />
      </div>
    );
  }

  if (!games || games.length === 0) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'grid gap-4',
        'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
        className
      )}
    >
      {games.map((g) => (
        <GameCard key={g.app_id} game={g} />
      ))}
    </div>
  );
}
