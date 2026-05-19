/**
 * Top navigation bar
 * 상단 네비게이션 바
 */
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Moon, Sun } from 'lucide-react';
import { useEffect } from 'react';
import { useUserStore } from '@/store/useUserStore';
import { cn } from '@/lib/utils';

const TABS = [
  { href: '/', label: '홈' },
  { href: '/ranking', label: '랭킹' },
  { href: '/search', label: '취향 분석' },
];

/**
 * Diamond logo SVG icon
 * 다이아몬드 로고 아이콘
 */
function DiamondIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 0L14 7L7 14L0 7L7 0Z" fill="#7C3AED" />
    </svg>
  );
}

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
        {/* 로고 / Logo */}
        <Link href="/" className="flex items-center gap-2">
          <DiamondIcon />
          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            Hidden Gem
          </span>
        </Link>

        {/* 탭 / Tabs */}
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

        {/* 우측 액션 / Right actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={cn(
              'px-3 py-1.5 rounded-md text-[12px]',
              'border border-zinc-200 dark:border-zinc-800',
              'text-zinc-600 dark:text-zinc-300',
              'hover:border-purple-500 hover:text-purple-600'
            )}
          >
            Steam 로그인
          </button>
          <button
            type="button"
            onClick={toggleTheme}
            className={cn(
              'w-8 h-8 rounded-md flex items-center justify-center',
              'border border-zinc-200 dark:border-zinc-800',
              'text-zinc-600 dark:text-zinc-300',
              'hover:border-purple-500 hover:text-purple-600'
            )}
            aria-label="theme toggle"
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
