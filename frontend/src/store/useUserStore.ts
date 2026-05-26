/**
 * User-related store (zustand) with persistence
 * 사용자 관련 상태 저장소 — SSR-safe sessionId + JWT 인증
 *
 * v3 → v4:
 *   - JWT 토큰 저장 (access, refresh)
 *   - 유저 정보 저장 (id, email, nickname)
 *   - setLogin, setTokens, logout 추가
 */
'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

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
  // ==================== 인증 ====================
  isLoggedIn: boolean;
  user: UserInfo | null;
  accessToken: string | null;
  refreshToken: string | null;
  steamId: string | null;           // 하위 호환
  sessionId: string | null;
  // ==================== 액션 ====================
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  toggleFavorite: (appId: number) => void;
  setLogin: (user: UserInfo) => void;
  setTokens: (tokens: { access: string; refresh: string }) => void;
  logout: () => void;
  ensureSessionId: () => string;
}

export const useUserStore = create<UserStoreState>()(
  persist(
    (set, get) => ({
      theme:        'dark',
      favorites:    [],
      isLoggedIn:   false,
      user:         null,
      accessToken:  null,
      refreshToken: null,
      steamId:      null,
      sessionId:    null,

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
          accessToken:  tokens.access,
          refreshToken: tokens.refresh,
        }),

      logout: () =>
        set({
          isLoggedIn:   false,
          user:         null,
          accessToken:  null,
          refreshToken: null,
          steamId:      null,
        }),

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
      onRehydrateStorage: () => (state) => {
        if (state && !state.sessionId && typeof window !== 'undefined') {
          state.sessionId = generateSessionId();
        }
      },
    }
  )
);