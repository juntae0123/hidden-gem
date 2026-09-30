"""운영 이용 현황 (2026-09-28). 개인정보(이메일·닉네임)는 찍지 않고 숫자만.
관리자(is_staff/is_superuser) 계정 = 본인 → 따로 센다.

    docker compose run --rm -T batch python -m embeddings.usage_stats
"""
import os
import sys

from sqlalchemy import create_engine, text

url = os.environ.get("PROD_DATABASE_URL")
if not url:
    sys.exit("PROD_DATABASE_URL 없음 (.env)")
c = create_engine(url, connect_args={"connect_timeout": 10}).connect()
q = lambda sql: c.execute(text(sql)).fetchall()

u = q("""SELECT count(*) FILTER (WHERE NOT (is_staff OR is_superuser)) AS normal,
                count(*) FILTER (WHERE is_staff OR is_superuser) AS admin,
                count(*) FILTER (WHERE NOT (is_staff OR is_superuser) AND last_login > NOW() - INTERVAL '7 days') AS active7
         FROM users""")[0]
print(f"[가입자] 일반 {u.normal}명 (최근 7일 로그인 {u.active7}) / 관리자(본인) {u.admin}")
print("  가입일별 (일반):")
for r in q("""SELECT date_joined::date AS d, count(*) n FROM users
              WHERE NOT (is_staff OR is_superuser) GROUP BY 1 ORDER BY 1"""):
    print(f"    {r.d}  {r.n}명")

print("\n[행동 로그 user_actions] 날짜별 — 전체 / 방문 세션 / 로그인 사용자 (관리자 계정 제외)")
for r in q("""SELECT a.created_at::date AS d, count(*) n,
                     count(DISTINCT a.session_id) s, count(DISTINCT a.user_id) uu
              FROM user_actions a LEFT JOIN users x ON x.id = a.user_id
              WHERE x.id IS NULL OR NOT (x.is_staff OR x.is_superuser)
              GROUP BY 1 ORDER BY 1"""):
    print(f"    {r.d}  {r.n:>4}건  세션 {r.s:>3}  로그인 {r.uu:>2}명")
own = q("""SELECT count(*) n FROM user_actions a JOIN users x ON x.id = a.user_id
           WHERE x.is_staff OR x.is_superuser""")[0].n
print(f"  (관리자 계정 행동 {own}건은 위에서 뺐다 — 비로그인 상태의 본인 방문은 구분 불가)")

print("\n[행동 종류] (관리자 제외)")
for r in q("""SELECT action_type, count(*) n FROM user_actions a LEFT JOIN users x ON x.id = a.user_id
              WHERE x.id IS NULL OR NOT (x.is_staff OR x.is_superuser)
              GROUP BY 1 ORDER BY 2 DESC"""):
    print(f"    {r.action_type:<20} {r.n}")

for t in ("favorites", "game_surveys", "metric_ratings"):
    try:
        print(f"[{t}] {q(f'SELECT count(*) n FROM {t}')[0].n}건")
    except Exception as e:
        c.rollback()
        print(f"[{t}] 조회 실패 {type(e).__name__}")
c.close()
