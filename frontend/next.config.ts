import type { NextConfig } from 'next'
import path from 'path'

/**
 * Next.js config.
 * Korean: Vercel 배포 시 turbopack.root 제거 (outputFileTracingRoot 충돌 방지).
 *   로컬은 상위 lockfile 때문에 root 고정 필요하지만,
 *   Vercel은 Root Directory=frontend라 이미 격리됨.
 */

// Vercel 환경 감지 (VERCEL=1 자동 주입)
const isVercel = process.env.VERCEL === '1'

const nextConfig: NextConfig = {
  // 로컬에서만 turbopack.root 고정 (Vercel은 자동 격리)
  ...(isVercel ? {} : {
    turbopack: {
      root: path.join(__dirname),
    },
  }),
  allowedDevOrigins: ['192.168.75.81'],
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.cloudflare.steamstatic.com' },
      { protocol: 'https', hostname: 'shared.akamai.steamstatic.com' },
    ],
  },
}

export default nextConfig
