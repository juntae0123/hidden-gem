// src/app/mypage/edit/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getMe, submitOnboarding } from '@/lib/api';
import { useUserStore } from '@/store/useUserStore';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

const GENDERS = [
  { value: 'male',      label: '남성' },
  { value: 'female',    label: '여성' },
  { value: 'other',     label: '기타' },
  { value: 'no_answer', label: '응답 안 함' },
];

const AGE_GROUPS = [
  { value: '10s',      label: '10대' },
  { value: '20s',      label: '20대' },
  { value: '30s',      label: '30대' },
  { value: '40s',      label: '40대' },
  { value: '50s_plus', label: '50대 이상' },
];

/**
 * Edit profile page — update nickname/gender/age_group (reuses onboarding API).
 * Korean: 회원정보 수정 — 닉네임/성별/나이대 변경. 온보딩 API 재활용.
 */
export default function EditProfilePage() {
  const router     = useRouter();
  const isLoggedIn = useUserStore(s => s.isLoggedIn);
  const setLogin   = useUserStore(s => s.setLogin);

  const [firstName,  setFirstName]  = useState('');
  const [nickname,   setNickname]   = useState('');
  const [gender,     setGender]     = useState('');
  const [ageGroup,   setAgeGroup]   = useState('');
  const [loading,    setLoading]    = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error,      setError]      = useState('');
  const [hydrated,   setHydrated]   = useState(false);

  useEffect(() => { setHydrated(true); }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (!isLoggedIn) {
      router.replace('/login');
      return;
    }
    getMe()
      .then((me) => {
        setFirstName((me.first_name as string) || '');
        setNickname(me.nickname || '');
        setGender(me.gender || '');
        setAgeGroup(me.age_group || '');
      })
      .catch(() => setError('정보를 불러오지 못했어요.'))
      .finally(() => setLoading(false));
  }, [hydrated, isLoggedIn, router]);

  const canSubmit = gender !== '' && ageGroup !== '' && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError('');
    try {
      const updated = await submitOnboarding({
        first_name: firstName.trim(),
        nickname:   nickname.trim(),
        gender,
        age_group:  ageGroup,
      });
      setLogin(updated as unknown as Parameters<typeof setLogin>[0]);
      router.replace('/mypage');
    } catch (e) {
      setError((e as Error).message || '저장에 실패했어요. 다시 시도해주세요.');
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center">
        <LoadingSpinner size="lg" label="불러오는 중..." />
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
        회원정보 수정
      </h2>
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
        닉네임과 성별·나이대를 수정할 수 있어요.
      </p>

      <div className="mt-6 flex flex-col gap-6">
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
            이름 <span className="text-zinc-400">(선택)</span>
          </label>
          <input
            type="text"
            value={firstName}
            onChange={e => setFirstName(e.target.value)}
            placeholder="이름"
            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-purple-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
            닉네임 <span className="text-zinc-400">(선택)</span>
          </label>
          <input
            type="text"
            value={nickname}
            onChange={e => setNickname(e.target.value)}
            placeholder="서비스에서 보일 이름"
            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-purple-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            성별 <span className="text-purple-500">*</span>
          </label>
          <div className="grid grid-cols-2 gap-2">
            {GENDERS.map(g => (
              <button
                key={g.value}
                type="button"
                onClick={() => setGender(g.value)}
                className={[
                  'rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                  gender === g.value
                    ? 'border-purple-500 bg-purple-600 text-white'
                    : 'border-zinc-200 bg-white text-zinc-700 hover:border-purple-300 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300',
                ].join(' ')}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            나이대 <span className="text-purple-500">*</span>
          </label>
          <div className="grid grid-cols-3 gap-2">
            {AGE_GROUPS.map(a => (
              <button
                key={a.value}
                type="button"
                onClick={() => setAgeGroup(a.value)}
                className={[
                  'rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                  ageGroup === a.value
                    ? 'border-purple-500 bg-purple-600 text-white'
                    : 'border-zinc-200 bg-white text-zinc-700 hover:border-purple-300 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300',
                ].join(' ')}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => router.replace('/mypage')}
            className="flex-1 rounded-lg border border-zinc-200 px-4 py-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex-1 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-purple-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
          >
            {submitting ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}