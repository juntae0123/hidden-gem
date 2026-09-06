/**
 * Taste DNA card — canvas-rendered shareable image.
 * 취향 DNA 카드 — 조정한 지표 + 추천작을 1080x1080 이미지로 렌더해 저장/공유.
 *
 * 외부 이미지는 CORS taint 때문에 canvas에 넣지 않는다 (텍스트/도형만).
 */
'use client';

import { SITE_URL } from '@/lib/constants';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Share2, Download, X } from 'lucide-react';
import { METRIC_LABELS, cn } from '@/lib/utils';
import { trackEvent } from '@/lib/umami';
import type { RecommendedGame } from '@/types/game';

const SIZE = 1080;

interface DnaCardProps {
  prefs: Record<string, number>;
  games: RecommendedGame[];
}

/** 조정 폭이 큰 순서로 상위 지표 추출 (5.0 = 중립) */
function topMetrics(prefs: Record<string, number>, n: number) {
  return Object.entries(prefs)
    .filter(([, v]) => Math.abs(v - 5.0) >= 0.5)
    .sort((a, b) => Math.abs(b[1] - 5.0) - Math.abs(a[1] - 5.0))
    .slice(0, n);
}

function drawCard(
  canvas: HTMLCanvasElement,
  prefs: Record<string, number>,
  games: RecommendedGame[],
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  canvas.width = SIZE;
  canvas.height = SIZE;

  // 배경
  const bg = ctx.createLinearGradient(0, 0, SIZE, SIZE);
  bg.addColorStop(0, '#0F0F13');
  bg.addColorStop(1, '#1A1025');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, SIZE, SIZE);

  // 상단 브랜드
  ctx.fillStyle = '#A78BFA';
  ctx.font = '600 34px system-ui, -apple-system, sans-serif';
  ctx.fillText('✦ HIDDEN GEM', 72, 96);

  ctx.fillStyle = '#FFFFFF';
  ctx.font = '700 64px system-ui, -apple-system, sans-serif';
  ctx.fillText('나의 게임 취향 DNA', 72, 190);

  ctx.fillStyle = '#71717A';
  ctx.font = '400 28px system-ui, -apple-system, sans-serif';
  ctx.fillText('60개 지표 취향 분석 결과', 72, 238);

  // 지표 바 차트
  const metrics = topMetrics(prefs, 6);
  const barX = 72;
  const barW = SIZE - 144;
  let y = 330;

  metrics.forEach(([key, value]) => {
    const label = METRIC_LABELS[key] || key;
    const up = value > 5;

    ctx.fillStyle = '#E4E4E7';
    ctx.font = '500 30px system-ui, -apple-system, sans-serif';
    ctx.fillText(`${label} ${up ? '↑' : '↓'}`, barX, y);

    ctx.fillStyle = '#A1A1AA';
    ctx.font = '600 28px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(value.toFixed(1), barX + barW, y);
    ctx.textAlign = 'left';

    // 트랙
    ctx.fillStyle = '#27272A';
    roundRect(ctx, barX, y + 16, barW, 16, 8);
    // 값
    ctx.fillStyle = up ? '#8B5CF6' : '#52525B';
    roundRect(ctx, barX, y + 16, Math.max(barW * (value / 10), 24), 16, 8);

    y += 92;
  });

  // 추천작
  y = Math.max(y + 40, 900 - games.slice(0, 3).length * 56);
  ctx.fillStyle = '#A78BFA';
  ctx.font = '600 30px system-ui, -apple-system, sans-serif';
  ctx.fillText('이 취향의 추천작', 72, y);
  y += 56;

  games.slice(0, 3).forEach((g, i) => {
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '500 32px system-ui, -apple-system, sans-serif';
    const name = g.name.length > 28 ? g.name.slice(0, 27) + '…' : g.name;
    ctx.fillText(`${i + 1}. ${name}`, 72, y);

    ctx.fillStyle = '#8B5CF6';
    ctx.textAlign = 'right';
    ctx.font = '600 32px system-ui, -apple-system, sans-serif';
    ctx.fillText(`${Math.round(g.similarity_score)}점`, SIZE - 72, y);
    ctx.textAlign = 'left';
    y += 56;
  });

  // 푸터 (배포 도메인을 자동으로 따라감)
  const host = typeof window !== 'undefined' ? window.location.host : SITE_URL.replace(/^https?:\/\//, '');
  ctx.fillStyle = '#52525B';
  ctx.font = '400 26px system-ui, -apple-system, sans-serif';
  ctx.fillText(`내 취향 분석하기 → ${host}`, 72, SIZE - 64);
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}

export function DnaCard({ prefs, games }: DnaCardProps) {
  const [open, setOpen] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (open && canvasRef.current) {
      drawCard(canvasRef.current, prefs, games);
    }
  }, [open, prefs, games]);

  const handleOpen = () => {
    setOpen(true);
    trackEvent('dna_card_create');
  };

  const handleSave = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = 'hidden-gem-dna.png';
    a.click();
    trackEvent('dna_card_save');
  }, []);

  const handleShare = useCallback(async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    trackEvent('dna_card_share');

    const blob: Blob | null = await new Promise((res) => canvas.toBlob(res, 'image/png'));
    if (blob && typeof navigator.share === 'function') {
      const file = new File([blob], 'hidden-gem-dna.png', { type: 'image/png' });
      try {
        await navigator.share({
          title: 'Hidden Gem — 나의 게임 취향 DNA',
          text: '60개 지표로 분석한 내 게임 취향',
          files: [file],
        });
        return;
      } catch {
        // 사용자가 취소했거나 파일 공유 미지원 — 저장으로 폴백
      }
    }
    handleSave();
  }, [handleSave]);

  if (topMetrics(prefs, 1).length === 0) return null;

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        className={cn(
          'px-4 py-2 rounded-lg text-[13px] font-medium',
          'bg-purple-600/10 text-purple-700 dark:text-purple-300',
          'border border-purple-200 dark:border-purple-800',
          'hover:bg-purple-600/20 transition-colors'
        )}
      >
        취향 DNA 카드 만들기
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-zinc-950 border border-zinc-800 rounded-2xl p-4 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-zinc-200">취향 DNA 카드</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기"
                className="w-8 h-8 rounded-md flex items-center justify-center text-zinc-400 hover:text-zinc-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <canvas
              ref={canvasRef}
              className="w-full rounded-xl border border-zinc-800"
              aria-label="취향 DNA 카드 미리보기"
            />

            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={handleSave}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-zinc-800 text-zinc-100 text-[13px] hover:bg-zinc-700 transition-colors"
              >
                <Download className="w-4 h-4" />
                이미지 저장
              </button>
              <button
                type="button"
                onClick={handleShare}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-purple-600 text-white text-[13px] hover:bg-purple-700 transition-colors"
              >
                <Share2 className="w-4 h-4" />
                공유하기
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
