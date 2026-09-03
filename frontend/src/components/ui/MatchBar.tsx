/**
 * Match score bar — compact (card) and full (detail) modes.
 * 매치 점수 바 — 컴팩트(카드)와 풀(상세) 두 모드.
 *
 * v1 → v2:
 *   - "52" (단위 불명확) → "52 / 99" (절대 점수 명확)
 *   - compact prop 추가 (게임 카드용)
 *   - 점수 등급별 그라데이션
 */
import { cn } from '@/lib/utils';
import {
  getScoreGradient,
  getMatchLabel,
  scoreToWidthPercent,
  isAnchorScore,
  MATCH_TIERS,
} from '@/lib/score';

interface MatchBarProps {
  /** 매치 점수 (0~99, 앵커는 100) */
  value: number;
  /** 표시 컨텍스트 */
  context?: 'search' | 'similar' | 'preference';
  /** 컴팩트 모드 (게임 카드용) */
  compact?: boolean;
  className?: string;
}

/**
 * Match bar with clear unit display ("52 / 99").
 * 단위가 명확한 매치 바 ("52 / 99").
 */
export function MatchBar({
  value,
  context = 'preference',
  compact = false,
  className,
}: MatchBarProps) {
  // 기준 게임 앵커 처리
  if (isAnchorScore(value)) {
    return (
      <div className={cn('flex items-center gap-1', className)}>
        <span className="text-purple-600 dark:text-purple-400 text-[11px] font-medium">
          ★ 기준 게임
        </span>
      </div>
    );
  }

  const displayValue = Math.round(value);
  const widthPct    = scoreToWidthPercent(value);
  const gradient    = getScoreGradient(value);
  const label       = getMatchLabel(value);
  const contextLabel = context === 'similar' ? '유사도' : '매치';

  // ==================== 컴팩트 모드 (카드용) ====================
  if (compact) {
    return (
      <div className={cn('space-y-1', className)}>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-500 dark:text-zinc-400">
            {contextLabel}
          </span>
          <span className="text-[11px] font-mono font-medium">
            <span className="text-zinc-900 dark:text-zinc-100">{displayValue}</span>
            <span className="text-zinc-400 dark:text-zinc-600"> / 99</span>
          </span>
        </div>
        <div className="h-1 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', `bg-gradient-to-r ${gradient}`)}
            style={{ width: `${widthPct}%` }}
          />
        </div>
      </div>
    );
  }

  // ==================== 풀 모드 (상세용) ====================
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-mono font-semibold text-zinc-900 dark:text-zinc-100">
            {displayValue}
          </span>
          <span className="text-xs text-zinc-400">/ 99</span>
          {label && (
            <span
              className={cn(
                'ml-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
                value >= MATCH_TIERS.EXCELLENT
                  ? 'bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300'
                  : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300'
              )}
            >
              {label}
            </span>
          )}
        </div>
      </div>
      <div className="h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', `bg-gradient-to-r ${gradient}`)}
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  );
}
