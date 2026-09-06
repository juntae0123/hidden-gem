// src/components/ui/SignupNudge.tsx
'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useUserStore } from '@/store/useUserStore';
import { trackEvent } from '@/lib/umami';

const SNOOZE_KEY = 'signup-nudge-snooze-until';   // 닫으면 7일 안 보임 (localStorage)
const SHOWN_KEY = 'signup-nudge-shown';           // 세션당 1회 (sessionStorage)
const COUNT_KEY = 'signup-nudge-views';           // 의미 있는 화면 조회 수 (sessionStorage)

const VIEWS_BEFORE_NUDGE = 2;   // 게임 상세/검색 결과를 2번 본 뒤에
const DELAY_MS = 2500;          // 화면 뜨자마자가 아니라 한 박자 늦게
const SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;

/** 이 경로를 '취향을 드러낸 행동'으로 본다 — 홈만 훑고 나가는 사람은 건드리지 않는다. */
function isEngagedPath(path: string): boolean {
  return path.startsWith('/game/') || path.startsWith('/search');
}

/**
 * Signup nudge — non-blocking prompt to save taste by logging in.
 * Korean: 회원가입 유도 — 검색/상세를 두 번 이상 본 비로그인 방문자에게만,
 * 화면을 가리지 않는 카드로 한 번. 닫으면 7일간 안 뜬다.
 *
 * 설계 이유: 첫 화면에서 가입부터 막으면 이탈한다. 취향을 이미 드러낸 뒤,
 * "그 취향을 저장한다"는 구체적 이득으로 제안하는 게 전환이 높다.
 */
export function SignupNudge() {
  const isLoggedIn = useUserStore((s) => s.isLoggedIn);
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (isLoggedIn || open) return;

    try {
      // 쿠키 동의 배너와 같은 자리에 뜬다 — 배너가 떠 있는 동안은 양보한다
      if (!localStorage.getItem('hidden-gem-cookie-consent')) return;
      if (sessionStorage.getItem(SHOWN_KEY)) return;
      const until = localStorage.getItem(SNOOZE_KEY);
      if (until && Date.now() < Number(until)) return;

      if (!isEngagedPath(pathname)) return;
      const views = Number(sessionStorage.getItem(COUNT_KEY) || 0) + 1;
      sessionStorage.setItem(COUNT_KEY, String(views));
      if (views < VIEWS_BEFORE_NUDGE) return;
    } catch {
      return; // 스토리지를 못 쓰면 조용히 포기 — 매번 띄우는 쪽이 더 나쁘다
    }

    const t = setTimeout(() => {
      try { sessionStorage.setItem(SHOWN_KEY, '1'); } catch { /* ignore */ }
      setOpen(true);
      trackEvent('signup_nudge_shown', { path: pathname });
    }, DELAY_MS);

    return () => clearTimeout(t);
  }, [pathname, isLoggedIn, open]);

  if (!open || isLoggedIn) return null;

  const close = (reason: 'dismiss' | 'login') => {
    if (reason === 'dismiss') {
      try { localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_MS)); } catch { /* ignore */ }
      trackEvent('signup_nudge_dismiss', { path: pathname });
    }
    setLeaving(true);
    setTimeout(() => setOpen(false), 150);
  };

  return (
    <div
      role="dialog"
      aria-label="로그인 안내"
      className={[
        'fixed bottom-4 left-4 right-4 z-[60] md:left-auto md:right-4 md:max-w-sm',
        'rounded-2xl border border-zinc-200 bg-white p-4 shadow-xl',
        'dark:border-zinc-800 dark:bg-zinc-900',
        'transition-all duration-150',
        leaving ? 'translate-y-2 opacity-0' : 'translate-y-0 opacity-100',
      ].join(' ')}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-950">
          <svg className="h-5 w-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            이 취향, 저장해둘까요?
          </p>
          <p className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            로그인하면 찜한 게임과 취향 분석 결과가 다음 방문에도 남아요.
            추천도 본 게임을 반영해서 점점 정확해져요.
          </p>
          <div className="mt-3 flex gap-2">
            <a
              href="/login"
              onClick={() => { trackEvent('signup_nudge_click', { path: pathname }); close('login'); }}
              className="rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-purple-700"
            >
              3초 만에 시작하기
            </a>
            <button
              type="button"
              onClick={() => close('dismiss')}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-zinc-500 transition-colors hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
            >
              괜찮아요
            </button>
          </div>
        </div>
        <button
          type="button"
          aria-label="닫기"
          onClick={() => close('dismiss')}
          className="-mr-1 -mt-1 rounded p-1 text-zinc-400 transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
