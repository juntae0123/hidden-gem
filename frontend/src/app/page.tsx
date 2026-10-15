/**
 * Home page (Server Component).
 * 홈 — 히어로는 서버가 그리고, 검색·추천 같은 상호작용은 HomeContent(client)가 맡는다.
 *
 * v1 → v2 (SEO 2026-10-14):
 *   - 이전: 페이지 전체가 'use client' + useSearchParams 라 정적 렌더 때 Suspense 폴백(스켈레톤)만
 *     HTML 에 실렸다. 크롤러·링크 미리보기에는 h1 도 링크도 없는 빈 홈이었다.
 *   - 지금: h1·서비스 한 줄 설명·주요 진입 링크(/search, /ranking, /onboarding/swipe)를 서버 HTML 로.
 *     검색창·Vibe 칩·추천 그리드는 그대로 클라이언트(HomeContent)다 — 동작 변화 없음.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { Suspense } from 'react';
import { HomeContent } from '@/components/home/HomeContent';
import { HeroTasteCta } from '@/components/home/HeroTasteCta';
import { GameGridSkeleton } from '@/components/ui/LoadingSkeleton';
import { OG_BASE, SERVICE_TAGLINE } from '@/lib/seo';

export const metadata: Metadata = {
  // 루트 layout 에서 옮겨 온 canonical — 홈만 '/' 를 선언한다
  alternates: { canonical: '/' },
  openGraph: {
    ...OG_BASE,
    url: '/',
    title: 'Hidden Gem · 취향에 맞는 스팀 게임 찾기',
    description: `${SERVICE_TAGLINE} — 좋아하는 게임과 비슷한 게임을 찾아드려요`,
  },
};

/** HomeContent 가 클라이언트에서 뜨기 전 자리 — 검색창 높이를 맞춰 화면이 덜 밀리게 */
function HomeContentFallback() {
  return (
    <>
      <section className="-mt-12 pb-2 flex flex-col items-center">
        <div className="w-full max-w-2xl px-5 py-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm">
          <div className="h-5" />
        </div>
      </section>
      <GameGridSkeleton count={9} />
    </>
  );
}

export default function HomePage() {
  return (
    <div className="flex flex-col gap-12">
      <section className="pt-10 flex flex-col items-center text-center">
        <div className="mb-8 flex flex-col items-center">
          {/* h1 에 브랜드와 서비스 정의를 함께 — 화면 모양은 예전(제목 + 부제)과 같다 */}
          <h1 className="flex flex-col items-center">
            <span className="text-4xl md:text-5xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
              <span aria-hidden="true" className="text-purple-500 dark:text-purple-400">✦</span> Hidden Gem
            </span>
            <span className="mt-3 text-sm md:text-base font-normal text-zinc-500 dark:text-zinc-400">
              {SERVICE_TAGLINE}
            </span>
          </h1>
          <p className="mt-1.5 text-[13px] md:text-sm text-zinc-500 dark:text-zinc-400">
            좋아하는 게임과 비슷한 스팀 게임을 49개 플레이 지표로 비교해 찾아드려요
          </p>

          {/* 핵심 CTA — 취향 분석이 이 서비스의 차별점 (클릭 이벤트 때문에 클라이언트 컴포넌트) */}
          <HeroTasteCta />

          {/* 보조 진입 — 크롤러가 따라갈 내부 링크이기도 하다. 좁은 폭에서 줄바꿈되도록 flex-wrap */}
          <nav aria-label="바로가기" className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1 text-[12px] sm:text-[13px] text-zinc-500 dark:text-zinc-400">
            <Link href="/onboarding/swipe" className="whitespace-nowrap hover:text-purple-600 dark:hover:text-purple-300 underline-offset-4 hover:underline">
              스와이프로 취향 찾기
            </Link>
            <span aria-hidden="true" className="text-zinc-300 dark:text-zinc-700">·</span>
            <Link href="/ranking" className="whitespace-nowrap hover:text-purple-600 dark:hover:text-purple-300 underline-offset-4 hover:underline">
              숨은 명작 랭킹
            </Link>
          </nav>
        </div>
      </section>

      {/* useSearchParams 때문에 Suspense 필요 — 폴백은 클라이언트가 뜰 때까지의 자리 */}
      <Suspense fallback={<HomeContentFallback />}>
        <HomeContent />
      </Suspense>
    </div>
  );
}
