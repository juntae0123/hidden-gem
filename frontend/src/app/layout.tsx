/**
 * Root layout with providers.
 * 프로바이더 포함 루트 레이아웃.
 *
 * v1 → v3: Umami 분석 스크립트 + CookieConsent + 메타데이터 강화
 * v3 → v4: Umami <Script>를 <head> 밖 body로 이동 (#418 hydration mismatch 해결)
 *          / React error #418 fix — afterInteractive script는 head에 두지 않는다
 * v4 → v5: SEO 메타데이터 정리 — 기본 제목·설명을 서비스 정의에 맞춤, '인디게임' 키워드 제거,
 *          루트 canonical 제거(하위 페이지가 '/' 를 물려받던 문제), 기본 OG 이미지는 opengraph-image.tsx
 */
import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';
import { Providers } from './providers';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { CookieConsent } from '@/components/ui/CookieConsent';
import { SurveyGate } from '@/components/ui/SurveyGate';
import { SignupNudge } from '@/components/ui/SignupNudge';
import { SITE_URL } from '@/lib/constants';
import { OG_BASE, SERVICE_TAGLINE } from '@/lib/seo';

const UMAMI_URL = process.env.NEXT_PUBLIC_UMAMI_URL || 'http://localhost:3001';
const UMAMI_WEBSITE_ID = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '';

export const metadata: Metadata = {
  // metadataBase 가 있어야 OG/트위터 카드의 상대 경로가 절대 URL 로 바뀐다 (카톡·디시 공유 미리보기)
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Hidden Gem · 취향에 맞는 스팀 게임 찾기',
    template: '%s · Hidden Gem',
  },
  description:
    `${SERVICE_TAGLINE}. 좋아하는 게임과 비슷한 스팀 게임을 49개 플레이 지표로 비교하고, 자연어로 검색해 찾아보세요.`,
  // '인디게임' 은 넣지 않는다 — 인디 전용 서비스가 아니다 (사용자 지정, SEO 2026-10-14)
  keywords: ['게임 추천', '비슷한 게임', '같은 게임 추천', '스팀 게임 추천', 'Steam', '숨은 명작', '취향 분석'],
  // canonical·og:url 은 여기 두지 않는다 — 루트에 두면 모든 하위 페이지가 '/' 를 canonical 로 물려받아
  // 상세·랭킹이 홈의 중복으로 취급된다 (SEO 2026-10-14 발견). 각 페이지가 자기 경로를 선언한다.
  openGraph: {
    ...OG_BASE,
    title: 'Hidden Gem · 취향에 맞는 스팀 게임 찾기',
    description: `${SERVICE_TAGLINE} — 좋아하는 게임과 비슷한 게임을 찾아드려요`,
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Hidden Gem · 취향에 맞는 스팀 게임 찾기',
    description: `${SERVICE_TAGLINE} — 좋아하는 게임과 비슷한 게임을 찾아드려요`,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" suppressHydrationWarning className="dark">
      <body className="min-h-screen flex flex-col bg-[#FAFAF7] dark:bg-[#0F0F13] text-zinc-900 dark:text-zinc-100 antialiased">
        <Providers>
          <Navbar />
          <main className="flex-1 w-full max-w-7xl mx-auto px-6 py-8">{children}</main>
          <Footer />
          <CookieConsent />
          <SurveyGate />
          <SignupNudge />
        </Providers>

        {/* Umami 분석 — afterInteractive는 body 끝에 (head에 두면 #418) */}
        {/* Umami analytics: mounted in body, not head, to avoid hydration mismatch */}
        {UMAMI_WEBSITE_ID && (
          <Script
            src={`${UMAMI_URL}/script.js`}
            data-website-id={UMAMI_WEBSITE_ID}
            strategy="afterInteractive"
          />
        )}
      </body>
    </html>
  );
}