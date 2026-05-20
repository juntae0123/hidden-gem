/**
 * Home page
 * 메인 페이지 - 검색바 + AI 추천 그리드
 */
'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { SearchBar } from '@/components/ui/SearchBar';
import { GameGrid } from '@/components/game/GameGrid';
import { useRecommendByPreference } from '@/hooks/useRecommend';
import { semanticSearchGames } from '@/lib/api';
import type { RecommendedGame } from '@/types/game';

// 초기 AI 추천용 기본 선호도 벡터 / Default preference vector for cold start
const DEFAULT_PREFS: Record<string, number> = {
  narrative_depth: 8,
  lore_richness: 7,
  art_style_uniqueness: 7,
  replay_value: 6,
  exploration_reward: 7,
  soundtrack_impact: 7,
};

/**
 * Home page component
 * 메인 페이지 - 자연어 시맨틱 검색 + AI 초기 추천
 */
export default function HomePage() {
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const recommendMutation = useRecommendByPreference();
  const [aiGames, setAiGames] = useState<RecommendedGame[]>([]);

  // 시맨틱 검색 쿼리 / Semantic search query
  const {
    data: searchResult,
    isLoading: searching,
    isFetching,
  } = useQuery({
    queryKey: ['semantic-search', submittedQuery],
    queryFn: () => semanticSearchGames(submittedQuery, 12),
    enabled: submittedQuery.trim().length > 0,
    staleTime: 1000 * 60 * 2,
  });

  // 초기 AI 추천 로드 / Load initial AI recommendations on mount
  useEffect(() => {
    recommendMutation.mutate(
      { preferences: DEFAULT_PREFS, count: 9 },
      { onSuccess: (res) => setAiGames(res.recommendations ?? []) }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 검색 제출 핸들러 / Handle search submit
  const handleSubmit = (value: string) => {
    if (value.trim()) {
      setSubmittedQuery(value.trim());
    }
  };

  const showSearch = submittedQuery.trim().length > 0;
  const searchGames = searchResult?.recommendations ?? [];
  const displayGames = showSearch ? searchGames : aiGames;
  const isLoading = showSearch ? (searching || isFetching) : recommendMutation.isPending;

  return (
    <div className="flex flex-col gap-12">
      {/* Hero / 검색 영역 */}
      <section className="pt-8 pb-2 flex flex-col items-center text-center">
        <div className="mb-6">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            <span className="text-purple-600">✦</span> Hidden Gem
          </h1>
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
            당신의 취향에 맞는 게임을 찾아드려요
          </p>
        </div>
        <div className="w-full max-w-2xl">
          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={handleSubmit}
          />
        </div>
      </section>

      {/* 결과 그리드 / Results grid */}
      <section>
        <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
          {showSearch
            ? `"${submittedQuery}" 검색 결과 ${searchGames.length}개`
            : `오늘의 AI 추천 · ${aiGames[0]?.match_reasons?.[0]?.replace('✓ ', '').replace(' 높음', ' 높은 게임').replace(/ \([^)]*\)/g, '') ?? '취향 분석 기반'}`}
        </h2>
        <GameGrid
          games={displayGames}
          loading={isLoading}
          emptyMessage={
            showSearch ? '검색 결과가 없어요. 다른 표현으로 검색해보세요.' : '추천을 불러올 수 없어요.'
          }
        />
      </section>
    </div>
  );
}