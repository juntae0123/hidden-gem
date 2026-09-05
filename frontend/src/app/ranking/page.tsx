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
  { key: 'steady', label: '스테디 히든젬', desc: '출시 6개월 지난 게임 중, 인지도 대비 평가가 높은 순 — 리뷰 30건 이상만' },
  { key: 'rising', label: '요즘 뜨는',     desc: '최근 30일 리뷰 증가율 순 — 유명작이 독식하지 않게 비율로 봅니다' },
  { key: 'new',    label: '신작',         desc: '출시 6개월 이내, 하루 평균 리뷰 수 순 — 데이터가 적어 발굴 판단은 보류 중' },
];

export default function RankingPage() {
  const [type, setType]   = useState<RankingType>('steady');
  const [genre, setGenre] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useRanking(type, genre, 30);
  const items = data?.items ?? [];
  const tab = TABS.find((t) => t.key === type)!;

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
              type === t.key
                ? 'border-purple-600 text-purple-700 dark:text-purple-300'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

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
          <p className="mt-1 text-[12px] text-zinc-500">{data.note || '리뷰 이력이 30일치 모이면 계산됩니다.'}</p>
        </div>
      )}

      {!isLoading && !error && data?.status === 'ok' && items.length === 0 && (
        <ErrorState type="not-found" variant="inline" title="조건에 맞는 게임이 없어요" description="장르를 바꿔보세요" />
      )}

      {!isLoading && !error && items.length > 0 && <RankingTable items={items} type={type} />}

      {type === 'new' && items.length > 0 && (
        <p className="text-[12px] text-zinc-500">
          신작은 리뷰가 적어 발굴 지수를 매기지 않아요. 여기서 마음에 드는 게임을 골라 리뷰를 남기는 것이 다음 히든젬을 만드는 일이에요.
        </p>
      )}
    </div>
  );
}
