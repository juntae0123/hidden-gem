"""
Hidden Gem - 학생 모델(gpt-5.4-mini few-shot) 품질 감사
======================================================
"신작 데이터가 교사(GPT-5.4) 데이터와 같은 잣대로 매겨졌는가"를 숫자로 확인한다.
회차별 gem 평균이 비슷하다는 건 드리프트 감시일 뿐 품질 검증이 아니다 — 모집단이
다르고(교사=인기순 샘플, 신작=전수), 평균이 같은 것은 few-shot 사전분포로의
회귀일 수도 있다. 진짜 검증은 같은 게임에 대한 교사 vs 학생 직접 비교다.

모드:
    --make-holdout N     교사 데이터 게임 N개를 gem 5분위 층화 샘플 → data/audit/holdout.csv
                         (few-shot 예시 게임은 제외). 이어서 학생 모델로 돌릴 명령을 출력.
    --compare FILE       학생 결과 JSONL vs game_metrics의 교사 값 비교
                         (49 수치 MAE/상관, 9 불리언 일치율, gem MAE/스피어만/구간 혼동, confidence 분포)
                         → data/audit/holdout_compare.csv. 결과 JSONL은 data/audit/로 옮겨 오적재를 막는다.
    --new-sample         신작 중 gem 상위 15 / 하위 15 / 무작위 15 → data/audit/new_games_sample.csv (눈검수용)

사용법 (루프가 끝난 뒤, 데스크탑에서):
    docker compose exec batch python -m embeddings.audit_student --make-holdout 150
    docker compose exec batch python -m embeddings.batch_generator --csv data/audit/holdout.csv --full --yes \\
        --model gpt-5.4-mini --fewshot data/fewshot/fewshot_examples.jsonl --fewshot-n 12 --sync
    docker compose exec batch python -m embeddings.audit_student --compare data/batch_output_<timestamp>.jsonl
    docker compose exec batch python -m embeddings.audit_student --new-sample

주의: holdout 결과 JSONL을 batch_processor로 적재하면 교사 값이 학생 값으로 덮인다. 절대 적재 금지.
"""

import argparse
import csv
import json
import random
from datetime import datetime
import shutil
import sys
from pathlib import Path
from typing import Dict, List

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from embeddings.batch_processor import (  # noqa: E402
    BOOLEAN_TAG_FIELDS, DATA_DIR, NUMERIC_METRIC_FIELDS, engine, parse_batch_result,
)

AUDIT_DIR = DATA_DIR / "audit"
# DB의 실제 교사 라벨. 최초 4,190개 구축 시 games.analysis_method 에 기록된 값이며,
# batch_processor의 extraction_version 기본값("gpt5.4-batch-v1")과 다르다 — 혼동 주의.
TEACHER = "gpt5.4_batch"
STUDENT = "fewshot_5.4based"
FEWSHOT_FILE = DATA_DIR / "fewshot" / "fewshot_examples.jsonl"
BASELINE_FILE = AUDIT_DIR / "quality_baseline.json"
DRIFT_TOLERANCE = 1.30      # 기준선 대비 평균 MAE가 이 배수를 넘으면 품질 회귀로 본다


def _fewshot_app_ids() -> set:
    ids = set()
    if FEWSHOT_FILE.exists():
        with open(FEWSHOT_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        ids.add(int(json.loads(line).get("app_id")))
                    except (TypeError, ValueError):
                        pass
    return ids


# ============== 1) holdout 샘플 ==============
def make_holdout(n: int, seed: int, teacher_label: str = None) -> Path:
    global TEACHER
    if teacher_label:
        TEACHER = teacher_label
    exclude = _fewshot_app_ids()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT g.app_id, g.name, g.genres, g.description, m.gem_potential
            FROM games g JOIN game_metrics m ON m.game_id = g.id
            WHERE g.analysis_method = :ver AND g.is_active = TRUE
              AND m.gem_potential IS NOT NULL
              AND COALESCE(g.description, '') <> ''
        """), {"ver": TEACHER}).fetchall()
    rows = [dict(r._mapping) for r in rows if r.app_id not in exclude]
    if not rows:
        with engine.connect() as conn:
            dist = conn.execute(text("""
                SELECT analysis_method, COUNT(*) FROM games
                WHERE is_analyzed = TRUE GROUP BY 1 ORDER BY 2 DESC
            """)).fetchall()
        print(f"교사 라벨 '{TEACHER}' 게임이 0건입니다. DB의 analysis_method 분포:")
        for method, n in dist:
            print(f"   {method}: {n:,}건")
        print("→ 위 목록에서 교사(GPT-5.4로 최초 구축한) 라벨을 골라 --teacher-label 로 지정하세요.")
        raise SystemExit(2)
    rows.sort(key=lambda r: r["gem_potential"])
    random.seed(seed)
    k = 5
    per = n // k
    picked: List[Dict] = []
    for i in range(k):
        stratum = rows[i * len(rows) // k:(i + 1) * len(rows) // k]
        picked += random.sample(stratum, min(per, len(stratum)))
    random.shuffle(picked)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIT_DIR / "holdout.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["app_id", "name", "genres", "description"])
        w.writeheader()
        for r in picked:
            w.writerow({k2: r[k2] for k2 in w.fieldnames})
    # 정답(교사 gem)은 별도 파일에 — 블라인드 CSV엔 넣지 않는다
    with open(AUDIT_DIR / "holdout_truth.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["app_id", "teacher_gem"])
        for r in picked:
            w.writerow([r["app_id"], r["gem_potential"]])

    gems = [r["gem_potential"] for r in picked]
    print(f"holdout {len(picked)}건 (교사 풀 {len(rows):,}건, few-shot 제외 {len(exclude)}건)")
    print(f"   교사 gem 범위 {min(gems):.0f}~{max(gems):.0f}, 평균 {sum(gems)/len(gems):.1f}")
    print(f"   저장: {out}")
    print("\n다음 (학생 모델로 블라인드 분석, DB 미접촉):")
    print(f"   python -m embeddings.batch_generator --csv {out} --full --yes "
          f"--model gpt-5.4-mini --fewshot data/fewshot/fewshot_examples.jsonl --fewshot-n 12 --sync")
    print("   python -m embeddings.audit_student --compare data/batch_output_<timestamp>.jsonl")
    return out


# ============== 2) 비교 ==============
def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return float("nan")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


def _spearman(xs: List[float], ys: List[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                r[order[t]] = avg
            i = j + 1
        return r
    return _pearson(ranks(xs), ranks(ys))


def _gem_bucket(g: float) -> str:
    return "low(<35)" if g < 35 else "mid(35-64)" if g < 65 else "high(65+)"


def compare(result_file: Path) -> None:
    results, _ = parse_batch_result(result_file)
    app_ids = list(results.keys())
    cols = NUMERIC_METRIC_FIELDS + BOOLEAN_TAG_FIELDS + ["gem_potential", "confidence_score"]
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT g.app_id, g.name, {', '.join('m.' + c for c in cols)}
            FROM games g JOIN game_metrics m ON m.game_id = g.id
            WHERE g.app_id = ANY(:ids) AND g.analysis_method = :ver
        """), {"ids": app_ids, "ver": TEACHER}).fetchall()
    teacher = {r.app_id: dict(r._mapping) for r in rows}
    common = [a for a in app_ids if a in teacher]
    print(f"\n비교 대상: 학생 {len(results)}건 ∩ 교사 {len(common)}건")
    if len(common) < 10:
        print("교사 데이터와 겹치는 게임이 너무 적습니다 (holdout.csv로 만든 결과인지 확인)")
        return

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    report_rows = []

    # 수치 49개
    print(f"\n{'지표':28} {'MAE':>6} {'r':>6}   {'교사μ':>6} {'학생μ':>6}  판정")
    worst = []
    for c in NUMERIC_METRIC_FIELDS:
        pairs = [(teacher[a][c], results[a]["row"].get(c)) for a in common]
        pairs = [(float(t), float(s)) for t, s in pairs if t is not None and s is not None]
        if not pairs:
            continue
        ts, ss = zip(*pairs)
        mae = sum(abs(t - s) for t, s in pairs) / len(pairs)
        r = _pearson(list(ts), list(ss))
        flag = "" if (mae <= 1.5 and (r != r or r >= 0.6)) else "주의" if mae <= 2.5 else "불량"
        worst.append((mae, c))
        report_rows.append({"metric": c, "type": "numeric", "mae": round(mae, 3), "r": round(r, 3) if r == r else "",
                            "teacher_mean": round(sum(ts) / len(ts), 2), "student_mean": round(sum(ss) / len(ss), 2), "flag": flag})
    for row in sorted(report_rows, key=lambda x: -x["mae"]):
        print(f"{row['metric']:28} {row['mae']:6.2f} {str(row['r']):>6}   {row['teacher_mean']:6.2f} {row['student_mean']:6.2f}  {row['flag']}")
    maes = [m for m, _ in worst]
    print(f"\n수치 49개 평균 MAE {sum(maes)/len(maes):.2f} (0~10 스케일)  |  MAE>2.5 지표 {sum(1 for m in maes if m > 2.5)}개")

    # 불리언 9개
    print(f"\n{'태그':28} {'일치율':>7}")
    for c in BOOLEAN_TAG_FIELDS:
        pairs = [(teacher[a][c], results[a]["row"].get(c)) for a in common]
        pairs = [(bool(t), bool(s)) for t, s in pairs if t is not None and s is not None]
        if not pairs:
            continue
        acc = sum(1 for t, s in pairs if t == s) / len(pairs)
        flag = "" if acc >= 0.85 else "주의" if acc >= 0.7 else "불량"
        print(f"{c:28} {acc*100:6.1f}%  {flag}")
        report_rows.append({"metric": c, "type": "boolean", "mae": "", "r": "", "teacher_mean": "", "student_mean": "",
                            "flag": flag, "agreement": round(acc, 3)})

    # gem_potential
    gp = [(float(teacher[a]["gem_potential"]), float(results[a]["row"].get("gem_potential")))
          for a in common if teacher[a]["gem_potential"] is not None and results[a]["row"].get("gem_potential") is not None]
    tg, sg = zip(*gp)
    gem_mae = sum(abs(t - s) for t, s in gp) / len(gp)
    gem_rho = _spearman(list(tg), list(sg))
    bias = sum(s - t for t, s in gp) / len(gp)
    print(f"\ngem_potential  MAE {gem_mae:.1f}  스피어만 ρ {gem_rho:.3f}  편향(학생-교사) {bias:+.1f}")
    print(f"   교사 μ {sum(tg)/len(tg):.1f} σ {(sum((x-sum(tg)/len(tg))**2 for x in tg)/len(tg))**0.5:.1f}"
          f"  |  학생 μ {sum(sg)/len(sg):.1f} σ {(sum((x-sum(sg)/len(sg))**2 for x in sg)/len(sg))**0.5:.1f}")
    conf = {}
    for t, s in gp:
        key = (_gem_bucket(t), _gem_bucket(s))
        conf[key] = conf.get(key, 0) + 1
    buckets = ["low(<35)", "mid(35-64)", "high(65+)"]
    print("   구간 혼동 (행=교사, 열=학생)")
    print(f"   {'':12}" + "".join(f"{b:>12}" for b in buckets))
    for tb in buckets:
        print(f"   {tb:12}" + "".join(f"{conf.get((tb, sb), 0):12d}" for sb in buckets))
    diag = sum(conf.get((b, b), 0) for b in buckets)
    print(f"   구간 일치율 {diag/len(gp)*100:.1f}%")

    # confidence
    tc = [float(teacher[a]["confidence_score"]) for a in common if teacher[a]["confidence_score"] is not None]
    sc = [float(results[a]["row"].get("confidence_score")) for a in common if results[a]["row"].get("confidence_score") is not None]
    if tc and sc:
        sd = lambda v: (sum((x - sum(v)/len(v))**2 for x in v)/len(v))**0.5
        print(f"\nconfidence  교사 μ {sum(tc)/len(tc):.2f} σ {sd(tc):.2f}  |  학생 μ {sum(sc)/len(sc):.2f} σ {sd(sc):.2f}"
              f"  (σ가 0.05 미만이면 4o-mini처럼 평탄화된 것)")

    # 종합
    print("\n판정 기준(휴리스틱): gem MAE ≤ 8 & ρ ≥ 0.7 & 구간 일치 ≥ 70% & 수치 MAE>2.5 지표 ≤ 5개 → 교사 잣대 유지로 봄")
    ok = gem_mae <= 8 and gem_rho >= 0.7 and diag / len(gp) >= 0.7 and sum(1 for m in maes if m > 2.5) <= 5
    print("→ " + ("통과" if ok else "재검토 필요: few-shot 개수/예시 구성 조정 또는 교사 모델 재분석 검토"))

    # 개별 게임 CSV
    per_game = AUDIT_DIR / "holdout_compare.csv"
    with open(per_game, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "name", "teacher_gem", "student_gem", "diff", "teacher_conf", "student_conf"])
        for a in common:
            t = teacher[a]; s = results[a]["row"]
            w.writerow([a, t["name"], t["gem_potential"], s.get("gem_potential"),
                        (s.get("gem_potential") or 0) - (t["gem_potential"] or 0),
                        t["confidence_score"], s.get("confidence_score")])
    # 지표별 쌍 (calibrate_student 입력): app_id, metric, teacher, student
    with open(AUDIT_DIR / "holdout_pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "metric", "teacher", "student"])
        for a in common:
            t = teacher[a]; s = results[a]["row"]
            for c in NUMERIC_METRIC_FIELDS + ["gem_potential", "confidence_score"]:
                if t.get(c) is not None and s.get(c) is not None:
                    w.writerow([a, c, t[c], s.get(c)])
    with open(AUDIT_DIR / "holdout_metrics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "type", "mae", "r", "teacher_mean", "student_mean", "agreement", "flag"])
        w.writeheader()
        for r in report_rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    print(f"\n저장: {per_game}, {AUDIT_DIR / 'holdout_metrics.csv'}, {AUDIT_DIR / 'holdout_pairs.csv'}")

    # ===== 품질 기준선 / 드리프트 게이트 =====
    # 이후 회차에서 같은 검사를 돌렸을 때 학생 모델 품질이 떨어졌는지 자동으로 잡는다.
    summary = {
        "n": len(common), "numeric_mae_mean": round(sum(maes) / len(maes), 4),
        "numeric_mae_over_2_5": sum(1 for m in maes if m > 2.5),
        "gem_mae": round(gem_mae, 3), "gem_spearman": round(gem_rho, 3),
        "gem_bucket_agreement": round(diag / len(gp), 3),
        "per_metric_mae": {r["metric"]: r["mae"] for r in report_rows if r["type"] == "numeric"},
    }
    drift_failed = False
    if BASELINE_FILE.exists():
        base = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        b_mae = base.get("numeric_mae_mean")
        print(f"\n품질 기준선 대조 (기준선 {base.get('recorded_at', '?')[:10]}, n={base.get('n')})")
        if b_mae:
            ratio = summary["numeric_mae_mean"] / b_mae
            print(f"   49지표 평균 MAE {b_mae:.2f} → {summary['numeric_mae_mean']:.2f} "
                  f"({(ratio - 1) * 100:+.0f}%)")
            drift_failed = ratio > DRIFT_TOLERANCE
            worst = sorted(
                ((summary["per_metric_mae"].get(k, 0) - v, k, v, summary["per_metric_mae"].get(k, 0))
                 for k, v in (base.get("per_metric_mae") or {}).items()), reverse=True)[:5]
            print("   악화 상위 5개 (기준선 → 현재):")
            for d, k, bv, cv in worst:
                print(f"      {k:26} {bv:.2f} → {cv:.2f} ({d:+.2f})")
            print("   → " + ("품질 회귀 감지: few-shot/모델 변경 여부 확인 필요"
                             if drift_failed else "기준선 대비 이상 없음"))
    else:
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(
            {"recorded_at": datetime.now().isoformat(), "model_hint": "gpt-5.4-mini + 12shot", **summary},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n품질 기준선 신규 기록: {BASELINE_FILE}")
        print("   이후 --compare 실행 시 이 값과 자동 대조해 품질 회귀를 잡는다.")
    (AUDIT_DIR / "quality_last.json").write_text(json.dumps(
        {"recorded_at": datetime.now().isoformat(), **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    if drift_failed:
        raise SystemExit(3)

    # 오적재 방지: 결과 파일을 audit 폴더로 이동
    if result_file.parent.resolve() == DATA_DIR.resolve():
        dest = AUDIT_DIR / f"holdout_{result_file.name}"
        shutil.move(str(result_file), str(dest))
        print(f"결과 JSONL 이동 (batch_processor 오적재 방지): {dest}")


# ============== 3) 신작 눈검수 샘플 ==============
def new_sample(k: int = 15) -> None:
    with engine.connect() as conn:
        base = """
            SELECT g.app_id, g.name, g.genres, LEFT(g.description, 140) AS description,
                   m.gem_potential, m.confidence_score, g.review_count, g.is_active, g.release_date
            FROM games g JOIN game_metrics m ON m.game_id = g.id
            WHERE g.analysis_method = :ver AND m.gem_potential IS NOT NULL
        """
        top = conn.execute(text(base + " ORDER BY m.gem_potential DESC, g.review_count DESC LIMIT :k"), {"ver": STUDENT, "k": k}).fetchall()
        bottom = conn.execute(text(base + " ORDER BY m.gem_potential ASC LIMIT :k"), {"ver": STUDENT, "k": k}).fetchall()
        rnd = conn.execute(text(base + " ORDER BY random() LIMIT :k"), {"ver": STUDENT, "k": k}).fetchall()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIT_DIR / "new_games_sample.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "app_id", "name", "genres", "release_date", "gem", "confidence", "review_count", "is_active", "description"])
        for grp, rows in (("top", top), ("bottom", bottom), ("random", rnd)):
            for r in rows:
                w.writerow([grp, r.app_id, r.name, r.genres, r.release_date, r.gem_potential, r.confidence_score,
                            r.review_count, r.is_active, r.description])
    print(f"저장: {out} ({3*k}행)")
    for grp, rows in (("gem 상위", top), ("gem 하위", bottom)):
        print(f"\n{grp} {k}건")
        for r in rows:
            print(f"   {r.gem_potential:5.0f}  conf {r.confidence_score or 0:.2f}  리뷰 {r.review_count or 0:>5}  {str(r.name)[:34]:36} {str(r.genres)[:28]}")


def main():
    global TEACHER
    p = argparse.ArgumentParser(description="학생 모델 품질 감사")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--make-holdout", type=int, metavar="N")
    g.add_argument("--compare", metavar="FILE")
    g.add_argument("--new-sample", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--teacher-label", default=None,
                   help=f"교사 games.analysis_method 값 (기본 {TEACHER})")
    a = p.parse_args()
    if a.make_holdout:
        make_holdout(a.make_holdout, a.seed, a.teacher_label)
    elif a.compare:
        if a.teacher_label:
            TEACHER = a.teacher_label
        path = Path(a.compare)
        if not path.exists():
            path = DATA_DIR / a.compare
        compare(path)
    else:
        new_sample()


if __name__ == "__main__":
    main()
