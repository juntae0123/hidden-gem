'use client';

import React, { useMemo } from 'react';
import type { GameScores, TierType } from '../types';

interface RadarChartProps {
  scores: GameScores;
  tier: TierType;
  size?: number;
}

// 차트에 표시할 주요 지표 (6개)
const CHART_METRICS = [
  { key: 'story_depth', label: '스토리' },
  { key: 'originality', label: '독창성' },
  { key: 'art_style', label: '아트' },
  { key: 'addictiveness', label: '중독성' },
  { key: 'emotional_impact', label: '감동' },
  { key: 'atmosphere_intensity', label: '분위기' },
] as const;

const TIER_COLORS: Record<TierType, string> = {
  legendary: '#FFD700',
  mythic: '#FF0000',
  epic: '#A335EE',
  rare: '#0070DD',
  uncommon: '#1EFF00',
  solid: '#CD7F32',
  maniac: '#00FF41',
};

export default function RadarChart({ scores, tier, size = 200 }: RadarChartProps) {
  const centerX = size / 2;
  const centerY = size / 2;
  // 💡 수정 포인트 1: radius를 0.38에서 0.32로 줄여서 라벨이 들어갈 여백을 충분히 확보
  const radius = size * 0.32; 
  const angleStep = (2 * Math.PI) / CHART_METRICS.length;
  const color = TIER_COLORS[tier] || '#3b82f6';

  // 각 지표의 좌표 계산
  const points = useMemo(() => {
    return CHART_METRICS.map((metric, i) => {
      const angle = i * angleStep - Math.PI / 2;
      const rawScore = scores[metric.key as keyof GameScores] || 50;
      const value = rawScore / 100;
      const x = centerX + radius * value * Math.cos(angle);
      const y = centerY + radius * value * Math.sin(angle);
      return { x, y, value, rawScore, label: metric.label, angle };
    });
  }, [scores, centerX, centerY, radius, angleStep]);

  // SVG 경로 생성
  const pathD = points.map((p, i) => 
    `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
  ).join(' ') + ' Z';

  // 배경 격자 생성
  const gridLevels = [0.25, 0.5, 0.75, 1];

  return (
    <div className="radar-chart-container flex justify-center items-center w-full">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
        {/* 배경 격자 */}
        {gridLevels.map((level) => (
          <polygon
            key={level}
            points={CHART_METRICS.map((_, i) => {
              const angle = i * angleStep - Math.PI / 2;
              const x = centerX + radius * level * Math.cos(angle);
              const y = centerY + radius * level * Math.sin(angle);
              return `${x},${y}`;
            }).join(' ')}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="1"
          />
        ))}

        {/* 축 선 */}
        {CHART_METRICS.map((_, i) => {
          const angle = i * angleStep - Math.PI / 2;
          const x = centerX + radius * Math.cos(angle);
          const y = centerY + radius * Math.sin(angle);
          return (
            <line
              key={i}
              x1={centerX}
              y1={centerY}
              x2={x}
              y2={y}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="1"
            />
          );
        })}

        {/* 데이터 영역 */}
        <path
          d={pathD}
          fill={`${color}25`}
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {/* 데이터 포인트 */}
        {points.map((point, i) => (
          <circle
            key={i}
            cx={point.x}
            cy={point.y}
            r="3.5"
            fill={color}
            stroke="#111"
            strokeWidth="1.5"
          />
        ))}

        {/* 라벨 & 점수 표시 */}
        {points.map((point, i) => {
          const labelRadius = radius + 24; // 격자 바깥으로 텍스트 밀어내기
          const angle = i * angleStep - Math.PI / 2;
          const labelX = centerX + labelRadius * Math.cos(angle);
          const labelY = centerY + labelRadius * Math.sin(angle);
          
          return (
            <text
              key={i}
              textAnchor="middle"
              dominantBaseline="middle"
            >
              {/* 💡 수정 포인트 2: tspan을 사용해 지표 이름과 점수를 위아래로 분리 배치 */}
              <tspan x={labelX} y={labelY - 6} fill="#888" fontSize="11" fontWeight="500">
                {point.label}
              </tspan>
              <tspan x={labelX} y={labelY + 8} fill={color} fontSize="13" fontWeight="800">
                {Math.round(point.rawScore)}
              </tspan>
            </text>
          );
        })}
      </svg>
    </div>
  );
}