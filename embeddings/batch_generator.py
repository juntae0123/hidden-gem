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
SYSTEM_PROMPT = '''You are "Hidden Gem Analyzer v5.0", an elite game analyst AI for Korea's #1 Steam game discovery platform. You extract 52 precision metrics and generate compelling Korean marketing content.

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
SECTION 3: 52 METRICS SCHEMA
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
    }
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
    print(f"📂 CSV 로드 중: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"   원본: {len(df)}개, 컬럼 {len(df.columns)}개")
    
    # 🚨 블라인드 테스트: 4개 컬럼만 추출!
    required_cols = ['app_id', 'name', 'genres', 'description']
    
    # 컬럼 존재 확인
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"❌ 필수 컬럼 누락: {missing}")
    
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
        print(f"   ⚠️ description 부족으로 {before - after}개 제외")
    
    # 제한
    if limit:
        df_blind = df_blind.head(limit)
    
    print(f"   ✅ 블라인드 데이터: {len(df_blind)}개 (컬럼: {list(df_blind.columns)})")
    
    return df_blind


# ============== User Prompt 생성 ==============
def create_user_prompt(row: pd.Series) -> str:
    """
    게임 데이터 → User Prompt
    🚨 4개 필드만! (app_id, name, genres, description)
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


# ============== JSONL 생성 ==============
def generate_batch_jsonl(df: pd.DataFrame, output_path: Path, model: str) -> dict:
    """
    Batch API용 JSONL 생성
    포맷: {"custom_id": "request-{app_id}", ...}
    """
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
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": create_user_prompt(row)}
                        ],
                        "temperature": 0.3,
                        "max_completion_tokens": 3000
                    }
                }
                
                f.write(json.dumps(batch_item, ensure_ascii=False) + "\n")
                success += 1
                
            except Exception as e:
                errors.append({"app_id": row.get('app_id', 'unknown'), "error": str(e)})
    
    return {"success": success, "errors": errors}


# ============== Batch API 업로드 & 실행 ==============
def upload_batch(jsonl_path: Path) -> str:
    """파일 업로드 → Batch 생성"""
    print("\n📤 OpenAI에 파일 업로드 중...")
    
    with open(jsonl_path, 'rb') as f:
        file_obj = client.files.create(file=f, purpose="batch")
    
    file_id = file_obj.id
    print(f"   ✅ 업로드 완료: {file_id}")
    
    print("\n🚀 Batch 작업 생성 중...")
    batch = client.batches.create(
        input_file_id=file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    
    print(f"   ✅ Batch ID: {batch.id}")
    print(f"   📊 상태: {batch.status}")
    
    return batch.id


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


def wait_and_download(batch_id: str, interval: int = 30) -> Path:
    """완료까지 대기 후 다운로드"""
    print(f"\n⏳ Batch 완료 대기 중... (매 {interval}초 확인)")
    
    while True:
        status = check_batch_status(batch_id)
        print(f"   📊 {status['status']} | {status['completed']}/{status['total']} 완료")
        
        if status['status'] == 'completed':
            print("\n✅ Batch 완료!")
            break
        elif status['status'] in ['failed', 'expired', 'cancelled']:
            print(f"\n❌ Batch 실패: {status['status']}")
            return None
        
        time.sleep(interval)
    
    # 결과 다운로드
    output_file_id = status['output_file_id']
    print(f"\n📥 결과 다운로드 중... ({output_file_id})")
    
    content = client.files.content(output_file_id)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"batch_output_{timestamp}.jsonl"
    
    with open(output_path, 'wb') as f:
        f.write(content.content)
    
    print(f"   ✅ 저장: {output_path}")
    
    return output_path


# ============== 비용 계산 ==============
def estimate_cost(num_games: int, model: str) -> dict:
    """예상 비용 계산"""
    avg_input_tokens = 2500   # 시스템 프롬프트 + 게임 데이터
    avg_output_tokens = 1500  # JSON 응답
    
    # Batch API 50% 할인 적용 가격 (per 1M tokens)
    pricing = {
        "gpt-5.4": {"input": 1.25, "output": 7.50},  # 🔥 5.4 Batch 가격표 추가!
        "gpt-4o": {"input": 1.25, "output": 5.00},
        "gpt-4o-mini": {"input": 0.075, "output": 0.30},
    }
    
    prices = pricing.get(model, pricing["gpt-4o"])
    
    total_input = num_games * avg_input_tokens
    total_output = num_games * avg_output_tokens
    
    cost_input = (total_input / 1_000_000) * prices["input"]
    cost_output = (total_output / 1_000_000) * prices["output"]
    total_cost = cost_input + cost_output
    
    return {
        "model": model,
        "games": num_games,
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
    parser.add_argument("--model", default="gpt-5.4", help="모델 (기본: gpt-5.4)")
    
    args = parser.parse_args()
    
    print("=" * 65)
    print("🎮 Hidden Gem - Batch API Generator (v5.0)")
    print("=" * 65)
    print(f"📁 프로젝트: {PROJECT_ROOT}")
    print(f"📂 CSV: {CSV_PATH}")
    print(f"🤖 모델: {args.model}")
    print("=" * 65)
    
    # CSV 확인
    if not CSV_PATH.exists():
        print(f"❌ CSV 파일 없음: {CSV_PATH}")
        return
    
    # 1. 모드 결정
    if args.test:
        limit = args.test
        mode = f"테스트 ({limit}개)"
    elif args.full:
        limit = None
        mode = "전체 (4,190개)"
    else:
        # 대화형 선택
        print("\n🎯 모드 선택:")
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
    
    print(f"\n📌 모드: {mode}")
    
    # 2. 블라인드 데이터 로드
    df = load_blind_data(CSV_PATH, limit=limit)
    
    # 3. 비용 예상
    cost = estimate_cost(len(df), args.model)
    print(f"\n💰 예상 비용:")
    print(f"   모델: {cost['model']}")
    print(f"   게임: {cost['games']:,}개")
    print(f"   토큰: ~{cost['input_tokens']:,} input / ~{cost['output_tokens']:,} output")
    print(f"   💵 ${cost['cost_usd']} USD (약 ₩{cost['cost_krw']:,.0f})")
    
    # 4. JSONL 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if limit:
        output_name = f"batch_test_{limit}_{timestamp}.jsonl"
    else:
        output_name = f"batch_tasks_{timestamp}.jsonl"
    
    output_path = DATA_DIR / output_name
    
    print(f"\n📝 JSONL 생성 중...")
    result = generate_batch_jsonl(df, output_path, args.model)
    
    print(f"   ✅ 성공: {result['success']}개")
    if result['errors']:
        print(f"   ⚠️ 실패: {len(result['errors'])}개")
        for err in result['errors'][:3]:
            print(f"      - {err}")
    
    file_size = output_path.stat().st_size / 1024
    print(f"   📦 파일: {output_path.name} ({file_size:.1f} KB)")
    
    # 5. 업로드?
    if args.upload or (not args.test and not args.full):
        confirm = input("\n🚀 OpenAI에 업로드할까요? (y/n): ").strip().lower()
        
        if confirm == 'y':
            batch_id = upload_batch(output_path)
            
            # 대기?
            if args.wait:
                output_result = wait_and_download(batch_id)
                if output_result:
                    print(f"\n🎉 완료! 다음 명령어 실행:")
                    print(f"   python -m embeddings.batch_processor {output_result.name}")
            else:
                print(f"\n📋 Batch ID: {batch_id}")
                print(f"   상태 확인: python -m embeddings.batch_generator --status {batch_id}")
                print(f"   또는: https://platform.openai.com/batches")
    else:
        print(f"\n📋 다음 단계:")
        print(f"   1. python -m embeddings.batch_generator --upload")
        print(f"   2. 또는 수동: https://platform.openai.com/batches 에서 업로드")
    
    print("\n" + "=" * 65)
    print("✅ 완료!")
    print("=" * 65)


if __name__ == "__main__":
    main()
