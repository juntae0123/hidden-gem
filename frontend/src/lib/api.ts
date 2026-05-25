/**
 * API client for Hidden Gem backend
 * 백엔드 FastAPI 서버와 통신하는 axios 인스턴스 및 API 함수 모음
 */
import axios, { AxiosInstance } from 'axios';
import type {
  Game,
  GameDetail,
  RecommendationResponse,
} from '@/types/game';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

/**
 * Axios instance with default config
 * 기본 baseURL과 헤더가 설정된 axios 인스턴스
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error?.response?.status, error?.message);
    return Promise.reject(error);
  }
);

// ==================== 게임 검색 / Game Search ====================

export async function searchGames(query: string, limit = 12): Promise<Game[]> {
  const { data } = await apiClient.get<Game[]>('/games/search', {
    params: { q: query, limit },
  });
  return data;
}

export async function semanticSearchGames(
  query: string,
  limit = 12
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/search/semantic',
    { query, limit }
  );
  return data;
}

// ==================== 게임 정보 / Game Info ====================

export async function getGameDetail(appId: number): Promise<GameDetail> {
  const { data } = await apiClient.get<GameDetail>(`/games/${appId}`);
  return data;
}

export async function getStatsOverview(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get('/games/stats/overview');
  return data;
}

export async function getMetricsList(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>('/games/metrics/list');
  return data;
}

// ==================== 추천 / Recommendation ====================

export async function recommendByGame(
  appId: number,
  count = 6
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/recommend/by-game',
    { app_id: appId, count }
  );
  return data;
}

export async function recommendByPreference(
  preferences: Record<string, number>,
  count = 12
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/recommend/by-preference',
    { preferences, count }
  );
  return data;
}

// ==================== 행동 로그 / Taste Action ====================

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
 * Record user action — regular async (fire-and-forget).
 * 유저 행동 기록 — 비동기, 실패해도 서비스 영향 없음.
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
 * Record action using sendBeacon — navigation-safe.
 * Navigation 시에도 전송 보장 (Steam 클릭 등 페이지 이탈 시).
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
    const blob = new Blob(
      [JSON.stringify(payload)],
      { type: 'application/json' }
    );
    return navigator.sendBeacon(`${API_BASE_URL}/taste/action`, blob);
  } catch {
    return false;
  }
}