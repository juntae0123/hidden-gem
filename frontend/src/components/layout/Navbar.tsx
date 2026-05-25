/**
 * Top navigation bar
 * 상단 네비게이션 바
 */
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Moon, Sun, User } from 'lucide-react';
import { useEffect } from 'react';
import { useUserStore } from '@/store/useUserStore';
import { cn } from '@/lib/utils';

const TABS = [
  { href: '/', label: '홈' },
  { href: '/ranking', label: '랭킹' },
  { href: '/search', label: '취향 분석' },
];

/**
 * Sticky navigation bar with theme toggle
 * 테마 토글 포함 sticky 네비게이션
 */
export function Navbar() {
  const pathname = usePathname();
  const theme = useUserStore((s) => s.theme);
  const toggleTheme = useUserStore((s) => s.toggleTheme);

  // 테마 적용 / Apply theme to document
  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.body.style.backgroundColor = theme === 'dark' ? '#0F0F13' : '#FAFAF7';
  }, [theme]);

  return (
    <header
      className={cn(
        'sticky top-0 z-40 w-full',
        'bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md',
        'border-b border-zinc-200 dark:border-zinc-800'
      )}
    >
      <nav className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* 로고 */}
        <Link href="/" className="flex items-center gap-2">
          <span className="text-purple-600 text-lg leading-none">✦</span>
          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            Hidden Gem
          </span>
        </Link>

        {/* 탭 */}
        <div className="flex items-center gap-1">
          {TABS.map((tab) => {
            const active =
              pathname === tab.href ||
              (tab.href !== '/' && pathname.startsWith(tab.href));
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  'px-3 py-1.5 rounded-md text-[13px] transition-colors',
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
        <div className="flex items-center gap-2">
          {/* 로그인 버튼 — 사람 아이콘 */}
          <button
            type="button"
            className={cn(
              'w-8 h-8 rounded-md flex items-center justify-center',
              'border border-zinc-200 dark:border-zinc-800',
              'text-zinc-600 dark:text-zinc-300',
              'hover:border-purple-500 hover:text-purple-600',
              'transition-colors'
            )}
            aria-label="로그인"
          >
            <User className="w-4 h-4" />
          </button>

          {/* 테마 토글 */}
          <button
            type="button"
            onClick={toggleTheme}
            className={cn(
              'w-8 h-8 rounded-md flex items-center justify-center',
              'border border-zinc-200 dark:border-zinc-800',
              'text-zinc-600 dark:text-zinc-300',
              'hover:border-purple-500 hover:text-purple-600',
              'transition-colors'
            )}
            aria-label="테마 전환"
          >
            {theme === 'light' ? (
              <Moon className="w-4 h-4" />
            ) : (
              <Sun className="w-4 h-4" />
            )}
          </button>
        </div>
      </nav>
    </header>
  );
}
