// src/components/ui/DeleteAccountModal.tsx
'use client';

import { useState } from 'react';

interface DeleteAccountModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}

/**
 * Account deletion confirmation modal — requires typing to confirm.
 * Korean: 회원 탈퇴 확인 모달 — 실수 방지 위해 문구 입력 요구.
 * 되돌릴 수 없는 액션이라 명확한 경고 + 확인 입력.
 */
export function DeleteAccountModal({ open, onClose, onConfirm }: DeleteAccountModalProps) {
  const [confirmText, setConfirmText] = useState('');
  const [submitting, setSubmitting]   = useState(false);

  if (!open) return null;

  const canDelete = confirmText.trim() === '탈퇴' && !submitting;

  const handleConfirm = async () => {
    if (!canDelete) return;
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-red-600 dark:text-red-400">
          정말 탈퇴하시겠어요?
        </h2>

        <div className="mt-3 space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
          <p>탈퇴하면 다음이 삭제돼요:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>계정 정보 (이메일, 닉네임, 성별·나이대)</li>
            <li>취향 설정, 찜한 게임</li>
          </ul>
          <p className="text-red-500 font-medium">
            이 작업은 되돌릴 수 없어요.
          </p>
        </div>

        <div className="mt-5">
          <label className="block text-sm text-zinc-600 dark:text-zinc-400 mb-1.5">
            확인을 위해 <span className="font-semibold text-zinc-900 dark:text-zinc-100">탈퇴</span>를 입력해주세요.
          </label>
          <input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="탈퇴"
            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-red-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </div>

        <div className="mt-6 flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-zinc-200 px-4 py-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!canDelete}
            className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
          >
            {submitting ? '처리 중...' : '탈퇴하기'}
          </button>
        </div>
      </div>
    </div>
  );
}