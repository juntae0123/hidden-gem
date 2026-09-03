# django_core/apps/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserAction


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username',
        'nickname',
        'steam_id',
        'total_searches',
        'total_clicks',
        'last_active_at',
        'is_active',
    ]
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'nickname', 'steam_id', 'email']

    fieldsets = UserAdmin.fieldsets + (
        ('Hidden Gem 정보', {
            'fields': (
                'nickname',
                'steam_id',
                'total_searches',
                'total_clicks',
                'total_ratings',
                'last_active_at',
                'taste_dna_json',
            )
        }),
    )

    readonly_fields = [
        'total_searches',
        'total_clicks',
        'total_ratings',
        'last_active_at',
        'taste_dna_json',
    ]


@admin.register(UserAction)
class UserActionAdmin(admin.ModelAdmin):
    """
    유저 행동 로그 관리자 (User Action Log Admin)
    Phase 2에서 데이터 분석 시 여기서 확인.
    """
    list_display = [
        'id',
        'user',
        'session_id',
        'action_type',
        'app_id',
        'created_at',
    ]
    list_filter = ['action_type', 'created_at']
    search_fields = ['session_id', 'user__username', 'app_id']
    readonly_fields = ['created_at', 'context']

    # 대량 데이터 대비 페이지네이션
    list_per_page = 50

    def has_add_permission(self, request):
        # 관리자에서 직접 추가 불가 (FastAPI 엔드포인트로만 생성)
        return False