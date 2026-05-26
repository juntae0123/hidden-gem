/**
 * OAuth2 callback page — receive JWT tokens and save to store.
 * OAuth2 콜백 페이지 — JWT 토큰 수신 후 스토어에 저장.
 *
 * Django가 /auth/callback?access=...&refresh=... 으로 리다이렉트.
 * 토큰을 저장하고 메인 페이지로 이동.
 */
'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useUserStore } from '@/store/useUserStore';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8001';

function CallbackContent() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const setLogin     = useUserStore(s => s.setLogin);
  const setTokens    = useUserStore(s => s.setTokens);

  useEffect(() => {
    const access  = searchParams.get('access');
    const refresh = searchParams.get('refresh');

    if (!access || !refresh) {
      // 토큰 없음 → 로그인 실패
      router.replace('/login?error=token_missing');
      return;
    }

    // 토큰 저장 + 유저 정보 조회
    setTokens({ access, refresh });

    // 유저 정보 조회 (/api/auth/me/)
    fetch(`${DJANGO_URL}/api/auth/me/`, {
      headers: { Authorization: `Bearer ${access}` },
    })
      .then(res => res.json())
      .then(user => {
        setLogin(user);
        router.replace('/');  // 메인 페이지로
      })
      .catch(() => {
        router.replace('/login?error=fetch_failed');
      });
  }, [searchParams, setLogin, setTokens, router]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <LoadingSpinner size="lg" label="로그인 중..." />
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<LoadingSpinner size="lg" />}>
      <CallbackContent />
    </Suspense>
  );
}
