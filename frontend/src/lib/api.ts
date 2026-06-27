/**
 * API client for Hidden Gem backend.
 * 백엔드 통신용 axios 인스턴스 + 토큰 자동 갱신.
 *
 * v3 → v4:
 *   - Request interceptor: JWT 자동 추가
 *   - Response interceptor: 401 → refresh token → 재요청
 *   - 갱신 실패: 로그아웃 + /login 리다이렉트
 *   - 동시 401 요청 큐잉 (중복 갱신 방지)
 */
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type {
  Game,
  GameDetail,
  RecommendationResponse,
} from '@/types/game';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

const DJANGO_URL =
  process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8001';

/**
 * Axios instance with default config.
 * 기본 axios 인스턴스.
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,  // 쿠키 포함 (CORS_ALLOW_CREDENTIALS 대응)
});

// ==================== Request Interceptor ====================

/**
 * Request interceptor — attach JWT to every request.
 * 요청 인터셉터 — 모든 요청에 JWT 자동 추가.
 */
apiClient.interceptors.request.use(
  async (config) => {
    // SSR 환경 스킵
    if (typeof window === 'undefined') return config;

    // dynamic import (SSR 안전)
    const { useUserStore } = await import('@/store/useUserStore');
    const token = useUserStore.getState().accessToken;

    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ==================== Token Refresh Queue ====================

/**
 * 토큰 갱신 중인지 플래그.
 * 동시 401 요청이 여러 번 refresh 호출하는 것 방지.
 */
let isRefreshing = false;

/**
 * 갱신 대기 중인 요청 큐.
 * Korean: 토큰 갱신 끝나면 일괄 처리할 요청 큐.
 */
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

/**
 * Process queued requests after token refresh.
 * 큐에 쌓인 요청들 일괄 처리.
 */
function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else if (token) resolve(token);
  });
  failedQueue = [];
}

// ==================== Response Interceptor ====================

/**
 * Response interceptor — auto refresh on 401.
 * 응답 인터셉터 — 401 시 자동 토큰 갱신.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // 401이 아니거나, 이미 재시도한 요청이면 그대로 에러
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      if (process.env.NODE_ENV === 'development') {
        console.error('[API Error]', error?.response?.status, error?.message);
      }
      return Promise.reject(error);
    }

    // 토큰 갱신 엔드포인트 자체가 401이면 → 로그아웃 (refresh 토큰도 만료)
    if (originalRequest.url?.includes('/auth/token/refresh/')) {
      await handleLogout();
      return Promise.reject(error);
    }

    // 이미 갱신 중이면 큐에 추가
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((token) => {
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${token}`;
        }
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const { useUserStore } = await import('@/store/useUserStore');
      const refreshToken = useUserStore.getState().refreshToken;

      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      // refresh token으로 새 access token 발급
      const { data } = await axios.post(
        `${DJANGO_URL}/api/auth/token/refresh/`,
        { refresh: refreshToken },
        {
          headers: { 'Content-Type': 'application/json' },
          withCredentials: true,
        }
      );

      const newAccess = data.access;
      // ROTATE_REFRESH_TOKENS=True이므로 refresh도 새 거 받음
      const newRefresh = data.refresh || refreshToken;

      // 새 토큰 저장
      useUserStore.getState().setTokens({
        access: newAccess,
        refresh: newRefresh,
      });

      // 큐에 쌓인 요청들 일괄 처리
      processQueue(null, newAccess);

      // 원래 요청 재시도
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newAccess}`;
      }
      return apiClient(originalRequest);
    } catch (refreshError) {
      // 갱신 실패 → 로그아웃
      processQueue(refreshError, null);
      await handleLogout();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

/**
 * Handle logout - clear store + redirect.
 * 로그아웃 처리 - 스토어 클리어 + 로그인 페이지로.
 */
async function handleLogout() {
  if (typeof window === 'undefined') return;

  const { useUserStore } = await import('@/store/useUserStore');
  await useUserStore.getState().logout();

  // 로그인 페이지로 (현재 URL이 이미 /login이면 스킵)
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login?error=session_expired';
  }
}

// ==================== 기존 API 함수들 ====================

/**
 * Search games by name/genre/developer.
 * 이름/장르/개발사 검색.
 */
export async function searchGames(
  query: string,
  limit: number = 12
): Promise<Game[]> {
  const { data } = await apiClient.get<Game[]>('/games/search', {
    params: { q: query, limit },
  });
  return data;
}

/**
 * Semantic search by natural language.
 * 자연어 시맨틱 검색.
 */
export async function semanticSearchGames(
  query: string,
  limit: number = 12
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/search/semantic',
    { query, limit }
  );
  return data;
}

/**
 * Get game detail.
 * 게임 상세 조회.
 */
export async function getGameDetail(appId: number): Promise<GameDetail> {
  const { data } = await apiClient.get<GameDetail>(`/games/${appId}`);
  return data;
}

/**
 * Get stats overview.
 * 통계 개요 조회.
 */
export async function getStatsOverview(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get('/games/stats/overview');
  return data;
}

/**
 * Get metrics list.
 * 지표 목록 조회.
 */
export async function getMetricsList(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>('/games/metrics/list');
  return data;
}

/**
 * Recommend by game.
 * 특정 게임 기반 추천.
 */
export async function recommendByGame(
  appId: number,
  count: number = 6
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/recommend/by-game',
    { app_id: appId, count }
  );
  return data;
}

/**
 * Recommend by preference vector.
 * 선호도 벡터 기반 추천.
 */
export async function recommendByPreference(
  preferences: Record<string, number>,
  count: number = 12
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/recommend/by-preference',
    { preferences, count }
  );
  return data;
}

// ==================== Taste Action API ====================

export type TasteActionType =
  | 'search'
  | 'detail_view'
  | 'rec_click'
  | 'search_click'
  | 'steam_click'
  | 'like'
  | 'neg_feedback'
  | 'revisit';

export interface TasteActionPayload {
  session_id: string;
  app_id?: number;
  action_type: TasteActionType;
  context?: Record<string, unknown>;
}

export interface TasteActionResponse {
  success: boolean;
  action_id?: number;
  message: string;
}

/**
 * Record user action (fire-and-forget).
 * 유저 행동 기록 — 실패해도 서비스 영향 X.
 */
export async function recordTasteAction(
  payload: TasteActionPayload
): Promise<TasteActionResponse | null> {
  if (!payload.session_id) return null;

  try {
    const { data } = await apiClient.post<TasteActionResponse>(
      '/taste/action',
      payload
    );
    return data;
  } catch (error) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[TasteAction] 기록 실패:', error);
    }
    return null;
  }
}

/**
 * Record action using sendBeacon (navigation-safe).
 * Navigation 시에도 안전한 행동 기록.
 */
export function recordTasteActionBeacon(
  payload: TasteActionPayload
): boolean {
  if (!payload.session_id) return false;

  if (typeof navigator === 'undefined' || !navigator.sendBeacon) {
    recordTasteAction(payload);
    return false;
  }

  try {
    const url = `${API_BASE_URL}/taste/action`;
    const blob = new Blob(
      [JSON.stringify(payload)],
      { type: 'application/json' }
    );
    return navigator.sendBeacon(url, blob);
  } catch {
    return false;
  }
}
