/**
 * /search metadata — 페이지가 'use client' 라 메타데이터를 여기(서버 layout)에 둔다 (SEO 2026-10-14).
 */
import type { Metadata } from 'next';
import { DEFAULT_OG_IMAGE, OG_BASE, SITE_NAME } from '@/lib/seo';

const TITLE = '취향 분석 · 내 취향에 맞는 게임 찾기';
const DESCRIPTION =
  '아늑함·전략 깊이·서사 같은 49개 플레이 지표를 조절해 내 취향을 만들고, 그 취향에 맞는 스팀 게임을 추천받아 보세요.';

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: '/search' },
  openGraph: {
    ...OG_BASE, url: '/search', title: `${TITLE} · ${SITE_NAME}`, description: DESCRIPTION,
    images: [DEFAULT_OG_IMAGE],   // openGraph 를 덮어쓰면 루트 OG 이미지가 빠진다 (lib/seo.ts)
  },
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
