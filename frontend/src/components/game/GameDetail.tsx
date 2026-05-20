/**
 * Game detail panel
 * 게임 상세 정보 패널
 */
'use client';

import { useState } from 'react';
import { ExternalLink, Heart } from 'lucide-react';
import { useGameDetail } from '@/hooks/useGames';
import { useUserStore } from '@/store/useUserStore';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { RadarChart } from '@/components/ui/RadarChart';
import { getTopMetrics, METRIC_LABELS, cn, toPercent } from '@/lib/utils';

interface GameDetailProps {
  appId: number;
}

/**
 * Build Steam header URL
 * Steam 헤더 이미지 URL 생성
 */
function steamHeader(appId: number, fallback?: string | null) {
  return fallback || `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}

/**
 * Detailed game view with radar chart and metrics bar list
 * 레이더 차트와 지표 바 리스트가 포함된 게임 상세 뷰
 */
export function GameDetail({ appId }: GameDetailProps) {
  const { data: game, isLoading, error } = useGameDetail(appId);
  const favorites = useUserStore((s) => s.favorites);
  const toggleFavorite = useUserStore((s) => s.toggleFavorite);
  const [imgError, setImgError] = useState(false);

  if (isLoading) {
    return (
      <div className="py-20">
        <LoadingSpinner label="게임 정보 로딩 중..." />
      </div>
    );
  }

  if (error || !game) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">
        게임 정보를 불러올 수 없어요.
      </div>
    );
  }

  const isFav = favorites.includes(appId);
  const topMetrics = getTopMetrics((game.metrics as unknown as Record<string, number | boolean | null>) ?? {}, 6);
  const radarData = topMetrics.map(({ key, value }) => ({ metric: key, value }));

  return (
    <article className="w-full">
      {/* 헤더 영역 / Hero */}
      <div className="w-full rounded-xl overflow-hidden bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
        <div className="relative w-full aspect-[460/215] bg-zinc-200 dark:bg-zinc-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imgError ? '/placeholder-game.png' : steamHeader(appId, game.header_image)}
            alt={game.name}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover"
          />
        </div>

        <div className="p-6 flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
              {game.name}
            </h1>
            {game.one_line_summary && (
              <p className="mt-1.5 text-sm text-zinc-600 dark:text-zinc-400">
                {game.one_line_summary}
              </p>
            )}
            {game.marketing_hook && (
              <p className="mt-3 text-sm text-purple-700 dark:text-purple-300 italic">
                &ldquo;{game.marketing_hook}&rdquo;
              </p>
            )}
            {game.genres && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {game.genres.split(',').map(g => g.trim()).filter(Boolean).map((g) => (
                  <span
                    key={g}
                    className="px-2 py-0.5 rounded text-[11px] bg-purple-600/10 text-purple-700 dark:text-purple-300"
                  >
                    {g}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* 액션 버튼 / Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <a
              href={`https://store.steampowered.com/app/${appId}`}
              target="_blank"
              rel="noreferrer noopener"
              className={cn(
                'inline-flex items-center gap-1.5 px-4 py-2 rounded-md',
                'bg-purple-600 text-white text-[12px] font-medium',
                'hover:bg-purple-700 transition-colors'
              )}
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Steam에서 보기
            </a>
            <button
              type="button"
              onClick={() => toggleFavorite(appId)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-2 rounded-md',
                'border text-[12px]',
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

      {/* 레이더 + 지표 / Radar + metric bars */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="flex flex-col items-center justify-center bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <h3 className="text-[12px] font-medium text-zinc-500 dark:text-zinc-400 mb-2 self-start">
            상위 6개 지표
          </h3>
          <RadarChart data={radarData} size={300} />
        </div>

        <div className="flex flex-col gap-3 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <h3 className="text-[12px] font-medium text-zinc-500 dark:text-zinc-400 mb-1">
            세부 지표
          </h3>
          {topMetrics.map(({ key: metric, value }) => {
            const norm = value <= 1 ? value : value / 10;
            const pct = Math.max(0, Math.min(100, norm * 100));
            return (
              <div key={metric}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] text-zinc-700 dark:text-zinc-300">
                    {METRIC_LABELS[metric] || metric}
                  </span>
                  <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400">
                    {value.toFixed(0)} / 10
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-600 dark:bg-purple-500 rounded-full transition-all duration-500"
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
