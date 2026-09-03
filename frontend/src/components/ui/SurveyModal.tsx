// src/components/ui/SurveyModal.tsx
'use client';

import { useEffect, useState } from 'react';
import { getGameDetail, submitSurvey, type PendingSurvey } from '@/lib/api';
import { getGenreCoreMetrics, METRIC_LABELS } from '@/lib/utils';

interface SurveyModalProps {
  survey: PendingSurvey;
  onClose: () => void;           // 닫기 (그냥 닫음)
  onDone: () => void;            // 설문 완료/스킵 → 다시 안 뜸
}

interface MetricItem {
  key:   string;
  label: string;
  our:   number;  // 0~10
}

/**
 * Game survey modal — step1 (played?) + step2 (metric sliders).
 * Korean: 지표 검증 설문 — 1단계 즐겼나, 2단계 핵심지표 5단계 평가.
 */
export function SurveyModal({ survey, onClose, onDone }: SurveyModalProps) {
  const [step, setStep]       = useState<1 | 2>(1);
  const [metrics, setMetrics] = useState<MetricItem[]>([]);
  // 지표별 유저 점수 (1~5), 기본 3(보통)
  const [scores, setScores]   = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);

  // 게임 지표 로드 → 핵심 3개 추출
  useEffect(() => {
    let alive = true;
    getGameDetail(survey.app_id)
      .then((game) => {
        if (!alive) return;
        const core = getGenreCoreMetrics(
          game.metrics as unknown as Record<string, number | boolean | null>,
          survey.genres ?? '',
          6
        );
        // 점수 높은 순 상위 3개
        const top3 = [...core]
          .sort((a, b) => b.value - a.value)
          .slice(0, 3)
          .map((m) => ({
            key:   m.key,
            label: METRIC_LABELS[m.key] ?? m.key,
            our:   m.value,
          }));
        setMetrics(top3);
        setScores(Object.fromEntries(top3.map((m) => [m.key, 3])));
      })
      .catch(() => {
        // 지표 못 불러오면 설문 무의미 → 조용히 종료
        onDone();
      });
    return () => { alive = false; };
  }, [survey.app_id, survey.genres, onDone]);

  // "안 해봤어요"
  const handleNotPlayed = async () => {
    setSubmitting(true);
    try {
      await submitSurvey({ app_id: survey.app_id, played: false });
    } catch { /* 무시 */ }
    onDone();
  };

  // 2단계 제출
  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitSurvey({
        app_id: survey.app_id,
        played: true,
        ratings: metrics.map((m) => ({
          metric:     m.key,
          our_score:  m.our,
          user_score: scores[m.key] ?? 3,
        })),
      });
    } catch { /* 무시 */ }
    onDone();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        {/* 닫기 (크게, 명확) */}
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-sm text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800"
          >
            ✕ 닫기
          </button>
        </div>

        {/* 게임 헤더 */}
        <div className="mt-1 flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={survey.header_image}
            alt={survey.name}
            className="h-12 w-24 rounded object-cover"
          />
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 line-clamp-2">
            {survey.name}
          </p>
        </div>

        {step === 1 ? (
          <div className="mt-5">
            <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              이 게임, 재밌게 즐기셨나요? 🎮
            </p>
            <p className="mt-2 text-sm text-purple-600 dark:text-purple-400">
              알려주시면 취향을 더 정확히 파악해서
              당신께 맞는 게임을 추천해드려요.
            </p>

            <div className="mt-5 flex gap-2">
              <button
                type="button"
                disabled={submitting || metrics.length === 0}
                onClick={() => setStep(2)}
                className="flex-1 rounded-lg bg-purple-600 px-4 py-3 text-sm font-semibold text-white hover:bg-purple-700 disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
              >
                네, 해봤어요
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleNotPlayed}
                className="flex-1 rounded-lg border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                아직 안 해봤어요
              </button>
            </div>

            {/* 작게 — 도피로 */}
            <div className="mt-4 flex justify-center gap-4 text-xs text-zinc-400">
              <button type="button" onClick={onDone} className="hover:underline">
                1주일 동안 안 보기
              </button>
              <button type="button" onClick={onClose} className="hover:underline">
                닫기
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-5">
            <p className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              실제로 어떻게 느끼셨나요?
            </p>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              느낀 정도를 표시해주세요.
            </p>

            <div className="mt-5 flex flex-col gap-5">
              {metrics.map((m) => (
                <div key={m.key}>
                  <div className="flex justify-between text-sm">
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">
                      {m.label}, 어느 정도였나요?
                    </span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={5}
                    step={1}
                    value={scores[m.key] ?? 3}
                    onChange={(e) =>
                      setScores((s) => ({ ...s, [m.key]: Number(e.target.value) }))
                    }
                    className="mt-2 w-full accent-purple-600"
                  />
                  <div className="flex justify-between text-[11px] text-zinc-400">
                    <span>전혀</span>
                    <span>매우</span>
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              disabled={submitting}
              onClick={handleSubmit}
              className="mt-6 w-full rounded-lg bg-purple-600 px-4 py-3 text-sm font-semibold text-white hover:bg-purple-700 disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
            >
              {submitting ? '제출 중...' : '제출하기'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}