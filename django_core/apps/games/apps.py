# django_core/apps/games/apps.py
from django.apps import AppConfig


class GamesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.games'
    verbose_name = '게임 관리'
    
    def ready(self):
        # 시그널 등록
        import apps.games.signals  # noqa
