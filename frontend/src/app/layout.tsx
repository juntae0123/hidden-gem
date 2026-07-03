/**
 * Root layout with providers.
 * 프로바이더 포함 루트 레이아웃.
 *
 * v1 → v3: Umami 분석 스크립트 + CookieConsent + 메타데이터 강화
 */
import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';
import { Providers } from './providers';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { CookieConsent } from '@/components/ui/CookieConsent';
import { SurveyGate } from '@/components/ui/SurveyGate';

const UMAMI_URL = process.env.NEXT_PUBLIC_UMAMI_URL || 'http://localhost:3001';
const UMAMI_WEBSITE_ID = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '';

export const metadata: Metadata = {
  title: 'Hidden Gem · Steam 게임 AI 추천',
  description:
    '숨겨진 명작 게임을 찾아드립니다. 자연어로 검색하고 AI가 취향에 맞는 게임을 추천합니다.',
  keywords: ['게임 추천', 'Steam', '인디게임', 'AI 추천', '숨은 명작'],
  openGraph: {
    title: 'Hidden Gem · Steam 게임 AI 추천',
    description: '취향에 맞는 숨겨진 명작 게임을 찾아드려요',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" suppressHydrationWarning className="dark">
      <head>
        {/* Umami 분석 (Website ID 있을 때만) */}
        {UMAMI_WEBSITE_ID && (
          <Script
            src={`${UMAMI_URL}/script.js`}
            data-website-id={UMAMI_WEBSITE_ID}
            strategy="afterInteractive"
          />
        )}
      </head>
        <body className="min-h-screen bg-[#FAFAF7] dark:bg-[#0F0F13] text-zinc-900 dark:text-zinc-100 antialiased">
          <Providers>
            <Navbar />
            <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
            <Footer />
            <CookieConsent />
            <SurveyGate />
          </Providers>
        </body>
    </html>
  );
}