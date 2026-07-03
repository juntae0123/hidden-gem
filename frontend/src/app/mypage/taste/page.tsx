// src/app/mypage/taste/page.tsx
'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getTastePreference, saveTastePreference } from '@/lib/api';
import { useUserStore } from '@/store/useUserStore';
import { GENRE_CORE_METRICS, METRIC_LABELS } from '@/lib/utils';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

// 선호 장르 선택지 (DB 실제 장르 기준) / Selectable genres
const GENRES = ['액션', '어드벤처', 'RPG', '전략', '시뮬레이션', '캐주얼', '인디'];

const MAX_GENRES  = 3;   // 장르 최대 선택 수 / Max genres
const MAX_METRICS = 15;  // 지표 슬라이더 최대 수 / Max metric sliders

/**
 * Taste preference page — pick genres, then rate their core metrics.
 * Korean: 취향 설정 — 선호 장르 선택 → 그 장르들의 핵심 지표에 점수(1~5).
 * 수집만: 저장된 취향은 추후 개인화 추천에 활용 (지금은 반영 안 함).
 */
export default function TastePage() {
  const router     = useRouter();
  const isLoggedIn = useUserStore(s => s.isLoggedIn);

  const [genres,     setGenres]     = useState<string[]>([]);
  const [scores,     setScores]     = useState<Record<string, number>>({});
  const [loading,    setLoading]    = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [saved,      setSaved]      = useState(false);
  const [hydrated,   setHydrated]   = useState(false);

  useEffect(() => { setHydrated(true); }, []);

  // 저장된 취향 불러오기
  useEffect(() => {
    if (!hydrated) return;
    if (!isLoggedIn) {
      router.replace('/login');
      return;
    }
    getTastePreference()
      .then((pref) => {
        setGenres(pref.preferred_genres || []);
        setScores(pref.metric_preferences || {});
      })
      .catch(() => { /* 없으면 빈 상태 */ })
      .finally(() => setLoading(false));
  }, [hydrated, isLoggedIn, router]);

  // 고른 장르들의 핵심 지표 모음 (중복 제거, 최대 15개)
  const metricKeys = useMemo(() => {
    const keys: string[] = [];
    for (const g of genres) {
      const coreList = GENRE_CORE_METRICS[g] || [];
      for (const k of coreList) {
        if (!keys.includes(k)) keys.push(k);
      }
    }
    return keys.slice(0, MAX_METRICS);
  }, [genres]);

  // 장르 토글 (최대 3개)
  const toggleGenre = (g: string) => {
    setSaved(false);
    setGenres((prev) => {
      if (prev.includes(g)) return prev.filter((x) => x !== g);
      if (prev.length >= MAX_GENRES) return prev;  // 상한
      return [...prev, g];
    });
  };

  // 지표 점수 변경
  const setScore = (key: string, val: number) => {
    setSaved(false);
    setScores((s) => ({ ...s, [key]: val }));
  };

  const handleSave = async () => {
    setSubmitting(true);
    setSaved(false);
    try {
      // 현재 보이는 지표만 저장 (장르 바꾸면 안 보이는 건 제외)
      const cleanScores: Record<string, number> = {};
      for (const k of metricKeys) {
        cleanScores[k] = scores[k] ?? 3;  // 기본 3(보통)
      }
      await saveTastePreference({
        preferred_genres:   genres,
        metric_preferences: cleanScores,
      });
      setSaved(true);
    } catch {
      // 실패 조용히 (다시 시도 가능)
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingSpinner size="lg" label="불러오는 중..." />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
        취향 설정
      </h1>
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
        좋아하는 장르를 고르고, 어떤 요소를 중요하게 여기는지 알려주세요.
        더 잘 맞는 게임을 추천받을 수 있어요.
      </p>

      {/* 1단계: 선호 장르 */}
      <section className="mt-8">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          선호 장르
          <span className="ml-2 text-xs font-normal text-zinc-400">
            최대 {MAX_GENRES}개
          </span>
        </h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {GENRES.map((g) => {
            const active = genres.includes(g);
            const disabled = !active && genres.length >= MAX_GENRES;
            return (
              <button
                key={g}
                type="button"
                onClick={() => toggleGenre(g)}
                disabled={disabled}
                className={[
                  'rounded-full border px-4 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'border-purple-500 bg-purple-600 text-white'
                    : disabled
                      ? 'border-zinc-100 bg-zinc-50 text-zinc-300 cursor-not-allowed dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-600'
                      : 'border-zinc-200 bg-white text-zinc-700 hover:border-purple-300 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300',
                ].join(' ')}
              >
                {g}
              </button>
            );
          })}
        </div>
      </section>

      {/* 2단계: 지표 점수 (장르 골라야 나타남) */}
      {metricKeys.length > 0 && (
        <section className="mt-8">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            어떤 요소를 좋아하나요?
          </h2>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            왼쪽일수록 별로, 오른쪽일수록 중요하게 여긴다는 뜻이에요.
          </p>

          <div className="mt-5 flex flex-col gap-5">
            {metricKeys.map((key) => (
              <div key={key}>
                <div className="flex justify-between text-sm">
                  <span className="font-medium text-zinc-800 dark:text-zinc-200">
                    {METRIC_LABELS[key] ?? key}
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={5}
                  step={1}
                  value={scores[key] ?? 3}
                  onChange={(e) => setScore(key, Number(e.target.value))}
                  className="mt-2 w-full accent-purple-600"
                />
                <div className="flex justify-between text-[11px] text-zinc-400">
                  <span>별로예요</span>
                  <span>중요해요</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 저장 */}
      <div className="mt-8 flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.replace('/mypage')}
          className="rounded-lg border border-zinc-200 px-4 py-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          마이페이지로
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={submitting || genres.length === 0}
          className="flex-1 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-purple-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
        >
          {submitting ? '저장 중...' : saved ? '저장됐어요 ✓' : '저장하기'}
        </button>
      </div>
    </div>
  );
}