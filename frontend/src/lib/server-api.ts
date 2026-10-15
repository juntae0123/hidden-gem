/**
 * Server-side API helpers (Server Components / metadata routes only).
 * 서버 컴포넌트·사이트맵 전용 API 호출 — 클라이언트 컴포넌트에서 import 하지 않는다.
 *
 * 왜 api.ts(axios)를 쓰지 않는가:
 *   api.ts 는 브라우저 전제(토큰 인터셉터·401 리다이렉트)다. 서버 렌더에서는 Next 의 fetch 캐시
 *   (ISR 데이터 캐시)를 타야 크롤러가 페이지를 열 때마다 API 를 다시 부르지 않는다.
 *
 * 실패 정책 (SEO 2026-10-14):
 *   - API 가 죽어도 페이지·빌드는 죽지 않는다 → null 을 돌려주고 호출자가 최소 페이지를 그린다.
 *   - 단, 실패한 렌더가 하루(86400s) 동안 캐시되면 크롤러가 하루 내내 빈 페이지를 본다.
 *     그래서 첫 시도가 실패하면 revalidate 를 짧게(FAILURE_REVALIDATE) 준 재시도를 한 번 한다.
 *     Next 는 fetch 의 revalidate 가 라우트 값보다 작으면 라우트 전체 주기를 그 값으로 낮춘다
 *     (patch-fetch: 요청 전에 반영) — 재시도마저 실패해도 그 페이지는 몇 분 뒤 다시 그려진다.
 *   - 200 이 아닌 응답은 데이터 캐시에 들어가지 않는다 (patch-fetch: res.status === 200 만 저장).
 */
import { cache } from 'react';
import type { GameDetail, RecommendationResponse, RankingResponse, RankingType } from '@/types/game';

// 클라이언트(api.ts)와 같은 변수를 쓴다 — 새 환경변수를 늘리지 않는다 (도메인·변수 '네 곳' 규칙)
const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '');

/** 정상 응답의 캐시 주기 — 페이지 revalidate 와 같다 */
export const DATA_REVALIDATE = 86400;
/** 실패 시 재시도의 캐시 주기 — 이 값이 페이지 주기를 끌어내린다 */
const FAILURE_REVALIDATE = 300;
/** 느린 API 가 렌더를 붙잡지 않게 */
const TIMEOUT_MS = 8000;

/** 게임 사이트맵 한 파일당 URL 수 (구글 상한 5만, 응답 크기·생성 시간을 보고 1만으로) */
export const GAME_SITEMAP_CHUNK = 10000;

type FetchResult<T> = { ok: true; data: T } | { ok: false; status: number };

async function requestOnce<T>(
  path: string,
  init: { method?: 'GET' | 'POST'; body?: unknown },
  revalidate: number,
): Promise<FetchResult<T>> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: init.method ?? 'GET',
      headers: init.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      next: { revalidate },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return { ok: false, status: res.status };
    return { ok: true, data: (await res.json()) as T };
  } catch {
    return { ok: false, status: 0 };   // 네트워크 오류·타임아웃
  }
}

/**
 * GET/POST JSON with one short-revalidate retry on failure.
 * notFoundIsFinal: 404 가 '그 대상이 없다'는 확정 답인 호출(게임 상세·게임별 추천)만 재시도하지 않는다.
 *   사이트맵·랭킹의 404 는 '엔드포인트가 아직 없다'(백엔드 배포가 프런트보다 늦음)일 수 있어 재시도한다 —
 *   안 그러면 빈 사이트맵이 하루 동안 캐시된다.
 */
async function requestJson<T>(
  path: string,
  init: { method?: 'GET' | 'POST'; body?: unknown } = {},
  revalidate: number = DATA_REVALIDATE,
  notFoundIsFinal: boolean = false,
): Promise<FetchResult<T>> {
  const first = await requestOnce<T>(path, init, revalidate);
  if (first.ok || (notFoundIsFinal && first.status === 404)) return first;
  return requestOnce<T>(path, init, Math.min(revalidate, FAILURE_REVALIDATE));
}

/**
 * 게임 상세 — generateMetadata 와 page 가 같은 렌더에서 두 번 부르므로 React cache 로 묶는다.
 * 반환: 데이터 / 'not-found'(API 404) / null(API 장애).
 */
export const getGameDetailServer = cache(
  async (appId: number): Promise<GameDetail | 'not-found' | null> => {
    const r = await requestJson<GameDetail>(`/games/${appId}`, {}, DATA_REVALIDATE, true);
    if (r.ok) return r.data;
    return r.status === 404 ? 'not-found' : null;
  },
);

/**
 * 비슷한 게임 — 클라이언트 RecommendList 와 같은 요청(count 6)이라 서버 Redis 캐시 키도 같다.
 */
export const getSimilarGamesServer = cache(
  async (appId: number, count: number = 6): Promise<RecommendationResponse | null> => {
    // 404 = 기준 게임이 없거나 지표가 없음 (확정 답)
    const r = await requestJson<RecommendationResponse>(
      '/games/recommend/by-game',
      { method: 'POST', body: { app_id: appId, count } },
      DATA_REVALIDATE,
      true,
    );
    return r.ok ? r.data : null;
  },
);

/**
 * 랭킹 (랭킹 페이지 첫 화면 SSR 용).
 * revalidate 는 페이지 값과 맞춘다 — 데이터 캐시가 더 길면 페이지만 다시 그려지고 목록은 옛것이 된다.
 */
export async function getRankingServer(
  type: RankingType,
  limit: number = 30,
  revalidate: number = 3600,
): Promise<RankingResponse | null> {
  const params = new URLSearchParams({ type, limit: String(limit) });
  const r = await requestJson<RankingResponse>(`/games/ranking?${params.toString()}`, {}, revalidate);
  return r.ok ? r.data : null;
}

/** GET /games/sitemap-ids 응답 (fastapi_app/schemas/game.py SitemapIdsResponse) */
export interface SitemapIdsResponse {
  total: number;
  offset: number;
  limit: number;
  app_ids: number[];
}

export async function getSitemapIds(
  offset: number,
  limit: number,
): Promise<SitemapIdsResponse | null> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  const r = await requestJson<SitemapIdsResponse>(`/games/sitemap-ids?${params.toString()}`);
  return r.ok ? r.data : null;
}

/**
 * 게임 사이트맵 파일 개수.
 * API 장애로 총계를 모르면 FALLBACK 개(5만 URL 분량)를 만든다 — 파일 개수는 빌드 때 정해지므로
 * 여기서 1개로 줄여 두면 다음 배포까지 나머지 게임이 사이트맵에서 빠진다. 빈 파일은 해가 없다.
 */
const SITEMAP_FALLBACK_FILES = 5;

export async function getGameSitemapCount(): Promise<number> {
  const r = await getSitemapIds(0, 1);
  if (!r) return SITEMAP_FALLBACK_FILES;
  return Math.max(1, Math.ceil(r.total / GAME_SITEMAP_CHUNK));
}
