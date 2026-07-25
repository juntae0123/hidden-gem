/**
 * Footer component.
 * 하단 푸터 — 개인정보처리방침 + 이용약관 링크 추가.
 *
 * v1 → v2: 법적 링크 추가
 */
import Link from 'next/link';
import { cn } from '@/lib/utils';

export function Footer() {
  return (
    <footer
      className={cn(
        'w-full border-t border-zinc-200 dark:border-zinc-800',
        'bg-white dark:bg-zinc-950',
        'mt-16'
      )}
    >
      <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col gap-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-[12px] text-zinc-500">
            <span aria-hidden className="text-purple-600">✦</span>
            <span>Hidden Gem · Steam 게임 AI 추천</span>
          </div>

          <nav className="flex items-center gap-4 text-[12px]">
            <Link
              href="/privacy"
              className="text-zinc-500 hover:text-purple-600 transition-colors"
            >
              개인정보처리방침
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">·</span>
            <Link
              href="/terms"
              className="text-zinc-500 hover:text-purple-600 transition-colors"
            >
              이용약관
            </Link>
          </nav>
        </div>

        <div className="text-[11px] text-zinc-400 text-center md:text-left">
             © 2026 Hidden Gem. Made with ☕ + AI.
        </div>
      </div>
    </footer>
  );
}
