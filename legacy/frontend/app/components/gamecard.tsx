// components/gamecard.tsx - v4.2 메달 글로우 + 점수 글로우
"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { GameResult, STATUS_COLORS, METRIC_LABELS } from "../types";
import RadarChart from "./radarchart";

interface GameCardProps {
  game: GameResult;
  rank: number;
}

export default function GameCard({ game, rank }: GameCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusColor = STATUS_COLORS[game.status] || STATUS_COLORS.COMMON;
  const steamUrl = `https://store.steampowered.com/app/${game.app_id}`;

  // 🔥 글로우 결정 로직: 1~3등은 메달, 4등 이하는 점수
  const getGlowClass = (): string => {
    // 1~3등: 메달 색상 글로우
    if (rank === 1) return "glow-gold";
    if (rank === 2) return "glow-silver";
    if (rank === 3) return "glow-bronze";
    
    // 4등 이하: 점수 기반 글로우
    if (game.final_score >= 100 || game.status === "LEGENDARY") return "glow-legendary";
    if (game.status === "EPIC") return "glow-epic";
    if (game.status === "RARE") return "glow-rare";
    if (game.status === "UNCOMMON") return "glow-uncommon";
    return "";
  };

  // 메달 이모지 + 클래스
  const getMedal = (): { emoji: string; className: string } | null => {
    if (rank === 1) return { emoji: "🥇", className: "medal-gold" };
    if (rank === 2) return { emoji: "🥈", className: "medal-silver" };
    if (rank === 3) return { emoji: "🥉", className: "medal-bronze" };
    return null;
  };

  const medal = getMedal();
  const glowClass = getGlowClass();

  return (
    <motion.div layout className={`game-card ${glowClass}`}>
      {/* 순위 배지 */}
      <div
        className={`absolute top-3 right-3 w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg z-10 ${
          medal ? medal.className : ""
        }`}
        style={
          !medal
            ? { background: `linear-gradient(135deg, ${statusColor}, ${statusColor}cc)` }
            : {}
        }
      >
        {medal ? medal.emoji : rank}
      </div>

      {/* Fallback 뱃지 */}
      {game.is_fallback && (
        <div className="absolute top-3 left-3 z-10">
          <span className="fallback-badge px-3 py-1 rounded-full text-white text-xs font-bold">
            🔥 인기 추천 명작
          </span>
        </div>
      )}

      <div className="p-5">
        {/* 게임 이름 */}
        <h3 className="text-xl font-bold text-white mb-3 pr-12 leading-tight">
          {game.name}
        </h3>

        {/* 점수 & 등급 */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-baseline gap-1">
            <span
              className={`text-3xl font-black ${
                game.final_score >= 100 ? "score-fire" : ""
              }`}
              style={{ color: game.final_score < 100 ? statusColor : undefined }}
            >
              {game.final_score.toFixed(1)}
            </span>
            {game.final_score >= 100 && <span className="text-xl">🔥</span>}
          </div>

          <span
            className="px-3 py-1 rounded-full text-sm font-bold text-white"
            style={{
              background: `linear-gradient(135deg, ${statusColor}, ${statusColor}cc)`,
            }}
          >
            {game.status}
          </span>

          {/* 유사도 (Fallback 아닐 때만) */}
          {!game.is_fallback && (
            <span className="text-gray-500 text-sm">
              {(game.similarity * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {/* 장르 */}
        <div className="flex flex-wrap gap-2 mb-3">
          {game.genres
            .split(",")
            .slice(0, 3)
            .map((genre, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-gray-700/50 text-gray-300 rounded text-xs"
              >
                {genre.trim()}
              </span>
            ))}
        </div>

        {/* 개발사 */}
        <p className="text-gray-500 text-sm mb-3">🎮 {game.developer}</p>

        {/* 인텐트 */}
        {game.matched_intents && game.matched_intents.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {game.matched_intents.slice(0, 2).map((intent, i) => (
              <span
                key={intent.id || i}
                className="px-2 py-1 bg-purple-500/20 text-purple-300 rounded-full text-xs"
              >
                ✨ {intent.name}
              </span>
            ))}
          </div>
        )}

        {/* 확장 토글 */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full py-2 text-gray-400 hover:text-white text-sm transition-colors"
        >
          {isExpanded ? "▲ 접기" : "▼ 상세 보기"}
        </button>

        {/* 확장 영역 */}
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-4 pt-4 border-t border-gray-700"
          >
            <p className="text-gray-400 text-sm mb-4 line-clamp-3">
              {game.description || "설명이 없습니다."}
            </p>

            <div className="mb-4">
              <RadarChart scores={game.scores} statusColor={statusColor} size={180} />
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              {Object.entries(game.scores)
                .slice(0, 6)
                .map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-gray-500">{METRIC_LABELS[key] || key}</span>
                    <span className="text-white font-semibold">{value}</span>
                  </div>
                ))}
            </div>

            <a
              href={steamUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full py-3 bg-linear-to-r from-blue-600 to-blue-700 rounded-xl text-white text-center font-semibold hover:from-blue-500 hover:to-blue-600 transition-all"
            >
              🎮 Steam에서 보기
            </a>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
