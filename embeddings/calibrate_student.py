"""
Hidden Gem - 학생 지표 사후 보정 (교사 스케일 매핑, 재분석 없음 = 비용 0)
=========================================================================
홀드아웃(audit_student --compare)에서 얻은 교사·학생 쌍(holdout_pairs.csv)으로
"학생 점수 → 교사 스케일" 선형 매핑을 지표별로 적합하고, 이미 적재된 학생 결과에 적용한다.

언제 쓰나: 홀드아웃에서 학생이 교사와 '순서'는 맞추는데(ρ 높음) '수준'이 일관되게
다를 때(예: 학생이 전반적으로 1~2점 낮게, gem을 30점 낮게). 순서조차 안 맞으면(ρ 낮음)
보정으로 살릴 수 없으니 이 도구는 거부한다.

안전장치:
    - 적용 전 원본을 student_raw_metrics(game_id, metric, raw_value)에 보존 (이미 있으면 덮지 않음)
    - --revert 로 원본 복원
    - 적합 파라미터는 data/audit/calibration_params.json 에 기록 (git 추적 대상)
    - 지표별로 r < MIN_R 이거나 쌍 수 부족이면 보정 건너뜀(그대로 둠)
    - |평균 편향| < MIN_BIAS 이면 보정 불필요로 건너뜀
    - embedding, gem_percentile 무접촉 (percentile은 보정 후 recalc_percentile로 재계산)

사용법:
    python -m embeddings.calibrate_student --fit                 # 파라미터 적합 + 리포트
    python -m embeddings.calibrate_student --apply --dry-run     # 적용 미리보기 (분포 전/후)
    python -m embeddings.calibrate_student --apply --yes
    python -m embeddings.calibrate_student --revert --yes
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from embeddings.batch_processor import DATA_DIR, NUMERIC_METRIC_FIELDS, engine  # noqa: E402

AUDIT_DIR = DATA_DIR / "audit"
PAIRS_FILE = AUDIT_DIR / "holdout_pairs.csv"
PARAMS_FILE = AUDIT_DIR / "calibration_params.json"
BACKUP_TABLE = "student_raw_metrics"
STUDENT = "fewshot_5.4based"

MIN_PAIRS = 60
MIN_R = 0.45          # 순서 일치가 이 아래면 보정 불가
MIN_BIAS = 0.5        # 0~10 지표: 이 아래 편향은 보정 안 함
MIN_BIAS_GEM = 5.0    # gem_potential(0~100)
MIN_SLOPE = 0.7       # 이 아래면 '범위 압축'(평균 회귀) — 변별력을 죽이므로 거부
MAX_MAE_RATIO = 0.85  # 보정 후 MAE가 (교사 평균만 찍는) 상수 예측 MAE의 이 비율을 넘으면 퇴화로 판정
ZERO_MASS_FOR_ORIGIN = 0.10  # 홀드아웃 쌍에서 0 이 이 비율 이상이면 절편 없는 원점 고정 보정(y=bx). 0 은 0 으로 남는다


def fit():
    if not PAIRS_FILE.exists():
        print(f"{PAIRS_FILE} 없음 — audit_student --compare 먼저"); return 1
    pairs = defaultdict(list)
    with open(PAIRS_FILE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                pairs[r["metric"]].append((float(r["student"]), float(r["teacher"])))
            except ValueError:
                pass
    params, report = {}, []
    for metric in NUMERIC_METRIC_FIELDS + ["gem_potential"]:
        pts = pairs.get(metric, [])
        n = len(pts)
        if n < MIN_PAIRS:
            report.append((metric, n, None, None, None, "쌍 부족 → 건너뜀")); continue
        x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
        bias = float((y - x).mean())
        r = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")
        hi = 100.0 if metric == "gem_potential" else 10.0
        min_bias = MIN_BIAS_GEM if metric == "gem_potential" else MIN_BIAS
        if not (r == r) or r < MIN_R:
            report.append((metric, n, r, bias, None, "r 낮음 → 보정 불가(그대로)")); continue
        if abs(bias) < min_bias:
            report.append((metric, n, r, bias, None, "편향 작음 → 불필요")); continue
        # 0 이 의미 있는 지표(공포 0 = 공포 없음, 아늑함 0 = 아늑하지 않음)는 원점을 고정한다.
        # 2026-09-05 절제 실측: 절편 있는 보정(y=+0.77+0.97x)이 학생 cozy 0 을 0.77 로 밀어
        # 공포 프리셋(cozy 목표 0)에서 학생 게임을 전부 밀어냈다(교사 비율 0.85 → 1.00).
        # 평균 편향은 중간 구간에서 나오는데 절편은 0 에도 같은 이동을 강제한다 — 형태가 틀렸다.
        zero_frac = float(((x == 0) | (y == 0)).mean())
        origin_fixed = zero_frac >= ZERO_MASS_FOR_ORIGIN
        if origin_fixed:
            b_raw = float((x * y).sum() / (x * x).sum()) if (x * x).sum() > 0 else 1.0
            b = float(np.clip(b_raw, 0.5, 2.0)); a = 0.0
        else:
            # 최소제곱 y = a + b x
            b_raw, a_raw = np.polyfit(x, y, 1)
            b = float(np.clip(b_raw, 0.5, 2.0)); a = float(y.mean() - b * x.mean())
        resid = float(np.abs(y - np.clip(a + b * x, 0, hi)).mean())
        # 상수 예측(교사 평균) 대비 개선폭. 홀드아웃 교사 범위가 좁으면(범위 제한)
        # 최소제곱은 모든 값을 교사 평균 쪽으로 밀어 넣어 "MAE는 좋아 보이지만 변별력이 죽는"
        # 퇴화 매핑이 나온다. 그걸 여기서 걸러낸다.
        mad_const = float(np.abs(y - y.mean()).mean())
        ratio = resid / mad_const if mad_const > 0 else 1.0
        if b_raw < MIN_SLOPE:
            report.append((metric, n, r, bias, resid,
                           f"거부: 기울기 {b_raw:.2f} < {MIN_SLOPE} — 범위 압축(평균 회귀)"))
            continue
        mae_before = float(np.abs(y - x).mean())
        if resid >= mae_before:
            report.append((metric, n, r, bias, resid,
                           f"거부: 보정 후 MAE {resid:.2f} ≥ 보정 전 {mae_before:.2f} — 개선 없음"))
            continue
        if ratio > MAX_MAE_RATIO:
            report.append((metric, n, r, bias, resid,
                           f"거부: 상수 예측 대비 개선 {(1-ratio)*100:.0f}%뿐 — 퇴화 매핑"))
            continue
        params[metric] = {"a": round(a, 4), "b": round(b, 4), "n": n, "r": round(r, 3),
                          "form": "origin" if origin_fixed else "affine", "zero_frac": round(zero_frac, 3),
                          "bias_before": round(bias, 3), "mae_after": round(resid, 3),
                          "mae_before": round(mae_before, 3), "mae_const": round(mad_const, 3), "hi": hi,
                          "holdout_student_range": [float(x.min()), float(x.max())],
                          "holdout_teacher_range": [float(y.min()), float(y.max())]}
        report.append((metric, n, r, bias, resid,
                       f"보정 y={b:.2f}x (원점 고정, 0비율 {zero_frac:.0%})" if origin_fixed else f"보정 y={a:+.2f}+{b:.2f}x"))

    print(f"{'지표':26} {'n':>4} {'r':>6} {'편향(교사-학생)':>14} {'보정후MAE':>9}  처리")
    for m, n, r, bias, resid, note in report:
        print(f"{m:26} {n:4} {('%.2f' % r) if r is not None else '':>6} {('%+.2f' % bias) if bias is not None else '':>14} "
              f"{('%.2f' % resid) if resid is not None else '':>9}  {note}")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    PARAMS_FILE.write_text(json.dumps({"fitted_at": datetime.now().isoformat(), "source": str(PAIRS_FILE),
                                       "params": params}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n보정 대상 지표 {len(params)}개 → {PARAMS_FILE}")
    if "gem_potential" not in params:
        print("gem_potential은 보정 대상에서 제외됨 — 위 표의 사유 확인.")
        print("  (교사 홀드아웃 gem 범위가 좁으면 선형 보정이 모든 신작을 교사 평균 근처로")
        print("   밀어 넣어 변별력을 죽인다. 이럴 때 보정은 '개선'이 아니라 값 조작이다.)")
    for metric, p_ in params.items():
        sr = p_["holdout_student_range"]
        print(f"  주의({metric}): 검증된 학생값 구간은 {sr[0]:.0f}~{sr[1]:.0f}. "
              f"이 밖의 값에 적용되는 부분은 외삽이다.")
    return 0


def _ensure_backup(conn):
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
            game_id INTEGER NOT NULL, metric VARCHAR(64) NOT NULL,
            raw_value DOUBLE PRECISION, saved_at TIMESTAMP NOT NULL,
            PRIMARY KEY (game_id, metric)
        )
    """))


def apply(dry_run: bool, yes: bool):
    if not PARAMS_FILE.exists():
        print(f"{PARAMS_FILE} 없음 — --fit 먼저"); return 1
    params = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))["params"]
    if not params:
        print("보정 대상 지표 없음"); return 0
    metrics = list(params)
    with engine.connect() as conn:
        n_target = conn.execute(text("""
            SELECT COUNT(*) FROM game_metrics m JOIN games g ON g.id = m.game_id
            WHERE g.analysis_method = :ver
        """), {"ver": STUDENT}).scalar()
        print(f"학생 행 {n_target:,}건, 보정 지표 {len(metrics)}개")
        print("\n지표별 전/후 평균 (학생 전체):")
        for met in metrics:
            p = params[met]
            row = conn.execute(text(f"""
                SELECT AVG(m.{met}), AVG(LEAST(:hi, GREATEST(0, :a + :b * m.{met})))
                FROM game_metrics m JOIN games g ON g.id = m.game_id
                WHERE g.analysis_method = :ver AND m.{met} IS NOT NULL
            """), {"ver": STUDENT, "a": p["a"], "b": p["b"], "hi": p["hi"]}).fetchone()
            print(f"   {met:26} {row[0]:6.2f} → {row[1]:6.2f}   (y={p['a']:+.2f}+{p['b']:.2f}x, n={p['n']}, r={p['r']})")
    if dry_run:
        print("\nDry-run: DB 미변경"); return 0
    if not yes and input("\n적용할까요? (y/n): ").strip().lower() != "y":
        print("취소됨"); return 0

    with engine.begin() as conn:
        _ensure_backup(conn)
        for met in metrics:
            p = params[met]
            saved = conn.execute(text(f"""
                INSERT INTO {BACKUP_TABLE} (game_id, metric, raw_value, saved_at)
                SELECT m.game_id, :met, m.{met}, NOW()
                FROM game_metrics m JOIN games g ON g.id = m.game_id
                WHERE g.analysis_method = :ver AND m.{met} IS NOT NULL
                ON CONFLICT (game_id, metric) DO NOTHING
            """), {"met": met, "ver": STUDENT}).rowcount
            # 원본 기준으로 매핑 (재적용 시 이중 보정 방지: 백업의 raw_value에서 계산)
            updated = conn.execute(text(f"""
                UPDATE game_metrics m SET {met} = LEAST(:hi, GREATEST(0, ROUND((:a + :b * b.raw_value)::numeric, 1)))
                FROM {BACKUP_TABLE} b, games g
                WHERE b.game_id = m.game_id AND b.metric = :met
                  AND g.id = m.game_id AND g.analysis_method = :ver
            """), {"met": met, "ver": STUDENT, "a": p["a"], "b": p["b"], "hi": p["hi"]}).rowcount
            print(f"   {met:26} 백업 신규 {saved:,} / 보정 적용 {updated:,}")
    print("\n완료. 다음: python -m embeddings.recalc_percentile --yes  (gem 보정 시 백분위 재계산 필수)")
    return 0


def revert(yes: bool):
    if not yes and input("백업(student_raw_metrics)으로 원본 복원할까요? (y/n): ").strip().lower() != "y":
        print("취소됨"); return 0
    with engine.begin() as conn:
        mets = [r[0] for r in conn.execute(text(f"SELECT DISTINCT metric FROM {BACKUP_TABLE}")).fetchall()]
        for met in mets:
            n = conn.execute(text(f"""
                UPDATE game_metrics m SET {met} = b.raw_value
                FROM {BACKUP_TABLE} b WHERE b.game_id = m.game_id AND b.metric = :met
            """), {"met": met}).rowcount
            print(f"   {met:26} 복원 {n:,}")
    print("복원 완료. 다음: recalc_percentile --yes")
    return 0


def main():
    ap = argparse.ArgumentParser(description="학생 지표 사후 보정")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fit", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.fit:
        return fit()
    if a.apply:
        return apply(a.dry_run, a.yes)
    return revert(a.yes)


if __name__ == "__main__":
    sys.exit(main() or 0)
