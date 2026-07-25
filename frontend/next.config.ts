import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  // workspace root를 frontend로 고정 (루트 package-lock.json 오인 방지)
  // Korean: 상위 폴더의 lockfile 때문에 Tailwind가 클래스를 못 스캔하는 문제 해결
  turbopack: {
    root: path.join(__dirname),
  },
  allowedDevOrigins: ['192.168.75.81'],
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.cloudflare.steamstatic.com' },
      { protocol: 'https', hostname: 'shared.akamai.steamstatic.com' },
    ],
  },
}

export default nextConfig