/**
 * Top navigation bar
 * 상단 네비게이션 바
 *
 * v2 → v3: 로그인 상태에 따라 User 아이콘 / 닉네임 + 로그아웃 표시
 * v3 → v4: 드롭다운에 마이페이지 추가 + 취향 분석 탭 강조
 */
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Moon, Sun, User, LogOut, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useUserStore } from '@/store/useUserStore';
import { cn } from '@/lib/utils';
import { trackEvent } from '@/lib/umami';

const TABS = [
  { href: '/',        label: '홈' },
  { href: '/ranking', label: '랭킹' },
  { href: '/search',  label: '취향 분석', highlight: true },
];

export function Navbar() {
  const pathname    = usePathname();
  const theme       = useUserStore((s) => s.theme);
  const toggleTheme = useUserStore((s) => s.toggleTheme);
  const isLoggedIn  = useUserStore((s) => s.isLoggedIn);
  const user        = useUserStore((s) => s.user);
  const logout      = useUserStore((s) => s.logout);

  // 드롭다운 상태
  const [showMenu, setShowMenu] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.body.style.backgroundColor = theme === 'dark' ? '#0F0F13' : '#FAFAF7';
  }, [theme]);

  // 바깥 클릭 시 드롭다운 닫기
  useEffect(() => {
    if (!showMenu) return;
    const handler = () => setShowMenu(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [showMenu]);

  return (
    <header className={cn(
      'sticky top-0 z-40 w-full',
      'bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md',
      'border-b border-zinc-200 dark:border-zinc-800'
    )}>
      <nav className="max-w-7xl mx-auto px-3 sm:px-6 h-14 sm:h-[68px] flex items-center justify-between gap-2">
        {/* 로고 */}
        <Link href="/" className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <span className="text-purple-600 text-xl sm:text-2xl leading-none">✦</span>
          {/* 좁은 화면(≤399px)에서는 이름을 숨긴다 — 히어로에 같은 이름이 바로 나온다.
              키운 글씨를 그대로 두면 '랭 킹' 처럼 메뉴가 세로로 쪼개진다 (2026-09-07 모바일 사고) */}
          <span className="hidden min-[400px]:inline text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100 whitespace-nowrap">
            Hidden Gem
          </span>
        </Link>

        {/* 탭 */}
        <div className="flex items-center gap-0.5 sm:gap-1 shrink-0">
          {TABS.map((tab) => {
            const active =
              pathname === tab.href ||
              (tab.href !== '/' && pathname.startsWith(tab.href));

            // 취향 분석 — 강조 탭 (핵심 기능)
            if (tab.highlight) {
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  onClick={() => trackEvent('nav_taste_click')}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg font-semibold transition-colors whitespace-nowrap',
                    'px-2.5 py-2 text-[13px] sm:px-4 sm:py-2.5 sm:text-[15px]',
                    active
                      ? 'bg-purple-600 text-white'
                      : 'bg-purple-600/10 text-purple-700 dark:text-purple-300 hover:bg-purple-600/20'
                  )}
                >
                  <Sparkles className="hidden sm:block w-4 h-4" />
                  {tab.label}
                </Link>
              );
            }

            // 일반 탭 (홈/랭킹)
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  'rounded-lg font-medium transition-colors whitespace-nowrap',
                  'px-2.5 py-2 text-[13px] sm:px-4 sm:py-2.5 sm:text-[15px]',
                  active
                    ? 'bg-purple-600/10 text-purple-700 dark:text-purple-300'
                    : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>

        {/* 우측 액션 */}
        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          {/* 로그인 상태에 따른 분기 */}
          {mounted && isLoggedIn && user ? (
            // 로그인됨 — 닉네임 + 드롭다운
            <div className="relative">
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setShowMenu(v => !v); }}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1.5 sm:px-2.5 rounded-md',
                  'border border-zinc-200 dark:border-zinc-800',
                  'text-zinc-700 dark:text-zinc-200 text-[12px]',
                  'hover:border-purple-500 transition-colors'
                )}
              >
                <User className="w-3.5 h-3.5 text-purple-600" />
                <span className="max-w-[56px] sm:max-w-[80px] truncate">
                  {user.nickname || user.email.split('@')[0]}
                </span>
              </button>

              {showMenu && (
                <div className={cn(
                  'absolute right-0 top-full mt-1 w-40',
                  'bg-white dark:bg-zinc-900',
                  'border border-zinc-200 dark:border-zinc-800',
                  'rounded-xl shadow-md py-1 z-50'
                )}>
                  <div className="px-3 py-2 text-[11px] text-zinc-400 border-b border-zinc-100 dark:border-zinc-800">
                    {user.email}
                  </div>

                  {/* 마이페이지 */}
                  <Link
                    href="/mypage"
                    onClick={() => setShowMenu(false)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[13px] text-zinc-600 dark:text-zinc-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/20 transition-colors"
                  >
                    <User className="w-3.5 h-3.5" />
                    마이페이지
                  </Link>

                  {/* 로그아웃 */}
                  <button
                    type="button"
                    onClick={logout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[13px] text-zinc-600 dark:text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors border-t border-zinc-100 dark:border-zinc-800"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          ) : (
            // 비로그인 — 아이콘 버튼
            <Link
              href="/login"
              className={cn(
                'w-8 h-8 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center',
                'border border-zinc-200 dark:border-zinc-800',
                'text-zinc-600 dark:text-zinc-300',
                'hover:border-purple-500 hover:text-purple-600',
                'transition-colors'
              )}
              aria-label="로그인"
            >
              <User className="w-4 h-4" />
            </Link>
          )}

          {/* 테마 토글 */}
          <button
            type="button"
            onClick={toggleTheme}
            className={cn(
              'w-8 h-8 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center',
              'border border-zinc-200 dark:border-zinc-800',
              'text-zinc-600 dark:text-zinc-300',
              'hover:border-purple-500 hover:text-purple-600',
              'transition-colors'
            )}
            aria-label="테마 전환"
          >
            {mounted && theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
        </div>
      </nav>
    </header>
  );
}