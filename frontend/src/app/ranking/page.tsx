/**
 * Ranking page — using useQuery hooks.
 * 랭킹 페이지 — useQuery 전환.
 *
 * v1 → v2:
 *   - useEffect+mutation → useRecommendByGenre (useQuery, 30분 캐싱)
 *   - 에러 → ErrorState
 *   - 로딩 → RankingListSkeleton
 */
'use client';

import { useState } from 'react';
import { RankingList } from '@/components/game/RankingList';
import { ErrorState } from '@/components/ui/ErrorState';
import { RankingListSkeleton } from '@/components/ui/LoadingSkeleton';
import { useRecommendByGenre } from '@/hooks/useRecommend';
import { GENRES } from '@/lib/constants';
import { cn } from '@/lib/utils';

type Tab = 'all' | 'genre' | 'mine';

const GENRE_PREFS: Record<string, Record<string, number>> = {
  RPG:       { narrative_depth: 9, lore_richness: 9, choice_consequence: 8, growth_reward: 8 },
  액션:      { action_pacing: 9, reflex_demand: 8, replay_value: 7 },
  전략:      { strategic_depth: 10, management_complexity: 8, replay_value: 9 },
  시뮬레이션: { management_complexity: 9, freedom_level: 8, replay_value: 8 },
  어드벤처:  { exploration_reward: 9, narrative_depth: 8, environmental_storytelling: 8 },
  인디:      { art_style_uniqueness: 9, narrative_depth: 7, audio_design: 7 },
  로그라이크: { replay_value: 10, rng_dependency: 7, learning_curve: 8 },
  공포:      { horror_factor: 9, melancholy: 7, dark_fantasy_vibe: 7 },
  퍼즐:      { puzzle_complexity: 9, strategic_depth: 7 },
};

const ALL_PREFS: Record<string, number> = {
  narrative_depth: 8, art_style_uniqueness: 8,
  replay_value: 7, lore_richness: 7, audio_design: 7,
};

export default function RankingPage() {
  const [tab, setTab]   = useState<Tab>('all');
  const [genre, setGenre] = useState<string>('RPG');

  const activePrefs =
    tab === 'all'   ? ALL_PREFS :
    tab === 'genre' ? (GENRE_PREFS[genre] ?? ALL_PREFS) :
    null;

  const { data, isLoading, error, refetch } = useRecommendByGenre(activePrefs, 10);
  const items = data?.recommendations ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">랭킹</h1>
        <p className="text-sm text-zinc-500 mt-1">gem potential 기준 Top 10</p>
      </header>

      {/* 탭 */}
      <div className="flex items-center gap-1 border-b border-zinc-200 dark:border-zinc-800">
        {([
          { key: 'all',   label: '전체' },
          { key: 'genre', label: '장르별' },
          { key: 'mine',  label: '내 취향 기반' },
        ] as { key: Tab; label: string }[]).map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              'px-3 py-2 text-[13px] -mb-px border-b-2',
              tab === t.key
                ? 'border-purple-600 text-purple-700 dark:text-purple-300'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 장르 칩 */}
      {tab === 'genre' && (
        <div className="flex flex-wrap gap-2">
          {GENRES.filter(g => g !== '전체').map(g => (
            <button
              key={g}
              type="button"
              onClick={() => setGenre(g)}
              className={cn(
                'px-3 py-1.5 rounded-full text-[12px] border',
                genre === g
                  ? 'bg-purple-600/10 border-purple-500 text-purple-700 dark:text-purple-300'
                  : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-purple-400'
              )}
            >
              {g}
            </button>
          ))}
        </div>
      )}

      {/* 로그인 필요 */}
      {tab === 'mine' && (
        <div className="rounded-xl p-6 text-center bg-purple-600/[0.04] border border-purple-600/30">
          <div className="text-purple-700 dark:text-purple-300 text-sm font-medium">Steam 로그인이 필요해요</div>
          <p className="mt-1 text-[12px] text-zinc-500">로그인하면 당신의 라이브러리 기반으로 맞춤 랭킹을 보여드려요.</p>
        </div>
      )}

      {/* 랭킹 리스트 */}
      {tab !== 'mine' && (
        <>
          {error && (
            <ErrorState error={error as Error} onRetry={() => refetch()} variant="inline" />
          )}
          {isLoading && !error && <RankingListSkeleton count={10} />}
          {!isLoading && !error && <RankingList items={items} />}
        </>
      )}
    </div>
  );
}
