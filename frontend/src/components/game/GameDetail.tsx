/**
 * Game detail panel.
 * 게임 상세 정보 패널.
 *
 * v1 → v2:
 *   - img → GameImage
 *   - LoadingSpinner → GameDetailSkeleton
 *   - 에러 → ErrorState (재시도 버튼 포함)
 *   - getTopMetrics → getDistinctiveMetrics (편차 기반)
 *   - 지표 카테고리 표시 (높음/낮음 뱃지)
 */
'use client';

import { ExternalLink, Heart } from 'lucide-react';
import { useGameDetail } from '@/hooks/useGames';
import { useUserStore } from '@/store/useUserStore';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameDetailSkeleton } from '@/components/ui/LoadingSkeleton';
import { GameImage } from '@/components/ui/GameImage';
import { RadarChart } from '@/components/ui/RadarChart';
import { getDistinctiveMetrics, METRIC_LABELS, cn } from '@/lib/utils';

interface GameDetailProps {
  appId: number;
}

export function GameDetail({ appId }: GameDetailProps) {
  const { data: game, isLoading, error, refetch } = useGameDetail(appId);
  const favorites      = useUserStore(s => s.favorites);
  const toggleFavorite = useUserStore(s => s.toggleFavorite);

  if (isLoading) return <GameDetailSkeleton />;

  if (error) {
    return (
      <ErrorState
        error={error as Error}
        onRetry={() => refetch()}
        variant="page"
      />
    );
  }

  if (!game) {
    return (
      <ErrorState
        type="not-found"
        title="게임 정보가 없어요"
        variant="page"
      />
    );
  }

  const isFav = favorites.includes(appId);

  // 편차 기반 특징적 지표 6개
  const distinctiveMetrics = getDistinctiveMetrics(
    game.metrics as unknown as Record<string, number | boolean | null>,
    6
  );
  const radarData = distinctiveMetrics.map(({ key, value }) => ({ metric: key, value }));

  const genres = game.genres?.split(',').map(g => g.trim()).filter(Boolean) ?? [];

  return (
    <article className="w-full">
      {/* Hero */}
      <div className="w-full rounded-xl overflow-hidden bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
        <div className="relative w-full aspect-[460/215] bg-zinc-200 dark:bg-zinc-800">
          <GameImage appId={appId} name={game.name} fallback={game.header_image} size="hero" priority />
        </div>

        <div className="p-6 flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">{game.name}</h1>
            {game.one_line_summary && (
              <p className="mt-1.5 text-sm text-zinc-600 dark:text-zinc-400">{game.one_line_summary}</p>
            )}
            {game.marketing_hook && (
              <p className="mt-3 text-sm text-purple-700 dark:text-purple-300 italic">
                &ldquo;{game.marketing_hook}&rdquo;
              </p>
            )}
            {genres.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {genres.map(g => (
                  <span key={g} className="px-2 py-0.5 rounded text-[11px] bg-purple-600/10 text-purple-700 dark:text-purple-300">
                    {g}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <a
              href={`https://store.steampowered.com/app/${appId}`}
              target="_blank"
              rel="noreferrer noopener"
              className={cn(
                'inline-flex items-center gap-1.5 px-4 py-2 rounded-md',
                'bg-purple-600 text-white text-[12px] font-medium hover:bg-purple-700 transition-colors'
              )}
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Steam에서 보기
            </a>
            <button
              type="button"
              onClick={() => toggleFavorite(appId)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-2 rounded-md border text-[12px]',
                isFav
                  ? 'border-purple-500 text-purple-600 bg-purple-50 dark:bg-purple-950/20'
                  : 'border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300'
              )}
            >
              <Heart className={cn('w-3.5 h-3.5', isFav && 'fill-current')} />
              {isFav ? '찜됨' : '찜하기'}
            </button>
          </div>
        </div>
      </div>

      {/* 레이더 + 지표 */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="flex flex-col items-center justify-center bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <div className="self-start mb-1">
            <h3 className="text-[12px] font-medium text-zinc-500 dark:text-zinc-400">가장 특징적인 지표</h3>
            <p className="text-[10px] text-zinc-400">평균(5점)에서 가장 멀리 떨어진 지표</p>
          </div>
          <RadarChart data={radarData} size={300} />
        </div>

        <div className="flex flex-col gap-3 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <h3 className="text-[12px] font-medium text-zinc-500 dark:text-zinc-400 mb-1">세부 지표</h3>
          {distinctiveMetrics.map(({ key, value, category }) => {
            const pct = Math.max(0, Math.min(100, (value / 10) * 100));
            return (
              <div key={key}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[12px] text-zinc-700 dark:text-zinc-300">
                      {METRIC_LABELS[key] || key}
                    </span>
                    {category === 'high' && (
                      <span className="text-[9px] px-1 rounded bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300">높음</span>
                    )}
                    {category === 'low' && (
                      <span className="text-[9px] px-1 rounded bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">낮음</span>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400">
                    {value.toFixed(0)} / 10
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-500',
                      category === 'high'   ? 'bg-purple-600' :
                      category === 'low'    ? 'bg-blue-500'   : 'bg-zinc-400'
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </article>
  );
}
