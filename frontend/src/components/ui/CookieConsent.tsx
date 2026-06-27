/**
 * Cookie consent banner.
 * 쿠키 동의 배너 — PIPA/GDPR 준수, localStorage 저장.
 */
'use client';

import { useEffect, useState } from 'react';
import { Cookie, X } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

const CONSENT_KEY = 'hidden-gem-cookie-consent';

/**
 * Check if user has consented to analytics.
 * 분석 쿠키 동의 여부 확인 (umami.ts에서 import).
 */
export function hasAnalyticsConsent(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    if (!raw) return false;
    return JSON.parse(raw).accepted === true;
  } catch {
    return false;
  }
}

/**
 * Cookie consent banner component.
 * 쿠키 동의 배너.
 */
export function CookieConsent() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(CONSENT_KEY);
    if (!consent) {
      const timer = setTimeout(() => setShow(true), 1000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleConsent = (accepted: boolean) => {
    localStorage.setItem(
      CONSENT_KEY,
      JSON.stringify({ accepted, timestamp: Date.now() })
    );
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      className={cn(
        'fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-md z-50',
        'bg-white dark:bg-zinc-900',
        'border border-zinc-200 dark:border-zinc-800',
        'rounded-xl shadow-lg p-4',
        'animate-in slide-in-from-bottom-4 duration-300'
      )}
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-950/40 flex items-center justify-center flex-shrink-0">
          <Cookie className="w-4 h-4 text-purple-600" />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            쿠키 사용 안내
          </h3>
          <p className="mt-1 text-[12px] text-zinc-500 dark:text-zinc-400 leading-relaxed">
            로그인 유지 및 더 나은 추천을 위해 쿠키를 사용합니다.{' '}
            <Link href="/privacy" className="text-purple-600 hover:underline">
              자세히
            </Link>
          </p>

          <div className="mt-3 flex gap-2">
            <button
              onClick={() => handleConsent(true)}
              className="px-3 py-1.5 rounded-lg bg-purple-600 text-white text-[12px] font-medium hover:bg-purple-700 transition-colors"
            >
              동의
            </button>
            <button
              onClick={() => handleConsent(false)}
              className="px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 text-[12px] hover:border-zinc-300 transition-colors"
            >
              필수만
            </button>
          </div>
        </div>

        <button
          onClick={() => handleConsent(false)}
          className="text-zinc-400 hover:text-zinc-600 transition-colors"
          aria-label="닫기"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
