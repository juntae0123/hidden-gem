/**
 * Preference analysis page — 49 metrics with categories and tooltips.
 * 취향 분석 페이지.
 *
 * v3: ensureSessionId 사용 (SSR-safe)
 */
'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import * as Slider from '@radix-ui/react-slider';
import { GameGrid } from '@/components/game/GameGrid';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameGridSkeleton } from '@/components/ui/LoadingSkeleton';
import { useRecommendByPreference } from '@/hooks/useRecommend';
import { METRIC_LABELS, cn } from '@/lib/utils';
import { METRIC_DESCRIPTIONS, METRIC_CATEGORIES_KO } from '@/lib/constants';
import { recordTasteAction } from '@/lib/api';
import { useUserStore } from '@/store/useUserStore';
import { DnaCard } from '@/components/ui/DnaCard';

const buildInitialPrefs = (): Record<string, number> => {
  const prefs: Record<string, number> = {};
  Object.values(METRIC_CATEGORIES_KO).forEach(({ metrics }) => {
    metrics.forEach((m) => { prefs[m] = 5.0; });
  });
  return prefs;
};

function MetricSlider({
  metricKey, value, onChange,
}: {
  metricKey: string;
  value: number;
  onChange: (key: string, val: number) => void;
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const label       = METRIC_LABELS[metricKey] || metricKey;
  const description = METRIC_DESCRIPTIONS[metricKey] || '';

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 relative">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] text-zinc-700 dark:text-zinc-300 font-medium">{label}</span>
          <button
            type="button"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
            aria-label={`${label} 설명 보기`}
            className="w-4 h-4 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400 text-[10px] flex items-center justify-center hover:bg-purple-100 hover:text-purple-600 transition-colors"
          >
            ?
          </button>
        </div>
        <span className="text-[12px] font-mono text-purple-600 dark:text-purple-400 font-medium">
          {value.toFixed(1)} / 10
        </span>
      </div>

      {showTooltip && description && (
        <div className="absolute z-20 left-0 top-full mt-1 w-full px-3 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-[11px] rounded-lg shadow-lg leading-relaxed">
          {description}
        </div>
      )}

      <Slider.Root
        className="relative flex items-center select-none touch-none w-full h-5"
        min={0} max={10} step={0.5}
        value={[value]}
        onValueChange={(v) => onChange(metricKey, v[0])}
      >
        <Slider.Track className="bg-zinc-200 dark:bg-zinc-800 relative grow rounded-full h-1.5">
          <Slider.Range className="absolute bg-purple-600 rounded-full h-full" />
        </Slider.Track>
        <Slider.Thumb
          className="block w-4 h-4 bg-white border-2 border-purple-600 rounded-full shadow focus:outline-none focus:ring-2 focus:ring-purple-400 cursor-pointer"
          aria-label={label}
        />
      </Slider.Root>
    </div>
  );
}

export default function SearchPage() {
  const [prefs, setPrefs]               = useState<Record<string, number>>(buildInitialPrefs);
  const [activeCategory, setActiveCategory] = useState<string>('vibe');
  const mutation        = useRecommendByPreference();
  const ensureSessionId = useUserStore(s => s.ensureSessionId);
  const swipeApplied    = useRef(false);

  // 스와이프 온보딩에서 넘어온 초기 취향 적용 + 즉시 추천
  useEffect(() => {
    if (swipeApplied.current) return;
    swipeApplied.current = true;
    let raw: string | null = null;
    try {
      raw = sessionStorage.getItem('hg_swipe_prefs');
      if (raw) sessionStorage.removeItem('hg_swipe_prefs');
    } catch { return; }
    if (!raw) return;
    try {
      const swipePrefs = JSON.parse(raw) as Record<string, number>;
      const merged = { ...buildInitialPrefs(), ...swipePrefs };
      const nonNeutral = Object.fromEntries(
        Object.entries(merged).filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
      );
      // effect 내 동기 setState 회피 (react-hooks/set-state-in-effect)
      queueMicrotask(() => {
        setPrefs(merged);
        mutation.mutate({ preferences: Object.keys(nonNeutral).length ? nonNeutral : merged, count: 12 });
      });
    } catch { /* 파싱 실패 시 기본 슬라이더로 */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const results       = mutation.data?.recommendations ?? [];
  const categories    = Object.entries(METRIC_CATEGORIES_KO);
  const adjustedCount = Object.entries(prefs).filter(([, v]) => Math.abs(v - 5.0) >= 0.5).length;

  const setPref = (key: string, value: number) => {
    setPrefs((p) => ({ ...p, [key]: value }));
  };

  const handleSubmit = () => {
    const nonNeutral = Object.fromEntries(
      Object.entries(prefs).filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
    );
    const toSend = Object.keys(nonNeutral).length > 0 ? nonNeutral : prefs;

    recordTasteAction({
      session_id:  ensureSessionId(),
      action_type: 'search',
      context: {
        adjusted_metrics: Object.keys(nonNeutral),
        adjusted_count:   Object.keys(nonNeutral).length,
        referrer:         '/search',
      },
    });

    mutation.mutate({ preferences: toSend, count: 12 });
  };

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-xl font-semibold">취향 분석</h1>
        <p className="text-sm text-zinc-500 mt-1">
          각 지표를 조정해 당신만의 이상적인 게임을 찾아보세요.{' '}
          <span className="text-purple-600">?</span> 버튼을 누르면 지표 설명을 볼 수 있어요.
        </p>
        <Link
          href="/onboarding/swipe"
          className="mt-3 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-purple-600/10 border border-purple-300 dark:border-purple-800 text-purple-700 dark:text-purple-300 text-sm font-medium hover:bg-purple-600/20 transition-colors"
        >
          슬라이더가 낯설다면 — 카드 스와이프로 취향 잡기 →
        </Link>
      </header>

      <div className="flex flex-wrap gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-3">
        {categories.map(([key, { label }]) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveCategory(key)}
            className={cn(
              'px-3 py-1.5 rounded-full text-[12px] border transition-all',
              activeCategory === key
                ? 'bg-purple-600/10 border-purple-500 text-purple-700 dark:text-purple-300 font-medium'
                : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-purple-400'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {categories.map(([catKey, { metrics }]) => (
        <div
          key={catKey}
          className={cn('grid grid-cols-1 md:grid-cols-2 gap-3', activeCategory !== catKey && 'hidden')}
        >
          {metrics.map((metricKey) => (
            <MetricSlider
              key={metricKey}
              metricKey={metricKey}
              value={prefs[metricKey] ?? 5.0}
              onChange={setPref}
            />
          ))}
        </div>
      ))}

      {adjustedCount > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-[12px] text-zinc-500">조정된 지표 ({adjustedCount}개):</span>
          {Object.entries(prefs)
            .filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
            .map(([key, val]) => (
              <span
                key={key}
                className="px-2 py-0.5 rounded-full text-[11px] bg-purple-600/10 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800"
              >
                {METRIC_LABELS[key]} {val > 5 ? '↑' : '↓'} {val.toFixed(1)}
              </span>
            ))}
        </div>
      )}

      <div className="flex justify-center">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={mutation.isPending}
          className={cn(
            'px-8 py-3 rounded-xl bg-purple-600 text-white text-[14px] font-medium',
            'hover:bg-purple-700 transition-colors disabled:opacity-60 shadow-sm hover:shadow-md'
          )}
        >
          {mutation.isPending ? '분석 중...' : '✦ 내 취향에 맞는 게임 찾기'}
        </button>
      </div>

      <section>
        {mutation.error && (
          <ErrorState error={mutation.error as Error} onRetry={handleSubmit} variant="inline" title="추천을 가져오지 못했어요" />
        )}
        {mutation.isPending && !mutation.error && (
          <>
            <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">당신의 취향을 분석 중...</h2>
            <GameGridSkeleton count={12} />
          </>
        )}
        {!mutation.isPending && !mutation.error && mutation.isSuccess && results.length === 0 && (
          <ErrorState type="not-found" variant="inline" title="조건에 맞는 게임이 없어요" description="지표 조건을 조금 완화해보세요" />
        )}
        {!mutation.isPending && !mutation.error && results.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300">
                당신의 취향에 맞는 게임 {results.length}개
              </h2>
              <DnaCard prefs={prefs} games={results} />
            </div>
            <GameGrid games={results} />
          </>
        )}
      </section>
    </div>
  );
}
