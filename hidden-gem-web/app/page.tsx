import { Search, Gamepad2, Sparkles, Zap } from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center p-8 font-sans">
      {/* 783D + 5070 파워 뱃지 */}
      <div className="flex items-center gap-2 px-4 py-2 bg-blue-900/20 border border-blue-500/30 rounded-full text-blue-400 text-xs font-mono mb-20">
        <Zap size={14} /> 783D + 5070 POWERED SYSTEM
      </div>

      {/* 메인 타이틀 */}
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
          AI가 분석한 <span className="text-white font-medium">500+ 게임 데이터</span>로 <br />
          당신의 인생 명작을 0.1초 만에 발굴합니다.
        </p>
      </section>

      {/* 검색창 */}
      <section className="max-w-3xl w-full mt-16 relative">
        <div className="relative group">
          <input
            type="text"
            placeholder="어떤 게임을 찾으시나요? (예: 위쳐3 스타일의 RPG)"
            className="w-full bg-[#111] border-2 border-gray-800 rounded-3xl px-10 py-8 text-2xl focus:outline-none focus:border-blue-600 transition-all shadow-2xl text-white"
          />
          <button className="absolute right-5 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 p-4 rounded-2xl transition-all">
            <Search size={32} />
          </button>
        </div>
      </section>

      {/* 하단 카드 섹션 */}
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