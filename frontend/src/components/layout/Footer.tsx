/**
 * Footer component
 * 하단 푸터 컴포넌트
 */
import { cn } from '@/lib/utils';

/**
 * Site footer
 * 사이트 푸터
 */
export function Footer() {
  return (
    <footer
      className={cn(
        'w-full border-t border-zinc-200 dark:border-zinc-800',
        'bg-white dark:bg-zinc-950',
        'mt-16'
      )}
    >
      <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-[12px] text-zinc-500">
          <span aria-hidden className="text-purple-600">
            ✦
          </span>
          <span>Hidden Gem · Steam 인디게임 AI 추천</span>
        </div>
        <div className="text-[11px] text-zinc-400">
          © {new Date().getFullYear()} Hidden Gem. Made with ☕ + Claude.
        </div>
      </div>
    </footer>
  );
}
