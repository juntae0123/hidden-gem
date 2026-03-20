# 🎮 Hidden-Gem Finder

**Steam이 못 찾는 숨겨진 명작을 찾아주는 AI 기반 개인화 게임 추천 서비스**

![프로젝트 썸네일 이미지 자리 - 나중에 UI 캡처해서 넣으세요]

---

## 📌 1. 프로젝트 개요 (Overview)

**Hidden-Gem Finder**는 단순한 장르 매칭이나 인기순 추천을 넘어, 사용자의 세밀한 플레이 스타일과 텍스트 리뷰(메타데이터)를 분석하여 '숨겨진 취향 저격 게임'을 찾아주는 AI 추천 웹 서비스입니다.

자연어 처리(NLP) 임베딩 기술을 활용해 게임 간의 딥러닝 기반 유사도를 측정하고, LLM(거대 언어 모델)을 통해 **"왜 이 게임이 당신에게 맞는지"**를 사람의 언어로 설명해 주는 **XAI(설명 가능한 AI)** 시스템을 구현하는 것을 목표로 합니다.

---

## ❗ 2. 문제 정의 (Problem Statement)

기존 대형 플랫폼(Steam 등)의 게임 추천 알고리즘은 다음과 같은 고질적인 한계(Filter Bubble)를 지니고 있습니다.

- **인기도 편향 (Popularity Bias):** 사용자의 세부 취향과 무관하게, 결국 GTA5, 배틀그라운드 같은 유명 게임만 반복 추천됨.
- **단순 메타데이터 매칭:** "RPG"를 좋아한다고 해서 모든 RPG를 좋아하는 것이 아님. (예: 다크 판타지 RPG vs 캐주얼 RPG의 차이를 구분하지 못함)
- **블랙박스 현상:** "이 게임을 왜 나에게 추천했는지" 이유를 알 수 없어 사용자의 클릭률(CTR) 및 신뢰도가 떨어짐.

👉 **해결책:** 본 프로젝트는 **'유명 게임 패널티 부여', '게임 설명 텍스트의 벡터화(Vectorization)', 'LLM 기반 추천 이유 생성'**을 통해 인지도 높은 게임에 가려진 **나만의 명작(Hidden Gem)**을 발굴합니다.

---

## 💡 3. 핵심 기능 (Core Features)

### 🎯 1) 취향 프로파일링 (User Profiling)
단순 장르 선택이 아닌, **선호/비선호 키워드** (예: "스토리 중심", "어두운 분위기", "멀티플레이 비선호") 및 **'가장 재밌게 한 인생 게임 3개'**를 입력받아 유저 벡터(User Vector)를 생성합니다.

### 🧠 2) 하이브리드 추천 엔진 (Hybrid Recommendation)
- **콘텐츠 기반 필터링 (임베딩 검색):** RAWG API에서 수집한 게임의 Description(설명)을 `Sentence-Transformers` 모델을 사용해 다차원 벡터로 변환합니다. FAISS(또는 pgvector)를 활용해 유저 취향 벡터와 코사인 유사도(Cosine Similarity)가 가장 높은 게임을 탐색합니다.
- **인기도 패널티 (Long-tail 알고리즘):** 너무 뻔한 AAA급 게임이 추천을 도배하지 않도록, 리뷰 수가 일정 기준을 초과하는 게임은 추천 가중치를 낮춥니다.

### 💬 3) XAI: 설명 가능한 추천 (LLM Integration)
검색된 결과값(게임 메타데이터)과 사용자의 초기 입력 데이터를 조합하여 LLM(OpenAI/Claude API)에 프롬프트로 전달합니다.
- **출력 예시:** *"이 게임은 [어두운 다크 판타지] 요소가 강하며, 당신이 인생 게임으로 꼽은 [다크소울 3]와 유사한 [패링 액션] 시스템을 갖추고 있어 추천합니다."*

### 🔄 4) 피드백 루프 (Data Flywheel)
추천 결과에 대한 사용자의 **좋아요(Like) / 싫어요(Dislike)** 데이터를 DB에 축적합니다. 향후 데이터가 쌓이면 협업 필터링(Collaborative Filtering)을 도입하여 추천 모델을 고도화할 수 있도록 설계했습니다.

---

## ⚙️ 4. 시스템 흐름 및 아키텍처 (System Architecture)

### Core Flow
> **User Input** → **User Profile Text 생성** → **Embedding 변환** → **Vector DB 유사도 검색** → **Popularity Penalty 적용** → **Top-K 게임 선정** → **LLM 추천 이유 생성** → **결과 반환**

### Architecture Diagram
```text
[ Client (Next.js) ]    │   1. 유저 취향 데이터 전송 (인생게임, 키워드)
   ▼
[ Backend API (FastAPI) ] 
   │   2. 텍스트 데이터를 벡터화 (Embedding)
   │   3. Vector DB에서 유사도 검색 (Cosine Similarity)
   ▼
[ Vector DB (pgvector / FAISS) ] -> (가장 유사한 인디/명작 게임 Top 3 반환)
   │
   │   4. 검색된 게임 정보 + 유저 취향 텍스트 묶음
   ▼
[ LLM (OpenAI API) ] -> ("추천 이유" 자연어 문장 생성)
   │
   │   5. 최종 JSON (게임 데이터 + 추천 이유) 반환
   ▼
[ Client (Next.js) ] -> (사용자에게 예쁜 UI로 렌더링)
```

### Recommendation Logic (추천 점수 수식)
유명 게임 편향을 줄이고 Hidden Gem 노출을 강화하기 위해 아래 수식을 사용합니다.

$$Final\ Score = \alpha \times Similarity - \beta \times \log(review\_count + 1)$$

* **$Similarity$**: 유저 취향 ↔ 게임 설명 간의 의미적 유사도 (Cosine Similarity)
* **$review\_count$**: 게임 인기도 (리뷰 수)
* **$\alpha, \beta$**: 하이퍼파라미터

---

## 🛠️ 5. 기술 스택 (Tech Stack)

### 🎨 Frontend
- **Next.js (React):** SEO 최적화 및 빠른 렌더링
- **Tailwind CSS:** 직관적이고 반응형인 UI 구현
- **Zustand:** 가벼운 전역 상태 관리 (유저 취향 데이터 임시 저장)

### ⚙️ Backend & DB
- **FastAPI (Python):** 비동기 처리(Async)를 통한 빠르고 가벼운 AI 추론 API 서버
- **PostgreSQL (Supabase):** 관계형 데이터 및 유저 피드백 저장
- **pgvector (또는 FAISS):** 게임 설명 텍스트의 임베딩 벡터 저장 및 초고속 유사도 검색

### 🤖 AI / ML Pipeline
- **Data Collection:** RAWG API (게임 메타데이터 크롤링)
- **Embedding Model:** `Sentence-Transformers` (오픈소스 텍스트 임베딩)
- **LLM:** OpenAI GPT-4o-mini / Claude 3.5 API (추천 이유 자연어 생성)

---

## 🔌 6. API Example

**`POST /api/recommend`**

**Request**
```json
{
  "favorite_games": ["Dark Souls 3", "Hades"],
  "preferred_keywords": ["dark atmosphere", "impactful combat"],
  "disliked_keywords": ["multiplayer"]
}
```

**Response**
```json
{
  "recommendations": [
    {
      "title": "Blasphemous",
      "score": 0.81,
      "reason": "어두운 분위기와 높은 전투 몰입감이 Dark Souls 3와 유사하여 추천됩니다."
    }
  ]
}
```

---

## 🚀 7. 개발 로드맵 (Roadmap)

- **Phase 1: 데이터 파이프라인 구축 (Data Engineering)**
  - RAWG API 연동 및 게임 데이터 5,000건 추출 (CSV 저장)
  - 결측치 처리 및 데이터 정제 (Pandas 활용)
- **Phase 2: 코어 AI 모델링 (ML/AI)**
  - 게임 텍스트 설명 임베딩 변환 및 FAISS 로컬 검색 테스트
  - 유명 게임 패널티 로직(Long-tail) 수식 적용
- **Phase 3: 백엔드 API 개발 (Backend)**
  - FastAPI 세팅 및 추천 로직 API화 (`/api/recommend`)
  - 프롬프트 엔지니어링을 통한 LLM 추천 이유 생성 연동
- **Phase 4: 프론트엔드 UI/UX (Frontend)**
  - Next.js 화면 구현 (선호도 조사 뷰, 결과 페이지 뷰)
  - API 연동 및 에러/로딩 상태(Skeleton) 처리
- **Phase 5: 배포 및 피드백 루프 (DevOps)**
  - Vercel(Front) 및 Render(Back) 클라우드 배포
  - Supabase 연동하여 사용자 '좋아요/싫어요' DB 적재