# django_core/apps/users/admin.py
"""
유저 관리자 설정 (User Admin Configuration)

Django 기본 UserAdmin을 확장하여 Hidden Gem 전용 필드(nickname, steam_id)를
관리자 페이지 수정 폼에 추가.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    커스텀 유저 관리자 (Custom User Admin)

    기본 UserAdmin의 목록/폼에 서비스 전용 필드를 추가.
    - list_display: 목록 페이지에 표시할 컬럼
    - fieldsets: 수정 폼의 섹션 구성 (기존 섹션 + '추가 정보' 섹션)
    """
    # 목록 페이지 표시 컬럼 - username, 닉네임, 이메일, 관리자 여부
    list_display = ['username', 'nickname', 'email', 'is_staff']

    # 기존 UserAdmin fieldsets(계정 정보/권한 등)에 Hidden Gem 전용 필드 섹션 추가
    fieldsets = UserAdmin.fieldsets + (
        ('추가 정보 (Hidden Gem)', {'fields': ('nickname', 'steam_id')}),
    )
