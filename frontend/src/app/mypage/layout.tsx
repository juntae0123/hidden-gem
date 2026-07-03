// src/app/mypage/layout.tsx
'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useUserStore } from '@/store/useUserStore';
import { deleteAccount } from '@/lib/api';
import { DeleteAccountModal } from '@/components/ui/DeleteAccountModal';

/**
 * My page layout with sidebar navigation.
 * Korean: 마이페이지 공통 레이아웃 — 좌측 사이드바 + 우측 콘텐츠.
 * /mypage, /mypage/taste, /mypage/edit가 이 레이아웃을 공유.
 */
export default function MyPageLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const logout   = useUserStore(s => s.logout);

  const [showDelete, setShowDelete] = useState(false);

  const handleLogout = async () => {
    await logout();
    router.replace('/');
  };

  const handleDeleteAccount = async () => {
    try {
      await deleteAccount();
      await logout();
      router.replace('/');
    } catch {
      // 실패 시 모달 유지
    }
  };

  const menus = [
    { href: '/mypage',       label: '내 정보' },
    { href: '/mypage/taste', label: '취향 설정' },
    { href: '/mypage/edit',  label: '회원정보 수정' },
  ];

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mb-6">
        마이페이지
      </h1>

      <div className="flex flex-col md:flex-row gap-6">
        {/* 사이드바 */}
        <aside className="w-full md:w-52 flex-shrink-0">
          <nav className="flex flex-col gap-1">
            {menus.map((m) => {
              const active = pathname === m.href;
              return (
                <Link
                  key={m.href}
                  href={m.href}
                  className={[
                    'rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
                    active
                      ? 'bg-purple-600 text-white'
                      : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800',
                  ].join(' ')}
                >
                  {m.label}
                </Link>
              );
            })}

            <div className="my-2 border-t border-zinc-200 dark:border-zinc-800" />

            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg px-4 py-2.5 text-left text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              로그아웃
            </button>

            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="rounded-lg px-4 py-2.5 text-left text-sm font-medium text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/20"
            >
              회원 탈퇴
            </button>
          </nav>
        </aside>

        {/* 콘텐츠 영역 */}
        <div className="flex-1 min-w-0">
          {children}
        </div>
      </div>

      <DeleteAccountModal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={handleDeleteAccount}
      />
    </div>
  );
}