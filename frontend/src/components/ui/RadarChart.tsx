/**
 * Canvas-based radar (hexagon) chart
 * Canvas 기반 6축 헥사곤 레이더 차트
 */
'use client';

import { useEffect, useRef } from 'react';
import { METRIC_LABELS } from '@/lib/utils';

interface RadarChartProps {
  data: { metric: string; value: number }[]; // value 0~10 스케일 / 0~10 scale
  size?: number;
  className?: string;
}

/**
 * Draw hexagonal radar chart on canvas
 * Canvas에 6축 헥사곤 레이더 차트를 그림
 */
export function RadarChart({ data, size = 280, className }: RadarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 고해상도 대응 / Retina support
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const radius = size * 0.36;
    const axes = Math.min(data.length, 6);

    ctx.clearRect(0, 0, size, size);

    // 격자선 (4단계) / Grid rings (4 levels)
    ctx.strokeStyle = 'rgba(124,58,237,0.12)';
    ctx.lineWidth = 1;
    for (let level = 1; level <= 4; level++) {
      const r = (radius * level) / 4;
      ctx.beginPath();
      for (let i = 0; i < axes; i++) {
        const angle = (Math.PI * 2 * i) / axes - Math.PI / 2;
        const x = cx + Math.cos(angle) * r;
        const y = cy + Math.sin(angle) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();
    }

    // 축 선 / Axis lines
    ctx.strokeStyle = 'rgba(124,58,237,0.15)';
    for (let i = 0; i < axes; i++) {
      const angle = (Math.PI * 2 * i) / axes - Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
      ctx.stroke();
    }

    // 데이터 영역 / Data area
    ctx.fillStyle = 'rgba(124,58,237,0.12)';
    ctx.strokeStyle = '#7C3AED';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < axes; i++) {
      const angle = (Math.PI * 2 * i) / axes - Math.PI / 2;
      const raw = data[i]?.value ?? 0;
      // 0~10 스케일을 0~1로 정규화 / Normalize 0~10 to 0~1
      const norm = raw / 10;
      const clamped = Math.max(0, Math.min(1, norm));
      const r = radius * clamped;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // 데이터 포인트 / Data points
    ctx.fillStyle = '#7C3AED';
    for (let i = 0; i < axes; i++) {
      const angle = (Math.PI * 2 * i) / axes - Math.PI / 2;
      const raw = data[i]?.value ?? 0;
      // 0~10 스케일을 0~1로 정규화 / Normalize 0~10 to 0~1
      const norm = raw / 10;
      const clamped = Math.max(0, Math.min(1, norm));
      const r = radius * clamped;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // 축 라벨 / Axis labels
    ctx.font = '9px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillStyle = '#71717a';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < axes; i++) {
      const angle = (Math.PI * 2 * i) / axes - Math.PI / 2;
      const labelR = radius + 18;
      const x = cx + Math.cos(angle) * labelR;
      const y = cy + Math.sin(angle) * labelR;
      const key = data[i]?.metric ?? '';
      const label = METRIC_LABELS[key] || key;
      ctx.fillText(label, x, y);
    }
  }, [data, size]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: size, height: size }}
    />
  );
}