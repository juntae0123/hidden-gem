"""
Hidden Gem - Batch API Result Processor (normalized 60-column UPSERT)
=====================================================================
GPT Batch API 결과를 파싱해 game_metrics 정규화 60컬럼에 UPSERT

계약 (Project A와 홈 맞추기):
    - 스키마 정본: fastapi_app/models/game.py (SQLAlchemy). models.py(Django)는 참조용.
    - game_metrics PK = game_id (FK -> games.id). app_id가 아니므로 2단계 조회 필요.
    - custom_id prefix는 diet-/request-/game- 혼재 → 숫자만 추출해 app_id로 사용.
    - gem_potential은 0~100 스케일 그대로 저장 (/10 금지, DB 실측 MAX=100).
    - gem_percentile, embedding 컬럼은 절대 건드리지 않음 (task5 + 임베딩 파이프라인 관리).
    - GPT 출력은 두 형태 모두 지원:
        (a) 중첩형: {"metrics": {"vibe": {...}, ..., "extended": {...}, "gem_potential": 87}}
        (b) 평면형: {"build_variety": 3, "progression_clarity": 6, ...}  (과거 diet 배치)

사용법:
    cd Hidden-Gem-project
    source .venv/Scripts/activate

    # 1) 파싱만 (DB 안 건드림) - 항상 이것부터
    python -m embeddings.batch_processor data/batch_outputs/xxx_output.jsonl --dry-run

    # 2) 실제 적재
    python -m embeddings.batch_processor data/batch_outputs/xxx_output.jsonl
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from tqdm import tqdm

# ============== 경로 / DB ==============
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError(".env에 DATABASE_URL이 없습니다!")

engine = create_engine(DB_URL)


# ============== 컬럼 계약 (game.py와 1:1 일치) ==============
# 49 numeric metrics used by the recommendation engine's vector.
# 추천 엔진이 벡터화에 쓰는 49개 수치 지표.
NUMERIC_METRIC_FIELDS = [
    # VIBE (7)
    'cozy_factor', 'horror_factor', 'gore_level', 'humor_rating',
    'dark_fantasy_vibe', 'epic_scale', 'melancholy',
    # DEMANDS (5)
    'reflex_demand', 'strategic_depth', 'grind_factor',
    'time_pressure', 'learning_curve',
    # MECHANICS (9)
    'freedom_level', 'action_pacing', 'rng_dependency', 'growth_reward',
    'exploration_reward', 'management_complexity', 'stealth_importance',
    'session_length', 'narrative_linearity',
    # MECHANICS EXTRA (2)
    'puzzle_complexity', 'platforming_precision',
    # SOCIAL (5)
    'coop_synergy', 'competitive_stress', 'npc_interaction',
    'user_creation', 'multiplayer_scale',
    # PRESENTATION (5)
    'lore_richness', 'choice_consequence', 'visual_spectacle',
    'environmental_storytelling', 'soundtrack_impact',
    # SYSTEM/UX (7)
    'build_variety', 'progression_clarity', 'save_flexibility',
    'difficulty_accessibility', 'tutorial_quality', 'ui_ux_polish',
    'modding_support',
    # ART/AUDIO (3)
    'art_style_uniqueness', 'audio_design', 'animation_quality',
    # OTHER (2)
    'world_reactivity', 'community_dependency',
    # NEW (4)
    'narrative_depth', 'replay_value', 'endgame_content',
    'monetization_fairness',
]

BOOLEAN_TAG_FIELDS = [
    'is_turn_based', 'is_real_time', 'is_first_person', 'is_third_person',
    'has_permadeath', 'has_base_building', 'has_crafting',
    'is_anime_style', 'is_retro_aesthetic',
]

# NEVER write these. Owned by task5 (percentile) and the embedding pipeline.
# 절대 쓰지 않는 컬럼. task5(백분위)와 임베딩 파이프라인이 소유.
FORBIDDEN_COLUMNS = {'gem_percentile', 'embedding'}

# gem_potential stays on the 0-100 scale (DB measured MIN=0 MAX=100 AVG=75.68).
GEM_POTENTIAL_MIN, GEM_POTENTIAL_MAX = 0.0, 100.0


# ============== 파싱 헬퍼 ==============
def extract_app_id(custom_id: str) -> Optional[int]:
    """Pull the numeric app_id out of any custom_id prefix (diet-/request-/game-).
    prefix가 무엇이든 custom_id에서 숫자(app_id)만 추출한다."""
    if not custom_id:
        return None
    m = re.search(r'(\d+)', str(custom_id))
    return int(m.group(1)) if m else None


def strip_code_fence(content: str) -> str:
    """Remove ```json fences the model sometimes wraps its JSON in.
    모델이 감싸는 ```json 코드펜스를 제거한다."""
    c = content.strip()
    if c.startswith('```json'):
        c = c[7:]
    elif c.startswith('```'):
        c = c[3:]
    if c.endswith('```'):
        c = c[:-3]
    return c.strip()


def flatten_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten metrics regardless of nesting; group names are ignored, keys win.
    중첩/평면 상관없이 지표를 평탄화. 그룹명은 무시하고 키 이름으로만 매핑한다."""
    flat: Dict[str, Any] = {}
    metrics = data.get('metrics', data)   # nested has 'metrics'; flat IS the dict
    if not isinstance(metrics, dict):
        return flat

    for key, value in metrics.items():
        if isinstance(value, dict):
            # group (vibe / demands / ... / extended)
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, (int, float, bool)):
                    flat[sub_key] = sub_val
        elif isinstance(value, (int, float, bool)):
            # scalar directly under metrics (e.g. gem_potential)
            flat[key] = value
    return flat


def coerce_float(value: Any) -> Optional[float]:
    """Cast to float, returning None for non-numeric input.
    숫자가 아니면 None을 반환하며 float으로 변환한다."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_metric_row(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Map one GPT result into the game_metrics column contract.
    GPT 결과 1건을 game_metrics 컬럼 계약에 맞춰 매핑한다."""
    flat = flatten_metrics(parsed)
    tags = parsed.get('tags', {}) or {}
    content = parsed.get('content', {}) or {}
    reasoning = parsed.get('reasoning', {}) or {}

    row: Dict[str, Any] = {}

    # 49 numeric metrics
    for field in NUMERIC_METRIC_FIELDS:
        row[field] = coerce_float(flat.get(field))

    # 9 boolean tags
    for field in BOOLEAN_TAG_FIELDS:
        val = tags.get(field, flat.get(field))
        row[field] = bool(val) if val is not None else False

    # gem_potential: 0-100 scale kept as-is, clamped defensively
    gem = coerce_float(flat.get('gem_potential'))
    if gem is not None:
        gem = max(GEM_POTENTIAL_MIN, min(GEM_POTENTIAL_MAX, gem))
    row['gem_potential'] = gem

    row['confidence_score'] = coerce_float(reasoning.get('confidence_score'))

    # reasoning text columns
    row['analysis_summary'] = reasoning.get('analysis_summary', '') or ''
    row['genre_classification'] = (reasoning.get('genre_classification', '') or '')[:255]
    row['core_loop'] = reasoning.get('core_loop', '') or ''
    row['metric_justifications'] = json.dumps(
        reasoning.get('metric_justifications', {}) or {}, ensure_ascii=False)
    row['data_limitations'] = reasoning.get('data_limitations', '') or ''

    # raw payloads for auditing / reprocessing
    row['raw_content'] = json.dumps(content, ensure_ascii=False)
    row['raw_reasoning'] = json.dumps(reasoning, ensure_ascii=False)

    return row


def metric_completeness(row: Dict[str, Any]) -> int:
    """Count how many of the 49 numeric metrics were actually filled.
    49개 수치 지표 중 실제로 채워진 개수를 센다."""
    return sum(1 for f in NUMERIC_METRIC_FIELDS if row.get(f) is not None)


# ============== Batch 결과 파싱 ==============
def parse_batch_result(result_file: Path) -> Tuple[Dict[int, Dict], Dict[str, int]]:
    """Parse a Batch API output JSONL keyed by app_id.
    Batch API 출력 JSONL을 app_id 기준으로 파싱한다."""
    results: Dict[int, Dict] = {}
    stats = {"success": 0, "http_error": 0, "parse_error": 0, "no_app_id": 0}

    print(f"파일 읽는 중: {result_file}")

    with open(result_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"   Line {line_num} JSONL 파싱 실패: {e}")
                stats["parse_error"] += 1
                continue

            app_id = extract_app_id(item.get("custom_id", ""))
            if app_id is None:
                stats["no_app_id"] += 1
                continue

            response = item.get("response") or {}
            if response.get("status_code") != 200:
                err = (response.get("error") or {}).get("message", "Unknown error")
                print(f"   app_id={app_id} HTTP 오류: {err}")
                stats["http_error"] += 1
                continue

            body = response.get("body") or {}
            choices = body.get("choices") or []
            if not choices:
                stats["parse_error"] += 1
                continue

            content = choices[0].get("message", {}).get("content", "{}")
            try:
                parsed = json.loads(strip_code_fence(content))
            except json.JSONDecodeError as e:
                print(f"   app_id={app_id} content 파싱 실패: {e}")
                stats["parse_error"] += 1
                continue

            results[app_id] = {
                "row": build_metric_row(parsed),
                "usage": body.get("usage", {}),
            }
            stats["success"] += 1

    print(f"파싱 완료: 성공 {stats['success']}, "
          f"HTTP오류 {stats['http_error']}, 파싱실패 {stats['parse_error']}, "
          f"app_id없음 {stats['no_app_id']}")
    return results, stats


# ============== app_id -> games.id 매핑 ==============
def resolve_game_ids(app_ids: List[int]) -> Dict[int, int]:
    """Resolve app_id -> games.id (game_metrics PK is game_id, not app_id).
    app_id를 games.id로 변환한다. game_metrics의 PK는 app_id가 아닌 game_id다."""
    if not app_ids:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT app_id, id FROM games WHERE app_id = ANY(:app_ids)"),
            {"app_ids": app_ids},
        ).fetchall()
    return {r[0]: r[1] for r in rows}


# ============== UPSERT ==============
def build_upsert_sql() -> str:
    """Compose the INSERT ... ON CONFLICT (game_id) DO UPDATE statement.
    game_id 충돌 시 갱신하는 UPSERT 문을 구성한다 (금지 컬럼은 제외)."""
    cols = (NUMERIC_METRIC_FIELDS + BOOLEAN_TAG_FIELDS + [
        'gem_potential', 'confidence_score',
        'analysis_summary', 'genre_classification', 'core_loop',
        'metric_justifications', 'data_limitations',
        'raw_content', 'raw_reasoning',
        'extraction_version', 'extracted_at', 'updated_at',
    ])

    # hard guard: never emit forbidden columns
    assert not (set(cols) & FORBIDDEN_COLUMNS), "금지 컬럼이 UPSERT에 포함됨!"

    insert_cols = ['game_id'] + cols
    placeholders = [f":{c}" for c in insert_cols]
    updates = [f"{c} = EXCLUDED.{c}" for c in cols]

    return f"""
        INSERT INTO game_metrics ({', '.join(insert_cols)})
        VALUES ({', '.join(placeholders)})
        ON CONFLICT (game_id) DO UPDATE SET
            {', '.join(updates)}
    """


UPSERT_SQL = build_upsert_sql()


def activate_games(game_ids: List[int], version: str) -> int:
    """Flip games live only after BOTH metrics AND embedding landed.
    metrics와 embedding이 모두 채워진 게임만 서비스에 노출시킨다.

    이유: embedding이 NULL인 채 is_active=TRUE가 되면, A의 추천 엔진
    (score_v6, pgvector 40% 비중)에서 신작이 벡터 검색에 안 잡히는데도
    검색·랭킹엔 노출되는 반쪽 상태가 된다. 그 사고를 구조적으로 막는다.

    is_analyzed/analysis_method는 metrics 기준으로 갱신하되,
    is_active만 embedding 조건을 추가로 요구한다.
    (embedding은 별도 파이프라인(generate_embeddings)이 채운 뒤 재호출로 활성화)
    """
    if not game_ids:
        return 0
    now = datetime.now()
    with engine.begin() as conn:
        # 분석 상태는 metrics 기준으로 항상 갱신
        conn.execute(text("""
            UPDATE games SET
                is_analyzed = TRUE,
                analysis_method = :version,
                analyzed_at = :now,
                updated_at = :now
            WHERE id = ANY(:ids)
        """), {"ids": game_ids, "version": version, "now": now})

        # is_active는 embedding이 있는 게임만 켠다 (반쪽 노출 방지)
        result = conn.execute(text("""
            UPDATE games g SET
                is_active = TRUE,
                updated_at = :now
            WHERE g.id = ANY(:ids)
              AND EXISTS (
                  SELECT 1 FROM game_metrics m
                  WHERE m.game_id = g.id AND m.embedding IS NOT NULL
              )
        """), {"ids": game_ids, "now": now})

    activated = result.rowcount or 0
    pending = len(game_ids) - activated
    print(f"games 활성화: {activated}개 (metrics + embedding 모두 완비)")
    if pending > 0:
        print(f"   {pending}개는 embedding 대기 → is_active=FALSE 유지")
        print(f"      (generate_embeddings 실행 후 재활성화 필요)")
    return activated


def upsert_metrics(results: Dict[int, Dict], version: str) -> Tuple[int, int, int]:
    """Write metrics into game_metrics; skip app_ids missing from games.
    game_metrics에 UPSERT한다. games에 없는 app_id는 건너뛴다."""
    app_ids = list(results.keys())
    id_map = resolve_game_ids(app_ids)

    missing = [a for a in app_ids if a not in id_map]
    if missing:
        print(f"games 테이블에 없는 app_id {len(missing)}개 (건너뜀): {missing[:10]}")
        print("   → 크롤러가 games 등록을 했는지 확인 (steam_crawler --no-register 썼나?)")

    now = datetime.now()
    success = failed = 0
    written_game_ids: List[int] = []

    print(f"\ngame_metrics UPSERT 중... ({len(id_map)}개)")
    with engine.begin() as conn:
        for app_id, payload in tqdm(results.items(), desc="UPSERT"):
            game_id = id_map.get(app_id)
            if game_id is None:
                continue

            params = dict(payload["row"])
            params.update({
                "game_id": game_id,
                "extraction_version": version,
                "extracted_at": now,
                "updated_at": now,
            })
            try:
                conn.execute(text(UPSERT_SQL), params)
                written_game_ids.append(game_id)
                success += 1
            except Exception as e:
                print(f"\n   app_id={app_id} (game_id={game_id}) 실패: {e}")
                failed += 1

    # only games whose metrics actually landed become visible
    if written_game_ids:
        activate_games(written_game_ids, version)

    return success, failed, len(missing)


# ============== 검증 ==============
def validate_results(results: Dict[int, Dict]) -> None:
    """Report completeness and scale sanity before touching the DB.
    DB를 건드리기 전에 완전성과 스케일 정합성을 리포트한다."""
    print("\n결과 품질 검증")
    total = len(results)
    if total == 0:
        print("   결과 없음")
        return

    complete = [metric_completeness(p["row"]) for p in results.values()]
    full = sum(1 for c in complete if c == len(NUMERIC_METRIC_FIELDS))
    gems = [p["row"]["gem_potential"] for p in results.values()
            if p["row"]["gem_potential"] is not None]

    print(f"   총 {total}건 | 49지표 완전체 {full}건 "
          f"({full / total * 100:.1f}%) | 평균 채움 {sum(complete) / total:.1f}/49")

    if gems:
        print(f"   gem_potential: MIN {min(gems):.1f} / MAX {max(gems):.1f} "
              f"/ AVG {sum(gems) / len(gems):.1f}  (0-100 스케일이어야 정상)")
        if max(gems) <= 10:
            print("   경고: MAX<=10 → 0-10 스케일로 나온 듯. 프롬프트 앵커 확인 필요!")
    else:
        print("   경고: gem_potential이 하나도 없음")

    sample_id, sample = next(iter(results.items()))
    row = sample["row"]
    print(f"\n   샘플 app_id={sample_id}")
    print(f"      cozy_factor={row['cozy_factor']} horror_factor={row['horror_factor']}")
    print(f"      build_variety={row['build_variety']} (extended flatten 확인)")
    print(f"      gem_potential={row['gem_potential']} confidence={row['confidence_score']}")


def verify_after_write(app_ids: List[int]) -> None:
    """Read back a few rows to prove the write actually landed.
    실제로 기록됐는지 되읽어 확인한다 ('코드 있음 ≠ 동작함')."""
    if not app_ids:
        return
    sample = app_ids[:5]
    print("\n적재 후 실측 검증 (되읽기)")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT g.app_id, m.gem_potential, m.cozy_factor, m.build_variety,
                   m.gem_percentile, m.extraction_version,
                   g.is_active, g.is_analyzed, g.analysis_method
            FROM game_metrics m
            JOIN games g ON g.id = m.game_id
            WHERE g.app_id = ANY(:ids)
        """), {"ids": sample}).fetchall()

    for r in rows:
        pct = "NULL(보존됨)" if r[4] is None else f"{r[4]:.2f}(기존값 보존)"
        print(f"   app_id={r[0]}: gem={r[1]} cozy={r[2]} build_variety={r[3]}")
        print(f"      gem_percentile={pct} | ver={r[5]}")
        print(f"      is_active={r[6]} is_analyzed={r[7]} method={r[8]}")


# ============== 메인 ==============
def main():
    parser = argparse.ArgumentParser(
        description="Hidden Gem - Batch 결과 → game_metrics 정규화 적재")
    parser.add_argument("result_file", help="Batch API 결과 JSONL 경로")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB 미변경, 파싱/검증만 수행")
    parser.add_argument("--version", default="gpt5.4-batch-v1",
                        help="extraction_version 값 (신작 few-shot이면 fewshot_5.4based)")
    parser.add_argument("--yes", action="store_true", help="확인 프롬프트 생략")
    args = parser.parse_args()

    print("=" * 60)
    print("Hidden Gem - Batch 결과 처리기 (정규화 60컬럼)")
    print("=" * 60)

    result_path = Path(args.result_file)
    if not result_path.exists():
        result_path = DATA_DIR / args.result_file
        if not result_path.exists():
            print(f"파일을 찾을 수 없습니다: {args.result_file}")
            return

    print(f"결과 파일: {result_path}")
    print(f"DB: {DB_URL[:30]}...")
    print(f" extraction_version: {args.version}")
    print(f"제외 컬럼: {', '.join(sorted(FORBIDDEN_COLUMNS))}")
    print("=" * 60)

    results, _ = parse_batch_result(result_path)
    if not results:
        print("파싱된 결과가 없습니다!")
        return

    validate_results(results)

    if args.dry_run:
        print("\nDry-run 모드: DB 업데이트 건너뜀")
        return

    if not args.yes:
        confirm = input(f"\n{len(results)}건을 game_metrics에 UPSERT할까요? (y/n): ").strip().lower()
        if confirm != 'y':
            print("취소됨")
            return

    success, failed, missing = upsert_metrics(results, args.version)

    print("\n" + "=" * 60)
    print("처리 완료!")
    print(f"   UPSERT 성공: {success}개")
    print(f"   실패: {failed}개")
    print(f"   games에 없어 건너뜀: {missing}개")
    print("=" * 60)

    verify_after_write(list(results.keys()))
    print("\n신작을 적재했다면 gem_percentile 전체 재계산(task5)이 필요합니다.")


if __name__ == "__main__":
    main()