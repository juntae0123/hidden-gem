"""
pytest conftest.py — 공유 픽스처 + 설정

Korean: 테스트 전체에서 공유하는 픽스처와 pytest 설정.
위치: fastapi_app/tests/conftest.py
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

# fastapi_app 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.recommender import NUMERIC_METRIC_FIELDS


# ==================== 공통 픽스처 ====================

@pytest.fixture
def cozy_metric():
    """힐링 게임 GameMetric mock (Stardew Valley류)."""
    m = MagicMock()
    defaults = {f: 5.0 for f in NUMERIC_METRIC_FIELDS}
    defaults.update({
        "cozy_factor": 9.0, "horror_factor": 0.0, "gore_level": 0.0,
        "time_pressure": 1.0, "grind_factor": 3.0, "save_flexibility": 9.0,
        "freedom_level": 8.0, "exploration_reward": 9.0, "growth_reward": 8.0,
        "multiplayer_scale": 2.0, "competitive_stress": 0.0,
        "soundtrack_impact": 9.0, "difficulty_accessibility": 9.0,
        "gem_potential": 75.0, "gem_percentile": 78.0, "confidence_score": 0.9,
    })
    for f, v in defaults.items():
        setattr(m, f, v)
    m.embedding = None
    return m


@pytest.fixture
def null_metric():
    """모든 지표가 NULL인 GameMetric mock (크래시 테스트용)."""
    m = MagicMock()
    for f in NUMERIC_METRIC_FIELDS:
        setattr(m, f, None)
    m.gem_potential = None
    m.gem_percentile = None
    m.confidence_score = None
    m.embedding = None
    return m


@pytest.fixture
def mock_game(cozy_metric):
    """힐링 게임 Game mock."""
    g = MagicMock()
    g.id = 1
    g.app_id = 413150
    g.name = "Stardew Valley"
    g.genres = "RPG, Indie, Simulation"
    g.developer = "ConcernedApe"
    g.header_image = "https://cdn.example.com/stardew.jpg"
    g.one_line_summary = "농장 경영 힐링 RPG"
    g.marketing_hook = "도시를 떠나 자연 속에서"
    g.review_count = 500000
    g.steam_positive_ratio = 0.98
    g.metrics = cozy_metric
    return g