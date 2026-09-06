"""
운영 대시보드 — 관리자 로그인 한 번으로 "오늘 뭐가 쌓였나"를 한 화면에서 본다.

접속: /admin/dashboard/  (staff 로그인 필요, admin 상단 링크에서도 진입)

원칙:
  - 읽기 전용. 이 화면은 어떤 것도 쓰지 않는다.
  - 기간 경계는 파이썬에서 KST 기준 aware datetime 으로 만들어 넘긴다.
    DB 세션 타임존은 UTC 라 date 를 그대로 비교하면 09:00 KST 가 하루 경계가 된다.
  - Django 모델에 없는 컬럼(gem_evidence_*)·테이블(review_history)은 raw 로 읽고, 없으면 조용히 건너뛴다.
"""

from datetime import datetime, time, timedelta

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection
from django.shortcuts import render
from django.utils import timezone


def _rows(sql, params=None):
    with connection.cursor() as c:
        c.execute(sql, params or [])
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, r)) for r in c.fetchall()]


def _first(sql, params=None):
    r = _rows(sql, params)
    return r[0] if r else {}


@staff_member_required
def dashboard(request):
    today = timezone.localdate()
    d0 = timezone.make_aware(datetime.combine(today, time.min))   # 오늘 00:00 KST
    d7 = d0 - timedelta(days=7)
    d30 = d0 - timedelta(days=30)
    d14 = d0 - timedelta(days=13)

    # ---------- 방문 (user_actions 세션 기준) ----------
    traffic = _first("""
        SELECT COUNT(DISTINCT session_id) FILTER (WHERE created_at >= %s) AS today,
               COUNT(DISTINCT session_id) FILTER (WHERE created_at >= %s) AS d7,
               COUNT(DISTINCT session_id) FILTER (WHERE created_at >= %s) AS d30,
               COUNT(DISTINCT session_id)                                 AS total,
               COUNT(*) FILTER (WHERE created_at >= %s)                    AS acts_today,
               COUNT(*)                                                    AS acts_total
        FROM user_actions
    """, [d0, d7, d30, d0])

    daily = _rows("""
        SELECT (created_at AT TIME ZONE 'Asia/Seoul')::date AS day,
               COUNT(DISTINCT session_id) AS sessions,
               COUNT(*)                   AS acts,
               COUNT(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) AS logged_in
        FROM user_actions WHERE created_at >= %s
        GROUP BY 1 ORDER BY 1 DESC
    """, [d14])

    by_action = _rows("""
        SELECT action_type AS name,
               COUNT(*) FILTER (WHERE created_at >= %s) AS today,
               COUNT(*) FILTER (WHERE created_at >= %s) AS d7,
               COUNT(*)                                 AS total
        FROM user_actions GROUP BY 1 ORDER BY 4 DESC
    """, [d0, d7])

    top_queries = _rows("""
        SELECT context->>'query' AS q, COUNT(*) AS n
        FROM user_actions
        WHERE action_type = 'search' AND created_at >= %s
          AND COALESCE(context->>'query', '') <> ''
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """, [d7])

    top_games = _rows("""
        SELECT ua.app_id AS app_id, COALESCE(g.name, '(미등록)') AS name, COUNT(*) AS n
        FROM user_actions ua LEFT JOIN games g ON g.app_id = ua.app_id
        WHERE ua.action_type IN ('detail_view', 'rec_click', 'search_click')
          AND ua.created_at >= %s AND ua.app_id IS NOT NULL
        GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
    """, [d7])

    funnel = _first("""
        SELECT COUNT(*) FILTER (WHERE action_type = 'search')      AS search,
               COUNT(*) FILTER (WHERE action_type = 'detail_view') AS detail,
               COUNT(*) FILTER (WHERE action_type = 'steam_click') AS steam
        FROM user_actions WHERE created_at >= %s
    """, [d7])
    ctr = round(funnel.get("steam", 0) / funnel["detail"] * 100, 1) if funnel.get("detail") else 0

    # ---------- 회원 ----------
    users = _first("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE date_joined >= %s) AS today,
               COUNT(*) FILTER (WHERE date_joined >= %s) AS d7,
               COUNT(*) FILTER (WHERE date_joined >= %s) AS d30,
               COUNT(*) FILTER (WHERE onboarding_completed) AS onboarded,
               COUNT(*) FILTER (WHERE steam_id IS NOT NULL) AS steam,
               COUNT(*) FILTER (WHERE last_active_at >= %s) AS active7
        FROM users
    """, [d0, d7, d30, d7])

    recent_users = _rows("""
        SELECT id, COALESCE(NULLIF(nickname, ''), username) AS name, email,
               date_joined, last_active_at, total_searches, total_clicks,
               onboarding_completed, gender, age_group
        FROM users ORDER BY date_joined DESC LIMIT 15
    """)

    surveys = _first("""
        SELECT (SELECT COUNT(*) FROM game_surveys)   AS surveys,
               (SELECT COUNT(*) FROM metric_ratings) AS ratings,
               (SELECT COUNT(*) FROM favorites)      AS favorites
    """)

    # ---------- 데이터 ----------
    games = _first("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE is_analyzed) AS analyzed,
               COUNT(*) FILTER (WHERE analysis_method = 'pending') AS pending,
               COUNT(*) FILTER (WHERE is_active) AS active,
               COUNT(*) FILTER (WHERE created_at >= %s) AS today,
               COUNT(*) FILTER (WHERE release_date >= CURRENT_DATE - 180) AS new180,
               COUNT(*) FILTER (WHERE review_count >= 20000) AS famous,
               MAX(created_at) AS last_created
        FROM games
    """, [d0])

    by_method = _rows("""
        SELECT COALESCE(analysis_method, '-') AS name, COUNT(*) AS n
        FROM games GROUP BY 1 ORDER BY 2 DESC
    """)

    try:
        gem = _rows("""
            SELECT COALESCE(gem_evidence_reason, '(미산출)') AS name, COUNT(*) AS n
            FROM game_metrics GROUP BY 1 ORDER BY 2 DESC
        """)
        gem_updated = _first("SELECT MAX(gem_evidence_updated_at) AS at FROM game_metrics").get("at")
    except Exception:
        gem, gem_updated = [], None

    try:
        review_fresh = _first("SELECT MAX(refreshed_at) AS at, COUNT(*) AS n FROM review_history")
    except Exception:
        review_fresh = {"at": None, "n": 0}

    # each_context 를 넣어야 admin 상단바·사이드바·브레드크럼이 정상 렌더된다
    return render(request, "admin/ops_dashboard.html", {
        **admin.site.each_context(request),
        "title": "운영 대시보드",
        "now": timezone.localtime(),
        "traffic": traffic, "daily": daily, "by_action": by_action,
        "top_queries": top_queries, "top_games": top_games,
        "funnel": funnel, "ctr": ctr,
        "users": users, "recent_users": recent_users, "surveys": surveys,
        "games": games, "by_method": by_method,
        "gem": gem, "gem_updated": gem_updated, "review_fresh": review_fresh,
    })
