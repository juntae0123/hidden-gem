/**
 * Game detail panel.
 * 게임 상세 — 장르 핵심지표 + 지표 설명 툴팁.
 *
 * v5 → v6:
 *   - 각 지표에 호버 툴팁 (METRIC_DESCRIPTIONS)
 *   - "선택결과"가 무엇을 의미하는지 설명
 */
'use client';

import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Heart } from 'lucide-react';
import { useGameDetail } from '@/hooks/useGames';
import { useUserStore } from '@/store/useUserStore';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameDetailSkeleton } from '@/components/ui/LoadingSkeleton';
import { GameImage } from '@/components/ui/GameImage';
import { RadarChart } from '@/components/ui/RadarChart';
import { getGenreCoreMetrics, METRIC_LABELS, cn } from '@/lib/utils';
import { METRIC_DESCRIPTIONS } from '@/lib/constants';
import { recordTasteAction, recordTasteActionBeacon } from '@/lib/api';
import { LoginPromptModal } from '@/components/ui/LoginPromptModal';

interface GameDetailProps {
  appId: number;
}

/**
 * Metric bar with hover tooltip.
 * 호버 툴팁이 포함된 지표 바.
 */
function MetricBar({ metricKey, value }: { metricKey: string; value: number }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const pct = Math.max(0, Math.min(100, (value / 10) * 100));
  const description = METRIC_DESCRIPTIONS[metricKey] || '';
  const barColor =
    value >= 8 ? 'bg-purple-600' :
    value >= 5 ? 'bg-blue-500' :
    'bg-zinc-400';

  return (
    <div
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] text-zinc-700 dark:text-zinc-300">
            {METRIC_LABELS[metricKey] || metricKey}
          </span>
          {description && (
            <span className="w-3.5 h-3.5 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400 text-[9px] flex items-center justify-center cursor-help">
              ?
            </span>
          )}
          {value >= 9 && (
            <span className="text-[9px] px-1 rounded bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300">
              탁월
            </span>
          )}
        </div>
        <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400">
          {value.toFixed(0)} / 10
        </span>
      </div>

      <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>

      {showTooltip && description && (
        <div className="absolute z-20 left-0 top-full mt-1 w-full px-3 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-[11px] rounded-lg shadow-lg leading-relaxed">
          {description}
        </div>
      )}
    </div>
  );
}

export function GameDetail({ appId }: GameDetailProps) {
  const { data: game, isLoading, error, refetch } = useGameDetail(appId);
  const favorites       = useUserStore(s => s.favorites);
  const toggleFavorite  = useUserStore(s => s.toggleFavorite);
  const isLoggedIn      = useUserStore(s => s.isLoggedIn);
  const ensureSessionId = useUserStore(s => s.ensureSessionId);

  const hasLoggedRef = useRef(false);
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);

  useEffect(() => {
    if (!appId || hasLoggedRef.current) return;
    const timer = setTimeout(() => {
      if (hasLoggedRef.current) return;
      hasLoggedRef.current = true;
      recordTasteAction({
        session_id:  ensureSessionId(),
        app_id:      appId,
        action_type: 'detail_view',
        context:     { referrer: document.referrer || '/' },
      });
    }, 100);
    return () => clearTimeout(timer);
  }, [appId, ensureSessionId]);

  const handleSteamClick = () => {
    recordTasteActionBeacon({
      session_id:  ensureSessionId(),
      app_id:      appId,
      action_type: 'steam_click',
      context:     {},
    });
  };

  if (isLoading) return <GameDetailSkeleton />;
  if (error) return <ErrorState error={error as Error} onRetry={() => refetch()} variant="page" />;
  if (!game) return <ErrorState type="not-found" title="게임 정보가 없어요" variant="page" />;

  const isFav = favorites.includes(appId);
  const coreMetrics = getGenreCoreMetrics(
    game.metrics as unknown as Record<string, number | boolean | null>,
    game.genres ?? '',
    6
  );
  const radarData = coreMetrics.map(({ key, value }) => ({ metric: key, value }));
  const genres    = game.genres?.split(',').map(g => g.trim()).filter(Boolean) ?? [];
  const primaryGenre = genres[0] || '게임';

  return (
    <article className="w-full">
      {/* Hero */}
      <div className="w-full rounded-xl overflow-hidden bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
        {/* 헤더 이미지: 원본 비율로 늘리면 1080p에서 화면을 다 먹음 - 높이를 캡하고 object-cover로 크롭 */}
        <div className="relative w-full h-52 md:h-64 lg:h-72 bg-zinc-200 dark:bg-zinc-800">
          <GameImage appId={appId} name={game.name} fallback={game.header_image} size="hero" priority />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-zinc-100 dark:from-zinc-900 to-transparent" />
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
              onClick={handleSteamClick}
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
              onClick={() => {
                if (!isLoggedIn) {
                  setShowLoginPrompt(true);
                  return;
                }
                toggleFavorite(appId);
              }}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-2 rounded-md border text-[12px] transition-colors',
                isFav
                  ? 'border-red-200 text-red-600 bg-red-50 hover:bg-red-100 dark:bg-red-950/20 dark:border-red-900'
                  : 'border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800'
              )}
            >
              <Heart className={cn('w-3.5 h-3.5', isFav && 'fill-red-500 text-red-500')} />
              찜
            </button>
          </div>
        </div>
      </div>

      {/* 레이더 + 세부지표 */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="flex flex-col items-center justify-center bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <div className="self-start mb-1">
            <h3 className="text-[12px] font-medium text-zinc-500 dark:text-zinc-400">
              {primaryGenre} 핵심 지표
            </h3>
            <p className="text-[10px] text-zinc-400">
              이 게임이 어떤 {primaryGenre}인지 보여줍니다
            </p>
          </div>
          <RadarChart data={radarData} size={300} />
        </div>

        <div className="flex flex-col gap-3 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <h3 className="text-[12px] font-medium text-zinc-500 dark:text-zinc-400 mb-1">
            {primaryGenre} 평가
            <span className="ml-1.5 text-[10px] text-zinc-400">
              (지표에 마우스를 올리면 설명이 표시됩니다)
            </span>
          </h3>
          {coreMetrics.map(({ key, value }) => (
            <MetricBar key={key} metricKey={key} value={value} />
          ))}
        </div>
      </div>

      <LoginPromptModal
        open={showLoginPrompt}
        message="찜하기는 로그인 후 이용할 수 있어요."
        onClose={() => setShowLoginPrompt(false)}
      />
    </article>
  );
}
