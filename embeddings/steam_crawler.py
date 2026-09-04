"""
Hidden Gem - New Game Crawler (Steam only, no RAWG)
====================================================
Steam만으로 신작을 발견·수집해 batch_generator가 먹을 블라인드 CSV를 만든다.

RAWG를 쓰지 않는 이유:
    - RAWG ToS: 출처 표기 + 모든 페이지 하이퍼링크 의무, 월 20,000 요청 제한,
      데이터 재배포 금지(향후 게임사 대상 데이터 판매와 충돌 소지).
    - 우리는 Steam 추천 서비스이므로 Steam이 원천 데이터다. 의존을 끊는 게 싸다.
    - Steam ToS: 무료·상업적 사용 가능, 하루 100,000 콜.

발견 전략 (2단계, 폴백 포함):
    1) 주 경로: 스토어 검색 (sort_by=Released_DESC, category1=998)
       실제 출시일 역순 + 게임만. coming_soon=False 실측 확인됨.
       비공식 엔드포인트라 깨질 수 있어 폴백을 둔다.
    2) 폴백: IStoreService/GetAppList/v1 (공식 API, key 필요)
       include_games=true 로 DLC/소프트웨어/비디오 배제.
       출시일이 없어 app_id 내림차순(최근 등록순)으로 근사한다.

출력 계약 (batch_generator.load_blind_data와 일치):
    CSV 컬럼: app_id, name, genres, description  (정확히 4개)
    description 길이 10 초과만 통과. 정답 컬럼(gem_potential 등) 절대 금지.

사용법:
    # 최근 30일 신작, 3개만 (소량 테스트)
    docker compose exec batch python -m embeddings.steam_crawler --days 30 --limit 3

    # 특정 기간 백필
    docker compose exec batch python -m embeddings.steam_crawler \
        --from 2026-03-01 --to 2026-03-31 --limit 50

    # 공식 API 폴백 강제
    docker compose exec batch python -m embeddings.steam_crawler --days 30 --source applist
"""

import os
import re
import csv
import sys
import time
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set

import requests
from dotenv import load_dotenv

# ============== 경로 / 환경 ==============
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
DB_URL = os.getenv("DATABASE_URL")

STORE_SEARCH = "https://store.steampowered.com/search/results/"
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STORE_APPLIST = "https://api.steampowered.com/IStoreService/GetAppList/v1/"

STEAM_CATEGORY_GAMES = 998        # store search: games only (no DLC/soundtrack)

# generator contract: description must be longer than 10 chars.
MIN_DESCRIPTION_LEN = 11

# Undocumented store endpoints rate-limit around 200 req / 5 min.
STEAM_DELAY_SEC = 1.5
SEARCH_DELAY_SEC = 1.6

# 429를 맞을 때마다 검색 페이지 간격을 늘리는 적응형 지연 (백필처럼 수백 페이지 넘길 때 필수)
_adaptive = {"search_delay": SEARCH_DELAY_SEC}
MAX_RETRIES = 4

HTML_TAG = re.compile(r"<[^<]+?>")
APPID_IN_HTML = re.compile(r'data-ds-appid="(\d+)"')
RELEASED_IN_HTML = re.compile(r'search_released[^>]*>\s*([^<]+?)\s*<')

# Steam release_date.date locales: "2026년 7월 9일" / "9 Jul, 2026" / "Jul 9, 2026"
DATE_KO = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
DATE_EN_DMY = re.compile(r"(\d{1,2})\s+([A-Za-z]{3}),?\s+(\d{4})")
DATE_EN_MDY = re.compile(r"([A-Za-z]{3})\s+(\d{1,2}),?\s+(\d{4})")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# Non-game artifacts that slip past type/category filters.
EXCLUDE_NAME_PATTERNS = re.compile(
    r"(dedicated\s+server|soundtrack|original\s+score|art\s*book|"
    r"\bdemo\b|playtest|\bsdk\b|season\s+pass|\bdlc\b|"
    r"expansion\s+pass|upgrade\s+pack|bonus\s+content)",
    re.IGNORECASE,
)


# ============== HTTP ==============
def request_with_backoff(url: str, params: dict, label: str) -> Optional[requests.Response]:
    """GET with exponential backoff on 429/5xx.
    429/5xx 발생 시 지수 백오프로 재시도한다."""
    delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"   {label} 네트워크 오류 ({attempt}/{MAX_RETRIES}): {e}")
            time.sleep(delay)
            delay *= 2
            continue

        if resp.status_code == 200:
            return resp
        if resp.status_code == 429 or resp.status_code >= 500:
            if resp.status_code == 429 and label == "store search":
                # 재시도만으로는 다음 페이지에서 또 429 - 이후 페이지 간격 자체를 늘린다
                _adaptive["search_delay"] = min(_adaptive["search_delay"] + 0.5, 5.0)
                print(f"   {label} HTTP 429 → {delay:.0f}s 대기 (페이지 간격 {_adaptive['search_delay']:.1f}s로 상향)")
            else:
                print(f"   {label} HTTP {resp.status_code} → {delay:.0f}s 대기")
            time.sleep(delay)
            delay *= 2
            continue

        print(f"   {label} HTTP {resp.status_code}")
        return None

    print(f"   {label} 재시도 초과")
    return None


# ============== 날짜 파싱 ==============
def parse_release_date(raw: str) -> Optional[date]:
    """Parse Steam release_date.date across ko/en locales; None if unparseable.
    Steam 출시일 문자열을 한국어/영어 로케일 모두에서 파싱한다."""
    if not raw:
        return None

    m = DATE_KO.search(raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = DATE_EN_DMY.search(raw)
    if m and m.group(2)[:3].title() in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(2)[:3].title()], int(m.group(1)))

    m = DATE_EN_MDY.search(raw)
    if m and m.group(1)[:3].title() in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(1)[:3].title()], int(m.group(2)))

    return None


# ============== 1) 발견: 스토어 검색 (주 경로) ==============
def _parse_search_date(raw: str):
    """검색 결과 HTML의 출시일 문자열 파싱 (실패 시 None)."""
    raw = raw.strip()
    for fmt in ("%Y년 %m월 %d일", "%d %b, %Y", "%b %d, %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def discover_via_store_search(max_candidates: int, stop_before: Optional[date] = None) -> List[int]:
    """List app_ids sorted by real release date (games only).
    실제 출시일 역순으로 app_id를 수집한다 (게임만).
    stop_before가 주어지면(백필) 그 날짜보다 오래된 페이지에 도달하는 순간 중단 -
    2만 페이지를 무조건 도는 대신 필요한 깊이까지만 페이징한다."""
    app_ids: List[int] = []
    start = 0
    page_size = 50
    pages = 0

    print("발견: Steam 스토어 검색 (출시일 역순, 게임만)"
          + (f" — {stop_before} 이전 도달 시 중단" if stop_before else ""))
    while len(app_ids) < max_candidates:
        resp = request_with_backoff(STORE_SEARCH, {
            "query": "",
            "start": start,
            "count": page_size,
            "sort_by": "Released_DESC",
            "category1": STEAM_CATEGORY_GAMES,
            "infinite": 1,
            "json": 1,
            "l": "korean",
            "cc": "kr",
        }, label="store search")

        if resp is None:
            break

        try:
            payload = resp.json()
        except ValueError:
            print("   검색 응답이 JSON이 아님 → 폴백 필요")
            break

        if start == 0:
            print(f"   전체 게임 수: {payload.get('total_count', 0):,}")

        html = payload.get("results_html", "")
        found = APPID_IN_HTML.findall(html)
        if not found:
            break

        for aid in found:
            app_ids.append(int(aid))
            if len(app_ids) >= max_candidates:
                break

        # 백필 조기 종료: 이 페이지의 출시일들이 전부 시작일보다 오래됐으면 더 볼 필요 없음
        if stop_before:
            page_dates = [d for d in (_parse_search_date(s) for s in RELEASED_IN_HTML.findall(html)) if d]
            if page_dates and max(page_dates) < stop_before:
                print(f"   {stop_before} 이전 구간 도달 → 페이징 중단 (후보 {len(app_ids)}개)")
                break

        pages += 1
        if pages % 20 == 0:
            print(f"   ...{pages}페이지 / 후보 {len(app_ids):,}개 (간격 {_adaptive['search_delay']:.1f}s)")

        start += page_size
        time.sleep(_adaptive["search_delay"])

    # dedupe while preserving release-date order
    seen, ordered = set(), []
    for a in app_ids:
        if a not in seen:
            seen.add(a)
            ordered.append(a)

    print(f"   → 후보 {len(ordered)}개")
    return ordered


# ============== 1-b) 발견: 공식 API 폴백 ==============
def discover_via_applist(max_candidates: int) -> List[int]:
    """Official IStoreService/GetAppList; games only, newest app_ids first.
    공식 API 폴백. 출시일이 없어 app_id 내림차순(최근 등록순)으로 근사한다."""
    if not STEAM_API_KEY:
        print("STEAM_API_KEY 없음 → applist 폴백 불가")
        return []

    print("발견: IStoreService/GetAppList (공식 API 폴백)")
    collected: List[int] = []
    last_appid = None

    while True:
        params = {
            "key": STEAM_API_KEY,
            "include_games": "true",
            "include_dlc": "false",
            "include_software": "false",
            "include_videos": "false",
            "include_hardware": "false",
            "max_results": 50000,
        }
        if last_appid:
            params["last_appid"] = last_appid

        resp = request_with_backoff(STORE_APPLIST, params, label="GetAppList")
        if resp is None:
            break

        body = resp.json().get("response", {})
        apps = body.get("apps", [])
        if not apps:
            break

        collected.extend(a["appid"] for a in apps)
        if not body.get("have_more_results"):
            break
        last_appid = body.get("last_appid") or apps[-1]["appid"]
        time.sleep(1.0)

    collected.sort(reverse=True)     # newest registrations first
    print(f"   → 전체 {len(collected):,}개 중 상위 {max_candidates}개 사용")
    return collected[:max_candidates]


# ============== 2) 상세: Steam appdetails ==============
def fetch_steam_details(app_id: int) -> Optional[Dict]:
    """Fetch Korean details; None for non-games / unreleased / thin description.
    Steam 한글 상세를 가져온다. 비게임·미출시·설명부족이면 None."""
    resp = request_with_backoff(STEAM_APPDETAILS,
                                {"appids": app_id, "l": "korean"},
                                label=f"appdetails({app_id})")
    if resp is None:
        return None

    try:
        entry = resp.json().get(str(app_id), {})
    except ValueError:
        return None

    if not entry.get("success"):
        return None

    data = entry.get("data", {})

    # filter 1: real game only (no dlc / demo / music / video)
    if data.get("type") != "game":
        return None

    # filter 2: must already be released
    release = data.get("release_date", {}) or {}
    if release.get("coming_soon"):
        return None

    name = (data.get("name") or "").strip()

    # filter 3: non-game artifacts by name (dedicated server, soundtrack...)
    if not name or EXCLUDE_NAME_PATTERNS.search(name):
        return None

    genres = ", ".join(g.get("description", "") for g in data.get("genres", []))
    raw_desc = data.get("short_description") or data.get("detailed_description") or ""
    description = HTML_TAG.sub("", raw_desc).replace("\r", " ").replace("\n", " ")
    description = re.sub(r"\s+", " ", description).strip()

    # filter 4: generator drops description length <= 10
    if len(description) < MIN_DESCRIPTION_LEN:
        return None

    # Extra fields for the games table (all NOT NULL, no DB-level defaults).
    # games 테이블은 NOT NULL 24개에 DB 기본값이 없으므로 전부 채워야 한다.
    genre_tokens = {g.strip() for g in genres.split(",")}
    price_overview = data.get("price_overview") or {}
    price = None
    if price_overview.get("final") is not None:
        price = round(price_overview["final"] / 100.0, 2)

    return {
        "app_id": app_id,
        "name": name,
        "genres": genres or "Unknown",
        "description": description,
        "_released": parse_release_date(release.get("date", "")),
        # games-only fields (not written to the blind CSV)
        "_developer": ", ".join(data.get("developers", []) or [])[:255],
        "_publisher": ", ".join(data.get("publishers", []) or [])[:255],
        "_header_image": (data.get("header_image") or "")[:500],
        "_is_free": bool(data.get("is_free", False)),
        "_is_indie": "인디" in genre_tokens or "Indie" in genre_tokens,
        "_is_early_access": "앞서 해보기" in genre_tokens or "Early Access" in genre_tokens,
        "_price": price,
    }


# ============== 3) DB 중복 제거 ==============
def load_existing_app_ids() -> Set[int]:
    """Read app_ids already in games to avoid re-crawling.
    이미 games에 있는 app_id를 읽어 중복 수집을 막는다."""
    if not DB_URL:
        print("DATABASE_URL 없음 → 중복 체크 생략")
        return set()
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT app_id FROM games")).fetchall()
        existing = {r[0] for r in rows}
        print(f" DB 기존 게임: {len(existing):,}개 (중복 제외 기준)")
        return existing
    except Exception as e:
        # 조용히 빈 집합을 돌려주면 이미 분석된 게임(교사 4,190개 포함)을 재수집·재분석하고
        # batch_processor 가 그 metrics 를 학생 값으로 덮어쓴다. 되돌릴 백업이 없으므로 즉시 중단.
        print(f"DB 접속 실패 — 중복 체크 없이 진행하면 기존 데이터를 덮어쓸 수 있어 중단합니다: {e}")
        raise SystemExit(4)


def upsert_games(rows: List[Dict]) -> int:
    """Register crawled games as INACTIVE + UNANALYZED so they never surface
    in the live service before batch_processor fills game_metrics.
    크롤링한 신작을 비활성·미분석 상태로 등록한다. metrics 적재 전에는
    A의 검색/랭킹/추천에 절대 노출되지 않아야 하므로 is_active=False로 넣는다.

    주의 (실측): games 테이블은 NOT NULL 컬럼이 24개인데 DB 레벨 기본값이 없다.
    (Django ORM이 앱 레벨에서만 default를 채우기 때문) → raw SQL은 전부 명시해야 한다.
    특히 is_active 기본값은 ORM상 True이므로 반드시 FALSE를 명시한다.
    활성화는 batch_processor가 metrics 적재 성공 후에 수행한다.
    """
    if not DB_URL:
        print("DATABASE_URL 없음 → games 등록 생략")
        return 0

    from sqlalchemy import create_engine, text
    engine = create_engine(DB_URL)
    now = datetime.now()
    inserted = 0

    sql = text("""
        INSERT INTO games (
            app_id, name, genres, developer, publisher,
            description, short_description, header_image,
            release_date, price,
            steam_positive_ratio, review_count,
            is_free, is_indie, is_early_access,
            ai_curation_summary, marketing_hook, one_line_summary,
            target_personas, not_for_personas, similar_games, unique_selling_points,
            is_analyzed, analysis_method, is_active,
            created_at, updated_at
        ) VALUES (
            :app_id, :name, :genres, :developer, :publisher,
            :description, :short_description, :header_image,
            :release_date, :price,
            NULL, 0,
            :is_free, :is_indie, :is_early_access,
            '', '', '',
            '[]', '[]', '[]', '[]',
            FALSE, 'pending', FALSE,
            :now, :now
        )
        ON CONFLICT (app_id) DO NOTHING
    """)

    with engine.begin() as conn:
        for r in rows:
            result = conn.execute(sql, {
                "app_id": r["app_id"],
                "name": r["name"][:255],
                "genres": r["genres"][:500],
                "developer": r.get("_developer") or "Unknown",
                "publisher": r.get("_publisher") or "Unknown",
                "description": r["description"],
                "short_description": r["description"][:500],
                "header_image": r.get("_header_image") or "",
                "release_date": r.get("_released"),
                "price": r.get("_price"),
                "is_free": r.get("_is_free", False),
                "is_indie": r.get("_is_indie", False),
                "is_early_access": r.get("_is_early_access", False),
                "now": now,
            })
            inserted += result.rowcount or 0

    print(f" games 등록: {inserted}개 신규 "
          f"(is_active=FALSE, analysis_method='pending')")
    print("   metrics 적재 전까지 서비스에 노출되지 않음")
    return inserted


# ============== 4) CSV 출력 ==============
def write_blind_csv(rows: List[Dict], output_path: Path) -> None:
    """Write exactly the 4 blind columns (no answer columns).
    generator가 요구하는 블라인드 4컬럼만 기록한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["app_id", "name", "genres", "description"])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in ("app_id", "name", "genres", "description")})


# ============== main ==============
def main():
    parser = argparse.ArgumentParser(description="Hidden Gem 신작 크롤러 (Steam only)")
    parser.add_argument("--days", type=int, default=30, help="최근 N일 출시 (기본 30)")
    parser.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=50, help="최대 수집 게임 수")
    parser.add_argument("--source", choices=["search", "applist"], default="search",
                        help="발견 소스 (기본 search, 실패 시 applist 자동 폴백)")
    parser.add_argument("--output", default=str(DATA_DIR / "new_games.csv"))
    parser.add_argument("--no-db", action="store_true", help="DB 중복 체크 생략")
    parser.add_argument("--candidates", type=int, default=None,
                        help="발견 후보 수 오버라이드 (기본 limit*8). 백필 시 크게 - 중복은 상세 호출 없이 걸러지므로 비용 없음")
    parser.add_argument("--no-register", action="store_true",
                        help="games 테이블 등록 생략 (CSV만 생성)")
    args = parser.parse_args()

    # 킬 스위치: data/STOP_BACKFILL 파일이 있으면 수집하지 않고 정상 종료한다.
    # detached로 도는 weekly_pipeline --loop 를 컨테이너 접근 없이(파일만 만들어서) 멈추는 용도.
    # 크롤 0건 → 오케스트레이터가 "더 처리할 게임 없음"으로 루프를 끝내고 percentile까지 마무리한다.
    stop_flag = DATA_DIR / "STOP_BACKFILL"
    if stop_flag.exists():
        print(f"STOP_BACKFILL 파일 감지 ({stop_flag}) → 수집 생략, 루프 종료 유도. "
              f"재개하려면 파일을 지우고 파이프라인을 다시 실행.")
        return

    if args.date_from and args.date_to:
        start_date = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.date_to, "%Y-%m-%d").date()
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days)

    print("=" * 60)
    print(" Hidden Gem - 신작 크롤러 (Steam only, RAWG 미사용)")
    print("=" * 60)
    print(f"출시 기간: {start_date} ~ {end_date}")
    print(f"최대: {args.limit}개")
    print("=" * 60)

    existing = set() if args.no_db else load_existing_app_ids()

    # 발견: 필터 손실을 흡수하도록 여유있게 후보 수집
    max_candidates = args.candidates or args.limit * 8
    if args.source == "search":
        candidates = discover_via_store_search(max_candidates=max_candidates, stop_before=start_date)
        if not candidates:
            print("스토어 검색 실패 → 공식 API 폴백")
            candidates = discover_via_applist(max_candidates=max_candidates)
    else:
        candidates = discover_via_applist(max_candidates=max_candidates)

    if not candidates:
        print("발견된 후보가 없습니다.")
        return

    rows: List[Dict] = []
    stats = {"duplicate": 0, "filtered": 0, "out_of_range": 0}

    print(f"\nSteam 상세 수집 (요청 간 {STEAM_DELAY_SEC}s 지연)")
    for app_id in candidates:
        if len(rows) >= args.limit:
            break

        if app_id in existing:
            stats["duplicate"] += 1
            continue

        details = fetch_steam_details(app_id)
        time.sleep(STEAM_DELAY_SEC)

        if details is None:
            stats["filtered"] += 1
            continue

        # 날짜 필터: 파싱 실패 시엔 통과 (검색 정렬이 이미 출시일순)
        released = details.get("_released")
        if released and not (start_date <= released <= end_date):
            stats["out_of_range"] += 1
            # 검색은 출시일 내림차순 → 시작일보다 과거로 넘어가면 더 볼 필요 없음
            if args.source == "search" and released < start_date:
                print(f"   {released} < {start_date} → 기간 종료, 수집 중단")
                break
            continue

        rows.append(details)
        rd = released.isoformat() if released else "?"
        print(f"   [{len(rows):>3}] {details['name'][:32]:34} {rd:11} "
              f"{details['genres'][:20]:22} desc {len(details['description'])}자")

    print("\n" + "=" * 60)
    print(f"수집 결과: {len(rows)}개")
    print(f"   DB 중복 제외: {stats['duplicate']}")
    print(f"   비게임/미출시/설명부족 제외: {stats['filtered']}")
    print(f"   기간 밖 제외: {stats['out_of_range']}")

    if not rows:
        print("저장할 신작이 없습니다.")
        return

    output_path = Path(args.output)
    write_blind_csv(rows, output_path)
    print(f"\n저장: {output_path} ({len(rows)}행, 4컬럼)")

    # games 테이블 등록 (비활성 상태). batch_processor가 metrics 적재 후 활성화한다.
    if not args.no_db and not args.no_register:
        upsert_games(rows)

    print("=" * 60)
    print("\n다음 단계:")
    print(f"   python -m embeddings.batch_generator --csv {output_path} \\")
    print(f"       --test {len(rows)} --model gpt-5.4-mini \\")
    print("       --fewshot data/fewshot/fewshot_examples.jsonl --fewshot-n 6")


if __name__ == "__main__":
    main()