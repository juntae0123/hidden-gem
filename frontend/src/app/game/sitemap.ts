import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/constants';
import { GAME_SITEMAP_CHUNK, getGameSitemapCount, getSitemapIds } from '@/lib/server-api';

/**
 * Game detail sitemaps — /game/sitemap/<id>.xml (SEO 2026-10-14).
 * 게임 상세 전량 사이트맵. 파일당 GAME_SITEMAP_CHUNK(1만) 개, 노출 게이트를 통과한 게임만.
 *
 * - 목록은 FastAPI GET /games/sitemap-ids (is_active AND is_analyzed — 검색과 같은 노출 조건).
 * - 파일 개수(generateSitemaps)는 빌드 때 정해진다. 게임이 늘어 파일이 모자라면 다음 배포 때 늘어난다.
 * - 내용은 하루마다 다시 만든다(revalidate). API 가 죽어 있으면 빈 목록 → 재시도 주기(5분)로 다시 그린다.
 * - 사이트맵 묶음 안내는 /sitemap-index.xml (app/sitemap-index.xml/route.ts).
 */
export const revalidate = 86400;

export async function generateSitemaps() {
  const count = await getGameSitemapCount();
  return Array.from({ length: count }, (_, id) => ({ id }));
}

export default async function sitemap(props: {
  id: Promise<string>;
}): Promise<MetadataRoute.Sitemap> {
  const id = Number(await props.id);
  if (!Number.isInteger(id) || id < 0) return [];

  const page = await getSitemapIds(id * GAME_SITEMAP_CHUNK, GAME_SITEMAP_CHUNK);
  if (!page) return [];

  return page.app_ids.map((appId) => ({
    url: `${SITE_URL}/game/${appId}`,
    changeFrequency: 'weekly' as const,
    priority: 0.6,
  }));
}
