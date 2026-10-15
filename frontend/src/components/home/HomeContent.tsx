/**
 * Home interactive content — 검색창·Vibe 칩·추천 그리드 (client).
 * 홈 본문 중 상호작용 부분. app/page.tsx(서버)에서 옮겨 왔다 (SEO 2026-10-14).
 *
 * 왜 옮겼나: useSearchParams 를 쓰는 컴포넌트는 정적 렌더 때 가장 가까운 Suspense 까지
 * 클라이언트 렌더로 밀려난다. 히어로(h1)까지 이 안에 있어서 크롤러가 받은 홈 HTML 에는
 * 스켈레톤만 있었다. 히어로는 서버 page.tsx 로 빼고, 여기는 상호작용만 남겼다. 동작은 그대로다.
 */
'use client';

import { useState, useEffect, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';

import { SearchBar } from '@/components/ui/SearchBar';
import { GameGrid } from '@/components/game/GameGrid';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameGridSkeleton } from '@/components/ui/LoadingSkeleton';
import { useDefaultRecommendations, DEFAULT_THEME_LABEL, getTodaysTheme, useRecommendByVibe, useVibes } from '@/hooks/useRecommend';
import { semanticSearchGames, recordTasteAction } from '@/lib/api';
import { VibeChips } from '@/components/ui/VibeChips';
import { useUserStore } from '@/store/useUserStore';

/**
 * Inner home content using useSearchParams.
 * Korean: useSearchParams를 쓰는 실제 본문. Suspense로 감싸기 위해 분리.
 * 반환은 Fragment — 부모(app/page.tsx)의 flex gap-12 열에 섹션들이 그대로 놓인다.
 */
export function HomeContent() {
  const router        = useRouter();
  const searchParams  = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const ensureSessionId = useUserStore(s => s.ensureSessionId);

  const submittedQuery = searchParams.get('q') ?? '';
  const [inputValue, setInputValue] = useState(submittedQuery);

  // Vibe 칩 선택 상태
  const [selectedVibe, setSelectedVibe] = useState<string | null>(null);

  // 오늘의 테마 라벨 — SSR/CSR 동일 고정 초기값, mount 후 실제 갱신 (#418 방지)
  const [themeLabel, setThemeLabel] = useState(DEFAULT_THEME_LABEL);
  useEffect(() => {
    setThemeLabel(getTodaysTheme().label);
  }, []);

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
    <>
      {/* 검색창 — 히어로(h1·CTA)는 서버 page.tsx 가 그린다. 원래 한 섹션이던 간격(mb-8)을 맞추려고
          부모 flex gap-12 를 -mt-12 로 상쇄한다 */}
      <section className="-mt-12 pb-2 flex flex-col items-center text-center">
        <div className="w-full max-w-2xl">
          <SearchBar value={inputValue} onChange={setInputValue} onSubmit={handleSubmit} showChips={false} />
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
            ? searchResult?.reference_game
              ? `${searchResult.reference_game}와 비슷한 게임 ${searchGames.length}개 (기준 게임·시리즈 제외)`
              : `"${submittedQuery}" 검색 결과 ${searchGames.length}개`
            : showVibe
              ? `${selectedVibeLabel} 추천 ${vibeGames.length}개`
              : `오늘의 AI 추천 · ${themeLabel} 게임`}
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
          <>
            <ErrorState
              type="not-found"
              variant="page"
              title={showSearch ? '검색 결과가 없어요' : '추천을 불러올 수 없어요'}
              description={showSearch ? '다른 표현으로 검색해보세요' : '잠시 후 다시 시도해주세요'}
              onRetry={showSearch ? undefined : showVibe ? () => refetchVibe() : () => refetchAI()}
            />
            {/* 검색 0건 폴백 — 빈 화면 대신 오늘의 추천으로 이탈 방지 */}
            {showSearch && aiGames.length > 0 && (
              <div className="mt-10">
                <h3 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">
                  대신 이런 게임은 어때요? · 오늘의 {themeLabel} 추천
                </h3>
                <GameGrid games={aiGames} />
              </div>
            )}
          </>
        )}

        {!isLoading && !currentError && displayGames.length > 0 && (
          <GameGrid games={displayGames} />
        )}
      </section>
    </>
  );
}
