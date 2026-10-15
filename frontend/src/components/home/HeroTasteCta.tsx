/**
 * Hero CTA link with analytics event (client).
 * 홈 히어로의 '내 취향 분석하기' 버튼 — 클릭 이벤트(trackEvent)만 클라이언트에서 처리한다.
 * 히어로 나머지(h1·문구·보조 링크)는 서버 page.tsx 가 그린다 (SEO 2026-10-14).
 */
'use client';

import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { trackEvent } from '@/lib/umami';

export function HeroTasteCta() {
  return (
    <Link
      href="/search"
      onClick={() => trackEvent('hero_taste_cta')}
      className="mt-8 inline-flex items-center gap-2 px-7 py-3 rounded-full bg-purple-600 text-white text-sm md:text-[15px] font-medium hover:bg-purple-500 transition-colors shadow-lg shadow-purple-600/20"
    >
      <Sparkles className="w-4 h-4" />
      내 취향 분석하기
    </Link>
  );
}
