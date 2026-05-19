/**
 * Gem potential badge
 * gem potential 점수 뱃지 (90+ 표시)
 */
import { cn } from '@/lib/utils';

interface GemBadgeProps {
  score: number;
  showAlways?: boolean;
  className?: string;
}

/**
 * Render gem badge if score is high enough
 * 점수가 충분히 높을 때만 뱃지 렌더링
 */
export function GemBadge({
  score,
  showAlways = false,
  className,
}: GemBadgeProps) {
  if (!showAlways && score < 90) return null;

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-md',
        'bg-purple-600/95 text-white',
        'text-[11px] font-mono font-medium',
        'shadow-sm',
        className
      )}
    >
      <span aria-hidden>✦</span>
      <span>{Math.round(score)}</span>
    </div>
  );
}
