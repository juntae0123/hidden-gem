// components/herobanner.tsx - v4.2
"use client";

import { GameResult, METRIC_LABELS } from "../types/index";
import RadarChart from "./radarchart";

interface HeroBannerProps {
  game: GameResult;
}

export default function HeroBanner({ game }: HeroBannerProps) {
  const steamUrl = `https://store.steampowered.com/app/${game.app_id}`;

  return (
    <div className="hero-banner p-5 relative z-10">
      <div className="flex flex-col lg:flex-row gap-5">
        {/* 왼쪽: 기본 정보 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3">
            <span className="hero-crown text-3xl">👑</span>
            <h2 className="text-2xl font-black text-white truncate">{game.name}</h2>
          </div>

          <div className="flex items-center gap-3 mb-3">
            <span className="text-4xl font-black text-yellow-400">
              {game.final_score.toFixed(1)}
            </span>
            {game.final_score >= 100 && <span className="text-2xl">🔥</span>}
            <span className="px-3 py-1 bg-linear-to-r from-yellow-500 to-orange-500 rounded-full text-black font-bold text-sm">
              {game.status}
            </span>
          </div>

          <p className="text-gray-400 text-sm mb-2">🎮 {game.developer}</p>

          <div className="flex flex-wrap gap-2">
            {game.genres
              .split(",")
              .slice(0, 4)
              .map((genre, i) => (
                <span
                  key={i}
                  className="px-2 py-1 bg-yellow-500/20 text-yellow-300 rounded text-xs"
                >
                  {genre.trim()}
                </span>
              ))}
          </div>
        </div>

        {/* 중간: 설명 */}
        <div className="flex-1 lg:border-l lg:border-r border-yellow-500/20 lg:px-5">
          <p className="text-gray-300 text-sm leading-relaxed line-clamp-4 lg:line-clamp-none">
            {game.description || "설명이 없습니다."}
          </p>

          {game.matched_intents && game.matched_intents.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {game.matched_intents.slice(0, 3).map((intent, i) => (
                <span
                  key={intent.id || i}
                  className="px-2 py-1 bg-purple-500/30 text-purple-300 rounded-full text-xs"
                >
                  ✨ {intent.name}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 오른쪽: 차트 + 버튼 */}
        <div className="lg:w-48 flex flex-col items-center justify-center">
          <RadarChart scores={game.scores} statusColor="#FFD700" size={140} />

          <a
            href={steamUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 w-full py-2 bg-linear-to-r from-yellow-500 to-orange-500 rounded-lg text-black text-center font-bold text-sm hover:from-yellow-400 hover:to-orange-400 transition-all"
          >
            Steam
          </a>
        </div>
      </div>
    </div>
  );
}
