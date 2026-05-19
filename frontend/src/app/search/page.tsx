/**
 * Preference analysis page
 * 취향 분석 페이지 - 슬라이더로 선호도 조정 후 추천
 */
'use client';

import { useState } from 'react';
import * as Slider from '@radix-ui/react-slider';
import { GameGrid } from '@/components/game/GameGrid';
import { useRecommendByPreference } from '@/hooks/useRecommend';
import { METRIC_LABELS, cn } from '@/lib/utils';
import type { RecommendedGame } from '@/types/game';

const INITIAL_PREFS: Record<string, number> = {
  narrative_depth: 5,
  strategic_depth: 5,
  cozy_factor: 5,
  horror_factor: 3,
  action_pacing: 5,
  exploration_reward: 5,
  replay_value: 5,
  art_style_uniqueness: 5,
}

export default function SearchPage() {
  const [prefs, setPrefs] = useState<Record<string, number>>(INITIAL_PREFS);
  const [results, setResults] = useState<RecommendedGame[]>([]);
  const mutation = useRecommendByPreference();

  const setPref = (key: string, value: number) => {
    setPrefs((p) => ({ ...p, [key]: value }));
  };

  const handleSubmit = () => {
    mutation.mutate(
      { preferences: prefs, count: 12 },
      { onSuccess: (res) => setResults(res.recommendations ?? []) }
    );
  };

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-xl font-semibold">취향 분석</h1>
        <p className="text-sm text-zinc-500 mt-1">
          슬라이더로 당신이 중요하게 생각하는 요소를 조정해보세요. (0~10)
        </p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(prefs).map(([key, value]) => (
          <div
            key={key}
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] text-zinc-700 dark:text-zinc-300">
                {METRIC_LABELS[key] || key}
              </span>
              <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400">
                {value.toFixed(1)}
              </span>
            </div>
            <Slider.Root
              className="relative flex items-center select-none touch-none w-full h-5"
              min={0}
              max={10}
              step={0.5}
              value={[value]}
              onValueChange={(v) => setPref(key, v[0])}
            >
              <Slider.Track className="bg-zinc-200 dark:bg-zinc-800 relative grow rounded-full h-1">
                <Slider.Range className="absolute bg-purple-600 rounded-full h-full" />
              </Slider.Track>
              <Slider.Thumb className="block w-4 h-4 bg-white border-2 border-purple-600 rounded-full shadow focus:outline-none focus:ring-2 focus:ring-purple-400" />
            </Slider.Root>
          </div>
        ))}
      </section>

      <div className="flex justify-center">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={mutation.isPending}
          className={cn(
            'px-6 py-2.5 rounded-md bg-purple-600 text-white text-[13px] font-medium',
            'hover:bg-purple-700 transition-colors disabled:opacity-60'
          )}
        >
          {mutation.isPending ? '분석 중...' : '✦ 추천 받기'}
        </button>
      </div>

      {results.length > 0 && (
        <section>
          <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
            당신의 취향에 맞는 게임
          </h2>
          <GameGrid games={results} />
        </section>
      )}
    </div>
  );
}