/**
 * User-related store (zustand) with persistence
 * 사용자 관련 상태 저장소 — SSR-safe sessionId + 행동 로그용
 */
'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

type Theme = 'light' | 'dark';

/**
 * Generate a random session ID (21 chars, URL-safe).
 * 랜덤 세션 ID 생성 — crypto.randomUUID 우선, fallback은 수동 생성.
 */
function generateSessionId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, '').slice(0, 21);
  }
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-';
  return Array.from(
    { length: 21 },
    () => chars[Math.floor(Math.random() * chars.length)]
  ).join('');
}

interface UserStoreState {
  theme: Theme;
  favorites: number[];
  isLoggedIn: boolean;
  steamId: string | null;
  sessionId: string | null;  // nullable — SSR에서 null, 클라이언트에서 lazy 생성
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  toggleFavorite: (appId: number) => void;
  setLogin: (steamId: string | null) => void;
  ensureSessionId: () => string;  // 항상 유효한 sessionId 반환
}

/**
 * User store with localStorage persistence.
 * localStorage 영속화 적용 — sessionId는 최초 1회 생성 후 유지.
 */
export const useUserStore = create<UserStoreState>()(
  persist(
    (set, get) => ({
      theme:      'dark',
      favorites:  [],
      isLoggedIn: false,
      steamId:    null,
      sessionId:  null,  // 초기값 null → 클라이언트에서 onRehydrateStorage로 생성

      toggleTheme: () =>
        set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),

      setTheme: (t) => set({ theme: t }),

      toggleFavorite: (appId) =>
        set((s) => ({
          favorites: s.favorites.includes(appId)
            ? s.favorites.filter((id) => id !== appId)
            : [...s.favorites, appId],
        })),

      setLogin: (steamId) =>
        set({ steamId, isLoggedIn: steamId !== null }),

      /**
       * Ensure a valid sessionId exists and return it.
       * 유효한 sessionId 보장 — 없으면 생성 후 저장.
       */
      ensureSessionId: () => {
        const current = get().sessionId;
        if (current) return current;
        const newId = generateSessionId();
        set({ sessionId: newId });
        return newId;
      },
    }),
    {
      name:    'hidden-gem-user',
      storage: createJSONStorage(() => localStorage),
      // localStorage 복원 후 sessionId 없으면 생성
      onRehydrateStorage: () => (state) => {
        if (state && !state.sessionId && typeof window !== 'undefined') {
          state.sessionId = generateSessionId();
        }
      },
    }
  )
);