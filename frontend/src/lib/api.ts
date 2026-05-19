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
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Axios instance with default config
 * 기본 baseURL과 헤더가 설정된 axios 인스턴스
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 응답 인터셉터 - 에러 로깅 / Response interceptor for error logging
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error?.response?.status, error?.message);
    return Promise.reject(error);
  }
);

/**
 * Search games by natural language query
 * 자연어 쿼리로 게임을 검색
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
 * Get detailed info of a specific game
 * 특정 게임의 상세 정보 조회
 */
export async function getGameDetail(appId: number): Promise<GameDetail> {
  const { data } = await apiClient.get<GameDetail>(`/games/${appId}`);
  return data;
}

/**
 * Get overall stats overview
 * 전체 통계 개요 조회
 */
export async function getStatsOverview(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get('/games/stats/overview');
  return data;
}

/**
 * Get list of available metrics
 * 사용 가능한 지표 목록 조회
 */
export async function getMetricsList(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>('/games/metrics/list');
  return data;
}

/**
 * Recommend games similar to a given game
 * 특정 게임과 유사한 게임 추천
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
 * Recommend games by user preference vector
 * 사용자 선호도 벡터 기반 게임 추천
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
