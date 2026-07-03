// src/app/page.tsx

'use client';

import { Suspense, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';

import { SearchBar } from '@/components/ui/SearchBar';
import { GameGrid } from '@/components/game/GameGrid';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameGridSkeleton } from '@/components/ui/LoadingSkeleton';
import { useDefaultRecommendations, DEFAULT_THEME_LABEL, useRecommendByVibe, useVibes } from '@/hooks/useRecommend';
import { semanticSearchGames, recordTasteAction } from '@/lib/api';
import { VibeChips } from '@/components/ui/VibeChips';
import { useUserStore } from '@/store/useUserStore';

/**
 * Inner home content using useSearchParams.
 * Korean: useSearchParams를 쓰는 실제 본문. Suspense로 감싸기 위해 분리.
 */
function HomeContent() {
  const router        = useRouter();
  const searchParams  = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const ensureSessionId = useUserStore(s => s.ensureSessionId);

  const submittedQuery = searchParams.get('q') ?? '';
  const [inputValue, setInputValue] = useState(submittedQuery);

  // Vibe 칩 선택 상태
  const [selectedVibe, setSelectedVibe] = useState<string | null>(null);

  // 시맨틱 검색
  const {
    data:    searchResult,
    isLoading: searching,
    error:   searchError,
    refetch: refetchSearch,
  } = useQuery({
    queryKey: ['semantic-search', submittedQuery],
    queryFn:  () => semanticSearchGames(submittedQuery, 12),
    enabled:  submittedQuery.trim().length > 0,
    staleTime: 1000 * 60 * 5,
    gcTime:    1000 * 60 * 30,
    retry: 1,
  });

  // 기본 AI 추천 (오늘의 테마)
  const {
    data:    aiResult,
    isLoading: aiLoading,
    error:   aiError,
    refetch: refetchAI,
  } = useDefaultRecommendations(9);

  // Vibe 칩 추천
  const {
    data:    vibeResult,
    isLoading: vibeLoading,
    error:   vibeError,
    refetch: refetchVibe,
  } = useRecommendByVibe(selectedVibe, 12);

  // 검색 제출
  const handleSubmit = (value: string) => {
    const trimmed = value.trim();

    if (trimmed) {
      setSelectedVibe(null); // 검색하면 칩 선택 해제
      recordTasteAction({
        session_id:  ensureSessionId(),
        action_type: 'search',
        context: {
          query:        trimmed,
          query_length: trimmed.length,
          referrer:     '/',
        },
      });
    }

    startTransition(() => {
      router.push(trimmed ? `/?q=${encodeURIComponent(trimmed)}` : '/');
    });
  };

  // 칩 클릭
  const handleVibeSelect = (vibeKey: string | null) => {
    setSelectedVibe(vibeKey);
    if (vibeKey) {
      recordTasteAction({
        session_id:  ensureSessionId(),
        action_type: 'search',
        context: { query: `vibe:${vibeKey}`, referrer: '/' },
      });
    }
  };

  // 표시 우선순위: 검색 > 칩 > 기본추천
  const showSearch = submittedQuery.trim().length > 0;
  const showVibe   = !showSearch && selectedVibe !== null;

  const searchGames = searchResult?.recommendations ?? [];
  const vibeGames   = vibeResult?.recommendations ?? [];
  const aiGames     = aiResult?.recommendations ?? [];

  const displayGames = showSearch ? searchGames : showVibe ? vibeGames : aiGames;
  const isLoading    = showSearch
    ? (searching || isPending)
    : showVibe ? vibeLoading : aiLoading;
  const currentError = showSearch ? searchError : showVibe ? vibeError : aiError;

  // 선택된 vibe 라벨 (헤더 표시용)
  const { data: vibes } = useVibes();
  const selectedVibeLabel = vibes?.find(v => v.key === selectedVibe)?.label ?? '';

  return (
    <div className="flex flex-col gap-12">
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
          <SearchBar value={inputValue} onChange={setInputValue} onSubmit={handleSubmit} />
        </div>
      </section>

      {/* Vibe 칩 — 검색 중이 아닐 때만 노출 */}
      {!showSearch && (
        <section className="-mt-6">
          <VibeChips selected={selectedVibe} onSelect={handleVibeSelect} />
        </section>
      )}

      <section>
        <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
          {showSearch
            ? `"${submittedQuery}" 검색 결과 ${searchGames.length}개`
            : showVibe
              ? `${selectedVibeLabel} 추천 ${vibeGames.length}개`
              : `오늘의 AI 추천 · ${DEFAULT_THEME_LABEL} 게임`}
        </h2>

        {currentError && (
          <ErrorState
            error={currentError as Error}
            onRetry={() => showSearch ? refetchSearch() : showVibe ? refetchVibe() : refetchAI()}
            variant="page"
          />
        )}

        {isLoading && !currentError && <GameGridSkeleton count={9} />}

        {!isLoading && !currentError && displayGames.length === 0 && (
          <ErrorState
            type="not-found"
            variant="page"
            title={showSearch ? '검색 결과가 없어요' : '추천을 불러올 수 없어요'}
            description={showSearch ? '다른 표현으로 검색해보세요' : '잠시 후 다시 시도해주세요'}
            onRetry={showSearch ? undefined : showVibe ? () => refetchVibe() : () => refetchAI()}
          />
        )}

        {!isLoading && !currentError && displayGames.length > 0 && (
          <GameGrid games={displayGames} />
        )}
      </section>
    </div>
  );
}
/**
 * Home page wrapper with Suspense boundary.
 * Korean: useSearchParams가 prerender 시 Suspense를 요구해서 바깥에서 감쌈.
 */
export default function HomePage() {
  return (
    <Suspense fallback={<GameGridSkeleton count={9} />}>
      <HomeContent />
    </Suspense>
  );
}