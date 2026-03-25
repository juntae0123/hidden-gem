'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ExternalLink, Award, ChevronDown, ChevronUp, Zap } from 'lucide-react'; // Zap 추가
import type { Game, TierType, TierConfig } from '../types';
import RadarChart from './radarchart';
import './gamecard.css';

// 🆕 v2.5 인텐트 타입 정의
interface Intent {
  id: string;
  name: string;
}

// 지표 한글 매핑 (기존 유지)
const METRIC_KOREAN: Record<string, string> = {
  mania_score: "마니아 매력",
  story_depth: "스토리 깊이",
  originality: "독창성",
  difficulty: "난이도",
  art_style: "아트 스타일",
  replay_value: "리플레이 가치",
  indie_spirit: "인디 감성",
  character_appeal: "캐릭터 매력",
  user_friendliness: "접근성",
  addictiveness: "중독성",
  emotional_impact: "감정적 임팩트",
  atmosphere_intensity: "분위기 몰입",
  soundtrack_prominence: "사운드트랙",
  gem_potential: "숨겨진 명작"
};

// 등급 설정 (기존 유지)
const TIER_CONFIG: Record<TierType, TierConfig> = {
  legendary: { label: 'LEGENDARY', color: '#FFD700' },
  mythic: { label: 'MYTHIC', color: '#FF0000' },
  epic: { label: 'EPIC', color: '#A335EE' },
  rare: { label: 'RARE', color: '#0070DD' },
  uncommon: { label: 'UNCOMMON', color: '#1EFF00' },
  solid: { label: 'SOLID', color: '#CD7F32' },
  maniac: { label: 'ANOMALY', color: '#00FF41' }
};

const getTier = (score: number, status: string): TierType => {
  if (status === "MANIAC") return 'maniac';
  if (score > 100) return 'legendary';
  if (score === 100) return 'mythic';
  if (score >= 90) return 'epic';
  if (score >= 80) return 'rare';
  if (score >= 70) return 'uncommon';
  return 'solid';
};

interface GameCardProps {
  game: any; // 👈 타입을 잠시 any로 열어서 에러를 확실히 잡습니다
  rank: number;
}

export default function GameCard({ game, rank }: GameCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const tier = useMemo(() => getTier(game.final_score, game.status), [game.final_score, game.status]);
  const config = TIER_CONFIG[tier];

  const handleToggle = () => setIsExpanded(prev => !prev);
  
  const handleSteamClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const genreTags = useMemo(() => 
    game.genres.split(',').slice(0, 3).map((g: string) => g.trim()),
    [game.genres]
  );

  const boostEntries = useMemo(() => 
    game.boost_info ? Object.entries(game.boost_info) : [],
    [game.boost_info]
  );

  return (
    <motion.article 
      layout
      className={`game-card-container ${tier} mb-4`} // 여백 추가
      onClick={handleToggle}
      role="button"
      tabIndex={0}
      aria-expanded={isExpanded}
      onKeyDown={(e) => e.key === 'Enter' && handleToggle()}
    >
      {/* 헤더 (기존 디자인 100% 유지) */}
      <div className="card-header">
        <div className="rank-badge">#{rank}</div>
        
        <div className="game-info-main">
          <h3 className="game-name">{game.name}</h3>
          <div className="genre-tags">
            {genreTags.map((g: string, i: number) => (
              <span key={i} className="tag">{g}</span>
            ))}
          </div>
        </div>
        
        <div className="score-section" style={{ color: config.color }}>
          <span className="tier-label">{config.label}</span>
          <span className="score-value">{game.final_score.toFixed(1)}</span>
        </div>
      </div>

      {/* 🆕 한글 인텐트 태그 (헤더 하단에 추가) */}
      {!isExpanded && (
        <div className="flex flex-wrap gap-2 px-6 pb-3">
          {game.matched_intents?.map((intent: Intent) => (
            <span key={intent.id} className="text-[10px] text-blue-300 opacity-60">
              #{intent.name}
            </span>
          ))}
        </div>
      )}

      {/* 부스트 요약 (기존 유지) */}
      {!isExpanded && game.boost_reason && (
        <div className="boost-reason-summary flex items-center gap-2">
          <Zap size={12} /> {game.boost_reason}
        </div>
      )}

      {/* Fallback 뱃지 (기존 유지) */}
      {game.fallback_rescued && (
        <p className="fallback-rescued-badge px-6 pb-2">
          💎 기준 완화로 발굴된 숨겨진 보석
        </p>
      )}

      {/* 확장 영역 (기존 디자인 100% 유지) */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div 
            key="details"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="card-details"
          >
            <hr className="divider" />
            
            <div className="details-grid">
              <div className="details-text">
                <h4 className="details-title">
                  <Award size={18} className="inline mr-2 text-blue-400" />
                  감별 리포트
                </h4>
                
                <p className="description">{game.description}</p>
                
                {/* 🆕 장르 매칭 분석 정보 추가 (v2.5 신기능) */}
                {game.genre_match && (
                  <div className="mb-4 text-xs p-2 bg-white/5 rounded border border-white/10">
                    <span className="text-gray-500">AI 장르 분석: </span>
                    <span className={game.genre_match.is_match ? "text-green-400" : "text-yellow-400"}>
                      {game.genre_match.reason} (x{game.genre_match.multiplier})
                    </span>
                  </div>
                )}

                {boostEntries.length > 0 && (
                  <div className="boost-details-list">
                    <h5>📊 취향 반영 상세</h5>
                    {boostEntries.map(([metric, info]: [string, any]) => (
                      <div key={metric} className="boost-item">
                        <span className="metric-name">{METRIC_KOREAN[metric] || metric}</span>
                        <span className="boost-val">x{(info.final_weight || info.after_base || 1.0).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
              <div className="details-chart">
                <RadarChart scores={game.scores} tier={tier} />
              </div>
            </div>

            <div className="card-footer">
              <a 
                href={`https://store.steampowered.com/app/${game.app_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="steam-button"
                onClick={handleSteamClick}
              >
                🎮 Steam 상점 바로가기 
                <ExternalLink size={16} className="ml-2" />
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="expand-indicator">
        {isExpanded ? <><ChevronUp size={14} /> 접기</> : <><ChevronDown size={14} /> 상세 정보 보기</>}
      </div>
    </motion.article>
  );
}