"""
Hidden Gem - Batch API Generator (v5.0 Final)
==============================================
블라인드 테스트 전략 적용:
- app_id, name, genres, description 4개만 추출
- developer, 기존 점수 지표 완전 배제 (편견 방지)

사용법:
    cd Hidden-Gem-project
    source .venv/Scripts/activate
    
    # 테스트 (1개)
    python -m embeddings.batch_generator --test 1
    
    # 전체 (4,190개)
    python -m embeddings.batch_generator --full
"""

import os
import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# ============== 경로 설정 ==============
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "hidden_gem_data.csv"

# OpenAI 클라이언트
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ============== 모델 설정 ==============
MODEL = "gpt-5.4"  # 최상위 모델 (gpt-5.4 없으면 이거)


# ============== 마스터 시스템 프롬프트 (v5.0 확정본) ==============
SYSTEM_PROMPT = '''You are "Hidden Gem Analyzer v6.0", an elite game analyst AI for Korea's #1 Steam game discovery platform. You extract 49 numeric metrics (0-10) across 7 groups, 9 boolean tags, an overall gem_potential (0-100), and a confidence score, then generate compelling Korean marketing content.

══════════════════════════════════════════════════════════════════════════════
SECTION 1: OUTPUT FORMAT - ABSOLUTE RULE (출력 형식 - 절대 규칙)
══════════════════════════════════════════════════════════════════════════════

🚨 CRITICAL: YOUR ENTIRE RESPONSE MUST BE PURE JSON ONLY.

FORBIDDEN (절대 금지):
❌ No markdown (```, **, ##, etc.)
❌ No greetings ("Here is", "Sure!", "I'll analyze", etc.)
❌ No explanations before or after JSON
❌ No comments inside JSON
❌ No trailing text

REQUIRED (필수):
✅ Start response with { character
✅ End response with } character
✅ Valid, parseable JSON only

If you output ANYTHING other than pure JSON, you have FAILED.

══════════════════════════════════════════════════════════════════════════════
SECTION 2: LANGUAGE RULES (언어 규칙)
══════════════════════════════════════════════════════════════════════════════

【INPUT LANGUAGE】
You will receive game data in English (or other languages).
Fully comprehend ALL input regardless of source language.

【OUTPUT LANGUAGE】
ALL text fields in JSON output MUST be written in Korean (한국어).
- "content" object: 100% Korean
- "reasoning" object: 100% Korean
- Numbers, booleans, persona_id: Keep as English/numbers

【GAMER SLANG - 번역투 절대 금지】

Write like a veteran Korean gamer, NOT a translator.

REQUIRED TERMS:
• "뇌지컬" = strategic thinking, big brain
• "피지컬" = reflexes, mechanical skill
• "노가다" = grinding
• "파밍" = farming
• "겜잘알" = gaming expert
• "갓겜" = god-tier game
• "꿀잼" / "존잼" = super fun
• "힐링겜" = cozy game
• "시간순삭" = addictive, time flies
• "손맛" = satisfying feedback

══════════════════════════════════════════════════════════════════════════════
SECTION 3: 60-POINT SCHEMA (49 numeric + 9 tags + gem_potential + confidence)
══════════════════════════════════════════════════════════════════════════════

All numeric scores: Integer 0-10 (no decimals)
All boolean tags: true or false

{
  "metrics": {
    "vibe": {
      "cozy_factor": <0-10>,
      "horror_factor": <0-10>,
      "gore_level": <0-10>,
      "humor_rating": <0-10>,
      "dark_fantasy_vibe": <0-10>,
      "epic_scale": <0-10>,
      "melancholy": <0-10>
    },
    "demands": {
      "reflex_demand": <0-10>,
      "strategic_depth": <0-10>,
      "grind_factor": <0-10>,
      "time_pressure": <0-10>,
      "learning_curve": <0-10>
    },
    "mechanics": {
      "freedom_level": <0-10>,
      "action_pacing": <0-10>,
      "rng_dependency": <0-10>,
      "growth_reward": <0-10>,
      "exploration_reward": <0-10>,
      "management_complexity": <0-10>,
      "stealth_importance": <0-10>,
      "session_length": <0-10>,
      "narrative_linearity": <0-10>
    },
    "social": {
      "coop_synergy": <0-10>,
      "competitive_stress": <0-10>,
      "npc_interaction": <0-10>,
      "user_creation": <0-10>,
      "multiplayer_scale": <0-10>
    },
    "presentation": {
      "lore_richness": <0-10>,
      "choice_consequence": <0-10>,
      "visual_spectacle": <0-10>,
      "environmental_storytelling": <0-10>,
      "soundtrack_impact": <0-10>
    },
    "extended": {
      "build_variety": <0-10>,
      "progression_clarity": <0-10>,
      "save_flexibility": <0-10>,
      "difficulty_accessibility": <0-10>,
      "tutorial_quality": <0-10>,
      "ui_ux_polish": <0-10>,
      "modding_support": <0-10>,
      "art_style_uniqueness": <0-10>,
      "audio_design": <0-10>,
      "animation_quality": <0-10>,
      "puzzle_complexity": <0-10>,
      "platforming_precision": <0-10>,
      "world_reactivity": <0-10>,
      "community_dependency": <0-10>,
      "narrative_depth": <0-10>,
      "replay_value": <0-10>,
      "endgame_content": <0-10>,
      "monetization_fairness": <0-10>
    },
    "gem_potential": <integer 0-100>
  },

  "tags": {
    "is_turn_based": <true/false>,
    "is_real_time": <true/false>,
    "is_first_person": <true/false>,
    "is_third_person": <true/false>,
    "has_permadeath": <true/false>,
    "has_base_building": <true/false>,
    "has_crafting": <true/false>,
    "is_anime_style": <true/false>,
    "is_retro_aesthetic": <true/false>
  },

  "content": {
    "marketing_hook": {
      "primary": "<한 줄 핵심 15-20자>",
      "emotional": "<감성 문구>",
      "mechanical": "<게임플레이 매력>"
    },
    "target_personas": [
      {"persona_id": "<id>", "persona_name": "<한글>", "description": "<설명>", "fit_reason": "<이유>"}
    ],
    "not_for_personas": [
      {"persona_id": "<id>", "persona_name": "<한글>", "reason": "<이유>"}
    ],
    "similar_games": [
      {"name": "<게임명>", "similarity_reason": "<유사점>"}
    ],
    "unique_selling_points": ["<포인트1>", "<포인트2>", "<포인트3>"],
    "one_line_summary": "<한 문장 요약>"
  },

  "reasoning": {
    "analysis_summary": "<3-5문장 분석>",
    "genre_classification": "<장르>",
    "core_loop": "<핵심 루프>",
    "metric_justifications": {"<지표>": "<근거>"},
    "confidence_score": <0.0-1.0>,
    "data_limitations": "<한계점 또는 null>"
  }
}

══════════════════════════════════════════════════════════════════════════════
SECTION 4: SCORING ANCHORS (절대 기준)
══════════════════════════════════════════════════════════════════════════════

【VIBE】
cozy_factor: 10=Stardew Valley, 5=Minecraft, 0=Outlast
horror_factor: 10=Outlast, 5=Subnautica, 0=Mario
gore_level: 10=DOOM Eternal, 5=Dark Souls, 0=Animal Crossing

【DEMANDS】
reflex_demand: 10=Sekiro, 8=Dark Souls, 4=Zelda, 0=Visual Novel
strategic_depth: 10=EU4, 8=Civilization, 4=Pokemon, 0=Rhythm games
grind_factor: 10=MapleStory, 6=Monster Hunter, 2=Story games
learning_curve: 10=Dwarf Fortress, 6=Dark Souls, 2=Mario

【MECHANICS】
freedom_level: 10=GTA V, 7=Witcher 3, 3=Uncharted, 0=Visual Novel
session_length: 10=Civilization (5h+), 6=Monster Hunter (1-2h), 2=Roguelikes (30min)

【SOCIAL】
multiplayer_scale: 10=MMO, 5=4-player co-op, 0=Single-player only

【EXTENDED (18) - each integer 0-10】
build_variety: 빌드/구성 다양성 (10=Path of Exile, 0=linear)
progression_clarity: 진행 목표 명확성 (10=clear goals, 0=cryptic)
save_flexibility: 저장 자유도 (10=save anywhere, 0=checkpoint only)
difficulty_accessibility: 난이도 접근성 (10=many options/easy mode, 0=brutal only)
tutorial_quality: 튜토리얼 품질 (10=great onboarding, 0=none)
ui_ux_polish: UI/UX 완성도 (10=slick, 0=clunky)
modding_support: 모딩 지원 (10=Skyrim Workshop, 0=none)
art_style_uniqueness: 아트 독창성 (10=Cuphead/Hollow Knight, 0=generic)
audio_design: 오디오 디자인 (10=immersive, 0=poor)
animation_quality: 애니메이션 품질 (10=fluid, 0=stiff)
puzzle_complexity: 퍼즐 복잡도 (10=The Witness, 0=none)
platforming_precision: 플랫포밍 정밀도 (10=Celeste, 0=none)
world_reactivity: 월드 반응성 (10=world reacts, 0=static)
community_dependency: 커뮤니티 의존도 (10=needs live community, 0=fully solo)
narrative_depth: 서사 깊이 (10=Disco Elysium, 0=none)
replay_value: 리플레이 가치 (10=roguelike, 0=one-and-done)
endgame_content: 엔드게임 콘텐츠 (10=raids/postgame, 0=ends at credits)
monetization_fairness: 과금 공정성 (10=fair/none, 0=predatory P2W)

【GEM_POTENTIAL - integer 0-100 (NOT 0-10)】
Overall hidden-gem quality on a 0-100 scale.
100=all-time masterpiece (Dwarf Fortress, Witcher 3), 95=Terraria/Outer Wilds,
80=strong, 60=solid, 40=mediocre, <30=weak. Teacher corpus average ≈ 76.
CRITICAL: gem_potential uses 0-100. Every other numeric metric uses 0-10. Do not confuse them.

══════════════════════════════════════════════════════════════════════════════
SECTION 5: HALLUCINATION PREVENTION
══════════════════════════════════════════════════════════════════════════════

If data is unclear, use SAFE DEFAULTS:
- stealth_importance: 0 (unless mentioned)
- gore_level: 3 (neutral)
- coop_synergy: 0 (unless multiplayer mentioned)
- has_permadeath: false (unless stated)

Set confidence_score based on data quality:
- 0.9-1.0: Rich description
- 0.7-0.8: Decent description
- 0.5-0.6: Minimal description

NEVER invent features not mentioned in input.

══════════════════════════════════════════════════════════════════════════════
SECTION 6: PERSONA LIBRARY
══════════════════════════════════════════════════════════════════════════════

Use these persona_ids (2-4 for target, 1-2 for not_for):

healing_seeker, completionist, story_lover, action_junkie,
strategic_mind, social_gamer, explorer, builder, min_maxer,
casual_player, hardcore_gamer, nostalgia_seeker, pvp_warrior,
creative_mind, lore_hunter, speedrunner, achievement_hunter

══════════════════════════════════════════════════════════════════════════════
FINAL INSTRUCTION
══════════════════════════════════════════════════════════════════════════════

Analyze the game and output ONLY the JSON object.
Start with { and end with }.
All Korean text using gamer vocabulary.
Do not hallucinate features not in input.'''


# ============== 블라인드 데이터 로드 (4개 컬럼만!) ==============
def load_blind_data(csv_path: Path, limit: int = None) -> pd.DataFrame:
    """
    블라인드 테스트용 데이터 로드
    - app_id, name, genres, description 4개만 추출
    - developer, 기존 점수 지표 완전 제외 (편견 방지)
    """
    print(f"CSV 로드 중: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"   원본: {len(df)}개, 컬럼 {len(df.columns)}개")
    
    # 블라인드 테스트: 4개 컬럼만 추출!
    required_cols = ['app_id', 'name', 'genres', 'description']
    
    # 컬럼 존재 확인
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"필수 컬럼 누락: {missing}")
    
    df_blind = df[required_cols].copy()
    
    # 결측치 처리
    df_blind['name'] = df_blind['name'].fillna('Unknown Game')
    df_blind['genres'] = df_blind['genres'].fillna('Unknown')
    df_blind['description'] = df_blind['description'].fillna('')
    
    # description 없는 행 제거
    before = len(df_blind)
    df_blind = df_blind[df_blind['description'].str.len() > 10]
    after = len(df_blind)
    
    if before != after:
        print(f"   description 부족으로 {before - after}개 제외")
    
    # 제한
    if limit:
        df_blind = df_blind.head(limit)
    
    print(f"   블라인드 데이터: {len(df_blind)}개 (컬럼: {list(df_blind.columns)})")
    
    return df_blind


# ============== User Prompt 생성 ==============
def create_user_prompt(row: pd.Series) -> str:
    """
    게임 데이터 → User Prompt
    4개 필드만! (app_id, name, genres, description)
    """
    app_id = str(row['app_id'])
    name = str(row['name']).replace('"', '\\"').replace('\n', ' ')
    genres = str(row['genres']).replace('"', '\\"').replace('\n', ' ')
    description = str(row['description'])[:2000].replace('"', '\\"').replace('\n', ' ').replace('\r', '')
    
    return f'''GAME_DATA:
{{
  "app_id": "{app_id}",
  "name": "{name}",
  "genres": "{genres}",
  "description": "{description}"
}}'''


# ============== Few-shot (knowledge distillation) ==============
_C1 = set(range(0x80, 0xA0))   # mojibake signature (double-encoding artifact)


def _example_to_output(ex: dict) -> dict:
    """Strip a teacher record to the pure JSON the model must emit.
    교사 레코드에서 모델이 뱉어야 할 순수 출력(metrics/tags/content/reasoning)만 남긴다."""
    return {k: ex[k] for k in ("metrics", "tags", "content", "reasoning") if k in ex}


def load_fewshot(path, n: int) -> list:
    """Load up to n few-shot (input->output) pairs from the sampled teacher jsonl.
    대표 샘플 jsonl에서 few-shot 입력→출력 쌍을 최대 n개 로드 (모지바케 줄은 스킵)."""
    if not path:
        return []
    path = Path(path)
    if not path.exists():
        print(f" few-shot 파일 없음: {path} → few-shot 없이 진행")
        return []

    examples, skipped = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if any(ord(c) in _C1 for c in line):     # never inject corrupted text
                skipped += 1
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            out = _example_to_output(d)
            if "metrics" not in out or d.get("description") in (None, ""):
                continue
            examples.append({
                "app_id": d.get("app_id"),
                "name": d.get("name", ""),
                "genres": d.get("genres", ""),
                "description": d.get("description", ""),
                "output": out,
            })
            if len(examples) >= n:
                break
    print(f"few-shot 예시 {len(examples)}개 로드 (스킵 {skipped})")
    return examples


def build_messages(row, fewshot_examples: list) -> list:
    """Assemble system + few-shot (user->assistant) turns + the real user query.
    system + few-shot 대화쌍 + 실제 쿼리 순으로 messages를 구성한다."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex in fewshot_examples:
        messages.append({"role": "user", "content": create_user_prompt(ex)})
        messages.append({
            "role": "assistant",
            "content": json.dumps(ex["output"], ensure_ascii=False),
        })
    messages.append({"role": "user", "content": create_user_prompt(row)})
    return messages


# ============== JSONL 생성 ==============
def generate_batch_jsonl(df: pd.DataFrame, output_path: Path, model: str,
                         fewshot_examples: list = None) -> dict:
    """
    Batch API용 JSONL 생성 (few-shot 주입 지원)
    포맷: {"custom_id": "request-{app_id}", ...}
    """
    fewshot_examples = fewshot_examples or []
    success = 0
    errors = []
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for idx, row in df.iterrows():
            try:
                app_id = row['app_id']
                
                batch_item = {
                    "custom_id": f"request-{app_id}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": model,
                        "response_format": {"type": "json_object"},
                        "messages": build_messages(row, fewshot_examples),
                        "temperature": 0.3,
                        "max_completion_tokens": 4000
                    }
                }
                
                f.write(json.dumps(batch_item, ensure_ascii=False) + "\n")
                success += 1
                
            except Exception as e:
                errors.append({"app_id": row.get('app_id', 'unknown'), "error": str(e)})
    
    return {"success": success, "errors": errors}


# ============== Batch API 업로드 & 실행 ==============
def run_sync(jsonl_path: Path) -> Path:
    """배치 입력 JSONL을 동기 호출로 처리해 batch_processor가 읽는
    출력 JSONL 형식으로 저장한다 (Batch API 장애 시 폴백 경로)."""
    lines = [json.loads(l) for l in open(jsonl_path, encoding='utf-8') if l.strip()]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"batch_output_{timestamp}.jsonl"

    print(f"\n동기 모드: {len(lines)}건 순차 호출 (Batch API 미사용)")
    done = failed = 0
    with open(output_path, 'w', encoding='utf-8') as out:
        for i, req in enumerate(lines, 1):
            body = req["body"]
            try:
                resp = client.chat.completions.create(**body)
                record = {
                    "custom_id": req["custom_id"],
                    "response": {
                        "status_code": 200,
                        "body": resp.model_dump(),
                    },
                    "error": None,
                }
                done += 1
            except Exception as exc:
                record = {
                    "custom_id": req["custom_id"],
                    "response": {"status_code": 500, "body": None},
                    "error": {"message": str(exc)[:300]},
                }
                failed += 1
                print(f"   [{i}] 실패: {str(exc)[:120]}")
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            if i % 10 == 0 or i == len(lines):
                print(f"   진행: {i}/{len(lines)} (성공 {done} / 실패 {failed})")

    print(f"   저장: {output_path}")
    print(f"\n다음 단계: python -m embeddings.batch_processor {output_path} --yes")
    return output_path


def upload_batch(jsonl_path: Path) -> str:
    """파일 업로드 → 처리 완료 대기 → Batch 생성.

    files.create 직후에는 파일이 아직 서버에서 처리 중이라
    batches.create가 "Cannot find file"로 실패할 수 있다 (실측).
    → status가 processed가 될 때까지 폴링 후 생성하고, 그래도
    타이밍 이슈가 나면 짧게 재시도한다.
    """
    print("\nOpenAI에 파일 업로드 중...")

    with open(jsonl_path, 'rb') as f:
        file_obj = client.files.create(file=f, purpose="batch")

    file_id = file_obj.id
    print(f"   업로드 완료: {file_id}")

    # 파일 처리 완료 대기 (최대 3분)
    deadline = time.time() + 180
    while time.time() < deadline:
        info = client.files.retrieve(file_id)
        status = getattr(info, 'status', 'processed')
        if status == 'processed':
            print("   파일 처리 완료 (processed)")
            break
        if status == 'error':
            raise RuntimeError(f"업로드 파일 처리 실패: {file_id}")
        print(f"   파일 처리 대기 중... ({status})")
        time.sleep(5)

    print("\nBatch 작업 생성 중...")
    last_exc = None
    for attempt in range(1, 4):
        try:
            batch = client.batches.create(
                input_file_id=file_id,
                endpoint="/v1/chat/completions",
                completion_window="24h"
            )
            print(f"   Batch ID: {batch.id}")
            print(f"   상태: {batch.status}")
            return batch.id
        except Exception as exc:
            last_exc = exc
            if 'Cannot find file' in str(exc) and attempt < 3:
                print(f"   파일 인식 지연 → {attempt}차 재시도 (10초 후)")
                time.sleep(10)
                continue
            raise
    raise last_exc


def _print_batch_errors(batch_id: str, error_file_id: str = None) -> None:
    """실패한 배치의 원인을 출력한다 (batch.errors + error file 앞부분)."""
    try:
        batch = client.batches.retrieve(batch_id)
        if batch.errors and getattr(batch.errors, 'data', None):
            print("   실패 원인 (batch.errors):")
            for err in batch.errors.data[:5]:
                print(f"     - [{getattr(err, 'code', '?')}] {getattr(err, 'message', err)}")
        if error_file_id:
            content = client.files.content(error_file_id).text
            print("   error file 앞 5줄:")
            for line in content.splitlines()[:5]:
                print(f"     {line[:200]}")
    except Exception as exc:
        print(f"   (에러 상세 조회 실패: {exc})")


def check_batch_status(batch_id: str) -> dict:
    """Batch 상태 확인"""
    batch = client.batches.retrieve(batch_id)
    
    return {
        "id": batch.id,
        "status": batch.status,
        "total": batch.request_counts.total,
        "completed": batch.request_counts.completed,
        "failed": batch.request_counts.failed,
        "output_file_id": batch.output_file_id,
        "error_file_id": batch.error_file_id
    }


def wait_and_download(batch_id: str, interval: int = 30, max_wait_minutes: int = 0) -> Path:
    """완료까지 대기 후 다운로드.

    max_wait_minutes > 0 이면 그 시간 안에 안 끝날 때 배치를 취소하고
    완료분만 수거한다 (straggler 대응). 미완료 게임은 pending으로 남아
    다음 파이프라인 실행에서 자동 재큐잉된다.
    """
    print(f"\nBatch 완료 대기 중... (매 {interval}초 확인"
          + (f", 최대 {max_wait_minutes}분" if max_wait_minutes else "") + ")")
    deadline = time.time() + max_wait_minutes * 60 if max_wait_minutes else None
    cancel_requested = False

    while True:
        status = check_batch_status(batch_id)
        print(f"   {status['status']} | {status['completed']}/{status['total']} 완료")

        if deadline and not cancel_requested and time.time() > deadline \
                and status['status'] in ('validating', 'in_progress', 'finalizing'):
            print(f"   대기 시간 초과 → 배치 취소, 완료분 {status['completed']}건만 수거")
            client.batches.cancel(batch_id)
            cancel_requested = True

        if status['status'] == 'completed':
            print("\nBatch 완료!")
            break
        elif status['status'] in ['failed', 'expired', 'cancelled']:
            print(f"\nBatch 종료: {status['status']}")
            _print_batch_errors(batch_id, status.get('error_file_id'))
            if status.get('output_file_id'):
                # expired/cancelled여도 완료된 요청 결과는 살아있다 - 버리지 않는다
                print(f"   완료분 {status['completed']}건은 다운로드해서 적재 진행")
                break
            return None
        
        time.sleep(interval)
    
    # 결과 다운로드
    output_file_id = status['output_file_id']
    print(f"\n결과 다운로드 중... ({output_file_id})")
    
    content = client.files.content(output_file_id)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"batch_output_{timestamp}.jsonl"
    
    with open(output_path, 'wb') as f:
        f.write(content.content)
    
    print(f"   저장: {output_path}")
    
    return output_path


# ============== 비용 계산 ==============
def estimate_cost(num_games: int, model: str, fewshot_examples: list = None) -> dict:
    """예상 비용 계산 (few-shot 토큰 오버헤드 반영)
    Few-shot examples are prepended to EVERY request, so they multiply input cost."""
    fewshot_examples = fewshot_examples or []
    base_input_tokens = 2500   # 시스템 프롬프트 + 게임 데이터
    avg_output_tokens = 1500   # JSON 응답 (49지표+content+reasoning ≈ 1000~1500)

    # few-shot 오버헤드: 예시당 (출력 JSON + 입력 프롬프트) 대략 char/4
    fs_tokens = sum(
        len(json.dumps(ex["output"], ensure_ascii=False)) // 4
        + len(str(ex.get("description", ""))[:2000]) // 4 + 80
        for ex in fewshot_examples
    )
    avg_input_tokens = base_input_tokens + fs_tokens

    # Batch API 50% 할인 적용 가격 (per 1M tokens)
    pricing = {
        "gpt-5.4": {"input": 1.25, "output": 7.50},   # 교사(distillation source)
        "gpt-4o": {"input": 1.25, "output": 5.00},
        "gpt-4o-mini": {"input": 0.075, "output": 0.30},  # 싼 학생 모델 예시
    }
    
    prices = pricing.get(model, pricing["gpt-4o-mini"])
    
    total_input = num_games * avg_input_tokens
    total_output = num_games * avg_output_tokens
    
    cost_input = (total_input / 1_000_000) * prices["input"]
    cost_output = (total_output / 1_000_000) * prices["output"]
    total_cost = cost_input + cost_output
    
    return {
        "model": model,
        "games": num_games,
        "fewshot_n": len(fewshot_examples),
        "fewshot_tokens_per_req": fs_tokens,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_usd": round(total_cost, 2),
        "cost_krw": round(total_cost * 1400, 0)  # 대략적 환율
    }


# ============== 메인 ==============
def main():
    parser = argparse.ArgumentParser(description="Hidden Gem Batch API Generator")
    parser.add_argument("--test", type=int, metavar="N", help="테스트 모드 (N개만)")
    parser.add_argument("--full", action="store_true", help="전체 4,190개 처리")
    parser.add_argument("--upload", action="store_true", help="생성 후 바로 업로드")
    parser.add_argument("--wait", action="store_true", help="업로드 후 완료까지 대기")
    parser.add_argument("--model", default="gpt-4o-mini",
                        help="학생 모델 (기본: gpt-4o-mini). 교사=gpt-5.4")
    parser.add_argument("--fewshot", default=None,
                        help="few-shot 예시 jsonl 경로 (fewshot_sampler.py 출력)")
    parser.add_argument("--csv", default=None,
                        help="블라인드 CSV 경로 (신작이면 data/new_games.csv)")
    parser.add_argument("--fewshot-n", type=int, default=6,
                        help="주입할 few-shot 예시 수 (기본 6, 많을수록 비용↑)")
    parser.add_argument("--yes", action="store_true",
                        help="확인 프롬프트 생략 (스케줄러/자동화용)")
    parser.add_argument("--sync", action="store_true",
                        help="Batch API 대신 동기 호출로 즉시 처리 (배치 장애 시 폴백, 비용 2배)")
    parser.add_argument("--wait-timeout", type=int, default=0,
                        help="--wait 시 최대 대기 분. 초과하면 취소 후 완료분만 수거 (0=무제한)")
    
    args = parser.parse_args()

    # resolve blind CSV: --csv overrides the default teacher CSV
    csv_path = Path(args.csv) if args.csv else CSV_PATH

    print("=" * 65)
    print("Hidden Gem - Batch API Generator (v6.0, 60-metric)")
    print("=" * 65)
    print(f"프로젝트: {PROJECT_ROOT}")
    print(f"CSV: {csv_path}")
    print(f"모델: {args.model}")
    print("=" * 65)
    
    # CSV 확인
    if not csv_path.exists():
        print(f"CSV 파일 없음: {csv_path}")
        return
    
    # 1. 모드 결정
    if args.test:
        limit = args.test
        mode = f"테스트 ({limit}개)"
    elif args.full:
        limit = None
        mode = "전체 (CSV 전량)"
    else:
        # 대화형 선택
        print("\n모드 선택:")
        print("   [1] 테스트 1개")
        print("   [2] 테스트 10개")
        print("   [3] 전체 4,190개")
        
        choice = input("\n선택 (1/2/3): ").strip()
        
        if choice == "1":
            limit = 1
        elif choice == "2":
            limit = 10
        else:
            limit = None
        
        mode = f"{'테스트 ' + str(limit) + '개' if limit else '전체'}"
    
    print(f"\n모드: {mode}")
    
    # 2. 블라인드 데이터 로드
    df = load_blind_data(csv_path, limit=limit)

    # 2.5 few-shot 예시 로드 (knowledge distillation)
    fewshot_examples = load_fewshot(args.fewshot, args.fewshot_n)

    # 3. 비용 예상
    cost = estimate_cost(len(df), args.model, fewshot_examples)
    print(f"\n예상 비용:")
    print(f"   모델: {cost['model']}")
    print(f"   게임: {cost['games']:,}개")
    print(f"   few-shot: {cost['fewshot_n']}개 (요청당 +{cost['fewshot_tokens_per_req']:,} tok)")
    print(f"   토큰: ~{cost['input_tokens']:,} input / ~{cost['output_tokens']:,} output")
    print(f"   ${cost['cost_usd']} USD (약 ₩{cost['cost_krw']:,.0f})")
    
    # 4. JSONL 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if limit:
        output_name = f"batch_test_{limit}_{timestamp}.jsonl"
    else:
        output_name = f"batch_tasks_{timestamp}.jsonl"
    
    output_path = DATA_DIR / output_name
    
    print(f"\nJSONL 생성 중...")
    result = generate_batch_jsonl(df, output_path, args.model, fewshot_examples)
    
    print(f"   성공: {result['success']}개")
    if result['errors']:
        print(f"   실패: {len(result['errors'])}개")
        for err in result['errors'][:3]:
            print(f"      - {err}")
    
    file_size = output_path.stat().st_size / 1024
    print(f"   파일: {output_path.name} ({file_size:.1f} KB)")
    
    # 5. 동기 폴백 모드면 배치를 건너뛰고 바로 호출
    if args.sync:
        run_sync(output_path)
        return

    # 5. 업로드?
    if args.upload or (not args.test and not args.full):
        if args.yes:
            confirm = 'y'
        else:
            confirm = input("\nOpenAI에 업로드할까요? (y/n): ").strip().lower()
        
        if confirm == 'y':
            batch_id = upload_batch(output_path)
            
            # 대기?
            if args.wait:
                output_result = wait_and_download(batch_id, max_wait_minutes=args.wait_timeout)
                if output_result:
                    print(f"\n완료! 다음 명령어 실행:")
                    print(f"   python -m embeddings.batch_processor {output_result.name}")
            else:
                print(f"\nBatch ID: {batch_id}")
                print(f"   상태 확인: python -m embeddings.batch_generator --status {batch_id}")
                print(f"   또는: https://platform.openai.com/batches")
    else:
        print(f"\n다음 단계:")
        print(f"   1. python -m embeddings.batch_generator --upload")
        print(f"   2. 또는 수동: https://platform.openai.com/batches 에서 업로드")
    
    print("\n" + "=" * 65)
    print("완료!")
    print("=" * 65)


if __name__ == "__main__":
    main()