/**
 * Gem potential badge with tier system.
 * 등급 시스템이 있는 gem potential 뱃지.
 *
 * v1 → v2: 임계값 95 → 70 (v5 점수 체계 기준)
 * Tier: legendary(90+) / epic(80+) / rare(70+) / common(미표시)
 */
import { cn } from '@/lib/utils';
import { getGemTier, GEM_TIERS } from '@/lib/score';

interface GemBadgeProps {
  score: number;
  showAlways?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const TIER_STYLES = {
  legendary: 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-sm border border-purple-400/50',
  epic:      'bg-purple-600/95 text-white shadow-sm',
  rare:      'bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200',
  common:    'bg-zinc-100 dark:bg-zinc-800 text-zinc-500',
} as const;

const SIZE_STYLES = {
  sm: 'px-1.5 py-0.5 text-[10px] gap-0.5',
  md: 'px-2 py-0.5 text-[11px] gap-1',
  lg: 'px-2.5 py-1 text-xs gap-1',
} as const;

/**
 * Gem badge — shown at 70+ by default (previously 95+).
 * Gem 뱃지 — 기본 70+ 표시 (기존 95+에서 하향).
 */
export function GemBadge({
  score,
  showAlways = false,
  size = 'md',
  className,
}: GemBadgeProps) {
  if (!showAlways && score < GEM_TIERS.RARE) return null;

  const tier = getGemTier(score);

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-md font-mono font-medium',
        TIER_STYLES[tier],
        SIZE_STYLES[size],
        className
      )}
    >
      <span aria-hidden>✦</span>
      <span>{Math.round(score)}</span>
    </div>
  );
}
