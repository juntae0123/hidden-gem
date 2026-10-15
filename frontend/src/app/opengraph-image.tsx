/**
 * Default Open Graph image (1200x630) — 카톡·디스코드·검색 공유 카드의 기본 이미지.
 * 게임 상세는 게임별 Steam 헤더 이미지를 쓰고(game/[appId]/page.tsx), 그 밖의 페이지가 이걸 쓴다.
 *
 * 한글 글꼴 (SEO 2026-10-14):
 *   ImageResponse(satori)는 시스템 글꼴을 못 쓰고, 글꼴에 없는 글자는 빌드 중에 Google Fonts 에서
 *   내려받으려 한다(네트워크 의존). Noto Sans KR 전체(약 6MB)를 저장소에 넣는 대신, 아래 문구에
 *   쓰인 글자만 남긴 부분 글꼴(_og/NotoSansKR-Bold-og.ttf, 수십 KB)을 넣었다. 라이선스: _og/OFL.txt.
 *   주의: 아래 문구를 바꾸면 새 글자가 글꼴에 없을 수 있다 → 부분 글꼴을 다시 만든다 (fonttools):
 *       pip install fonttools
 *       pyftsubset NotoSansKR-Bold.ttf --text="<바뀐 문구 전부>" --unicodes=U+0020-007E \
 *         --layout-features='*' --no-hinting --output-file=src/app/_og/NotoSansKR-Bold-og.ttf
 *     (원본: Google Fonts 'Noto Sans KR' 정적 Bold TTF. 빠진 글자가 있으면 빌드가 Google Fonts 접속을 시도한다)
 *   이미지는 빌드 때 한 번 만들어지는 정적 파일이라 런타임 비용은 없다.
 */
import { ImageResponse } from 'next/og';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

export const alt = 'Hidden Gem · 취향에 맞는 게임을 찾아주는 서비스';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

// 부분 글꼴에 들어 있는 글자는 이 문구들 + ASCII 뿐이다 (주석 참고)
const OG_HEADLINE = '취향에 맞는 게임을 찾아주는 서비스';
// 한글은 글자 단위로 줄이 바뀌어 낱글자가 다음 줄로 떨어진다 — 줄을 직접 나눈다
const OG_SUBLINES = ['좋아하는 게임과 비슷한 스팀 게임을', '49개 플레이 지표로 비교해 찾아드려요'];
const OG_BRAND = 'Hidden Gem';
const OG_DOMAIN = 'hiddengemdb.com';

export default async function OpengraphImage() {
  const font = await readFile(join(process.cwd(), 'src/app/_og/NotoSansKR-Bold-og.ttf'));

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '72px 80px',
          background: 'linear-gradient(135deg, #0F0F13 0%, #1B1430 60%, #2A1650 100%)',
          color: '#FAFAF7',
          fontFamily: 'NotoSansKR',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          {/* 브랜드 별표(✦) — 글꼴에 없는 기호라 SVG 로 그린다 */}
          <svg width="44" height="44" viewBox="0 0 24 24">
            <path d="M12 0 L14.6 9.4 L24 12 L14.6 14.6 L12 24 L9.4 14.6 L0 12 L9.4 9.4 Z" fill="#A855F7" />
          </svg>
          <div style={{ fontSize: 44, letterSpacing: -0.5 }}>{OG_BRAND}</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
          <div style={{ fontSize: 64, lineHeight: 1.2, letterSpacing: -1.5, whiteSpace: 'nowrap' }}>{OG_HEADLINE}</div>
          <div style={{ display: 'flex', flexDirection: 'column', fontSize: 34, lineHeight: 1.45, color: '#C4B5FD' }}>
            {OG_SUBLINES.map((line) => (
              <div key={line} style={{ whiteSpace: 'nowrap' }}>{line}</div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', fontSize: 28, color: '#A1A1AA' }}>{OG_DOMAIN}</div>
      </div>
    ),
    {
      ...size,
      fonts: [{ name: 'NotoSansKR', data: font, style: 'normal', weight: 700 }],
    },
  );
}
