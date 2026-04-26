# django_core/apps/games/signals.py
"""
Hidden Gem - Django → FastAPI 동기화 시그널
게임 데이터 변경 시 Redis Pub/Sub으로 알림
"""

import json
import redis
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from .models import Game, GameMetric


# Redis 연결
def get_redis_client():
    """Redis 클라이언트 (lazy)"""
    host = getattr(settings, 'REDIS_HOST', 'localhost')
    port = getattr(settings, 'REDIS_PORT', 6379)
    return redis.Redis(host=host, port=port, db=0)


CHANNEL = "hidden_gem:game_updates"


@receiver(post_save, sender=Game)
def notify_game_update(sender, instance, created, **kwargs):
    """게임 생성/수정 시 FastAPI에 알림"""
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
        print(f"[Signal] Redis publish failed: {e}")


@receiver(post_save, sender=GameMetric)
def notify_metric_update(sender, instance, created, **kwargs):
    """지표 업데이트 시 FastAPI에 알림 (벡터 재계산 필요)"""
    try:
        r = get_redis_client()
        message = {
            "event": "metric_created" if created else "metric_updated",
            "app_id": instance.game.app_id,
            "requires_embedding_refresh": True,
        }
        r.publish(CHANNEL, json.dumps(message))
    except Exception as e:
        print(f"[Signal] Redis publish failed: {e}")


@receiver(post_delete, sender=Game)
def notify_game_delete(sender, instance, **kwargs):
    """게임 삭제 시 알림"""
    try:
        r = get_redis_client()
        message = {
            "event": "game_deleted",
            "app_id": instance.app_id,
        }
        r.publish(CHANNEL, json.dumps(message))
    except Exception as e:
        print(f"[Signal] Redis publish failed: {e}")
