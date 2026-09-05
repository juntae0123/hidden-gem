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
  isFamous?: boolean;
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
  isFamous = false,
  daysSinceRelease,
  reviewCount,
  size = 'sm',
  className,
}: LifecycleBadgeProps) {
  if (lifecycle === 'new') {
    const d = daysSinceRelease ?? null;
    const rc = reviewCount ?? 0;
    const thin = rc < 100;
    const when = d !== null ? `D+${d}` : '얼마 안 됨';
    // 두 축: 나이(신작)와 인지도(is_famous). 8.7만 리뷰 신작은 '신작 · 빠르게 검증됨'
    const label = isFamous ? `신작 · 빠르게 검증됨` : `신작${d !== null ? ` · D+${d}` : ''}`;
    return (
      <span
        title={
          isFamous
            ? `신작 리그 · 출시 ${when} · 리뷰 ${rc.toLocaleString()}건 — 신작인데 이미 검증됐어요`
            : thin
              ? `신작 리그 · 출시 ${when} · 첫 리뷰 ${rc}건 — 아직 조용한 게임이에요. 첫 리뷰를 남겨보세요`
              : `신작 리그 · 출시 ${when} · 리뷰 ${rc.toLocaleString()}건 — 빠르게 자리 잡는 중`
        }
        className={cn(
          'inline-flex items-center rounded-md font-medium cursor-help',
          'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30',
          SIZE[size], className,
        )}
      >
        {label}
      </span>
    );
  }
  if (lifecycle === 'upcoming') {
    return (
      <span
        title="아직 출시 전이에요"
        className={cn(
          'inline-flex items-center rounded-md font-medium cursor-help',
          'bg-sky-500/10 text-sky-700 dark:text-sky-400 border border-sky-500/30',
          SIZE[size], className,
        )}
      >
        출시 예정
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
