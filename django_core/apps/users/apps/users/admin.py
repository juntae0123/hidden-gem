# django_core/apps/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


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
