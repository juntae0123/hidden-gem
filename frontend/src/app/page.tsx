/**
 * Home page
 * 메인 페이지 - 검색바 + AI 추천 그리드
 */
'use client';

import { useState, useEffect } from 'react';
import { SearchBar } from '@/components/ui/SearchBar';
import { GameGrid } from '@/components/game/GameGrid';
import { useSearch } from '@/hooks/useSearch';
import { useRecommendByPreference } from '@/hooks/useRecommend';
import type { RecommendedGame } from '@/types/game';

const DEFAULT_PREFS: Record<string, number> = {
  narrative_depth: 8,
  lore_richness: 7,
  art_style_uniqueness: 7,
  replay_value: 6,
  exploration_reward: 7,
  soundtrack_impact: 7,
}

export default function HomePage() {
  const [query, setQuery] = useState('');
  const { data: searchResults, isLoading: searching } = useSearch(query);
  const recommendMutation = useRecommendByPreference();
  const [aiGames, setAiGames] = useState<RecommendedGame[]>([]);

  useEffect(() => {
    recommendMutation.mutate(
      { preferences: DEFAULT_PREFS, count: 9 },
      { onSuccess: (res) => setAiGames(res.recommendations ?? []) }
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const showSearch = query.trim().length > 0;
  const displayGames = (showSearch ? searchResults : aiGames) ?? [];

  return (
    <div className="flex flex-col gap-12">
      <section className="pt-8 pb-2 flex flex-col items-center text-center">
        <div className="mb-6">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
            <span className="text-purple-600">✦</span> 숨겨진 명작을 찾아드려요
          </h1>
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
            자연어로 검색하고, AI가 당신의 취향에 맞는 인디게임을 추천합니다.
          </p>
        </div>
        <div className="w-full max-w-2xl">
          <SearchBar value={query} onChange={setQuery} />
        </div>
      </section>

      <section>
        <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
          {showSearch ? `"${query}" 검색 결과` : '오늘의 AI 추천'}
        </h2>
        <GameGrid
          games={displayGames as RecommendedGame[]}
          loading={showSearch ? searching : recommendMutation.isPending}
          emptyMessage={showSearch ? '검색 결과가 없어요.' : '추천을 불러올 수 없어요.'}
        />
      </section>
    </div>
  );
}
