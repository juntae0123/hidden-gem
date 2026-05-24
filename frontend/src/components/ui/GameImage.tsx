/**
 * Optimized game image using next/image with fallback chain
 * next/image + 폴백 체인을 사용한 최적화된 게임 이미지
 *
 * 폴백 순서: 백엔드 URL → Steam CDN → /placeholder-game.png
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
  thumbnail: { width: 184,  height: 86  },
  card:      { width: 460,  height: 215 },
  hero:      { width: 920,  height: 430 },
} as const;

const SIZE_HINTS = {
  thumbnail: '(max-width: 768px) 100vw, 200px',
  card:      '(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 460px',
  hero:      '(max-width: 768px) 100vw, 920px',
} as const;

function buildSrc(appId: number, fallback?: string | null): string {
  if (fallback?.trim()) return fallback;
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appId}/header.jpg`;
}

/**
 * Game image with automatic CDN fallback and Next.js optimization.
 * 자동 CDN 폴백 + Next.js 최적화 게임 이미지.
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

  const src = hasError ? '/placeholder-game.png' : buildSrc(appId, fallback);

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
