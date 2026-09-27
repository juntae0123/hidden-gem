"""운영 DB 상태 한눈에 (R-27 후속, 2026-09-25).
refresh_reviews 가 '게이트: ...' 출력 뒤 멈춘 것처럼 보일 때: 진행 중인지 / 락에 막혔는지 / 연결이 안 되는지 가른다.

    docker compose run --rm -T batch python -m embeddings.diag_prod
    docker compose run --rm -T batch python -m embeddings.diag_prod --kill-idle-tx   # 5분 넘게 'idle in transaction' 인 세션 종료
"""
import os
import sys

from sqlalchemy import create_engine, text

url = os.environ.get("PROD_DATABASE_URL")
if not url:
    sys.exit("PROD_DATABASE_URL 없음 (.env)")
eng = create_engine(url, connect_args={"connect_timeout": 10})
try:
    conn = eng.connect()
except Exception as e:
    sys.exit(f"[연결 실패] {type(e).__name__}: {str(e).splitlines()[0]}  -> 비번/호스트(.env PROD_DATABASE_URL) 확인")
print("[연결 OK]")

r = conn.execute(text("""
    SELECT count(*) FILTER (WHERE refreshed_at > NOW() - INTERVAL '1 day') AS last_24h,
           max(refreshed_at) AS latest, count(DISTINCT date_trunc('day', refreshed_at)) AS days
    FROM review_history""")).one()
print(f"[진행] review_history 최근 24h {r.last_24h:,}건 · 최신 {r.latest} · 스냅샷 날짜 {r.days}개")

rows = conn.execute(text("""
    SELECT pid, state, wait_event_type, wait_event,
           to_char(NOW() - COALESCE(xact_start, query_start), 'HH24:MI:SS') AS age,
           left(regexp_replace(query, '\\s+', ' ', 'g'), 90) AS q,
           pg_blocking_pids(pid) AS blocked_by
    FROM pg_stat_activity
    WHERE datname = current_database() AND pid <> pg_backend_pid()
    ORDER BY xact_start NULLS LAST""")).fetchall()
print(f"[세션] {len(rows)}개")
for x in rows:
    flag = "  <-- 막힘" if x.blocked_by else ""
    print(f"  pid={x.pid} {x.state} wait={x.wait_event_type}/{x.wait_event} age={x.age} blocked_by={x.blocked_by}{flag}\n      {x.q}")

if "--kill-idle-tx" in sys.argv:
    k = conn.execute(text("""
        SELECT pid, pg_terminate_backend(pid) AS ok FROM pg_stat_activity
        WHERE datname = current_database() AND pid <> pg_backend_pid()
          AND state LIKE 'idle in transaction%' AND NOW() - state_change > INTERVAL '5 minutes'""")).fetchall()
    print(f"[정리] idle in transaction 세션 {len(k)}개 종료: {[p.pid for p in k]}")
conn.close()
