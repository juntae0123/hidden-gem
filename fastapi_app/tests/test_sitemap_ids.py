"""
GET /games/sitemap-ids — 사이트맵용 노출 게임 목록 (SEO 2026-10-14).

검사하는 것 (CLAUDE.md 2''' — 설정이 아니라 '적용'을 본다):
  1. 라우트가 `/{app_id}` 보다 먼저 등록됐다 (뒤에 있으면 'sitemap-ids' 가 app_id 로 잡혀 422).
  2. 레이트 리밋 의존성이 실제로 붙어 있다.
  3. 쿼리가 노출 게이트(is_active AND is_analyzed)를 total·목록 **둘 다**에 건다.
  4. 입력 상한(limit ≤ 10000, offset ≥ 0)이 422 로 막힌다.
  5. 캐시 적중이면 DB 를 부르지 않는다.

DB 는 쓰지 않는다 — 실행된 SQL 을 받아 적는 가짜 세션으로 문장을 검사한다.
`main` 은 import 하지 않는다 (호스트 venv 에 sentry_sdk 가 없다 — tests/test_core.py 주석).
starlette TestClient 는 쓰지 않는다 — 고정 버전(fastapi 0.109 + httpx 0.28)에서 `Client(app=...)` 가
없어 TypeError 로 죽는다. httpx.ASGITransport 로 직접 부른다.
"""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.dialects import postgresql


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    """execute() 로 들어온 문장을 기록하고, count → total / 그 다음 → app_id 목록을 돌려준다."""

    def __init__(self, total, ids):
        self.total, self.ids = total, ids
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(str(stmt.compile(dialect=postgresql.dialect(),
                                                compile_kwargs={"literal_binds": True})))
        if len(self.statements) == 1:
            return _Result(scalar=self.total)
        return _Result(rows=self.ids)


@pytest.fixture
def cache_off(monkeypatch):
    """Redis 없이 — get 은 항상 miss, set 은 기록만."""
    from services.cache import recommendation_cache
    stored = {}

    async def _get(key):
        return None

    async def _set(key, value, ttl):
        stored[key] = (value, ttl)
        return True

    monkeypatch.setattr(recommendation_cache, "get", _get)
    monkeypatch.setattr(recommendation_cache, "set", _set)
    return stored


def _client(session):
    from routers.games import router, _LIMIT_DEFAULT
    from database import get_db

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _db():
        yield session

    async def _no_limit():
        return None

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[_LIMIT_DEFAULT] = _no_limit
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _get(session, params=None):
    async with _client(session) as c:
        return await c.get("/api/v1/games/sitemap-ids", params=params)


class TestSitemapIdsRoute:
    def test_registered_before_app_id_route(self):
        from routers.games import router
        paths = [r.path for r in router.routes]
        assert "/games/sitemap-ids" in paths
        assert paths.index("/games/sitemap-ids") < paths.index("/games/{app_id}"), (
            "sitemap-ids 가 /{app_id} 뒤에 있으면 'sitemap-ids' 가 app_id 로 잡혀 422 가 난다"
        )

    def test_rate_limit_attached(self):
        from routers.games import router
        route = next(r for r in router.routes if r.path == "/games/sitemap-ids")
        deps = " ".join(f"{getattr(d.call, '__module__', '')}.{getattr(d.call, '__qualname__', '')}"
                        for d in route.dependant.dependencies)
        assert "ratelimit" in deps, f"레이트 리밋이 붙지 않았다: {deps}"


class TestSitemapIdsQuery:
    async def test_exposure_gate_on_total_and_list(self, cache_off):
        session = _FakeSession(total=3, ids=[10, 20, 30])
        res = await _get(session, {"offset": 0, "limit": 2})
        assert res.status_code == 200, res.text
        assert res.json() == {"total": 3, "offset": 0, "limit": 2, "app_ids": [10, 20, 30]}

        count_sql, list_sql = session.statements
        for sql in (count_sql, list_sql):
            assert "games.is_active = true" in sql, sql
            assert "games.is_analyzed = true" in sql, sql
        assert "count(games.id)" in count_sql
        assert "ORDER BY games.app_id" in list_sql
        assert "LIMIT 2" in list_sql and "OFFSET 0" in list_sql

    async def test_response_is_cached_with_ttl(self, cache_off):
        session = _FakeSession(total=1, ids=[7])
        await _get(session, {"offset": 5, "limit": 1})
        assert "sitemap:ids:5:1" in cache_off
        value, ttl = cache_off["sitemap:ids:5:1"]
        assert value["app_ids"] == [7] and ttl > 0

    async def test_cache_hit_skips_db(self, monkeypatch):
        from services.cache import recommendation_cache
        cached = {"total": 2, "offset": 0, "limit": 10000, "app_ids": [1, 2]}

        async def _cached(key):
            return cached if key == "sitemap:ids:0:10000" else None

        monkeypatch.setattr(recommendation_cache, "get", _cached)
        session = _FakeSession(total=999, ids=[])
        res = await _get(session)
        assert res.status_code == 200
        assert res.json() == cached
        assert session.statements == [], "캐시 적중인데 DB 를 불렀다"

    async def test_empty_db(self, cache_off):
        session = _FakeSession(total=None, ids=[])   # count 가 NULL 이어도 0 으로
        res = await _get(session)
        assert res.status_code == 200
        assert res.json()["total"] == 0 and res.json()["app_ids"] == []

    @pytest.mark.parametrize("params", [
        {"limit": 10001},     # 상한 초과
        {"limit": 0},
        {"offset": -1},
        {"offset": "abc"},
    ])
    async def test_input_bounds(self, cache_off, params):
        res = await _get(_FakeSession(total=0, ids=[]), params)
        assert res.status_code == 422, (params, res.status_code)

    def test_app_id_route_still_works_for_numbers(self):
        """순서를 바꾼 뒤에도 /games/<숫자> 는 상세 라우트로 간다 (sitemap-ids 가 가로채지 않는다)."""
        from routers.games import router
        detail = next(r for r in router.routes if r.path == "/games/{app_id}")
        match, _ = detail.matches({"type": "http", "path": "/games/1145360", "method": "GET"})
        assert match.name == "FULL"
