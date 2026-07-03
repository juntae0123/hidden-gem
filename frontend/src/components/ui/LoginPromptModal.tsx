// src/components/ui/LoginPromptModal.tsx
'use client';

interface LoginPromptModalProps {
  open: boolean;
  message?: string;
  onClose: () => void;
}

/**
 * Login prompt modal — themed alternative to window.confirm.
 * Korean: 로그인 유도 모달 — 브라우저 confirm 대신 사이트 톤에 맞춘 안내.
 * 찜/리뷰 등 로그인 필요한 액션에서 공용으로 사용.
 */
export function LoginPromptModal({ open, message, onClose }: LoginPromptModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xs rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-950">
            <svg className="h-6 w-6 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </div>
        </div>

        <p className="mt-4 text-center text-sm text-zinc-700 dark:text-zinc-300">
          {message ?? '로그인 후 이용할 수 있어요.'}
        </p>

        <div className="mt-6 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => { window.location.href = '/login'; }}
            className="w-full rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-purple-700"
          >
            로그인하기
          </button>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg px-4 py-2.5 text-sm font-medium text-zinc-500 transition-colors hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            나중에
          </button>
        </div>
      </div>
    </div>
  );
}