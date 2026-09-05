/**
 * Ranking table — 사용자 무관 지표 랭킹 (R-12).
 * 랭킹 테이블. 탭마다 '근거 숫자'가 다르다:
 *   steady  발굴지수 · 리뷰 n · 긍정률
 *   rising  30일 +N건 (+x%)
 *   new     출시 D+n · 리뷰 n · 하루 x건
 * 신작에는 점수처럼 보이는 숫자를 붙이지 않는다 — 속도와 리뷰 수만.
 */
'use client';

import Link from 'next/link';
import { cn } from '@/lib/utils';
import { GameImage } from '@/components/ui/GameImage';
import type { RankingItem, RankingType } from '@/types/game';

interface RankingTableProps {
  items: RankingItem[];
  type: RankingType;
  className?: string;
}

const BADGE_STYLE: Record<string, string> = {
  '히든젬':   'bg-gradient-to-r from-purple-600 to-pink-600 text-white',
  '주목':     'bg-purple-600/10 text-purple-700 dark:text-purple-300 border border-purple-300 dark:border-purple-800',
  '떠오르는': 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border border-orange-300 dark:border-orange-800',
  '신작':     'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30',
};

function pct(v: number | null): string {
  return v === null || v === undefined ? '-' : `${Math.round(v * 100)}%`;
}

function Evidence({ item, type }: { item: RankingItem; type: RankingType }) {
  const rc = item.review_count ?? 0;
  if (type === 'steady') {
    return (
      <div className="text-right flex-shrink-0">
        <div className="font-mono text-[13px] text-purple-700 dark:text-purple-300" title="발굴 지수 = 긍정률 Wilson 하한 × 무명도 (0~100)">
          {item.gem_evidence?.toFixed(0) ?? '-'}
        </div>
        <div className="text-[10px] text-zinc-500">리뷰 {rc.toLocaleString()} · {pct(item.positive_ratio)}</div>
      </div>
    );
  }
  if (type === 'rising') {
    return (
      <div className="text-right flex-shrink-0">
        <div className="font-mono text-[13px] text-orange-700 dark:text-orange-400" title="최근 30일 리뷰 증가">
          +{(item.delta_30d ?? 0).toLocaleString()}
        </div>
        <div className="text-[10px] text-zinc-500">30일 {item.growth_30d_pct !== null ? `+${item.growth_30d_pct}%` : ''} · 총 {rc.toLocaleString()}</div>
      </div>
    );
  }
  return (
    <div className="text-right flex-shrink-0">
      <div className="font-mono text-[13px] text-emerald-700 dark:text-emerald-400" title="출시 후 하루 평균 리뷰 수 (7일 하한)">
        {item.velocity_per_day !== null ? `${item.velocity_per_day >= 10 ? item.velocity_per_day.toFixed(0) : item.velocity_per_day.toFixed(1)}/일` : '-'}
      </div>
      <div className="text-[10px] text-zinc-500">
        {item.days_since_release !== null ? `D+${item.days_since_release}` : ''} · 리뷰 {rc.toLocaleString()} · {pct(item.positive_ratio)}
      </div>
    </div>
  );
}

export function RankingTable({ items, type, className }: RankingTableProps) {
  return (
    <div className={cn('bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden', className)}>
      {items.map((it) => {
        const genres = (it.genres ?? '').split(',').map((g) => g.trim()).filter(Boolean).slice(0, 3).join(' · ');
        return (
          <Link
            key={it.app_id}
            href={`/game/${it.app_id}`}
            className={cn(
              'flex items-center gap-4 px-4 py-3',
              'border-b border-zinc-100 dark:border-zinc-800 last:border-b-0',
              'hover:bg-purple-50/40 dark:hover:bg-purple-950/10 transition-colors',
            )}
          >
            <span className={cn('w-8 text-center font-mono text-[13px] flex-shrink-0', it.rank <= 3 ? 'text-purple-600 font-semibold' : 'text-zinc-500')}>
              {String(it.rank).padStart(2, '0')}
            </span>
            <div className="w-16 h-9 rounded overflow-hidden bg-zinc-100 dark:bg-zinc-800 flex-shrink-0">
              <GameImage appId={it.app_id} name={it.name} fallback={it.header_image} size="thumbnail" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate">{it.name}</div>
              <div className="text-[11px] text-zinc-500 truncate">{genres}</div>
            </div>
            {it.badge && (
              <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0', BADGE_STYLE[it.badge] ?? 'bg-zinc-100 text-zinc-500')}>
                {it.badge}
              </span>
            )}
            <Evidence item={it} type={type} />
          </Link>
        );
      })}
    </div>
  );
}
