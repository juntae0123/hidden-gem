/**
 * Game detail page (Server Component wrapper).
 * 게임 상세 페이지 — 서버에서 상세·비슷한 게임을 받아 첫 HTML 에 싣는다.
 *
 * v1 → v2 (SEO 2026-10-14):
 *   - 이전: 'use client' 페이지라 크롤러·카톡/디스코드 미리보기가 빈 껍데기(스켈레톤)만 봤다.
 *     게임별 <title>·설명도 없어 모든 상세 페이지가 홈과 같은 제목이었다.
 *   - 지금: generateMetadata 로 게임별 제목('<게임명> 같은 게임 · 비슷한 게임 추천')·설명·canonical·og:image.
 *     상세(GameDetail)와 추천(RecommendList)은 그대로 클라이언트 컴포넌트를 쓰되, 서버가 받은 값을
 *     initialData 로 넘겨 같은 화면이 서버 HTML 로 먼저 나온다 — 화면 중복 없이 기존 상호작용(찜·
 *     행동 로그·Steam 클릭)을 유지한다. 서버만 그리는 부분은 '게임 소개' 블록과 JSON-LD 뿐이다.
 *   - ISR 하루. API 장애면 최소 페이지(클라이언트가 다시 불러옴)를 그리고 몇 분 뒤 다시 그린다
 *     (lib/server-api.ts 실패 정책).
 */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { GameDetail } from '@/components/game/GameDetail';
import { RecommendList } from '@/components/game/RecommendList';
import { getGameDetailServer, getSimilarGamesServer } from '@/lib/server-api';
import { SITE_URL } from '@/lib/constants';
import {
  DEFAULT_OG_IMAGE, OG_BASE, SITE_NAME, SERVICE_TAGLINE,
  formatMetric, formatPositiveRatio, jsonLdString, splitGenres, strongestMetrics,
  toPlainText, truncate,
} from '@/lib/seo';
import type { GameDetail as GameDetailData } from '@/types/game';

// 하루 단위 ISR — 지표·추천은 주 1회 배치로 바뀌므로 충분하다
export const revalidate = 86400;

/**
 * 빌드 때는 한 페이지도 미리 만들지 않고(빈 배열), 처음 요청될 때 만들어 캐시한다.
 * 이 함수가 없으면 동적 경로라 매 요청 다시 렌더한다(빌드 표 'ƒ'). 빈 배열이어야 ISR('●')이 된다.
 */
export async function generateStaticParams(): Promise<{ appId: string }[]> {
  return [];
}

type PageProps = { params: Promise<{ appId: string }> };

/** API 가 실제로 돌려주는 필드 (fastapi_app/schemas/game.py GameWithMetrics) — is_active 는 타입에 없어 보탠다 */
type ServerGame = GameDetailData & { is_active?: boolean };

/** '123' 만 통과. '12abc'·'-1'·'1e5'·빈 값은 404 */
function parseAppId(raw: string | undefined): number | null {
  if (!raw || !/^\d{1,10}$/.test(raw)) return null;
  const n = Number(raw);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

/** 공유 카드 이미지 — API 의 header_image(Steam CDN) 우선. 없으면 undefined → 기본 OG 이미지(DEFAULT_OG_IMAGE) */
function headerImageOf(game: ServerGame): string | undefined {
  const url = game.header_image?.trim();
  return url && /^https?:\/\//.test(url) ? url : undefined;
}

function buildDescription(game: ServerGame): string {
  const name = game.name || '이 게임';
  const rawSummary = toPlainText(game.one_line_summary) || truncate(toPlainText(game.description), 70);
  // 요약은 대개 마침표 없이 끝난다 — 뒤 문장과 붙어 읽히지 않게 마침표를 보탠다
  const summary = rawSummary && !/[.!?…。]$/.test(rawSummary) ? `${rawSummary}.` : rawSummary;
  const metrics = strongestMetrics(game.metrics as unknown as Record<string, unknown>, game.genres)
    .map(formatMetric)
    .join(' · ');
  const parts = [
    `${name} 같은 게임을 찾는다면.`,
    summary,
    metrics ? `두드러진 특징: ${metrics}.` : '',
    '49개 플레이 지표로 비교해 비슷한 스팀 게임을 골라 드려요.',
  ].filter(Boolean);
  return truncate(parts.join(' '), 160);
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { appId: raw } = await params;
  const appId = parseAppId(raw);
  if (appId === null) return {};          // 페이지 쪽에서 notFound()

  const path = `/game/${appId}`;
  const game = (await getGameDetailServer(appId)) as ServerGame | 'not-found' | null;

  if (game === 'not-found') {
    return { title: '게임을 찾을 수 없어요', robots: { index: false, follow: true } };
  }

  if (!game) {
    // API 장애 — 제목은 일반 문구, canonical 은 유지 (noindex 를 걸지 않는다: 몇 분 뒤 다시 그려진다)
    const title = '비슷한 게임 추천';
    const description = `${SERVICE_TAGLINE}. 이 게임과 플레이 감각이 비슷한 스팀 게임을 찾아보세요.`;
    return {
      title,
      description,
      alternates: { canonical: path },
      openGraph: { ...OG_BASE, url: path, title: `${title} · ${SITE_NAME}`, description, images: [DEFAULT_OG_IMAGE] },
    };
  }

  const name = game.name || `Steam 게임 ${appId}`;
  const title = `${name} 같은 게임 · 비슷한 게임 추천`;
  const description = buildDescription(game);
  const image = headerImageOf(game);
  // 노출 게이트(is_active)에서 내려갔거나 분석 전인 게임은 검색 결과에 올리지 않는다 — 사이트맵 기준과 같다
  const indexable = game.is_active !== false && game.is_analyzed !== false;

  return {
    title,
    description,
    alternates: { canonical: path },
    robots: indexable ? undefined : { index: false, follow: true },
    openGraph: {
      ...OG_BASE,
      url: path,
      title: `${title} · ${SITE_NAME}`,
      description,
      // Steam 헤더 이미지는 460x215. 없으면 기본 OG 이미지 (openGraph 를 덮어쓰면 루트 이미지가 상속되지 않는다)
      images: image ? [{ url: image, width: 460, height: 215, alt: name }] : [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: 'summary_large_image',
      title: `${title} · ${SITE_NAME}`,
      description,
      ...(image ? { images: [image] } : {}),
    },
  };
}

/**
 * 서버만 그리는 '게임 소개' 블록 — Steam 설명·개발사·평가·두드러진 지표.
 * 상세 카드(GameDetail)에 없는 정보만 담아 화면 중복을 피한다.
 */
function GameAbout({ game }: { game: ServerGame }) {
  const description = truncate(toPlainText(game.description), 600);
  const strong = strongestMetrics(game.metrics as unknown as Record<string, unknown>, game.genres);
  const ratio = formatPositiveRatio(game.steam_positive_ratio);
  const reviews = game.review_count ?? 0;

  const facts: { label: string; value: string }[] = [];
  if (game.developer) facts.push({ label: '개발', value: game.developer });
  if (reviews > 0) {
    facts.push({
      label: 'Steam 평가',
      value: ratio ? `긍정 ${ratio} · 리뷰 ${reviews.toLocaleString('ko-KR')}개` : `리뷰 ${reviews.toLocaleString('ko-KR')}개`,
    });
  }
  if (strong.length > 0) facts.push({ label: '두드러진 특징', value: strong.map(formatMetric).join(' · ') });

  if (!description && facts.length === 0) return null;

  return (
    <section className="mt-8 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
      <h2 className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300">게임 소개</h2>
      {description && (
        <p className="mt-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400 whitespace-pre-line break-words">
          {description}
        </p>
      )}
      {facts.length > 0 && (
        <dl className="mt-4 grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-[12px]">
          {facts.map((f) => (
            <div key={f.label} className="contents">
              <dt className="text-zinc-500 dark:text-zinc-500">{f.label}</dt>
              <dd className="text-zinc-700 dark:text-zinc-300 mb-1.5 sm:mb-0">{f.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

export default async function GameDetailPage({ params }: PageProps) {
  const { appId: raw } = await params;
  const appId = parseAppId(raw);
  if (appId === null) notFound();

  // 상세와 추천은 서로 기다리지 않는다
  const [detail, similar] = await Promise.all([
    getGameDetailServer(appId) as Promise<ServerGame | 'not-found' | null>,
    getSimilarGamesServer(appId, 6),
  ]);
  if (detail === 'not-found') notFound();
  const game = detail;   // null = API 장애 → 클라이언트 컴포넌트가 다시 불러온다

  const jsonLd = game
    ? {
        '@context': 'https://schema.org',
        '@type': 'VideoGame',
        name: game.name,
        url: `${SITE_URL}/game/${appId}`,
        description: truncate(toPlainText(game.one_line_summary) || toPlainText(game.description), 300) || undefined,
        image: headerImageOf(game),
        genre: splitGenres(game.genres),
        gamePlatform: 'PC',
        ...(game.developer ? { author: { '@type': 'Organization', name: game.developer } } : {}),
        sameAs: `https://store.steampowered.com/app/${appId}`,
      }
    : null;

  return (
    <div className="flex flex-col gap-2">
      <GameDetail appId={appId} initialData={game ?? undefined} />

      {game ? (
        <GameAbout game={game} />
      ) : (
        <p className="mt-6 text-[12px] text-zinc-500">
          {SERVICE_TAGLINE} — 이 게임과 플레이 감각이 비슷한 스팀 게임을 49개 지표로 비교해 골라 드려요.
        </p>
      )}

      <RecommendList
        appId={appId}
        count={6}
        initialData={similar ?? undefined}
        title={game?.name ? `${game.name} 같은 게임` : undefined}
      />

      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdString(jsonLd) }}
        />
      )}
    </div>
  );
}
