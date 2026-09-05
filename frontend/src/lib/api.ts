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
  RankingResponse,
  RankingType,
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
/** 초유명작 제외 기준 — 이 리뷰 수를 넘는 게임은 '숨은 명작' 화면에서 제외 */
export const HIDDEN_GEM_MAX_REVIEWS = 20000;

export async function recommendByPreference(
  preferences: Record<string, number>,
  count: number = 12,
  options: { maxReviewCount?: number; includeNew?: boolean } = {}
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    '/games/recommend/by-preference',
    {
      preferences,
      count,
      ...(options.maxReviewCount !== undefined && { max_review_count: options.maxReviewCount }),
      // R-11: 리뷰 100 미만 신작은 기본 제외. 토글로만 들어온다.
      include_new: options.includeNew ?? false,
    }
  );
  return data;
}

// ==================== Ranking (R-12) ====================

/**
 * 사용자 무관 지표 랭킹. steady = 발굴 지수 / rising = 30일 상대 증가율 / new = 초기 속도(리뷰/일).
 * Korean: 취향 프리셋이 아닌 진짜 랭킹. 이전 /ranking 은 by-preference 결과였다.
 */
export async function fetchRanking(
  type: RankingType,
  genre: string | null = null,
  limit: number = 30,
): Promise<RankingResponse> {
  const params = new URLSearchParams({ type, limit: String(limit) });
  if (genre) params.set('genre', genre);
  const { data } = await apiClient.get<RankingResponse>(`/games/ranking?${params.toString()}`);
  return data;
}

// ==================== Vibe Cluster ====================

/** Vibe 칩 메타 (목록 표시용) / Vibe chip metadata */
export interface VibeItem {
  key:         string;
  label:       string;
  emoji:       string;
  description: string;
}

/**
 * Fetch all macro vibes for chip UI.
 * Korean: 칩 UI용 12개 Macro Vibe 목록 조회.
 */
export async function getVibes(): Promise<VibeItem[]> {
  const { data } = await apiClient.get<{ vibes: VibeItem[] }>(
    '/games/vibes'
  );
  return data.vibes;
}

/**
 * Recommend games by vibe chip (backend maps vibe → v6 preferences).
 * Korean: Vibe 칩 클릭 → 백엔드가 preferences로 변환 후 v6 추천.
 */
export async function recommendByVibe(
  vibeKey: string,
  count: number = 12,
  includeNew: boolean = false,
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>(
    `/games/recommend/by-vibe?vibe_key=${encodeURIComponent(vibeKey)}&count=${count}&include_new=${includeNew}`,
  );
  return data;
}

// ==================== Onboarding (Django auth) ====================

/** 온보딩 입력 / Onboarding form payload */
export interface OnboardingPayload {
  first_name?: string;
  nickname?:   string;
  gender:      string;  // 필수
  age_group:   string;  // 필수
}

/** 유저 정보 (온보딩 상태 포함) / User info incl. onboarding state */
export interface MeResponse {
  id:                   number;
  email:                string;
  nickname:             string | null;
  steam_id:             string | null;
  gender:               string | null;
  age_group:            string | null;
  onboarding_completed: boolean;
  [key: string]: unknown;
}

/**
 * Fetch current user (incl. onboarding_completed).
 * Korean: 현재 유저 정보 조회 — 온보딩 완료 여부 포함.
 * apiClient 사용 → 401 시 자동 토큰 갱신 interceptor를 탐.
 * Django(8001) 절대 URL을 주면 baseURL(FastAPI)을 무시함.
 */
export async function getMe(): Promise<MeResponse> {
  const { data } = await apiClient.get<MeResponse>(
    `${DJANGO_URL}/api/auth/me/`
  );
  return data;
}

/**
 * Submit onboarding data (name/nickname/gender/age_group).
 * Korean: 온보딩 데이터 제출. 성공 시 갱신된 유저 정보 반환.
 * apiClient 사용 → 401 자동 갱신 interceptor 적용.
 */
export async function submitOnboarding(
  payload: OnboardingPayload
): Promise<MeResponse> {
  const { data } = await apiClient.post<MeResponse>(
    `${DJANGO_URL}/api/auth/onboarding/`,
    payload
  );
  return data;
}

/** 최근 본 게임 1개 / Recently viewed game */
export interface RecentGame {
  app_id:       number;
  name:         string;
  header_image: string;
  genres:       string;
}

/**
 * Fetch user's recently viewed games (detail_view history).
 * Korean: 최근 본 게임 조회 — 로그인 유저의 detail_view 이력.
 * apiClient 사용 → 401 자동 갱신 적용.
 */
export async function getRecentGames(): Promise<RecentGame[]> {
  const { data } = await apiClient.get<{ games: RecentGame[] }>(
    `${DJANGO_URL}/api/auth/recent-games/`
  );
  return data.games;
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

// ==================== Game Survey (지표 검증 설문) ====================

/** 설문 대상 게임 / Game eligible for survey */
export interface PendingSurvey {
  app_id:       number;
  name:         string;
  header_image: string;
  genres:       string;
}

/** 지표 평가 1개 / One metric rating */
export interface MetricRatingInput {
  metric:     string;
  our_score:  number;
  user_score: number;  // 1~5
}

/** 설문 제출 payload */
export interface SurveySubmit {
  app_id:   number;
  played:   boolean;
  ratings?: MetricRatingInput[];
}

/**
 * Check if there's a pending survey for the user.
 * Korean: 설문 대상 게임 1개 조회 (1주일 전 본+스팀간 게임, 미설문).
 */
export async function getPendingSurvey(): Promise<PendingSurvey | null> {
  const { data } = await apiClient.get<{ survey: PendingSurvey | null }>(
    `${DJANGO_URL}/api/auth/pending-survey/`
  );
  return data.survey;
}

/**
 * Submit survey response.
 * Korean: 설문 응답 제출 (played + 지표별 점수).
 */
export async function submitSurvey(
  payload: SurveySubmit
): Promise<{ success?: boolean; duplicate?: boolean }> {
  const { data } = await apiClient.post(
    `${DJANGO_URL}/api/auth/submit-survey/`,
    payload
  );
  return data;
}

// ==================== Favorites (찜) ====================

/** 찜한 게임 1개 / One favorited game */
export interface FavoriteGame {
  app_id:       number;
  name:         string;
  header_image: string;
  genres:       string;
}

/**
 * Toggle favorite (add/remove). Login required.
 * Korean: 찜 토글 — 추가/삭제. 로그인 필요.
 * 반환: 토글 후 찜 상태 (true=찜됨).
 */
export async function toggleFavoriteApi(appId: number): Promise<boolean> {
  const { data } = await apiClient.post<{ favorited: boolean }>(
    `${DJANGO_URL}/api/auth/favorite/toggle/`,
    { app_id: appId }
  );
  return data.favorited;
}

/**
 * Get my favorites (game info + app_ids).
 * Korean: 내 찜 목록 — 게임 정보 + app_id 배열(store 동기화용).
 */
export async function getFavorites(): Promise<{
  favorites: FavoriteGame[];
  app_ids:   number[];
}> {
  const { data } = await apiClient.get<{
    favorites: FavoriteGame[];
    app_ids:   number[];
  }>(`${DJANGO_URL}/api/auth/favorites/`);
  return data;
}

// ==================== Taste Preference (취향 설정) ====================

/** 취향 설정 데이터 / Taste preference payload */
export interface TastePreference {
  preferred_genres:   string[];              // 선호 장르
  metric_preferences: Record<string, number>; // 지표별 선호 점수 (1~5)
}

/**
 * Get saved taste preferences.
 * Korean: 저장된 취향 조회 — 선호 장르 + 지표 점수.
 */
export async function getTastePreference(): Promise<TastePreference> {
  const { data } = await apiClient.get<TastePreference>(
    `${DJANGO_URL}/api/auth/taste-preference/`
  );
  return data;
}

/**
 * Save taste preferences.
 * Korean: 취향 저장 — 선호 장르 + 지표 점수.
 */
export async function saveTastePreference(
  payload: TastePreference
): Promise<TastePreference> {
  const { data } = await apiClient.post<TastePreference>(
    `${DJANGO_URL}/api/auth/taste-preference/`,
    payload
  );
  return data;
}

// ==================== Steam Library (스팀 라이브러리) ====================

export interface SteamLibraryGame {
  app_id: number;
  name: string;
  playtime_hours: number;
  in_db: boolean;
}

export interface SteamLibrary {
  steam_linked: boolean;
  library_count?: number;
  top_games: SteamLibraryGame[];
}

/**
 * Get user's Steam library (top by playtime).
 * Korean: 스팀 연동 유저의 보유 게임 상위 목록 (플레이타임 기준).
 */
export async function getSteamLibrary(): Promise<SteamLibrary> {
  const { data } = await apiClient.get<SteamLibrary>(
    `${DJANGO_URL}/api/auth/steam-library/`
  );
  return data;
}

// ==================== Delete Account (회원 탈퇴) ====================

/**
 * Delete account (anonymizes behavior/survey data, removes personal info).
 * Korean: 회원 탈퇴 — 개인정보 삭제 + 행동/설문 익명화. 되돌릴 수 없음.
 */
export async function deleteAccount(): Promise<{ success: boolean }> {
  const { data } = await apiClient.delete<{ success: boolean }>(
    `${DJANGO_URL}/api/auth/delete-account/`
  );
  return data;
}