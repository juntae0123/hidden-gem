// src/components/ui/VibeChips.tsx
'use client';

import { useVibes } from '@/hooks/useRecommend';
import type { VibeItem } from '@/lib/api';

interface VibeChipsProps {
  /** 현재 선택된 vibe key (없으면 null) */
  selected: string | null;
  /** 칩 클릭 핸들러 — 같은 칩 재클릭 시 선택 해제 */
  onSelect: (vibeKey: string | null) => void;
}

/**
 * Horizontal scrollable vibe chip row.
 * Korean: 가로 스크롤 Vibe 칩 줄. 클릭 시 추천, 재클릭 시 해제.
 */
export function VibeChips({ selected, onSelect }: VibeChipsProps) {
  const { data: vibes, isLoading, error } = useVibes();

  // 로딩 — 칩 자리만 스켈레톤
  if (isLoading) {
    return (
      <div className="flex gap-2 overflow-x-auto pb-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-9 w-24 shrink-0 animate-pulse rounded-full bg-zinc-200 dark:bg-zinc-800"
          />
        ))}
      </div>
    );
  }

  // 에러 시 칩 영역 숨김 (메인 추천은 그대로 동작)
  if (error || !vibes) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
      {vibes.map((v: VibeItem) => {
        const active = v.key === selected;
        return (
          <button
            key={v.key}
            type="button"
            title={v.description}
            onClick={() => onSelect(active ? null : v.key)}
            className={[
              'shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium',
              'border transition-colors whitespace-nowrap',
              active
                ? 'border-purple-500 bg-purple-600 text-white'
                : 'border-zinc-200 bg-white text-zinc-700 hover:border-purple-300 hover:bg-purple-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800',
            ].join(' ')}
          >
            <span className="mr-1">{v.emoji}</span>
            {v.label}
          </button>
        );
      })}
    </div>
  );
}