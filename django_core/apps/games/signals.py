# django_core/apps/games/signals.py
"""
Django → FastAPI 동기화 시그널 (Django-to-FastAPI Sync Signals)

Django Admin에서 게임 데이터가 변경될 때 Redis Pub/Sub 채널로 이벤트를 발행.
FastAPI 측에서 이 이벤트를 구독하여 캐시 무효화 또는 임베딩 재계산 처리.

채널: hidden_gem:game_updates
이벤트 타입: game_created, game_updated, game_deleted, metric_created, metric_updated

Note:
    Redis 연결 실패 시 예외를 삼켜서(silent fail) Django Admin 작업을 중단하지 않음.
    중요 데이터 손실 방지를 위해 시그널 실패는 로그만 출력.
"""

import json
import redis
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from .models import Game, GameMetric


def get_redis_client():
    """
    Redis 클라이언트 생성 (Lazy Redis Client Factory)

    매 시그널 호출마다 새 클라이언트를 생성하는 lazy 방식.
    settings.py의 REDIS_HOST/PORT를 참조하며, 없으면 로컬호스트 기본값 사용.
    """
    host = getattr(settings, 'REDIS_HOST', 'localhost')
    port = getattr(settings, 'REDIS_PORT', 6379)
    return redis.Redis(host=host, port=port, db=0)


# FastAPI가 구독하는 Redis 채널명
CHANNEL = "hidden_gem:game_updates"


@receiver(post_save, sender=Game)
def notify_game_update(sender, instance, created, **kwargs):
    """
    게임 저장 시 FastAPI에 Redis 이벤트 발행 (Game Save Signal)

    Django Admin에서 게임이 생성/수정될 때 자동 호출.
    FastAPI는 이 이벤트를 받아 관련 캐시를 무효화할 수 있음.

    Args:
        created (bool): True = 신규 생성, False = 기존 수정
    """
    try:
        r = get_redis_client()
        message = {
            "event": "game_created" if created else "game_updated",
            "app_id": instance.app_id,
            "name": instance.name,
            "is_analyzed": instance.is_analyzed,
        }
        r.publish(CHANNEL, json.dumps(message))
    except Exception as e:
        # Redis 실패해도 Django 작업은 계속 진행 (비필수 알림)
        print(f"[Signal] Redis publish failed: {e}")


@receiver(post_save, sender=GameMetric)
def notify_metric_update(sender, instance, created, **kwargs):
    """
    지표 저장 시 FastAPI에 임베딩 갱신 요청 이벤트 발행 (Metric Save Signal)

    지표가 변경되면 임베딩 벡터도 재계산이 필요하므로 requires_embedding_refresh=True 포함.
    FastAPI 추천 엔진이 이 이벤트를 받아 해당 게임 임베딩을 재처리할 수 있음.
    """
    try:
        r = get_redis_client()
        message = {
            "event": "metric_created" if created else "metric_updated",
            "app_id": instance.game.app_id,
            "requires_embedding_refresh": True,  # 임베딩 재계산 필요 플래그
        }
        r.publish(CHANNEL, json.dumps(message))
    except Exception as e:
        print(f"[Signal] Redis publish failed: {e}")


@receiver(post_delete, sender=Game)
def notify_game_delete(sender, instance, **kwargs):
    """
    게임 삭제 시 FastAPI에 알림 이벤트 발행 (Game Delete Signal)

    삭제된 게임이 추천 후보 풀에서 제거되도록 FastAPI에 알림.
    """
    try:
        r = get_redis_client()
        message = {
            "event": "game_deleted",
            "app_id": instance.app_id,
        }
        r.publish(CHANNEL, json.dumps(message))
    except Exception as e:
        print(f"[Signal] Redis publish failed: {e}")
