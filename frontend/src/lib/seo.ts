/**
 * SEO helpers — 메타데이터 문구와 서버 렌더 텍스트를 한곳에서 만든다.
 *
 * 서비스 정의 (사용자 지정 2026-10-14): 「취향에 맞는 게임을 찾아주는 서비스」.
 * '인디게임 추천'으로 쓰지 않는다 — 인디만 다루는 서비스가 아니다.
 */
import type { Metadata } from 'next';
import { getGenreCoreMetrics, METRIC_LABELS } from '@/lib/utils';

export const SITE_NAME = 'Hidden Gem';
export const SERVICE_TAGLINE = '취향에 맞는 게임을 찾아주는 서비스';

/**
 * openGraph 공통 필드.
 * Next 메타데이터는 openGraph 를 '통째로' 덮어쓴다 (얕은 병합) — 자식 페이지가 openGraph 를
 * 지정하면 루트의 siteName·locale 이 사라지므로 항상 이걸 펼쳐서 쓴다.
 */
export const OG_BASE = {
  siteName: SITE_NAME,
  locale: 'ko_KR',
  type: 'website',
} as const satisfies NonNullable<Metadata['openGraph']>;

/**
 * 기본 공유 이미지 (app/opengraph-image.tsx 가 만드는 1200x630).
 * 루트의 파일 기반 OG 이미지는 자식 페이지가 openGraph 를 지정하는 순간 함께 사라진다
 * (실측: /ranking·/search 에서 og:image 누락). openGraph 를 덮어쓰는 페이지는 이걸 images 로 넣는다.
 */
export const DEFAULT_OG_IMAGE = {
  url: '/opengraph-image',
  width: 1200,
  height: 630,
  alt: `${SITE_NAME} · ${SERVICE_TAGLINE}`,
} as const;

/** HTML 태그·엔티티를 걷어낸 평문 (Steam 설명에 태그가 섞여 들어올 수 있다) */
export function toPlainText(input: string | null | undefined): string {
  if (!input) return '';
  return input
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/[ \t]+/g, ' ')
    .replace(/\s*\n\s*/g, '\n')
    .trim();
}

/** 글자 수 기준으로 자르고 말줄임 (메타 설명·소개문) */
export function truncate(text: string, max: number): string {
  const flat = text.trim();
  if (flat.length <= max) return flat;
  return flat.slice(0, max - 1).trimEnd() + '…';
}

export interface StrongMetric {
  key: string;
  label: string;
  value: number;
}

/**
 * 이 게임에서 두드러지는 지표 (상세 화면과 같은 장르 핵심 지표 중 6점 이상, 높은 순).
 * 상세 화면의 레이더와 같은 함수(getGenreCoreMetrics)를 써서 화면과 설명문이 어긋나지 않게 한다.
 */
export function strongestMetrics(
  metrics: Record<string, unknown> | null | undefined,
  genres: string | null | undefined,
  n: number = 3,
): StrongMetric[] {
  if (!metrics) return [];
  return getGenreCoreMetrics(
    metrics as Record<string, number | boolean | null | undefined>,
    genres ?? '',
    6,
  )
    .filter((m) => m.value >= 6)
    .sort((a, b) => b.value - a.value)
    .slice(0, n)
    .map((m) => ({ key: m.key, label: METRIC_LABELS[m.key] ?? m.key, value: m.value }));
}

export function formatMetric(m: StrongMetric): string {
  return `${m.label} ${m.value.toFixed(0)}/10`;
}

/** Steam 긍정 비율 0~1 (예전 데이터가 0~100 이면 그대로 %) → '93%' */
export function formatPositiveRatio(ratio: number | null | undefined): string | null {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return null;
  const pct = ratio <= 1 ? ratio * 100 : ratio;
  return `${Math.round(pct)}%`;
}

/** 장르 문자열 'RPG, 액션' → ['RPG', '액션'] */
export function splitGenres(genres: string | null | undefined): string[] {
  return (genres ?? '').split(',').map((g) => g.trim()).filter(Boolean);
}

/**
 * JSON-LD 를 <script> 에 안전하게 넣기 위한 직렬화 — '<' 를 이스케이프해 </script> 주입을 막는다.
 * (Next 문서 guides/json-ld 권고와 같은 방식)
 */
export function jsonLdString(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}
