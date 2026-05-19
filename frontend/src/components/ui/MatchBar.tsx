/**
 * Match rate progress bar
 * 매치율 표시 프로그레스 바
 */
import { cn, toPercent } from '@/lib/utils';

interface MatchBarProps {
  value: number; // 0~1 or 0~100
  label?: string;
  className?: string;
}

/**
 * Horizontal match progress bar with percentage
 * 가로형 매치율 바 - 퍼센트 표기 포함
 */
export function MatchBar({ value, label = '매치율', className }: MatchBarProps) {
  // 0~1 범위면 100배 / Scale if value is in 0~1
  const pct = value <= 1 ? value * 100 : value;
  const clamped = Math.max(0, Math.min(100, pct));

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
          {label}
        </span>
        <span className="text-[11px] font-mono text-purple-600 dark:text-purple-400 font-medium">
          {toPercent(clamped / 100)}
        </span>
      </div>
      <div className="w-full h-1 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-purple-600 dark:bg-purple-500 rounded-full transition-all duration-500"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
