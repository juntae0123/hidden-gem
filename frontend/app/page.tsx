// app/page.tsx - v4.2
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import GameCard from "./components/gamecard";
import HeroBanner from "./components/herobanner";
import { SearchResponse, GameResult } from "./types";

type TabType = "main" | "alternative";

export default function Home() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("main");

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setSearchResult(null);
    setActiveTab("main");

    try {
      const response = await fetch("http://localhost:8000/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), top_k: 10 }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data: SearchResponse = await response.json();

      if (!data.is_game_search) {
        setError(data.error || "게임과 관련된 질문을 해주세요! 🎮");
        return;
      }

      setSearchResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "검색 중 오류가 발생했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  // 🔥 Exact Match 분리
  const heroGame: GameResult | null =
    searchResult?.main_results?.find((g) => g.is_exact_match) || null;

  // 히어로 제외한 메인 결과
  const filteredMainResults: GameResult[] =
    searchResult?.main_results?.filter((g) => !g.is_exact_match) || [];

  const altResults: GameResult[] = searchResult?.alternative_results || [];

  const getCurrentGames = (): GameResult[] => {
    return activeTab === "main" ? filteredMainResults : altResults;
  };

  const mainCount = filteredMainResults.length;
  const altCount = altResults.length;

  return (
    <div className="min-h-screen">
      {/* 헤더 */}
      <header className="pt-12 pb-8 text-center">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-5xl font-bold"
          style={{
            background: "linear-gradient(90deg, #FFD700, #FF6B6B, #A855F7, #3B82F6)",
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          💎 Hidden Gem
        </motion.h1>
        <p className="mt-2 text-gray-400">당신만을 위한 숨겨진 명작을 발굴합니다</p>
      </header>

      {/* 검색창 */}
      <div className="max-w-2xl mx-auto px-4 mb-8">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="어떤 게임을 찾으시나요? (예: 림월드 같은 건설 생존 게임)"
            className="w-full px-6 py-4 bg-gray-800/80 border border-gray-700 rounded-2xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-6 py-2 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl text-white font-semibold hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                검색중...
              </span>
            ) : (
              "🔍 검색"
            )}
          </button>
        </div>
      </div>

      {/* 에러 메시지 */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="max-w-2xl mx-auto px-4 mb-8"
          >
            <div className="bg-red-500/20 border border-red-500/50 rounded-xl p-6 text-center">
              <p className="text-red-400 text-lg font-semibold mb-2">{error}</p>
              <p className="text-gray-500 text-sm mt-4">
                💡 예: "림월드 같은 건설 생존 게임", "스토리 좋은 인디 RPG"
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 검색 결과 */}
      {searchResult && searchResult.is_game_search && (
        <div className="max-w-6xl mx-auto px-4 pb-16">
          {/* 탭 UI (상단) */}
          <div className="flex justify-center mb-6">
            <div className="inline-flex bg-gray-800/50 rounded-xl p-1">
              <button
                onClick={() => setActiveTab("main")}
                className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                  activeTab === "main"
                    ? "bg-gradient-to-r from-purple-600 to-pink-600 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                🎯 메인 결과
                {mainCount > 0 && (
                  <span className="ml-2 px-2 py-0.5 bg-white/20 rounded-full text-sm">
                    {mainCount}
                  </span>
                )}
              </button>

              <button
                onClick={() => setActiveTab("alternative")}
                className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                  activeTab === "alternative"
                    ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                💡 장르 다른 추천
                {altCount > 0 && (
                  <span className="ml-2 px-2 py-0.5 bg-white/20 rounded-full text-sm">
                    {altCount}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* 🏆 0등석 히어로 배너 (탭 아래) */}
          {heroGame && activeTab === "main" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="mb-8"
            >
              <div className="text-center mb-3">
                <span className="text-yellow-400 text-sm font-semibold">
                  👑 0등석 히어로 배너 (Exact Match)
                </span>
              </div>
              <HeroBanner game={heroGame} />
            </motion.div>
          )}

          {/* 요약 정보 */}
          <div className="mb-6 text-center">
            <p className="text-gray-400 text-sm">
              <span className="text-purple-400 font-semibold">
                "{searchResult.summary_query || query}"
              </span>
              {" "}검색 결과{" "}
              <span className="text-white font-bold">{searchResult.total_found}</span>개
            </p>
          </div>

          {/* 게임 카드 그리드 */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
            >
              {getCurrentGames().length > 0 ? (
                getCurrentGames().map((game, index) => (
                  <motion.div
                    key={game.app_id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.08 }}
                  >
                    <GameCard game={game} rank={index + 1} />
                  </motion.div>
                ))
              ) : (
                <div className="col-span-full text-center py-12">
                  <p className="text-gray-500 text-lg">
                    {activeTab === "main"
                      ? "😢 메인 결과가 없습니다"
                      : "이 탭에 표시할 게임이 없습니다"}
                  </p>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* 인텐트 태그 */}
          {searchResult.intents && searchResult.intents.length > 0 && (
            <div className="mt-8 text-center">
              <p className="text-gray-500 text-sm mb-2">감지된 취향:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {searchResult.intents.map((intent, i) => (
                  <span
                    key={intent.id || i}
                    className="px-3 py-1 bg-gray-700/50 text-gray-300 rounded-full text-sm"
                  >
                    {intent.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 초기 상태 */}
      {!searchResult && !error && !isLoading && (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">
            🎮 검색어를 입력하고 숨겨진 명작을 찾아보세요!
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {["림월드 같은 건설 생존", "스토리 좋은 인디 RPG", "어려운 로그라이크"].map(
              (example) => (
                <button
                  key={example}
                  onClick={() => setQuery(example)}
                  className="px-4 py-2 bg-gray-800/50 text-gray-400 rounded-lg hover:bg-gray-700/50 hover:text-white transition-all"
                >
                  {example}
                </button>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
