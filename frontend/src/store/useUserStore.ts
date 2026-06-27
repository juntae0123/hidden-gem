/**
 * User-related store (zustand) with persistence.
 * 사용자 관련 상태 저장소 — JWT 자동 갱신 + 백엔드 로그아웃 연동.
 *
 * v4 → v5: logout에 백엔드 호출 추가 (토큰 블랙리스트)
 */
'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

const DJANGO_URL =
  process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8001';

type Theme = 'light' | 'dark';

export interface UserInfo {
  id: number;
  email: string;
  nickname: string | null;
  steam_id: string | null;
}

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
  user: UserInfo | null;
  accessToken: string | null;
  refreshToken: string | null;
  steamId: string | null;
  sessionId: string | null;

  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  toggleFavorite: (appId: number) => void;
  setLogin: (user: UserInfo) => void;
  setTokens: (tokens: { access: string; refresh: string }) => void;
  logout: () => Promise<void>;
  ensureSessionId: () => string;
}

export const useUserStore = create<UserStoreState>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      favorites: [],
      isLoggedIn: false,
      user: null,
      accessToken: null,
      refreshToken: null,
      steamId: null,
      sessionId: null,

      toggleTheme: () =>
        set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),

      setTheme: (t) => set({ theme: t }),

      toggleFavorite: (appId) =>
        set((s) => ({
          favorites: s.favorites.includes(appId)
            ? s.favorites.filter((id) => id !== appId)
            : [...s.favorites, appId],
        })),

      setLogin: (user) =>
        set({
          isLoggedIn: true,
          user,
          steamId: user.steam_id,
        }),

      setTokens: (tokens) =>
        set({
          accessToken: tokens.access,
          refreshToken: tokens.refresh,
        }),

      /**
       * Logout — blacklist refresh token + clear state.
       * 로그아웃 — 백엔드에 토큰 블랙리스트 + 프론트 상태 클리어.
       */
      logout: async () => {
        const refreshToken = get().refreshToken;

        // 백엔드에 토큰 무효화 요청 (실패해도 계속)
        if (refreshToken) {
          try {
            await fetch(`${DJANGO_URL}/api/auth/logout/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ refresh: refreshToken }),
              credentials: 'include',
            });
          } catch (e) {
            console.warn('[Logout] 백엔드 호출 실패 (무시):', e);
          }
        }

        // 프론트 상태 클리어
        set({
          isLoggedIn: false,
          user: null,
          accessToken: null,
          refreshToken: null,
          steamId: null,
        });
      },

      ensureSessionId: () => {
        const current = get().sessionId;
        if (current) return current;
        const newId = generateSessionId();
        set({ sessionId: newId });
        return newId;
      },
    }),
    {
      name: 'hidden-gem-user',
      storage: createJSONStorage(() => localStorage),
      onRehydrateStorage: () => (state) => {
        if (state && !state.sessionId && typeof window !== 'undefined') {
          state.sessionId = generateSessionId();
        }
      },
    }
  )
);
