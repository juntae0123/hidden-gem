/**
 * Optimized game image with inline SVG fallback.
 * 인라인 SVG 폴백을 사용한 최적화 게임 이미지.
 *
 * v3 → v4: btoa 제거 (유니코드 ✦ 처리), encodeURIComponent 사용
 */
'use client';

import Image from 'next/image';
import { useState } from 'react';
import { cn } from '@/lib/utils';

interface GameImageProps {
  appId: number;
  name: string;
  fallback?: string | null;
  size?: 'thumbnail' | 'card' | 'hero';
  priority?: boolean;
  zoomOnHover?: boolean;
  className?: string;
}

const SIZE_CONFIG = {
  thumbnail: { width: 184, height: 86 },
  card: { width: 460, height: 215 },
  hero: { width: 920, height: 430 },
} as const;

const SIZE_HINTS = {
  thumbnail: '(max-width: 768px) 100vw, 200px',
  card: '(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 460px',
  hero: '(max-width: 768px) 100vw, 920px',
} as const;

/**
 * Inline SVG placeholder via encodeURIComponent (유니코드 안전).
 * btoa는 Latin1만 지원해서 ✦ 같은 유니코드 처리 못함.
 */
const PLACEHOLDER_SVG =
  'data:image/svg+xml,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="460" height="215" viewBox="0 0 460 215">
      <rect width="460" height="215" fill="#27272a"/>
      <text x="230" y="100" font-family="system-ui,sans-serif" font-size="40" fill="#a855f7" text-anchor="middle">&#10022;</text>
      <text x="230" y="140" font-family="system-ui,sans-serif" font-size="15" fill="#71717a" text-anchor="middle">Hidden Gem</text>
    </svg>`
  );

function buildSrc(appId: number, fallback?: string | null): string {
  if (fallback?.trim()) return fallback;
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}

/**
 * Game image with inline SVG fallback (파일 의존 X, 유니코드 안전).
 */
export function GameImage({
  appId,
  name,
  fallback,
  size = 'card',
  priority = false,
  zoomOnHover = false,
  className,
}: GameImageProps) {
  const [hasError, setHasError] = useState(false);
  const { width, height } = SIZE_CONFIG[size];

  if (hasError) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={PLACEHOLDER_SVG}
        alt={name}
        className={cn('object-cover w-full h-full', className)}
      />
    );
  }

  const src = buildSrc(appId, fallback);

  return (
    <Image
      src={src}
      alt={name}
      width={width}
      height={height}
      priority={priority}
      sizes={SIZE_HINTS[size]}
      onError={() => setHasError(true)}
      className={cn(
        'object-cover w-full h-full',
        zoomOnHover && 'group-hover:scale-105 transition-transform duration-500',
        className
      )}
    />
  );
}
