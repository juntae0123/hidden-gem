/**
 * Preference analysis page - full 49 metrics with categories and tooltips
 * 취향 분석 페이지 - 49개 전체 지표, 카테고리별 분류, 툴팁 설명
 */
'use client';

import { useState } from 'react';
import * as Slider from '@radix-ui/react-slider';
import { GameGrid } from '@/components/game/GameGrid';
import { useRecommendByPreference } from '@/hooks/useRecommend';
import { METRIC_LABELS, cn } from '@/lib/utils';
import { METRIC_DESCRIPTIONS, METRIC_CATEGORIES_KO } from '@/lib/constants';
import type { RecommendedGame } from '@/types/game';

// 카테고리별 초기값 (모두 5.0 중립) / Initial values for all metrics (neutral 5.0)
const buildInitialPrefs = (): Record<string, number> => {
  const prefs: Record<string, number> = {};
  Object.values(METRIC_CATEGORIES_KO).forEach(({ metrics }) => {
    metrics.forEach((m) => {
      prefs[m] = 5.0;
    });
  });
  return prefs;
};

/**
 * Single metric slider with tooltip
 * 툴팁이 포함된 단일 지표 슬라이더
 */
function MetricSlider({
  metricKey,
  value,
  onChange,
}: {
  metricKey: string;
  value: number;
  onChange: (key: string, val: number) => void;
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const label = METRIC_LABELS[metricKey] || metricKey;
  const description = METRIC_DESCRIPTIONS[metricKey] || '';

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 relative">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] text-zinc-700 dark:text-zinc-300 font-medium">
            {label}
          </span>
          {/* 툴팁 버튼 / Tooltip trigger */}
          <button
            type="button"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
            className="w-4 h-4 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400 text-[10px] flex items-center justify-center hover:bg-purple-100 hover:text-purple-600 transition-colors"
          >
            ?
          </button>
        </div>
        <span className="text-[12px] font-mono text-purple-600 dark:text-purple-400 font-medium">
          {value.toFixed(1)} / 10
        </span>
      </div>

      {/* 툴팁 / Tooltip */}
      {showTooltip && description && (
        <div className="absolute z-20 left-0 top-full mt-1 w-full px-3 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-[11px] rounded-lg shadow-lg leading-relaxed">
          {description}
        </div>
      )}

      {/* 슬라이더 / Slider */}
      <Slider.Root
        className="relative flex items-center select-none touch-none w-full h-5"
        min={0}
        max={10}
        step={0.5}
        value={[value]}
        onValueChange={(v) => onChange(metricKey, v[0])}
      >
        <Slider.Track className="bg-zinc-200 dark:bg-zinc-800 relative grow rounded-full h-1.5">
          <Slider.Range className="absolute bg-purple-600 rounded-full h-full" />
        </Slider.Track>
        <Slider.Thumb className="block w-4 h-4 bg-white border-2 border-purple-600 rounded-full shadow focus:outline-none focus:ring-2 focus:ring-purple-400 cursor-pointer" />
      </Slider.Root>
    </div>
  );
}

/**
 * Preference analysis page component
 * 취향 분석 페이지 - 49개 지표 카테고리별 슬라이더 + 추천 결과
 */
export default function SearchPage() {
  const [prefs, setPrefs] = useState<Record<string, number>>(buildInitialPrefs);
  const [results, setResults] = useState<RecommendedGame[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>('vibe');
  const mutation = useRecommendByPreference();

  const setPref = (key: string, value: number) => {
    setPrefs((p) => ({ ...p, [key]: value }));
  };

  // 중립값(5.0)과 다른 지표만 preferences로 전송 / Only send non-neutral metrics
  const handleSubmit = () => {
    const nonNeutral = Object.fromEntries(
      Object.entries(prefs).filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
    );
    // 모두 중립이면 전체 전송 / If all neutral, send all
    const toSend = Object.keys(nonNeutral).length > 0 ? nonNeutral : prefs;

    mutation.mutate(
      { preferences: toSend, count: 12 },
      { onSuccess: (res) => setResults(res.recommendations ?? []) }
    );
  };

  const categories = Object.entries(METRIC_CATEGORIES_KO);

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-xl font-semibold">취향 분석</h1>
        <p className="text-sm text-zinc-500 mt-1">
          각 지표를 조정해 당신만의 이상적인 게임을 찾아보세요. <span className="text-purple-600">?</span> 버튼을 누르면 지표 설명을 볼 수 있어요.
        </p>
      </header>

      {/* 카테고리 탭 / Category tabs */}
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

      {/* 슬라이더 그리드 / Slider grid */}
      {categories.map(([catKey, { metrics }]) => (
        <div
          key={catKey}
          className={cn(
            'grid grid-cols-1 md:grid-cols-2 gap-3',
            activeCategory !== catKey && 'hidden'
          )}
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

      {/* 조정된 지표 요약 / Summary of adjusted metrics */}
      {Object.entries(prefs).filter(([, v]) => Math.abs(v - 5.0) >= 0.5).length > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-[12px] text-zinc-500">조정된 지표:</span>
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

      {/* 추천 버튼 / Submit button */}
      <div className="flex justify-center">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={mutation.isPending}
          className={cn(
            'px-8 py-3 rounded-xl bg-purple-600 text-white text-[14px] font-medium',
            'hover:bg-purple-700 transition-colors disabled:opacity-60',
            'shadow-sm hover:shadow-md'
          )}
        >
          {mutation.isPending ? '분석 중...' : '✦ 내 취향에 맞는 게임 찾기'}
        </button>
      </div>

      {/* 추천 결과 / Results */}
      {results.length > 0 && (
        <section>
          <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
            당신의 취향에 맞는 게임 {results.length}개
          </h2>
          <GameGrid games={results} />
        </section>
      )}
    </div>
  );
}