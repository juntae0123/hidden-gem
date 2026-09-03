// src/app/mypage/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserStore } from '@/store/useUserStore';
import { getMe, getRecentGames, getFavorites, toggleFavoriteApi, getSteamLibrary, type MeResponse, type RecentGame, type FavoriteGame, type SteamLibrary } from '@/lib/api';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

// 코드값 → 한글 라벨 매핑
const GENDER_LABEL: Record<string, string> = {
  male: '남성',
  female: '여성',
  other: '기타',
  no_answer: '응답 안 함',
};

const AGE_LABEL: Record<string, string> = {
  '10s': '10대',
  '20s': '20대',
  '30s': '30대',
  '40s': '40대',
  '50s_plus': '50대 이상',
};

/**
 * My Page main content — profile + recently viewed + favorites.
 * Korean: 마이페이지 메인 — 내 정보 + 최근 본 게임 + 찜한 게임.
 * 제목/사이드바(취향·수정·로그아웃·탈퇴)는 layout.tsx가 담당.
 */
export default function MyPage() {
  const router     = useRouter();
  const isLoggedIn = useUserStore(s => s.isLoggedIn);

  const [me,        setMe]        = useState<MeResponse | null>(null);
  const [recent,    setRecent]    = useState<RecentGame[]>([]);
  const [favorites, setFavorites] = useState<FavoriteGame[]>([]);
  const [steamLib,  setSteamLib]  = useState<SteamLibrary | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');
  const [hydrated,  setHydrated]  = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;

    if (!isLoggedIn) {
      router.replace('/login');
      return;
    }
    Promise.all([getMe(), getRecentGames(), getFavorites()])
      .then(([meData, recentData, favData]) => {
        setMe(meData);
        setRecent(recentData);
        setFavorites(favData.favorites);
      })
      .catch(() => setError('정보를 불러오지 못했어요.'))
      .finally(() => setLoading(false));

    // Steam 라이브러리는 별도 로드 (미연동/실패 시 섹션만 숨김)
    getSteamLibrary().then(setSteamLib).catch(() => setSteamLib(null));
  }, [hydrated, isLoggedIn, router]);

  const handleRemoveFavorite = async (appId: number) => {
    setFavorites((prev) => prev.filter((g) => g.app_id !== appId));
    try {
      await toggleFavoriteApi(appId);
    } catch {
      // 실패 시 조용히 (새로고침하면 정확한 상태)
    }
  };

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center">
        <LoadingSpinner size="lg" label="불러오는 중..." />
      </div>
    );
  }

  if (error || !me) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-red-500">{error || '정보가 없어요.'}</p>
      </div>
    );
  }

  const displayName = me.nickname || me.email.split('@')[0];

  return (
    <div className="flex flex-col gap-6">
      {/* 내 정보 카드 */}
      <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-purple-100 text-xl font-semibold text-purple-600 dark:bg-purple-950">
            {displayName.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              {displayName}
            </p>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {me.email}
            </p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div className="rounded-lg bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
            <p className="text-zinc-500 dark:text-zinc-400">성별</p>
            <p className="mt-1 font-medium text-zinc-900 dark:text-zinc-100">
              {me.gender ? GENDER_LABEL[me.gender] ?? me.gender : '미설정'}
            </p>
          </div>
          <div className="rounded-lg bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
            <p className="text-zinc-500 dark:text-zinc-400">나이대</p>
            <p className="mt-1 font-medium text-zinc-900 dark:text-zinc-100">
              {me.age_group ? AGE_LABEL[me.age_group] ?? me.age_group : '미설정'}
            </p>
          </div>
        </div>
      </section>

      {/* Steam 라이브러리 (연동 시에만) */}
      {steamLib?.steam_linked && steamLib.top_games.length > 0 && (
        <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              내 Steam 라이브러리
            </h2>
            <span className="text-[12px] text-zinc-400">
              보유 {steamLib.library_count ?? steamLib.top_games.length}개 · 플레이타임 상위
            </span>
          </div>
          <ul className="mt-4 flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
            {steamLib.top_games.slice(0, 5).map((g) => (
              <li key={g.app_id} className="flex items-center justify-between py-2.5 gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-medium text-zinc-800 dark:text-zinc-200">
                    {g.name}
                  </p>
                  <p className="text-[11px] text-zinc-400">{g.playtime_hours}시간 플레이</p>
                </div>
                {g.in_db ? (
                  <Link
                    href={`/game/${g.app_id}`}
                    className="shrink-0 rounded-md bg-purple-600/10 px-2.5 py-1.5 text-[12px] font-medium text-purple-700 hover:bg-purple-600/20 dark:text-purple-300 transition-colors"
                  >
                    비슷한 숨은 명작 →
                  </Link>
                ) : (
                  <span className="shrink-0 text-[11px] text-zinc-400">분석 예정</span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-zinc-400">
            프로필이 비공개면 목록이 비어 보여요 — Steam 프로필 공개 설정을 확인하세요.
          </p>
        </section>
      )}

      {/* 최근 본 게임 */}
      <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          최근 본 게임
        </h2>

        {recent.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            아직 본 게임이 없어요. 마음에 드는 게임을 둘러보세요.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {recent.map((g) => (
              <Link
                key={g.app_id}
                href={`/game/${g.app_id}`}
                className="group rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-800 hover:border-purple-400 transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={g.header_image}
                  alt={g.name}
                  className="w-full aspect-[460/215] object-cover"
                  loading="lazy"
                />
                <div className="p-2">
                  <p className="text-xs font-medium text-zinc-800 dark:text-zinc-200 line-clamp-1">
                    {g.name}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* 찜한 게임 */}
      <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          찜한 게임
        </h2>

        {favorites.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            아직 찜한 게임이 없어요. 마음에 드는 게임에 찜을 눌러보세요.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {favorites.map((g) => (
              <div
                key={g.app_id}
                className="group relative rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-800"
              >
                <Link href={`/game/${g.app_id}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={g.header_image}
                    alt={g.name}
                    className="w-full aspect-[460/215] object-cover"
                    loading="lazy"
                  />
                  <div className="p-2">
                    <p className="text-xs font-medium text-zinc-800 dark:text-zinc-200 line-clamp-1">
                      {g.name}
                    </p>
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => handleRemoveFavorite(g.app_id)}
                  className="absolute top-1 right-1 rounded-full bg-black/60 p-1 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
                  aria-label="찜 삭제"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}