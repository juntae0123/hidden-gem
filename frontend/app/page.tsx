'use client';

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Gamepad2, Sparkles, Zap, AlertCircle } from "lucide-react";
// 💡 GameCard 경로는 멘티님의 폴더 구조에 맞춰야 합니다. (예: ./components/GameCard)
import GameCard from './components/gamecard'; 

// --- 인터페이스 (데이터 구조 정의) ---
interface Intent {
  id: string;
  name: string;
}

interface Game {
  app_id: string;
  name: string;
  genres: string;
  developer: string;
  description: string;
  final_score: number;
  status: string;
  similarity: number;
  matched_intents: Intent[]; 
  scores: Record<string, number>;
  genre_match?: {
    multiplier: number;
    reason: string;
    is_match: boolean;
  };
  fallback_rescued?: boolean;
}

interface SearchResponse {
  query: string;
  intents: Intent[]; 
  gems: Game[];
  maniacs: Game[];
  fallback_activated: boolean;
  fallback_message: string | null;
  search_stage: number;
  total_candidates: number;
  algorithm_version: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSearched, setIsSearched] = useState(false);

  const handleSearch = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setIsSearched(true);

    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          query: query.trim(), 
          top_k: 10, 
          include_maniac: true 
        }),
      });

      if (!response.ok) throw new Error(`서버 오류: ${response.status}`);

      const data: SearchResponse = await response.json();
      setResults(data);
    } catch (err) {
      console.error("❌ 검색 실패:", err);
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다");
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleReset = () => {
    setQuery("");
    setResults(null);
    setIsSearched(false);
    setError(null);
  };

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center p-4 md:p-8 font-sans overflow-x-hidden">
      
      {/* 🚀 헤더 */}
      <motion.header 
        layout
        className="w-full max-w-6xl flex items-center justify-between mb-8 md:mb-12"
      >
        <div 
          className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity" 
          onClick={handleReset}
        >
          <Gamepad2 size={28} className="text-blue-500 md:w-8 md:h-8" />
          <h1 className="text-2xl md:text-3xl font-black tracking-tighter italic uppercase">
            HIDDEN <span className="text-blue-500">GEM</span>
          </h1>
        </div>
        
        <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-blue-900/20 border border-blue-500/30 rounded-full text-blue-400 text-xs font-mono">
          <Zap size={14} /> v2.5 POWERED
        </div>
      </motion.header>

      <AnimatePresence mode="wait">
        {!isSearched ? (
          <motion.section 
            key="landing"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, y: -50 }}
            className="w-full max-w-4xl text-center space-y-6 mt-[5vh] md:mt-[10vh]"
          >
            <h1 className="text-4xl md:text-7xl lg:text-8xl font-black tracking-tighter italic uppercase leading-tight">
              당신의 <span className="text-blue-500">인생 명작</span>을 <br className="hidden md:block" />
              0.1초 만에 발굴합니다.
            </h1>
            <p className="text-gray-400 text-base md:text-xl lg:text-2xl font-light max-w-2xl mx-auto">
              AI가 스캔한 <span className="text-white font-medium">5,000+ 게임 데이터</span>로<br/>
              당신의 숨겨진 취향을 <span className="text-blue-400 font-bold">한글화 분석</span>합니다.
            </p>
            <form onSubmit={handleSearch} className="max-w-3xl w-full mt-8 md:mt-12 relative mx-auto px-4">
              <div className="relative group">
                <input
                  type="text"
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="예: 림월드 같이 세계 구축하면서 적들 잡는 게임"
                  className="w-full bg-[#111] border-2 border-gray-800 rounded-2xl md:rounded-3xl 
                             px-6 py-4 md:px-10 md:py-6 text-base md:text-xl text-white outline-none focus:border-blue-500 transition-all"
                />
                <button 
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="absolute right-2 md:right-4 top-1/2 -translate-y-1/2 bg-blue-600 p-3 md:p-4 rounded-xl transition-all"
                >
                  <Search size={20} className="md:w-6 md:h-6" />
                </button>
              </div>
            </form>
            <div className="mt-20 md:mt-32 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl w-full px-4 text-left">
                <FeatureCard 
                    icon={<Sparkles className="text-blue-500" size={36} />}
                    title="AI 감별 v2.5"
                    description="강화된 한글 분석으로 숨겨진 게임의 본질을 꿰뚫어봅니다."
                />
                <FeatureCard 
                    icon={<Gamepad2 className="text-blue-500" size={36} />}
                    title="Massive DB"
                    description="5,000여 개의 인디 게임 데이터를 실시간으로 비교 분석합니다."
                />
            </div>
          </motion.section>
        ) : (
          <motion.section 
            key="results"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-5xl"
          >
            <form onSubmit={handleSearch} className="w-full max-w-3xl mx-auto relative mb-12">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-[#111] border border-gray-800 rounded-xl px-5 py-3 text-white outline-none focus:border-blue-500"
              />
              <button type="submit" className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-blue-600 rounded-lg">
                <Search size={18} />
              </button>
            </form>

            {loading && <LoadingState />}
            {error && <ErrorState message={error} onRetry={handleSearch} />}

            {!loading && !error && results && (
              <div className="space-y-12">
                {results.intents && results.intents.length > 0 && (
                  <div className="flex flex-wrap gap-2 justify-center">
                    {results.intents.map((intent) => (
                      <span key={intent.id} className="bg-blue-900/40 text-blue-300 px-4 py-1.5 rounded-full text-sm font-bold border border-blue-500/30">
                        #{intent.name}
                      </span>
                    ))}
                  </div>
                )}
                <div className="space-y-6">
                  <h2 className="text-2xl md:text-3xl font-black text-blue-400 flex items-center gap-3">
                    <Sparkles size={28} /> 발굴된 보석 ({results.gems.length})
                  </h2>
                  <div className="space-y-6">
                    {results.gems.map((game, idx) => (
                      <GameCard key={game.app_id} game={game} rank={idx + 1} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </motion.section>
        )}
      </AnimatePresence>
    </main>
  );
}

// --- 하단 보조 컴포넌트 (절대 생략 금지) ---
function FeatureCard({ icon, title, description }: any) {
  return (
    <div className="p-8 bg-[#0f0f0f] border border-gray-800 rounded-2xl hover:border-blue-900/50 transition-all duration-300">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-bold mb-3">{title}</h3>
      <p className="text-gray-500 text-sm">{description}</p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="text-center py-24 space-y-4">
      <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
      <p className="text-blue-400 font-bold text-xl animate-pulse">DNA 분석 중...</p>
    </div>
  );
}

function ErrorState({ message, onRetry }: any) {
  return (
    <div className="text-center py-20 bg-red-950/20 border border-red-900/50 rounded-3xl p-10 max-w-md mx-auto">
      <AlertCircle className="text-red-500 mx-auto mb-6" size={60} />
      <p className="text-gray-400 mb-8">{message}</p>
      <button onClick={onRetry} className="bg-red-600 px-10 py-4 rounded-xl font-bold">다시 시도</button>
    </div>
  );
}