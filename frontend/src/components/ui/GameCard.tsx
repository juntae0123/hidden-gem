/**
 * Game recommendation card.
 * 게임 추천 카드 컴포넌트.
 *
 * v3: ensureSessionId 사용 (SSR-safe)
 */
'use client';

import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { cn, METRIC_LABELS } from '@/lib/utils';
import { GemBadge } from './GemBadge';
import { LifecycleBadge } from './LifecycleBadge';
import { MatchBar } from './MatchBar';
import { GameImage } from './GameImage';
import { GEM_TIERS } from '@/lib/score';
import { recordTasteAction } from '@/lib/api';
import { useUserStore } from '@/store/useUserStore';
import type { RecommendedGame } from '@/types/game';

interface GameCardProps {
  game: RecommendedGame;
  active?: boolean;
  context?: 'search' | 'similar' | 'preference';
  index?: number;
  className?: string;
}

export function GameCard({
  game,
  active = false,
  context = 'preference',
  index = 0,
  className,
}: GameCardProps) {
  const ensureSessionId = useUserStore((s) => s.ensureSessionId);
  const matchValue = game.similarity_score ?? 0;
  const gemScore   = game.gem_potential ?? 0;
  // R-3: 서버가 gem_evidence 를 주면(evidence 모드) 그걸로 뱃지. 아직 legacy 면 undefined → 옛 로직
  const gemEvidence = game.gem_evidence;
  const showGem = gemEvidence !== undefined && gemEvidence !== null
    ? gemEvidence >= 45
    : gemScore >= GEM_TIERS.RARE;
  const reasonText = game.match_reasons?.[0] ?? '';
  // 카드에서 '왜 맞는지'를 보여주는 핵심 지표 2개 (값 높은 순)
  const topMetrics = Object.entries(game.key_metrics ?? {})
    .filter(([, v]) => typeof v === 'number')
    .sort((a, b) => (b[1] as number) - (a[1] as number))
    .slice(0, 2);
  const genres     = game.genres
    ?.split(',').map(g => g.trim()).filter(Boolean).slice(0, 3) ?? [];

  const handleClick = () => {
    const actionType = context === 'search' ? 'search_click' : 'rec_click';
    recordTasteAction({
      session_id:  ensureSessionId(),
      app_id:      game.app_id,
      action_type: actionType,
      context: {
        click_position:   index,
        displayed_score:  matchValue,
        referrer_context: context,
      },
    });
  };

  return (
    <Link
      href={`/game/${game.app_id}`}
      onClick={handleClick}
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
      <div className="relative w-full aspect-[16/9] bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
        <GameImage
          appId={game.app_id}
          name={game.name}
          fallback={game.header_image}
          size="card"
          zoomOnHover
        />
        {(game.lifecycle === 'new' || showGem) && (
          <div className="absolute top-2 right-2">
            {game.lifecycle === 'new'
              ? <LifecycleBadge lifecycle="new" isFamous={game.is_famous} daysSinceRelease={game.days_since_release} reviewCount={game.review_count} size="sm" />
              : <GemBadge score={gemScore} evidence={gemEvidence} size="sm" />}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2.5 p-3.5">
        <h3 className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 line-clamp-1">
          {game.name}
        </h3>

        {genres.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {genres.map(g => (
              <span key={g} className="px-1.5 py-0.5 rounded text-[10px] bg-purple-600/10 text-purple-700 dark:text-purple-300">
                {g}
              </span>
            ))}
          </div>
        )}

        {topMetrics.length > 0 && (
          <div className="flex items-center gap-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
            {topMetrics.map(([k, v], i) => (
              <span key={k} className="flex items-center gap-1">
                {i > 0 && <span className="text-zinc-300 dark:text-zinc-700">·</span>}
                <span>{METRIC_LABELS[k] ?? k}</span>
                <span className="font-mono text-purple-600 dark:text-purple-400">{(v as number).toFixed(1)}</span>
              </span>
            ))}
          </div>
        )}

        <MatchBar value={matchValue} context={context} compact />

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
