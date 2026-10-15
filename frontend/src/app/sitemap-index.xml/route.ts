import { SITE_URL } from '@/lib/constants';
import { getGameSitemapCount } from '@/lib/server-api';

/**
 * Sitemap index — /sitemap-index.xml (SEO 2026-10-14).
 * 사이트맵 묶음 안내 파일. 구글 서치 콘솔·네이버 서치어드바이저에는 이 주소 하나만 제출한다.
 *   - /sitemap.xml            정적 페이지 (app/sitemap.ts)
 *   - /game/sitemap/<n>.xml   게임 상세 (app/game/sitemap.ts, generateSitemaps)
 * Next 는 generateSitemaps 로 나눈 파일의 색인 파일을 자동으로 만들어 주지 않아 직접 만든다.
 * 파일 개수는 app/game/sitemap.ts 와 같은 함수(getGameSitemapCount)로 센다.
 */
export const revalidate = 86400;

function escapeXml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export async function GET() {
  const count = await getGameSitemapCount();
  const urls = [
    `${SITE_URL}/sitemap.xml`,
    ...Array.from({ length: count }, (_, i) => `${SITE_URL}/game/sitemap/${i}.xml`),
  ];
  const body =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls.map((u) => `  <sitemap><loc>${escapeXml(u)}</loc></sitemap>`).join('\n') +
    '\n</sitemapindex>\n';

  return new Response(body, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
