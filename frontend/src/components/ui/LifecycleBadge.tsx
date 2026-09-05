/**
 * Lifecycle badge — 신작 / 정착(히든젬·주목) / 유명.
 * 생애주기 뱃지 (decisions R-11/R-12).
 *
 * 원칙: 신작에는 점수처럼 보이는 숫자를 붙이지 않는다. "판단 보류"를 그대로 보여준다.
 * 사용자가 신작을 클릭해 리뷰를 남기게 하는 것이 이 사이트가 신작에 해주는 일이다.
 */
import { cn } from '@/lib/utils';
import type { Lifecycle } from '@/types/game';

interface LifecycleBadgeProps {
  lifecycle?: Lifecycle;
  daysSinceRelease?: number | null;
  reviewCount?: number | null;
  size?: 'sm' | 'md';
  className?: string;
}

const SIZE = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-[11px]',
} as const;

export function LifecycleBadge({
  lifecycle,
  daysSinceRelease,
  reviewCount,
  size = 'sm',
  className,
}: LifecycleBadgeProps) {
  if (lifecycle === 'new') {
    const d = daysSinceRelease ?? null;
    const rc = reviewCount ?? 0;
    const thin = rc < 100;
    return (
      <span
        title={
          thin
            ? `출시 ${d !== null ? `D+${d}` : '얼마 안 됨'}, 리뷰 ${rc}건 — 데이터가 적어 발굴 판단은 보류 중이에요`
            : `출시 ${d !== null ? `D+${d}` : '얼마 안 됨'}, 리뷰 ${rc.toLocaleString()}건 — 신작이지만 근거는 충분해요`
        }
        className={cn(
          'inline-flex items-center rounded-md font-medium cursor-help',
          'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30',
          SIZE[size], className,
        )}
      >
        신작{d !== null ? ` · D+${d}` : ''}
      </span>
    );
  }
  if (lifecycle === 'famous') {
    return (
      <span
        title="리뷰 2만 건 이상 — 이미 검증된 게임이라 발굴 지수는 매기지 않아요"
        className={cn(
          'inline-flex items-center rounded-md font-medium cursor-help',
          'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border border-zinc-200 dark:border-zinc-700',
          SIZE[size], className,
        )}
      >
        검증됨
      </span>
    );
  }
  return null;
}
