/**
 * Preference analysis page — 49 metrics with categories and tooltips.
 * 취향 분석 페이지.
 *
 * v3: ensureSessionId 사용 (SSR-safe)
 */
'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import * as Slider from '@radix-ui/react-slider';
import { GameGrid } from '@/components/game/GameGrid';
import { ErrorState } from '@/components/ui/ErrorState';
import { GameGridSkeleton } from '@/components/ui/LoadingSkeleton';
import { useRecommendByPreference, useNewLeague } from '@/hooks/useRecommend';
import { METRIC_LABELS, cn } from '@/lib/utils';
import { METRIC_DESCRIPTIONS, METRIC_CATEGORIES_KO } from '@/lib/constants';
import { recordTasteAction } from '@/lib/api';
import { useUserStore } from '@/store/useUserStore';
import { DnaCard } from '@/components/ui/DnaCard';

/** 콜드스타트 완화용 프리셋 — 클릭 한 번으로 슬라이더가 잡히고 바로 추천 */
const PRESETS: { label: string; prefs: Record<string, number> }[] = [
  { label: '아늑한 힐링',   prefs: { cozy_factor: 9, time_pressure: 1.5, horror_factor: 0.5, difficulty_accessibility: 8, soundtrack_impact: 7 } },
  { label: '하드코어 전략', prefs: { strategic_depth: 9, management_complexity: 8, learning_curve: 8, reflex_demand: 2, replay_value: 8 } },
  { label: '감성 서사',     prefs: { narrative_depth: 9, choice_consequence: 8, melancholy: 7, lore_richness: 8, action_pacing: 2.5 } },
  { label: '손맛 액션',     prefs: { reflex_demand: 9, action_pacing: 9, time_pressure: 7, visual_spectacle: 7, learning_curve: 5 } },
  { label: '공포 서바이벌', prefs: { horror_factor: 9, time_pressure: 7, exploration_reward: 7, cozy_factor: 0.5, session_length: 6 } },
];

const buildInitialPrefs = (): Record<string, number> => {
  const prefs: Record<string, number> = {};
  Object.values(METRIC_CATEGORIES_KO).forEach(({ metrics }) => {
    metrics.forEach((m) => { prefs[m] = 5.0; });
  });
  return prefs;
};

function MetricSlider({
  metricKey, value, onChange,
}: {
  metricKey: string;
  value: number;
  onChange: (key: string, val: number) => void;
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const label       = METRIC_LABELS[metricKey] || metricKey;
  const description = METRIC_DESCRIPTIONS[metricKey] || '';

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 relative">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] text-zinc-700 dark:text-zinc-300 font-medium">{label}</span>
          <button
            type="button"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
            aria-label={`${label} 설명 보기`}
            className="w-4 h-4 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400 text-[10px] flex items-center justify-center hover:bg-purple-100 hover:text-purple-600 transition-colors"
          >
            ?
          </button>
        </div>
        <span className="text-[12px] font-mono text-purple-600 dark:text-purple-400 font-medium">
          {value.toFixed(1)} / 10
        </span>
      </div>

      {showTooltip && description && (
        <div className="absolute z-20 left-0 top-full mt-1 w-full px-3 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-[11px] rounded-lg shadow-lg leading-relaxed">
          {description}
        </div>
      )}

      <Slider.Root
        className="relative flex items-center select-none touch-none w-full h-5"
        min={0} max={10} step={0.5}
        value={[value]}
        onValueChange={(v) => onChange(metricKey, v[0])}
      >
        <Slider.Track className="bg-zinc-200 dark:bg-zinc-800 relative grow rounded-full h-1.5">
          <Slider.Range className="absolute bg-purple-600 rounded-full h-full" />
        </Slider.Track>
        <Slider.Thumb
          className="block w-4 h-4 bg-white border-2 border-purple-600 rounded-full shadow focus:outline-none focus:ring-2 focus:ring-purple-400 cursor-pointer"
          aria-label={label}
        />
      </Slider.Root>
    </div>
  );
}

export default function SearchPage() {
  const [prefs, setPrefs]               = useState<Record<string, number>>(buildInitialPrefs);
  const [activeCategory, setActiveCategory] = useState<string>('vibe');
  // R-12: 리뷰 100 미만 신작은 기본 제외. 켜면 '신작 · D+n' 뱃지와 함께 들어온다.
  const [includeNew, setIncludeNew]         = useState<boolean>(false);
  // 신작 리그: 마지막으로 제출한 취향으로 신작끼리만 다시 매칭 (개발자 취지 — 신생 게임을 보호하는 그들만의 리그)
  const [leaguePrefs, setLeaguePrefs]       = useState<Record<string, number> | null>(null);
  const league = useNewLeague(leaguePrefs, 6);
  const mutation        = useRecommendByPreference();
  const ensureSessionId = useUserStore(s => s.ensureSessionId);
  const isLoggedIn      = useUserStore(s => s.isLoggedIn);
  const swipeApplied    = useRef(false);

  // 스와이프 온보딩에서 넘어온 초기 취향 적용 + 즉시 추천
  useEffect(() => {
    if (swipeApplied.current) return;
    swipeApplied.current = true;
    let raw: string | null = null;
    try {
      raw = sessionStorage.getItem('hg_swipe_prefs');
      if (raw) sessionStorage.removeItem('hg_swipe_prefs');
    } catch { return; }
    if (!raw) return;
    try {
      const swipePrefs = JSON.parse(raw) as Record<string, number>;
      const merged = { ...buildInitialPrefs(), ...swipePrefs };
      const nonNeutral = Object.fromEntries(
        Object.entries(merged).filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
      );
      // effect 내 동기 setState 회피 (react-hooks/set-state-in-effect)
      queueMicrotask(() => {
        setPrefs(merged);
        // R-8: 중립(5.0) 그대로인 지표는 보내지 않는다 — 49개 전부 5.0 을 보내면 '모든 축에서 평범한 게임'이 만점을 받는다
        if (Object.keys(nonNeutral).length > 0) {
          mutation.mutate({ preferences: nonNeutral, count: 12, includeNew });
          setLeaguePrefs(nonNeutral);
        }
      });
    } catch { /* 파싱 실패 시 기본 슬라이더로 */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const results       = mutation.data?.recommendations ?? [];
  const categories    = Object.entries(METRIC_CATEGORIES_KO);
  const adjustedCount = Object.entries(prefs).filter(([, v]) => Math.abs(v - 5.0) >= 0.5).length;

  const setPref = (key: string, value: number) => {
    setPrefs((p) => ({ ...p, [key]: value }));
  };

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    const merged = { ...buildInitialPrefs(), ...preset.prefs };
    setPrefs(merged);
    recordTasteAction({
      session_id:  ensureSessionId(),
      action_type: 'search',
      context: { query: `preset:${preset.label}`, referrer: '/search' },
    });
    mutation.mutate({ preferences: preset.prefs, count: 12, includeNew });
    setLeaguePrefs(preset.prefs);
  };

  const [emptyHint, setEmptyHint] = useState(false);

  const handleSubmit = () => {
    const nonNeutral = Object.fromEntries(
      Object.entries(prefs).filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
    );
    if (Object.keys(nonNeutral).length === 0) {
      // R-8: 취향 없음은 추천이 아니다 — 랭킹으로 안내
      setEmptyHint(true);
      return;
    }
    setEmptyHint(false);
    // R-8: 아무것도 안 움직였으면 빈 preferences 를 보낸다 (백엔드가 발견 모드로 처리). 49개 5.0 폴백은 D-26 을 프런트에서 재현했다.
    const toSend = nonNeutral;

    recordTasteAction({
      session_id:  ensureSessionId(),
      action_type: 'search',
      context: {
        adjusted_metrics: Object.keys(nonNeutral),
        adjusted_count:   Object.keys(nonNeutral).length,
        referrer:         '/search',
      },
    });

    mutation.mutate({ preferences: toSend, count: 12, includeNew });
    setLeaguePrefs(toSend);
  };

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-xl font-semibold">취향 분석</h1>
        <p className="text-sm text-zinc-500 mt-1">
          각 지표를 조정해 당신만의 이상적인 게임을 찾아보세요.{' '}
          <span className="text-purple-600">?</span> 버튼을 누르면 지표 설명을 볼 수 있어요.
        </p>
        <Link
          href="/onboarding/swipe"
          className="mt-3 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-purple-600/10 border border-purple-300 dark:border-purple-800 text-purple-700 dark:text-purple-300 text-sm font-medium hover:bg-purple-600/20 transition-colors"
        >
          슬라이더가 낯설다면 — 카드 스와이프로 취향 잡기 →
        </Link>

        {/* 프리셋: 빈 슬라이더 49개 앞에서 멈추지 않게 한 클릭 시작점 */}
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-zinc-500 mr-1">빠른 시작</span>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => applyPreset(p)}
              className="px-3 py-1.5 rounded-full text-[12px] border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 hover:border-purple-400 hover:text-purple-600 dark:hover:text-purple-300 transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>
      </header>

      <div className="flex flex-wrap gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-3">
        {categories.map(([key, { label }]) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveCategory(key)}
            className={cn(
              'px-3 py-1.5 rounded-full text-[12px] border transition-all',
              activeCategory === key
                ? 'bg-purple-600/10 border-purple-500 text-purple-700 dark:text-purple-300 font-medium'
                : 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-purple-400'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {categories.map(([catKey, { metrics }]) => (
        <div
          key={catKey}
          className={cn('grid grid-cols-1 md:grid-cols-2 gap-3', activeCategory !== catKey && 'hidden')}
        >
          {metrics.map((metricKey) => (
            <MetricSlider
              key={metricKey}
              metricKey={metricKey}
              value={prefs[metricKey] ?? 5.0}
              onChange={setPref}
            />
          ))}
        </div>
      ))}

      {adjustedCount > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-[12px] text-zinc-500">조정된 지표 ({adjustedCount}개):</span>
          {Object.entries(prefs)
            .filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
            .map(([key, val]) => (
              <span
                key={key}
                className="px-2 py-0.5 rounded-full text-[11px] bg-purple-600/10 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800"
              >
                {METRIC_LABELS[key]} {val > 5 ? '↑' : '↓'} {val.toFixed(1)}
              </span>
            ))}
        </div>
      )}

      {emptyHint && (
        <p className="text-center text-[12px] text-orange-700 dark:text-orange-400">
          지표를 하나 이상 움직여주세요. 취향 없이 좋은 게임을 보고 싶다면{' '}
          <Link href="/ranking" className="underline">랭킹</Link>으로 가세요.
        </p>
      )}

      {/* R-12: 신작 포함 토글 — 기본 꺼짐 */}
      <label className="flex items-center justify-center gap-2 text-[12px] text-zinc-600 dark:text-zinc-400 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={includeNew}
          onChange={(e) => setIncludeNew(e.target.checked)}
          className="accent-purple-600 w-3.5 h-3.5"
        />
        <span>
          신작도 메인 결과에 섞어 보기
          <span className="text-zinc-400 dark:text-zinc-500"> — 꺼져 있어도 아래 &lsquo;신작 리그&rsquo;에서 따로 볼 수 있어요</span>
        </span>
      </label>

      <div className="flex justify-center">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={mutation.isPending}
          className={cn(
            'px-8 py-3 rounded-xl bg-purple-600 text-white text-[14px] font-medium',
            'hover:bg-purple-700 transition-colors disabled:opacity-60 shadow-sm hover:shadow-md'
          )}
        >
          {mutation.isPending ? '분석 중...' : '✦ 내 취향에 맞는 게임 찾기'}
        </button>
      </div>

      <section>
        {mutation.error && (
          <ErrorState error={mutation.error as Error} onRetry={handleSubmit} variant="inline" title="추천을 가져오지 못했어요" />
        )}
        {mutation.isPending && !mutation.error && (
          <>
            <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 mb-4">당신의 취향을 분석 중...</h2>
            <GameGridSkeleton count={12} />
          </>
        )}
        {!mutation.isPending && !mutation.error && mutation.isSuccess && results.length === 0 && (
          <ErrorState type="not-found" variant="inline" title="조건에 맞는 게임이 없어요" description="지표 조건을 조금 완화해보세요" />
        )}
        {!mutation.isPending && !mutation.error && results.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300">
                당신의 취향에 맞는 게임 {results.length}개
              </h2>
              <DnaCard prefs={prefs} games={results} />
            </div>
            {!isLoggedIn && (
              <p className="mb-4 text-[12px] text-zinc-500">
                이 취향은 페이지를 떠나면 사라져요 —{' '}
                <Link href="/login" className="text-purple-600 dark:text-purple-400 hover:underline">로그인</Link>
                하면 저장되고 다음 추천에 반영됩니다.
              </p>
            )}
            <GameGrid games={results} />
          </>
        )}
      </section>

      {/* 신작 리그 — 신작끼리만 같은 취향으로 경쟁. 정착 게임과 발굴 지수로 비교하지 않는다. */}
      {leaguePrefs && (
        <section className="rounded-2xl border border-emerald-500/30 bg-emerald-500/[0.04] p-5">
          <div className="flex items-baseline justify-between gap-3 mb-1">
            <h2 className="text-[14px] font-semibold text-emerald-800 dark:text-emerald-300">신작 리그</h2>
            <Link href="/ranking" className="text-[12px] text-emerald-700 dark:text-emerald-400 hover:underline">신작 랭킹 보기 →</Link>
          </div>
          <p className="text-[12px] text-zinc-500 mb-4">
            출시 6개월 이내 게임끼리만 같은 취향으로 매칭했어요. 리뷰가 적어 발굴 점수는 아직 매기지 않아요 —
            마음에 드는 게임에 첫 리뷰를 남기는 사람이 다음 히든젬을 만듭니다.
          </p>
          {league.isLoading && <GameGridSkeleton count={6} />}
          {league.data && league.data.recommendations.length === 0 && (
            <p className="text-[12px] text-zinc-500">이 취향에 맞는 신작이 아직 없어요.</p>
          )}
          {league.data && league.data.recommendations.length > 0 && (
            <GameGrid games={league.data.recommendations} />
          )}
        </section>
      )}
    </div>
  );
}
