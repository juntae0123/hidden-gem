import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/constants';

/**
 * robots.txt — 개인 영역만 막고 나머지는 수집 허용.
 * 마이페이지·인증 콜백은 색인될 이유가 없다(로그인 상태 페이지).
 *
 * 사이트맵 (SEO 2026-10-14): 묶음 안내(/sitemap-index.xml)가 정적 사이트맵과 게임 상세 사이트맵
 * (/game/sitemap/<n>.xml)을 모두 가리킨다. /sitemap.xml 은 이미 제출했을 수 있어 그대로 둔다.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/', disallow: ['/mypage', '/auth/'] }],
    sitemap: [`${SITE_URL}/sitemap-index.xml`, `${SITE_URL}/sitemap.xml`],
    host: SITE_URL,
  };
}
