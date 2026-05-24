/**
 * Loading skeleton components — shimmer effect placeholders
 * 로딩 스켈레톤 컴포넌트 — 시머 효과 플레이스홀더
 */
import { cn } from '@/lib/utils';

/** Base skeleton primitive */
function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-pulse rounded-md bg-zinc-200 dark:bg-zinc-800', className)} />
  );
}

/** Game card skeleton */
export function GameCardSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
      <Skeleton className="w-full aspect-[16/9] rounded-none" />
      <div className="flex flex-col gap-2.5 p-3.5">
        <Skeleton className="h-4 w-3/4" />
        <div className="flex gap-1">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
        </div>
        <div className="space-y-1 mt-1">
          <div className="flex justify-between">
            <Skeleton className="h-3 w-10" />
            <Skeleton className="h-3 w-16" />
          </div>
          <Skeleton className="h-1.5 w-full" />
        </div>
        <Skeleton className="h-3 w-2/3 mt-1" />
      </div>
    </div>
  );
}

/** Game grid skeleton — 3 columns */
export function GameGridSkeleton({ count = 9 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <GameCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Ranking row skeleton */
function RankingRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-zinc-100 dark:border-zinc-800">
      <Skeleton className="w-8 h-4" />
      <Skeleton className="w-16 h-9 flex-shrink-0" />
      <div className="flex-1 space-y-1">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-3 w-1/3" />
      </div>
      <Skeleton className="w-12 h-5" />
    </div>
  );
}

/** Ranking list skeleton */
export function RankingListSkeleton({ count = 10 }: { count?: number }) {
  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden">
      {Array.from({ length: count }).map((_, i) => (
        <RankingRowSkeleton key={i} />
      ))}
    </div>
  );
}

/** Game detail skeleton */
export function GameDetailSkeleton() {
  return (
    <article className="w-full">
      <div className="w-full rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800">
        <Skeleton className="w-full aspect-[460/215] rounded-none" />
        <div className="p-6 space-y-3">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-4 w-3/4" />
          <div className="flex gap-2 mt-3">
            <Skeleton className="h-6 w-16" />
            <Skeleton className="h-6 w-16" />
          </div>
        </div>
      </div>
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 flex items-center justify-center">
          <Skeleton className="w-64 h-64 rounded-full" />
        </div>
        <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-12" />
              </div>
              <Skeleton className="h-1.5 w-full" />
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
