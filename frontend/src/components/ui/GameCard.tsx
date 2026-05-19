/**
 * Game recommendation card
 * 게임 추천 카드 컴포넌트
 */
'use client';

import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { GemBadge } from './GemBadge';
import { MatchBar } from './MatchBar';
import type { RecommendedGame } from '@/types/game';

interface GameCardProps {
  game: RecommendedGame;
  active?: boolean;
  className?: string;
}

/**
 * Steam header image URL builder
 * Steam 헤더 이미지 URL 생성
 */
function getHeaderImage(appId: number, fallback?: string | null) {
  if (fallback) return fallback;
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}

/**
 * Game card with cover, match bar, gem badge
 * 커버 이미지, 매치바, gem 뱃지를 가진 게임 카드
 */
export function GameCard({ game, active = false, className }: GameCardProps) {
  const [imgError, setImgError] = useState(false);
  const imgSrc = imgError
    ? '/placeholder-game.png'
    : getHeaderImage(game.app_id, game.header_image);

  const matchValue = game.similarity_score ?? 0;
  const gemScore = game.gem_potential ?? 0;
  const reasonText = game.match_reasons?.[0] ?? '';

  return (
    <Link
      href={`/game/${game.app_id}`}
      className={cn(
        'group flex flex-col overflow-hidden',
        'bg-white dark:bg-zinc-900',
        'border rounded-xl',
        'transition-all duration-200',
        'hover:shadow-md hover:-translate-y-0.5',
        active
          ? 'border-[1.5px] border-purple-600'
          : 'border-zinc-200 dark:border-zinc-800 hover:border-purple-500/50',
        className
      )}
    >
      {/* 헤더 이미지 / Header image */}
      <div className="relative w-full aspect-[16/9] bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgSrc}
          alt={game.name}
          onError={() => setImgError(true)}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />
        {/* gem 코너 뱃지 / Gem corner badge */}
        {gemScore >= 95 && (
          <div className="absolute top-2 right-2">
            <GemBadge score={gemScore} />
          </div>
        )}
      </div>

      {/* 본문 / Body */}
      <div className="flex flex-col gap-2.5 p-3.5">
        {/* 제목 / Title */}
        <h3 className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 line-clamp-1">
          {game.name}
        </h3>

        {/* 장르 태그 / Genre tags */}
        {game.genres &&
          game.genres.split(',').map(g => g.trim()).filter(Boolean).slice(0, 3).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {game.genres.split(',').map(g => g.trim()).filter(Boolean).slice(0, 3).map((g) => (
              <span
                key={g}
                className="px-1.5 py-0.5 rounded text-[10px] bg-purple-600/10 text-purple-700 dark:text-purple-300"
              >
                {g}
              </span>
            ))}
          </div>
        )}

        {/* 매치율 바 / Match bar */}
        <MatchBar value={matchValue} />

        {/* 추천 이유 / Reason */}
        {reasonText && (
          <div className="flex items-start gap-1.5 pt-1 border-t border-zinc-100 dark:border-zinc-800">
            <Sparkles className="w-3 h-3 text-purple-500 mt-0.5 flex-shrink-0" />
            <span className="text-[11px] text-zinc-600 dark:text-zinc-400 line-clamp-1">
              {reasonText}
            </span>
          </div>
        )}
      </div>
    </Link>
  );
}
