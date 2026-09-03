/**
 * Swipe onboarding — rate 10 games to bootstrap taste metrics.
 * 스와이프 온보딩 — 게임 10개를 좋아요/별로로 평가해 초기 취향 지표를 만든다.
 *
 * 취향 산출: 좋아요한 게임들의 key_metrics 평균 (0~10)
 * 저장: 비로그인 → sessionStorage로 /search에 전달해 즉시 추천
 *       로그인   → taste-preference API에도 저장 (1~5 스케일 변환)
 */
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Heart, X, HelpCircle } from 'lucide-react';
import { getVibes, recommendByVibe, recordTasteAction, saveTastePreference } from '@/lib/api';
import { GameImage } from '@/components/ui/GameImage';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useUserStore } from '@/store/useUserStore';
import { trackEvent } from '@/lib/umami';
import type { RecommendedGame } from '@/types/game';

const DECK_SIZE = 12;
const SWIPE_THRESHOLD = 80; // px

type Verdict = 'like' | 'dislike' | 'skip';

/** vibe별 게임을 2개씩 순차 요청으로 모아 덱 구성.
 * 동시 5요청은 로컬 백엔드에서 타임아웃이 나서(실측) 동시성 2로 제한하고,
 * 실패/부족분은 다음 vibe로 계속 보충한다. */
async function buildDeck(): Promise<RecommendedGame[]> {
  const vibes = await getVibes();
  // 다양성: 앞에서부터가 아니라 전체에 고르게 분포하도록 섞기
  const shuffled = [...vibes].sort(() => Math.random() - 0.5);

  const seen = new Set<number>();
  const deck: RecommendedGame[] = [];

  for (let i = 0; i < shuffled.length && deck.length < DECK_SIZE; i += 2) {
    const batch = shuffled.slice(i, i + 2);
    const results = await Promise.all(
      batch.map(v => recommendByVibe(v.key, 4).catch(() => null))
    );
    for (const r of results) {
      for (const g of r?.recommendations ?? []) {
        if (!seen.has(g.app_id) && deck.length < DECK_SIZE) {
          seen.add(g.app_id);
          deck.push(g);
        }
      }
    }
  }
  return deck;
}

/** 좋아요 게임들의 key_metrics 평균 → 초기 취향 (0~10) */
function derivePrefs(liked: RecommendedGame[]): Record<string, number> {
  const sum: Record<string, { total: number; n: number }> = {};
  for (const g of liked) {
    for (const [k, v] of Object.entries(g.key_metrics ?? {})) {
      if (typeof v !== 'number') continue;
      sum[k] = { total: (sum[k]?.total ?? 0) + v, n: (sum[k]?.n ?? 0) + 1 };
    }
  }
  return Object.fromEntries(
    Object.entries(sum).map(([k, { total, n }]) => [k, Math.round((total / n) * 10) / 10])
  );
}

/** 좋아요 게임들의 장르 상위 3개 */
function deriveGenres(liked: RecommendedGame[]): string[] {
  const count: Record<string, number> = {};
  for (const g of liked) {
    for (const genre of (g.genres ?? '').split(',').map(s => s.trim()).filter(Boolean)) {
      count[genre] = (count[genre] ?? 0) + 1;
    }
  }
  return Object.entries(count).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([g]) => g);
}

export default function SwipeOnboardingPage() {
  const router = useRouter();
  const isLoggedIn = useUserStore(s => s.isLoggedIn);
  const ensureSessionId = useUserStore(s => s.ensureSessionId);

  const [deck, setDeck] = useState<RecommendedGame[] | null>(null);
  const [index, setIndex] = useState(0);
  const [likes, setLikes] = useState<RecommendedGame[]>([]);
  const [dislikes, setDislikes] = useState<number>(0);
  const [drag, setDrag] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragging = useRef(false);
  const startX = useRef(0);
  const finishing = useRef(false);

  useEffect(() => {
    buildDeck()
      .then(setDeck)
      .catch(() => setDeck([]));
  }, []);

  const finish = useCallback((finalLikes: RecommendedGame[], finalDislikes: number) => {
    if (finishing.current) return;
    finishing.current = true;

    trackEvent('swipe_complete', { likes: finalLikes.length, dislikes: finalDislikes });
    recordTasteAction({
      session_id: ensureSessionId(),
      action_type: 'search',
      context: {
        query: 'onboarding_swipe',
        likes: finalLikes.map(g => g.app_id),
        like_count: finalLikes.length,
        dislike_count: finalDislikes,
      },
    });

    if (finalLikes.length === 0) {
      router.replace('/search');
      return;
    }

    const prefs = derivePrefs(finalLikes);
    try {
      sessionStorage.setItem('hg_swipe_prefs', JSON.stringify(prefs));
    } catch {
      // sessionStorage 불가 환경 — 취향 전달 없이 진행
    }

    if (isLoggedIn) {
      // 1~5 스케일로 변환해 계정에도 저장 (실패해도 흐름 유지)
      const metricPrefs = Object.fromEntries(
        Object.entries(prefs).map(([k, v]) => [k, Math.min(5, Math.max(1, Math.round(v / 2)))])
      );
      saveTastePreference({
        preferred_genres: deriveGenres(finalLikes),
        metric_preferences: metricPrefs,
      }).catch(() => undefined);
    }

    router.replace('/search?from=swipe');
  }, [ensureSessionId, isLoggedIn, router]);

  const verdictFor = useCallback((v: Verdict) => {
    if (!deck || index >= deck.length) return;
    const game = deck[index];
    const nextLikes = v === 'like' ? [...likes, game] : likes;
    const nextDislikes = v === 'dislike' ? dislikes + 1 : dislikes;
    setLikes(nextLikes);
    setDislikes(nextDislikes);
    setDrag(0);

    if (index + 1 >= deck.length) {
      finish(nextLikes, nextDislikes);
    } else {
      setIndex(index + 1);
    }
  }, [deck, index, likes, dislikes, finish]);

  // 키보드: ← 별로 / → 좋아요 / ↓ 스킵
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') verdictFor('like');
      else if (e.key === 'ArrowLeft') verdictFor('dislike');
      else if (e.key === 'ArrowDown') verdictFor('skip');
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [verdictFor]);

  // 포인터 드래그 스와이프
  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    setIsDragging(true);
    startX.current = e.clientX;
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (dragging.current) setDrag(e.clientX - startX.current);
  };
  const onPointerUp = () => {
    if (!dragging.current) return;
    dragging.current = false;
    setIsDragging(false);
    if (drag > SWIPE_THRESHOLD) verdictFor('like');
    else if (drag < -SWIPE_THRESHOLD) verdictFor('dislike');
    else setDrag(0);
  };

  if (deck === null) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <LoadingSpinner />
        <p className="text-sm text-zinc-500">취향 스캔용 게임을 고르는 중...</p>
      </div>
    );
  }

  if (deck.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <p className="text-sm text-zinc-500">게임을 불러오지 못했어요. 잠시 후 다시 시도해주세요.</p>
        <button
          type="button"
          onClick={() => router.replace('/search')}
          className="px-4 py-2 rounded-lg bg-purple-600 text-white text-sm"
        >
          슬라이더로 취향 설정하기
        </button>
      </div>
    );
  }

  const game = deck[Math.min(index, deck.length - 1)];
  const progress = Math.min(index + 1, deck.length);

  return (
    <div className="flex flex-col items-center gap-7 py-6 select-none">
      <header className="text-center">
        <h1 className="text-2xl md:text-3xl font-semibold">3분 취향 스캔</h1>
        <p className="mt-2 text-sm md:text-base text-zinc-500">
          끌리는 게임엔 좋아요 — {deck.length}개면 초기 취향이 잡혀요 ({progress}/{deck.length})
        </p>
      </header>

      {/* 진행 바 */}
      <div className="w-full max-w-xl h-2 rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div
          className="h-full rounded-full bg-purple-600 transition-all"
          style={{ width: `${(index / deck.length) * 100}%` }}
        />
      </div>

      {/* 카드 */}
      <div
        className="relative w-full max-w-xl cursor-grab active:cursor-grabbing touch-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        style={{
          transform: `translateX(${drag}px) rotate(${drag / 25}deg)`,
          transition: isDragging ? 'none' : 'transform 0.2s',
        }}
      >
        <div className="rounded-2xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-md">
          <GameImage appId={game.app_id} name={game.name} fallback={game.header_image} size="hero" priority />
          <div className="p-5 flex flex-col gap-2">
            <h2 className="text-lg md:text-xl font-semibold text-zinc-900 dark:text-zinc-100">{game.name}</h2>
            <p className="text-[13px] text-zinc-500">{game.genres}</p>
            {game.one_line_summary && (
              <p className="text-sm md:text-[15px] text-zinc-600 dark:text-zinc-400 leading-relaxed">
                {game.one_line_summary}
              </p>
            )}
          </div>
        </div>

        {/* 드래그 방향 힌트 */}
        {drag > 30 && (
          <span className="absolute top-4 left-4 px-2 py-1 rounded-md bg-purple-600 text-white text-xs font-semibold">좋아요</span>
        )}
        {drag < -30 && (
          <span className="absolute top-4 right-4 px-2 py-1 rounded-md bg-zinc-700 text-white text-xs font-semibold">별로</span>
        )}
      </div>

      {/* 버튼 */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => verdictFor('dislike')}
          aria-label="별로예요"
          className="w-14 h-14 rounded-full border border-zinc-300 dark:border-zinc-700 flex items-center justify-center text-zinc-500 hover:border-red-400 hover:text-red-500 transition-colors"
        >
          <X className="w-6 h-6" />
        </button>
        <button
          type="button"
          onClick={() => verdictFor('skip')}
          aria-label="잘 모르겠어요"
          className="w-14 h-14 rounded-full border border-zinc-200 dark:border-zinc-800 flex items-center justify-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
        >
          <HelpCircle className="w-6 h-6" />
        </button>
        <button
          type="button"
          onClick={() => verdictFor('like')}
          aria-label="좋아요"
          className="w-14 h-14 rounded-full bg-purple-600 flex items-center justify-center text-white hover:bg-purple-700 transition-colors shadow-sm"
        >
          <Heart className="w-6 h-6" />
        </button>
      </div>

      <p className="text-[11px] text-zinc-400">카드를 옆으로 밀거나, 키보드 ←/→/↓로도 돼요</p>
    </div>
  );
}
