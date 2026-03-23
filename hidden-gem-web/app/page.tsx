// @ts-nocheck
"use client";

import { useState } from "react";
import { Search, Gamepad2, Sparkles, Zap } from "lucide-react";

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!query) return;
    setLoading(true);
    console.log("👉 프론트엔드: 백엔드로 검색 요청 보냄! 검색어:", query);

    try {
      // 💡 127.0.0.1 대신 localhost로 주소 통일!
      const response = await fetch(`http://localhost:8000/recommend?query=${query}`);
      const data = await response.json();
      console.log("👈 백엔드에서 받은 데이터:", data);
      setResults(data);
    } catch (error) {
      console.error("❌ 데이터 가져오기 실패 (연결 오류):", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center p-8 font-sans">
      <div className="flex items-center gap-2 px-4 py-2 bg-blue-900/20 border border-blue-500/30 rounded-full text-blue-400 text-xs font-mono mb-20">
        <Zap size={14} /> 783D + 5070 POWERED SYSTEM
      </div>

      <section className="max-w-4xl w-full text-center space-y-6">
        <div className="flex justify-center mb-6">
          <div className="p-4 bg-blue-600 rounded-3xl animate-bounce shadow-[0_0_40px_rgba(37,99,235,0.4)]">
            <Gamepad2 size={48} className="text-white" />
          </div>
        </div>
        <h1 className="text-7xl md:text-9xl font-black tracking-tighter italic uppercase">
          HIDDEN <span className="text-blue-600">GEM</span>
        </h1>
        <p className="text-gray-400 text-lg md:text-2xl font-light max-w-2xl mx-auto leading-relaxed">
          AI가 분석한 <span className="text-white font-medium">480+ 게임 데이터</span>로 <br />
          당신의 인생 명작을 0.1초 만에 발굴합니다.
        </p>
      </section>

      <section className="max-w-3xl w-full mt-16 relative">
        <div className="relative group">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="어떤 게임을 찾으시나요? (예: witcher, auto)"
            className="w-full bg-[#111] border-2 border-gray-800 rounded-3xl px-10 py-8 text-2xl focus:outline-none focus:border-blue-600 transition-all shadow-2xl text-white"
          />
          <button 
            onClick={handleSearch}
            className="absolute right-5 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 p-4 rounded-2xl transition-all"
          >
            <Search size={32} />
          </button>
        </div>
      </section>

      {/* 추천 결과 렌더링 */}
      {results.length > 0 && (
        <section className="mt-20 w-full max-w-5xl">
          <h2 className="text-3xl font-bold mb-8 text-blue-500 italic">💎 FOUND GEMS</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {results.map((game, idx) => (
              <div key={idx} className="bg-[#111] p-6 rounded-2xl border border-gray-800 hover:border-blue-600 transition-all">
                <h4 className="text-xl font-bold mb-2">{game.name}</h4>
                <div className="flex justify-between text-sm text-gray-400">
                  <span>⭐ {game.rating}</span>
                  <span>👥 {game.added} added</span>
                </div>
                {/* 💡 에러 방지용 안전장치: 점수가 있으면 보여주고, 없으면 N/A 처리! */}
                <div className="mt-4 text-xs text-blue-400 font-mono">
                  Score: {game.final_score ? game.final_score.toFixed(2) : 'N/A'}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 하단 카드 생략 없이 그대로 유지 */}
      <section className="mt-40 grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl w-full">
        <div className="p-10 bg-[#0f0f0f] border border-gray-800 rounded-[2.5rem] hover:border-blue-900/50 transition-all">
          <Sparkles className="text-blue-500 mb-6" size={40} />
          <h3 className="text-3xl font-bold mb-4 text-gray-100">AI Recommendation</h3>
          <p className="text-gray-500 text-lg leading-relaxed">
            실험실에서 검증된 <span className="text-blue-400">Vector Similarity</span> 로직이 적용되었습니다.
          </p>
        </div>
        <div className="p-10 bg-[#0f0f0f] border border-gray-800 rounded-[2.5rem] hover:border-blue-900/50 transition-all">
          <Gamepad2 className="text-blue-500 mb-6" size={40} />
          <h3 className="text-3xl font-bold mb-4 text-gray-100">Massive Database</h3>
          <p className="text-gray-500 text-lg leading-relaxed">
            RAWG API로 수집된 엄선된 데이터를 바탕으로 추천합니다.
          </p>
        </div>
      </section>
    </main>
  );
}