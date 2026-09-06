import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/constants';

/**
 * robots.txt — 개인 영역만 막고 나머지는 수집 허용.
 * 마이페이지·인증 콜백은 색인될 이유가 없다(로그인 상태 페이지).
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/', disallow: ['/mypage', '/auth/'] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
