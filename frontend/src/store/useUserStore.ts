/**
 * User-related store (zustand) with persistence
 * 사용자 관련 상태 저장소 - 테마, 찜한 게임, 로그인 정보
 */
'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'light' | 'dark';

interface UserStoreState {
  theme: Theme;
  favorites: number[];
  isLoggedIn: boolean;
  steamId: string | null;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  toggleFavorite: (appId: number) => void;
  setLogin: (steamId: string | null) => void;
}

/**
 * User store with localStorage persistence
 * localStorage 영속화 적용된 사용자 스토어
 */
export const useUserStore = create<UserStoreState>()(
  persist(
    (set) => ({
      theme: 'dark',
      favorites: [],
      isLoggedIn: false,
      steamId: null,
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
    }),
    { name: 'hidden-gem-user' }
  )
);
