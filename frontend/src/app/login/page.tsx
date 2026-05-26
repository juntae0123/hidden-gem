/**
 * Login page — Google OAuth2
 * 로그인 페이지 — Google 소셜 로그인
 */
'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { cn } from '@/lib/utils';

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8001';

function LoginContent() {
  const searchParams = useSearchParams();
  const error        = searchParams.get('error');

  const handleGoogleLogin = () => {
    // allauth Google 로그인 URL로 이동
    window.location.href = `${DJANGO_URL}/accounts/google/login/`;
  };

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center">
      <div className={cn(
        'w-full max-w-sm p-8 rounded-2xl',
        'bg-white dark:bg-zinc-900',
        'border border-zinc-200 dark:border-zinc-800',
        'shadow-sm'
      )}>
        {/* 로고 */}
        <div className="text-center mb-8">
          <span className="text-purple-600 text-3xl">✦</span>
          <h1 className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            Hidden Gem
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            취향에 맞는 게임을 찾아드려요
          </p>
        </div>

        {/* 에러 메시지 */}
        {error && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 text-xs text-center">
            로그인에 실패했어요. 다시 시도해주세요.
          </div>
        )}

        {/* Google 로그인 버튼 */}
        <button
          type="button"
          onClick={handleGoogleLogin}
          className={cn(
            'w-full flex items-center justify-center gap-3',
            'px-4 py-3 rounded-xl',
            'bg-white dark:bg-zinc-800',
            'border border-zinc-200 dark:border-zinc-700',
            'text-zinc-700 dark:text-zinc-200 text-sm font-medium',
            'hover:bg-zinc-50 dark:hover:bg-zinc-700',
            'transition-colors shadow-sm'
          )}
        >
          {/* Google SVG 아이콘 */}
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
            <path d="M3.964 10.706A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Google로 계속하기
        </button>

        <p className="mt-6 text-center text-[11px] text-zinc-400">
          로그인하면 취향 분석 기반 맞춤 추천을 받을 수 있어요
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
