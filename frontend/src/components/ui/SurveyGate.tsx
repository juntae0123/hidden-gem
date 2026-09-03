// src/components/ui/SurveyGate.tsx
'use client';

import { useEffect, useState } from 'react';
import { useUserStore } from '@/store/useUserStore';
import { getPendingSurvey, type PendingSurvey } from '@/lib/api';
import { SurveyModal } from './SurveyModal';

const SNOOZE_KEY = 'survey-snooze-until';

/**
 * Survey gate — checks for pending survey on mount, shows modal if any.
 * Korean: 설문 문지기 — 로그인 유저 재방문 시 설문 대상 조회, 있으면 모달.
 * "1주일 안 보기"는 localStorage 스누즈로 처리.
 */
export function SurveyGate() {
  const isLoggedIn = useUserStore(s => s.isLoggedIn);
  const [survey, setSurvey]   = useState<PendingSurvey | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => { setHydrated(true); }, []);

  useEffect(() => {
    if (!hydrated || !isLoggedIn) return;

    // 스누즈 중이면 스킵
    try {
      const until = localStorage.getItem(SNOOZE_KEY);
      if (until && Date.now() < Number(until)) return;
    } catch { /* ignore */ }

    // 설문 대상 조회 (한 박자 늦게 — 페이지 로드 방해 안 하게)
    const t = setTimeout(() => {
      getPendingSurvey()
        .then((s) => { if (s) setSurvey(s); })
        .catch(() => { /* 조용히 무시 */ });
    }, 2000);

    return () => clearTimeout(t);
  }, [hydrated, isLoggedIn]);

  if (!survey) return null;

  // "1주일 안 보기" — 스누즈 설정 후 닫기
  const snooze = () => {
    try {
      localStorage.setItem(SNOOZE_KEY, String(Date.now() + 7 * 24 * 60 * 60 * 1000));
    } catch { /* ignore */ }
    setSurvey(null);
  };

  return (
    <SurveyModal
      survey={survey}
      onClose={() => setSurvey(null)}   // 그냥 닫기 (다음에 또 뜰 수 있음)
      onDone={() => setSurvey(null)}    // 설문 완료/스킵 (DB에 기록됨 → 다시 안 뜸)
    />
  );
}