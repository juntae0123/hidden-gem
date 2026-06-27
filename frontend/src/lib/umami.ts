/**
 * Umami analytics helper.
 * Umami 분석 헬퍼 — 셀프호스팅 무료 분석.
 *
 * 쿠키 동의 후에만 추적 (CookieConsent 연동).
 */

import { hasAnalyticsConsent } from '@/components/ui/CookieConsent';

/**
 * Track custom event (동의한 경우만).
 * 커스텀 이벤트 추적 — 쿠키 동의 시에만.
 *
 * @example
 * trackEvent('search', { query: '힐링게임', count: 12 })
 * trackEvent('steam_click', { app_id: 1086940, score: 87 })
 */
export function trackEvent(
  eventName: string,
  data?: Record<string, unknown>
): void {
  if (typeof window === 'undefined') return;
  if (!hasAnalyticsConsent()) return;

  const umami = (window as {
    umami?: { track: (name: string, data?: unknown) => void };
  }).umami;

  if (umami?.track) {
    umami.track(eventName, data);
  }
}
