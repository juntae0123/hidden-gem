/**
 * User-related store (zustand) with persistence.
 * 사용자 관련 상태 저장소 — JWT 자동 갱신 + 백엔드 로그아웃 연동.
 *
 * v4 → v5: logout에 백엔드 호출 추가 (토큰 블랙리스트)
 * v5 → v6: UserInfo에 온보딩 필드 추가 (gender/age_group/onboarding_completed)
 * v6 → v7: 찜 DB 연동 (toggleFavorite 낙관적 업데이트 + loadFavorites, persist 제외)
 */
'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { toggleFavoriteApi, getFavorites } from '@/lib/api';

const DJANGO_URL =
  process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8001';

type Theme = 'light' | 'dark';

export interface UserInfo {
  id: number;
  email: string;
  nickname: string | null;
  steam_id: string | null;
  gender: string | null;
  age_group: string | null;
  onboarding_completed: boolean;
  first_name?: string;
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
  loadFavorites: () => Promise<void>;   // 로그인 시 DB에서 찜 로드
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

      /**
       * Toggle favorite with DB sync (optimistic update).
       * 찜 토글 — 화면 먼저 바꾸고(낙관적), DB 반영. 실패 시 롤백.
       * 비로그인이면 아무것도 안 함 (호출 측에서 로그인 유도).
       */
      toggleFavorite: (appId) => {
        const { isLoggedIn, favorites } = get();

        // 비로그인은 무시 (UI에서 로그인 안내 처리)
        if (!isLoggedIn) return;

        // 1) 낙관적 업데이트 — 화면 먼저 바꿈
        const wasFav = favorites.includes(appId);
        set({
          favorites: wasFav
            ? favorites.filter((id) => id !== appId)
            : [...favorites, appId],
        });

        // 2) DB 반영 — 실패하면 롤백
        toggleFavoriteApi(appId).catch(() => {
          set((s) => ({
            favorites: wasFav
              ? [...s.favorites, appId]
              : s.favorites.filter((id) => id !== appId),
          }));
        });
      },

      /**
       * Load favorites from DB (call on login / app init).
       * DB에서 찜 목록 로드 — 로그인 시 store 채움.
       */
      loadFavorites: async () => {
        if (!get().isLoggedIn) return;
        try {
          const { app_ids } = await getFavorites();
          set({ favorites: app_ids });
        } catch {
          // 실패해도 조용히 (찜 안 보일 뿐)
        }
      },

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

        // 프론트 상태 클리어 (찜도 비움 — 남의 찜 안 보이게)
        set({
          isLoggedIn: false,
          user: null,
          accessToken: null,
          refreshToken: null,
          steamId: null,
          favorites: [],
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
      // favorites는 DB가 진실 — localStorage에 저장 안 함 (제외)
      partialize: (state) => {
        const { favorites, ...rest } = state;
        return rest;
      },
      onRehydrateStorage: () => (state) => {
        if (state && !state.sessionId && typeof window !== 'undefined') {
          state.sessionId = generateSessionId();
        }
      },
    }
  )
);