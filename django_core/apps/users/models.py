# django_core/apps/users/models.py
"""
유저 모델 (User Model)

Django 기본 AbstractUser를 확장하여 Hidden Gem 서비스 전용 필드 추가.
settings.py의 AUTH_USER_MODEL = 'users.CustomUser' 로 등록하여
Django 인증 시스템 전체에서 이 모델을 사용.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    """
    커스텀 유저 모델 (Custom User Model extending AbstractUser)

    Django 기본 User에 Hidden Gem 서비스 전용 필드를 추가.
    - nickname: 서비스 내 표시 이름 (Steam 닉네임 또는 직접 설정)
    - steam_id: Steam 계정 연동 ID - null 허용, 연동 시 unique 보장

    Note:
        steam_id는 현재 직접 입력용이며, 추후 Steam OAuth 연동 시 자동 채워질 예정.
    """
    nickname = models.CharField(
        max_length=50, blank=True,
        verbose_name="닉네임",
        help_text="서비스 내 표시 이름"
    )
    steam_id = models.CharField(
        max_length=50, blank=True, null=True, unique=True,
        verbose_name="Steam ID",
        help_text="Steam 계정 연동 ID (17자리 숫자)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="가입일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")

    class Meta:
        db_table = 'users'
        verbose_name = '유저'
        verbose_name_plural = '유저 목록'

    def __str__(self):
        # 닉네임 미설정 시 username(기본 인증 ID)으로 대체 표시
        return self.nickname or self.username
