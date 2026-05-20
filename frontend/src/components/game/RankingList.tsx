/**
 * Ranking list component
 * 랭킹 리스트 컴포넌트
 */
'use client';

import Link from 'next/link';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { GemBadge } from '@/components/ui/GemBadge';
import type { RecommendedGame } from '@/types/game';

interface RankingListProps {
  items: RecommendedGame[];
  hotIndices?: number[];
  className?: string;
}

/**
 * Steam header URL helper
 * Steam 헤더 이미지 URL 생성
 */
function steamHeader(appId: number, fallback?: string | null) {
  return fallback || `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}

/**
 * Single ranking row
 * 랭킹 한 줄 컴포넌트
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
  const [imgError, setImgError] = useState(false);

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
      {/* 순위 / Rank number */}
      <span className={cn(
        'w-8 text-center font-mono text-[13px] flex-shrink-0',
        rank <= 3 ? 'text-purple-600 font-semibold' : 'text-zinc-500'
      )}>
        {String(rank).padStart(2, '0')}
      </span>

      {/* 썸네일 / Thumbnail */}
      <div className="w-16 h-9 rounded overflow-hidden bg-zinc-100 dark:bg-zinc-800 flex-shrink-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgError ? '/placeholder-game.png' : steamHeader(game.app_id, game.header_image)}
          alt={game.name}
          onError={() => setImgError(true)}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      </div>

      {/* 게임 정보 / Game info */}
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate">
          {game.name}
        </div>
        <div className="text-[11px] text-zinc-500 truncate">
          {(game.genres ?? '').split(',').map(g => g.trim()).filter(Boolean).slice(0, 3).join(' · ')}
        </div>
      </div>

      {/* HOT 뱃지 / HOT badge */}
      {isHot && (
        <span className={cn(
          'px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0',
          'bg-orange-500/10 text-orange-700 dark:text-orange-400'
        )}>
          HOT
        </span>
      )}

      {/* gem 점수 / Gem score */}
      <GemBadge score={game.gem_potential ?? 0} showAlways />
    </Link>
  );
}

/**
 * Ranking list sorted by gem_potential descending
 * gem_potential 기준 내림차순 정렬된 랭킹 리스트
 */
export function RankingList({ items, hotIndices = [1, 2, 3], className }: RankingListProps) {
  // gem_potential 기준 내림차순 정렬 / Sort by gem_potential descending
  const sorted = [...items].sort((a, b) => (b.gem_potential ?? 0) - (a.gem_potential ?? 0));

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