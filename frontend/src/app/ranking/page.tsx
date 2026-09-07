/**
 * Ranking page — 진짜 랭킹 (R-12).
 * 랭킹 페이지 v3.
 *
 * v2 → v3:
 *   - 이전 버전은 장르 프리셋을 by-preference 에 던진 결과였다 — 랭킹이 아니었다.
 *   - 사용자 무관 지표로 정렬하는 GET /games/ranking 3종으로 교체.
 *   - 탭: 스테디 히든젬(발굴 지수) / 요즘 뜨는(30일 증가율) / 신작(초기 속도)
 *   - 신작과 정착·유명작을 같은 줄에 놓지 않는다. 각 탭이 다른 질문에 답한다.
 */
'use client';

import { useState } from 'react';
import { RankingTable } from '@/components/game/RankingTable';
import { ErrorState } from '@/components/ui/ErrorState';
import { RankingListSkeleton } from '@/components/ui/LoadingSkeleton';
import { useRanking } from '@/hooks/useRecommend';
import { GENRES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { RankingType } from '@/types/game';

const TABS: { key: RankingType; label: string; desc: string }[] = [
  { key: 'steady', label: '숨은 명작',   desc: '많이 안 알려졌는데 해본 사람들 평이 좋은 게임' },
  { key: 'rising', label: '요즘 뜨는',   desc: '최근 한 달 사이 리뷰가 빠르게 늘고 있는 게임' },
  { key: 'new',    label: '신작',       desc: '최근 6개월 안에 나온 게임만' },
];

// 신작 리그 안의 두 시선: 지금 달리는 신작(180일 안에 모은 리뷰 수, 평가 70%+) / 아직 조용한 신작(리뷰 100 미만, 평가 순)  — R-17
const NEW_VIEWS: { key: RankingType; label: string; desc: string }[] = [
  { key: 'new',       label: '많이 해본', desc: '나온 뒤로 리뷰가 많이 쌓인 순' },
  { key: 'new_quiet', label: '아직 조용한', desc: '리뷰 100건이 안 되는 게임 중 평이 좋은 순' },
];

export default function RankingPage() {
  const [type, setType]   = useState<RankingType>('steady');
  const [genre, setGenre] = useState<string | null>(null);

  const isNewTab = type === 'new' || type === 'new_quiet';
  const { data, isLoading, error, refetch } = useRanking(type, genre, 30);
  const items = data?.items ?? [];
  const tab = TABS.find((t) => t.key === (isNewTab ? 'new' : type))!;

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">랭킹</h1>
        <p className="text-sm text-zinc-500 mt-1">{tab.desc}</p>
      </header>

      {/* 탭 — 생애주기별로 다른 질문 */}
      <div className="flex items-center gap-1 border-b border-zinc-200 dark:border-zinc-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setType(t.key)}
            className={cn(
              'px-3 py-2 text-[13px] -mb-px border-b-2',
              (t.key === 'new' ? isNewTab : type === t.key)
                ? 'border-purple-600 text-purple-700 dark:text-purple-300'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 신작 리그 하위 시선 */}
      {isNewTab && (
        <div className="flex flex-wrap items-center gap-2">
          {NEW_VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => setType(v.key)}
              title={v.desc}
              className={cn(
                'px-3 py-1.5 rounded-lg text-[12px] border',
                type === v.key
                  ? 'bg-emerald-500/10 border-emerald-500 text-emerald-700 dark:text-emerald-300'
                  : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-emerald-400',
              )}
            >
              {v.label}
            </button>
          ))}
          <span className="text-[11px] text-zinc-500">{NEW_VIEWS.find((v) => v.key === type)?.desc}</span>
        </div>
      )}

      {/* 장르 칩 — 모든 탭 공통 */}
      <div className="flex flex-wrap gap-2">
        {GENRES.map((g) => {
          const key = g === '전체' ? null : g;
          const on = genre === key;
          return (
            <button
              key={g}
              type="button"
              onClick={() => setGenre(key)}
              className={cn(
                'px-3 py-1.5 rounded-full text-[12px] border',
                on
                  ? 'bg-purple-600/10 border-purple-500 text-purple-700 dark:text-purple-300'
                  : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-purple-400',
              )}
            >
              {g}
            </button>
          );
        })}
      </div>

      {isLoading && <RankingListSkeleton />}
      {error && <ErrorState error={error as Error} onRetry={() => refetch()} variant="inline" title="랭킹을 가져오지 못했어요" />}

      {!isLoading && !error && data?.status === 'collecting' && (
        <div className="rounded-xl p-8 text-center bg-orange-500/[0.04] border border-orange-500/30">
          <div className="text-orange-700 dark:text-orange-400 text-sm font-medium">데이터 쌓는 중</div>
          <p className="mt-1 text-[12px] text-zinc-500">{data.note || '리뷰가 얼마나 늘었는지 보려면 한 달치 기록이 필요해요. 매주 쌓고 있습니다.'}</p>
        </div>
      )}

      {!isLoading && !error && data?.status === 'ok' && items.length === 0 && (
        <ErrorState type="not-found" variant="inline" title="조건에 맞는 게임이 없어요" description="장르를 바꿔보세요" />
      )}

      {!isLoading && !error && items.length > 0 && <RankingTable items={items} type={type} />}

      {isNewTab && items.length > 0 && (
        <p className="text-[12px] text-zinc-500">
          갓 나온 게임은 리뷰가 쌓일 시간이 없어서, 오래된 게임과 같은 줄에 세우면 늘 집니다. 그래서 따로 봅니다.
          마음에 드는 게임에 첫 리뷰를 남겨주면 다음 사람이 그 게임을 찾습니다.
        </p>
      )}
    </div>
  );
}
