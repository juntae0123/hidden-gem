/**
 * Ranking list component.
 * 랭킹 리스트 컴포넌트.
 *
 * v1 → v2:
 *   - img → GameImage (next/image 최적화, AVIF/WebP 자동 변환)
 *   - GemBadge size="sm" 명시
 *   - 인라인 steamHeader 함수 제거 (GameImage가 처리)
 */
'use client';

import Link from 'next/link';
import { cn } from '@/lib/utils';
import { GemBadge } from '@/components/ui/GemBadge';
import { GameImage } from '@/components/ui/GameImage';
import type { RecommendedGame } from '@/types/game';

interface RankingListProps {
  items: RecommendedGame[];
  /** HOT 뱃지 표시할 순위 (기본 1~3위) */
  hotIndices?: number[];
  className?: string;
}

/**
 * Single ranking row.
 * 랭킹 한 줄 컴포넌트.
 */
function RankingRow({
  game,
  rank,
  isHot,
}: {
  game: RecommendedGame;
  rank: number;
  isHot: boolean;
}) {
  const genres = (game.genres ?? '')
    .split(',')
    .map((g) => g.trim())
    .filter(Boolean)
    .slice(0, 3)
    .join(' · ');

  return (
    <Link
      href={`/game/${game.app_id}`}
      className={cn(
        'flex items-center gap-4 px-4 py-3',
        'border-b border-zinc-100 dark:border-zinc-800 last:border-b-0',
        'hover:bg-purple-50/40 dark:hover:bg-purple-950/10',
        'transition-colors'
      )}
    >
      {/* 순위 */}
      <span
        className={cn(
          'w-8 text-center font-mono text-[13px] flex-shrink-0',
          rank <= 3
            ? 'text-purple-600 font-semibold'
            : 'text-zinc-500'
        )}
      >
        {String(rank).padStart(2, '0')}
      </span>

      {/* 썸네일 — GameImage 사용 */}
      <div className="w-16 h-9 rounded overflow-hidden bg-zinc-100 dark:bg-zinc-800 flex-shrink-0">
        <GameImage
          appId={game.app_id}
          name={game.name}
          fallback={game.header_image}
          size="thumbnail"
        />
      </div>

      {/* 게임 정보 */}
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate">
          {game.name}
        </div>
        <div className="text-[11px] text-zinc-500 truncate">{genres}</div>
      </div>

      {/* HOT 뱃지 */}
      {isHot && (
        <span
          className={cn(
            'px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0',
            'bg-orange-500/10 text-orange-700 dark:text-orange-400'
          )}
        >
          HOT
        </span>
      )}

      {/* gem 점수 */}
      <GemBadge score={game.gem_potential ?? 0} showAlways size="sm" />
    </Link>
  );
}

/**
 * Ranking list sorted by gem_potential descending.
 * gem_potential 기준 내림차순 정렬된 랭킹 리스트.
 */
export function RankingList({
  items,
  hotIndices = [1, 2, 3],
  className,
}: RankingListProps) {
  // gem_potential 기준 내림차순 정렬
  const sorted = [...items].sort(
    (a, b) => (b.gem_potential ?? 0) - (a.gem_potential ?? 0)
  );

  return (
    <div
      className={cn(
        'bg-white dark:bg-zinc-900',
        'border border-zinc-200 dark:border-zinc-800',
        'rounded-xl overflow-hidden',
        className
      )}
    >
      {sorted.map((g, i) => (
        <RankingRow
          key={g.app_id}
          game={g}
          rank={i + 1}
          isHot={hotIndices.includes(i + 1)}
        />
      ))}
    </div>
  );
}
