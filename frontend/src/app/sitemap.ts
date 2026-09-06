import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/constants';

/**
 * Static sitemap for crawlers.
 * 정적 사이트맵 — 검색 엔진 수집용.
 *
 * 게임 상세(/game/[id]) 는 1만 건이 넘어 빌드 시 전량 나열하지 않는다.
 * 랭킹·검색 페이지에서 내부 링크로 도달 가능하므로 크롤러가 따라간다.
 * (전량 색인이 필요해지면 분할 사이트맵으로 나눈다 — 파일당 5만 URL 제한)
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const routes: Array<[string, MetadataRoute.Sitemap[number]['changeFrequency'], number]> = [
    ['', 'daily', 1],
    ['/search', 'daily', 0.9],
    ['/ranking', 'daily', 0.9],
    ['/onboarding', 'monthly', 0.5],
    ['/login', 'yearly', 0.3],
    ['/privacy', 'yearly', 0.3],
    ['/terms', 'yearly', 0.3],
  ];

  return routes.map(([path, changeFrequency, priority]) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency,
    priority,
  }));
}
