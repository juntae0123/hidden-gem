/**
 * Gem potential badge with tier system.
 * 등급 시스템이 있는 gem potential 뱃지.
 *
 * v1 → v2: 임계값 95 → 70 (v5 점수 체계 기준)
 * Tier: legendary(90+) / epic(80+) / rare(70+) / common(미표시)
 */
import { cn } from '@/lib/utils';
import { getGemTier, GEM_TIERS, getGemEvidenceTier } from '@/lib/score';

interface GemBadgeProps {
  score: number;
  /** R-3 리뷰 실측 발굴 지수. 주어지면 legacy score 대신 이걸로 등급을 매긴다 (히든젬 ≥60 / 주목 45~60). null = 근거 없음 → 미표시 */
  evidence?: number | null;
  showAlways?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const EVIDENCE_STYLES = {
  hidden_gem: 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-sm border border-purple-400/50',
  notable:    'bg-purple-600/10 text-purple-700 dark:text-purple-300 border border-purple-300 dark:border-purple-800',
  none:       'bg-zinc-100 dark:bg-zinc-800 text-zinc-500',
} as const;

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
  evidence,
  showAlways = false,
  size = 'md',
  className,
}: GemBadgeProps) {
  // R-3: 실측 지수가 있으면 그걸로. 근거 없음(null)은 뱃지를 만들지 않는다 — 0 과 다르다.
  if (evidence !== undefined) {
    if (evidence === null) return null;
    const et = getGemEvidenceTier(evidence);
    if (!showAlways && et === 'none') return null;
    const label = et === 'hidden_gem' ? '히든젬' : et === 'notable' ? '주목' : '';
    return (
      <div
        title={`발굴 지수 ${Math.round(evidence)} — Steam 리뷰 실측: 긍정률(Wilson 하한) × 인지도 대비 (매치율과 다른 값)`}
        className={cn(
          'inline-flex items-center rounded-md font-mono font-medium cursor-help',
          EVIDENCE_STYLES[et],
          SIZE_STYLES[size],
          className
        )}
      >
        <span aria-hidden>✦</span>
        <span>{Math.round(evidence)}</span>
        {label && <span className="font-sans">{label}</span>}
      </div>
    );
  }

  if (!showAlways && score < GEM_TIERS.RARE) return null;

  const tier = getGemTier(score);

  return (
    <div
      title={`숨은 명작 지수 ${Math.round(score)} — 인지도 대비 품질 (매치율과 다른 값)`}
      className={cn(
        'inline-flex items-center rounded-md font-mono font-medium cursor-help',
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
