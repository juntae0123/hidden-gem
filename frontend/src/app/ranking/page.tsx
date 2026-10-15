/**
 * Ranking page (Server Component wrapper).
 * 랭킹 — 메타데이터와 첫 탭(숨은 명작) 목록을 서버에서 싣고, 화면은 RankingPageClient 가 그린다.
 *
 * SEO 2026-10-14: 이전엔 'use client' 페이지라 제목이 홈과 같았고 목록도 HTML 에 없었다.
 * 랭킹 API 가 죽어 있으면 initialSteady 없이 그린다 — 클라이언트가 예전처럼 다시 불러온다.
 */
import type { Metadata } from 'next';
import { RankingPageClient } from '@/components/game/RankingPageClient';
import { getRankingServer } from '@/lib/server-api';
import { DEFAULT_OG_IMAGE, OG_BASE, SITE_NAME } from '@/lib/seo';

// 랭킹 서버 캐시(6h)보다 짧게 — 주간 갱신 직후 반나절 넘게 옛 목록을 들고 있지 않게
export const revalidate = 3600;

const TITLE = '숨은 명작 랭킹 · 요즘 뜨는 게임 · 신작';
const DESCRIPTION =
  '많이 알려지지 않았지만 해본 사람들 평이 좋은 스팀 게임, 최근 한 달 사이 리뷰가 빠르게 늘고 있는 게임, 최근 6개월 신작을 리뷰 실측 지표로 줄 세웠어요.';

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: '/ranking' },
  openGraph: {
    ...OG_BASE, url: '/ranking', title: `${TITLE} · ${SITE_NAME}`, description: DESCRIPTION,
    images: [DEFAULT_OG_IMAGE],   // openGraph 를 덮어쓰면 루트 OG 이미지가 빠진다 (lib/seo.ts)
  },
};

export default async function RankingPage() {
  const steady = await getRankingServer('steady', 30);
  return <RankingPageClient initialSteady={steady ?? undefined} />;
}
