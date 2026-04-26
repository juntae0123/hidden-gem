# django_core/apps/users/models.py
"""
Hidden Gem - Django 유저 모델
FastAPI와 공유하는 테이블
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """커스텀 유저 모델"""
    
    # Steam 연동
    steam_id = models.CharField(
        max_length=50, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name="Steam ID"
    )
    
    # 닉네임 (Steam에서 가져오거나 직접 설정)
    nickname = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        verbose_name="닉네임"
    )
    
    # 취향 DNA (FastAPI에서 관리, Django에서는 조회만)
    # JSONField로 저장 (PostgreSQL JSONB)
    taste_dna_json = models.JSONField(
        null=True, 
        blank=True,
        verbose_name="취향 DNA (JSON)"
    )
    
    # 통계
    total_searches = models.IntegerField(default=0, verbose_name="총 검색 수")
    total_clicks = models.IntegerField(default=0, verbose_name="총 클릭 수")
    total_ratings = models.IntegerField(default=0, verbose_name="총 평가 수")
    
    # 활동
    last_active_at = models.DateTimeField(null=True, blank=True, verbose_name="마지막 활동")
    
    class Meta:
        db_table = 'users'
        verbose_name = '유저'
        verbose_name_plural = '유저들'
    
    def __str__(self):
        return self.nickname or self.username or f"User {self.id}"
