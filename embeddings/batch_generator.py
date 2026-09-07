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
# 분석 시스템 프롬프트는 저장소에 두지 않는다 (2026-09-07).
# 60지표 데이터셋을 재현하는 '레시피'라 data/prompts/ (gitignore) 에서 읽는다.
# 지표 이름·스키마는 코드(모델·검증기)에 남지만, 채점 기준 문장과 예시는 저장소 밖이다.
_PROMPT_PATH = PROJECT_ROOT / "data" / "prompts" / "analysis_system_prompt_v6.txt"


_prompt_cache: dict = {}


def get_system_prompt() -> str:
    """지연 로드 — collect_batch 등이 helper 만 쓰려고 import 할 때 파일 부재로 죽지 않게."""
    if "v6" not in _prompt_cache:
        if not _PROMPT_PATH.exists():
            raise SystemExit(
                f"분석 프롬프트 파일이 없다: {_PROMPT_PATH}\n"
                "  저장소에는 포함되지 않는다(레시피 비공개). 백업에서 data/prompts/ 를 복원하라."
            )
        _prompt_cache["v6"] = _PROMPT_PATH.read_text(encoding="utf-8")
    return _prompt_cache["v6"]


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
    messages = [{"role": "system", "content": get_system_prompt()}]
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
            _explain_create_failure(exc, file_id)
            raise
    raise last_exc


# 배치 생성 거부 사유 → 사람이 읽을 한 줄 진단.
# 2026-09-06: 'billing_hard_limit_reached' 가 트레이스백으로만 떠서 파이프라인이
# 왜 멈췄는지 로그만 봐서는 알 수 없었다 (회차 4에서 중단).
_CREATE_HINTS = (
    ("billing_hard_limit_reached", "OpenAI 결제 하드 한도 도달 — 대시보드 Settings > Limits 의 월 예산을 올리거나 결제수단을 확인한다. 코드 문제가 아니다."),
    ("insufficient_quota", "OpenAI 잔액/쿼터 소진 — 충전 후 재개한다."),
    ("enqueued token limit", "배치 큐 토큰 한도 초과 — 진행 중 배치가 끝난 뒤 재시도하거나 회차 크기(--limit)를 줄인다."),
    ("rate limit", "레이트 리밋 — 잠시 후 재시도한다."),
)


def _explain_create_failure(exc: Exception, file_id: str) -> None:
    msg = str(exc)
    for needle, hint in _CREATE_HINTS:
        if needle.lower() in msg.lower():
            print(f"\n[진단] {hint}")
            break
    else:
        print("\n[진단] 배치 생성이 거부됐다. 위 메시지의 code/message 를 확인한다.")
    # 배치가 안 만들어졌으면 업로드된 입력 파일은 쓸 데가 없다 — 남겨두면 스토리지에 쌓인다.
    try:
        client.files.delete(file_id)
        print(f"[정리] 업로드만 된 입력 파일 삭제: {file_id}")
    except Exception as del_exc:
        print(f"[정리] 입력 파일 삭제 실패({file_id}) — 대시보드 Storage 에서 지운다: {del_exc}")


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
# 실측 (2026-09-03 백필, gpt-5.4-mini + 12-shot, 결과 파일 usage 합산):
#   요청당 입력 ≈ 26,500 tok (그중 ~95% 캐시 히트), 출력 ≈ 1,560 tok.
#   예전 추정(char/4)은 한글 텍스트에서 입력을 40% 가까이 적게 잡았고, 단가표에 없는
#   모델은 조용히 gpt-4o-mini 가격으로 계산해 실제보다 훨씬 싸게 보였다.
#   → 토큰은 실측 계수로, 단가는 등록된 모델만 달러 표시. 미등록이면 토큰만 보여주고 경고.
#   단가는 .env 로 덮어쓸 수 있다: OPENAI_PRICE_INPUT_PER_M / OPENAI_PRICE_OUTPUT_PER_M (배치 할인 적용가)
MEASURED_INPUT_TOK_PER_FEWSHOT = 1_950     # 예시 1개당 (12개 → ~23.4k) 실측 역산
MEASURED_BASE_INPUT_TOK = 3_100            # 시스템 프롬프트 + 게임 1건
MEASURED_OUTPUT_TOK = 1_560

# Batch API 50% 할인 적용 가격 (USD / 1M tok). 확인된 모델만 등록한다.
# gpt-5.4-mini 정가(2026-09 공식 가격표): 입력 $0.75 / 캐시 입력 $0.075 / 출력 $4.50
#   → 배치 50% 적용가가 아래 값. 캐시 입력은 정가의 1/10 이고, 우리 요청은 few-shot 12개가
#     매 요청 접두부로 반복돼 입력의 약 95%가 캐시 대상이다(동기 실측 94.3%).
#     배치에도 캐시 할인이 함께 적용된다 — 대시보드 Cost 에 'batch api | cached input' 항목이
#     별도로 잡히고, 정가 캐시 단가의 정확히 50%였다(2026-09-04 실측 검증: 계산 $42.97 vs 청구 $42.43).
#     따라서 배치가 동기보다 항상 싸다(동기 = 배치의 2배).
BATCH_PRICING = {
    "gpt-5.4": {"input": 1.25, "output": 7.50},     # 교사(distillation source) — 재확인 필요
    "gpt-4o": {"input": 1.25, "output": 5.00},
    "gpt-4o-mini": {"input": 0.075, "output": 0.30},
    "gpt-5.4-mini": {"input": 0.375, "output": 2.25, "cached_input": 0.0375},
}


def resolve_pricing(model: str):
    """등록 단가 또는 .env 지정 단가. 둘 다 없으면 None (달러 표시 안 함)."""
    env_in, env_out = os.getenv("OPENAI_PRICE_INPUT_PER_M"), os.getenv("OPENAI_PRICE_OUTPUT_PER_M")
    if env_in and env_out:
        return {"input": float(env_in), "output": float(env_out), "source": ".env"}
    base = model.split("-20")[0]           # gpt-5.4-mini-2026-03-17 → gpt-5.4-mini
    if base in BATCH_PRICING:
        return {**BATCH_PRICING[base], "source": "등록 단가표"}
    return None


def estimate_cost(num_games: int, model: str, fewshot_examples: list = None) -> dict:
    """예상 비용. 토큰은 실측 계수, 달러는 단가가 확인된 경우에만."""
    fewshot_examples = fewshot_examples or []
    fs_tokens = MEASURED_INPUT_TOK_PER_FEWSHOT * len(fewshot_examples)
    avg_input_tokens = MEASURED_BASE_INPUT_TOK + fs_tokens
    total_input = num_games * avg_input_tokens
    total_output = num_games * MEASURED_OUTPUT_TOK

    prices = resolve_pricing(model)
    cost = cost_cached = None
    if prices:
        cost = (total_input / 1e6) * prices["input"] + (total_output / 1e6) * prices["output"]
        # 캐시 하한: few-shot 접두부(요청당 fs_tokens)가 전부 캐시 적중한다고 가정
        cp = prices.get("cached_input")
        if cp is not None and fs_tokens:
            cached_tok = num_games * fs_tokens
            cost_cached = ((total_input - cached_tok) / 1e6) * prices["input"] \
                + (cached_tok / 1e6) * cp + (total_output / 1e6) * prices["output"]

    return {
        "model": model,
        "games": num_games,
        "fewshot_n": len(fewshot_examples),
        "fewshot_tokens_per_req": fs_tokens,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_usd": round(cost, 2) if cost is not None else None,
        "cost_krw": round(cost * 1400, 0) if cost is not None else None,
        "cost_usd_cached": round(cost_cached, 2) if cost_cached is not None else None,
        "price_source": prices["source"] if prices else None,
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
    print(f"   토큰: ~{cost['input_tokens']:,} input / ~{cost['output_tokens']:,} output (실측 계수)")
    if cost["cost_usd"] is not None:
        print(f"   ${cost['cost_usd']} USD (약 ₩{cost['cost_krw']:,.0f}) — 단가 출처: {cost['price_source']}")
        if cost.get("cost_usd_cached") is not None:
            print(f"   캐시 반영 실단가 기준 ${cost['cost_usd_cached']} USD  ← 실제 청구액에 가까움")
            print(f"   (few-shot 접두부가 매 요청 반복되어 캐시 적중, 배치에도 캐시 할인 적용됨)")
    else:
        print(f"   비용: 단가 미등록 모델({cost['model']}) — 달러 추정 생략. "
              f".env OPENAI_PRICE_INPUT_PER_M / OPENAI_PRICE_OUTPUT_PER_M 로 지정하면 표시됨")
    
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