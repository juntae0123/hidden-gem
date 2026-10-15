import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/constants';

/**
 * Static sitemap for crawlers.
 * 정적 사이트맵 — 검색 엔진 수집용.
 *
 * 게임 상세(/game/[id])는 여기 넣지 않고 분할 사이트맵(app/game/sitemap.ts → /game/sitemap/<n>.xml)이
 * 맡는다 (SEO 2026-10-14). 둘을 묶는 안내 파일은 /sitemap-index.xml.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const routes: Array<[string, MetadataRoute.Sitemap[number]['changeFrequency'], number]> = [
    ['', 'daily', 1],
    ['/search', 'daily', 0.9],
    ['/ranking', 'daily', 0.9],
    ['/onboarding', 'monthly', 0.5],
    ['/onboarding/swipe', 'monthly', 0.6],
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
