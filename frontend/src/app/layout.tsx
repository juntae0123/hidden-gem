/**
 * Root layout with providers
 * 프로바이더 포함 루트 레이아웃
 */
import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';

export const metadata: Metadata = {
  title: 'Hidden Gem · Steam 인디게임 AI 추천',
  description:
    '숨겨진 인디게임을 찾아드립니다. 자연어로 검색하고 AI가 추천합니다.',
};

/**
 * Root layout
 * 모든 페이지의 공통 레이아웃
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen bg-[#FAFAF7] dark:bg-[#0A0A0B] text-zinc-900 dark:text-zinc-100 antialiased">
        <Providers>
          <Navbar />
          <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
