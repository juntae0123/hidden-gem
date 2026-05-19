/**
 * Ranking page
 * 랭킹 페이지 - 전체 / 장르별 / 내 취향
 */
'use client';

import { useState, useEffect } from 'react';
import { RankingList } from '@/components/game/RankingList';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useRecommendByPreference } from '@/hooks/useRecommend';
import { GENRES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { RecommendedGame } from '@/types/game';

type Tab = 'all' | 'genre' | 'mine';

// 실제 49개 지표명 기반 장르별 선호도 / Genre prefs using real metric fields
const GENRE_PREFS: Record<string, Record<string, number>> = {
  RPG: { narrative_depth: 9, lore_richness: 9, choice_consequence: 8, growth_reward: 8 },
  액션: { action_pacing: 9, reflex_demand: 8, replay_value: 7 },
  전략: { strategic_depth: 10, management_complexity: 8, replay_value: 9 },
  시뮬레이션: { management_complexity: 9, freedom_level: 8, replay_value: 8 },
  어드벤처: { exploration_reward: 9, narrative_depth: 8, environmental_storytelling: 8 },
  인디: { art_style_uniqueness: 9, narrative_depth: 7, audio_design: 7 },
  로그라이크: { replay_value: 10, rng_dependency: 7, has_permadeath: 1 },
  공포: { horror_factor: 9, melancholy: 7, dark_fantasy_vibe: 7 },
  퍼즐: { puzzle_complexity: 9, strategic_depth: 7 },
}

const ALL_PREFS: Record<string, number> = {
  narrative_depth: 8,
  art_style_uniqueness: 8,
  replay_value: 7,
  lore_richness: 7,
  audio_design: 7,
}

export default function RankingPage() {
  const [tab, setTab] = useState<Tab>('all');
  const [genre, setGenre] = useState<string>('RPG');
  const [items, setItems] = useState<RecommendedGame[]>([]);
  const mutation = useRecommendByPreference();

  useEffect(() => {
    if (tab === 'mine') {
      setItems([]);
      return;
    }
    const prefs = tab === 'all' ? ALL_PREFS : (GENRE_PREFS[genre] ?? ALL_PREFS);
    mutation.mutate(
      { preferences: prefs, count: 10 },
      { onSuccess: (res) => setItems(res.recommendations ?? []) }
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, genre]);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">랭킹</h1>
        <p className="text-sm text-zinc-500 mt-1">gem potential 기준 Top 10</p>
      </header>

      {/* 탭 / Tabs */}
      <div className="flex items-center gap-1 border-b border-zinc-200 dark:border-zinc-800">
        {([
          { key: 'all', label: '전체' },
          { key: 'genre', label: '장르별' },
          { key: 'mine', label: '내 취향 기반' },
        ] as { key: Tab; label: string }[]).map((t) => (
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

      {/* 장르 칩 / Genre chips */}
      {tab === 'genre' && (
        <div className="flex flex-wrap gap-2">
          {GENRES.filter(g => g !== '전체').map((g) => (
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

      {/* 내 취향 기반 안내 / Login required */}
      {tab === 'mine' && (
        <div className="rounded-xl p-6 text-center bg-purple-600/[0.04] border border-purple-600/30">
          <div className="text-purple-700 dark:text-purple-300 text-sm font-medium">
            Steam 로그인이 필요해요
          </div>
          <p className="mt-1 text-[12px] text-zinc-500">
            로그인하면 당신의 라이브러리 기반으로 맞춤 랭킹을 보여드려요.
          </p>
        </div>
      )}

      {/* 랭킹 리스트 / Ranking list */}
      {tab !== 'mine' && (
        mutation.isPending
          ? <LoadingSpinner label="랭킹 계산 중..." />
          : <RankingList items={items} />
      )}
    </div>
  );
}