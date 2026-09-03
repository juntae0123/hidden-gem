// src/app/onboarding/page.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { submitOnboarding } from '@/lib/api';
import { useUserStore } from '@/store/useUserStore';

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
 * Onboarding page — collect name/nickname/gender/age_group.
 * Korean: 온보딩 — 이름/닉네임(선택) + 성별/나이대(필수) 수집.
 */
export default function OnboardingPage() {
  const router   = useRouter();
  const user     = useUserStore(s => s.user);
  const setLogin = useUserStore(s => s.setLogin);

  // user 객체에서 안전하게 읽기 (UserInfo 타입에 없는 필드도 허용)
  const u = user as Record<string, unknown> | null;

  const [firstName, setFirstName] = useState(
    (u?.first_name as string) || ''
  );
  const [nickname,  setNickname]  = useState(
    (u?.nickname as string) || ''
  );
  const [gender,    setGender]    = useState('');
  const [ageGroup,  setAgeGroup]  = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error,     setError]     = useState('');

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
      router.replace('/onboarding/swipe');  // 가입 정보 → 취향 스캔으로 이어짐
    } catch (e) {
      setError((e as Error).message || '저장에 실패했어요. 다시 시도해주세요.');
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
        환영해요 👋
      </h1>
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          더 잘 맞는 게임을 추천해드리기 위해 몇 가지만 여쭤볼게요.
          <br />
          좋아하는 장르·게임 같은 자세한 취향은 나중에{' '}
          <span className="text-purple-500 font-medium">마이페이지</span>에서
          더 설정할 수 있어요.
      </p>

      <div className="mt-8 flex flex-col gap-6">
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

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="mt-2 w-full rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-purple-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
        >
          {submitting ? '저장 중...' : '시작하기'}
        </button>
      </div>
    </div>
  );
}