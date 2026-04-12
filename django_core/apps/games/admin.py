# django_core/apps/games/admin.py
"""
Hidden Gem - Django Admin 커스터마이징
4,190개 GPT-5.4 데이터 + 52개 지표 관리
"""

from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from .models import Game, GameMetric


class GameMetricInline(admin.StackedInline):
    model = GameMetric
    can_delete = False
    
    fieldsets = (
        ('🌈 VIBE (분위기)', {
            'fields': (
                ('cozy_factor', 'horror_factor', 'gore_level', 'humor_rating'),
                ('dark_fantasy_vibe', 'epic_scale', 'melancholy'),
            ),
            'classes': ('collapse',),
        }),
        ('💪 DEMANDS (요구도)', {
            'fields': (
                ('reflex_demand', 'strategic_depth', 'grind_factor'),
                ('time_pressure', 'learning_curve'),
            ),
            'classes': ('collapse',),
        }),
        ('⚙️ MECHANICS (메커니즘)', {
            'fields': (
                ('freedom_level', 'action_pacing', 'rng_dependency'),
                ('growth_reward', 'exploration_reward', 'management_complexity'),
                ('stealth_importance', 'session_length', 'narrative_linearity'),
                ('puzzle_complexity', 'platforming_precision'),
            ),
            'classes': ('collapse',),
        }),
        ('👥 SOCIAL (소셜)', {
            'fields': (
                ('coop_synergy', 'competitive_stress', 'npc_interaction'),
                ('user_creation', 'multiplayer_scale'),
            ),
            'classes': ('collapse',),
        }),
        ('🎬 PRESENTATION (연출)', {
            'fields': (
                ('lore_richness', 'choice_consequence', 'visual_spectacle'),
                ('environmental_storytelling', 'soundtrack_impact'),
            ),
            'classes': ('collapse',),
        }),
        ('🏷️ TAGS', {
            'fields': (
                ('is_turn_based', 'is_real_time', 'is_first_person', 'is_third_person'),
                ('has_permadeath', 'has_base_building', 'has_crafting'),
                ('is_anime_style', 'is_retro_aesthetic'),
            ),
        }),
        ('📝 AI 콘텐츠', {
            'fields': ('marketing_hook', 'one_line_summary', 'target_personas', 'similar_games'),
            'classes': ('collapse',),
        }),
        ('🔍 분석 정보', {
            'fields': ('confidence_score', 'extraction_version', 'analysis_summary'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Game)
class GameAdmin(ImportExportModelAdmin):
    list_display = [
        'app_id', 
        'name_display', 
        'genres_short', 
        'method_badge',
        'cozy_score', 
        'horror_score', 
        'reflex_score',
        'is_active'
    ]
    list_filter = [
        'is_analyzed', 
        'analysis_method', 
        'is_active',
        'metrics__is_turn_based',
        'metrics__is_real_time', 
        'metrics__has_permadeath',
        'metrics__has_crafting',
        'metrics__is_anime_style',
    ]
    search_fields = ['app_id', 'name', 'genres', 'developer']
    list_per_page = 50
    list_editable = ['is_active']
    inlines = [GameMetricInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('metrics')
    
    @admin.display(description='게임명')
    def name_display(self, obj):
        name = obj.name[:35] + '...' if len(obj.name) > 35 else obj.name
        return name
    
    @admin.display(description='장르')
    def genres_short(self, obj):
        return obj.genres[:25] + '...' if len(obj.genres) > 25 else obj.genres
    
    @admin.display(description='분석방법')
    def method_badge(self, obj):
        colors = {
            'gpt5.4_batch': '#28a745',      # 녹색 - 원본
            'fewshot_5.4based': '#17a2b8',  # 파랑 - Few-Shot
            'manual': '#6c757d',            # 회색
            'pending': '#dc3545',           # 빨강
        }
        color = colors.get(obj.analysis_method, '#6c757d')
        label = obj.get_analysis_method_display()[:12]
        return format_html(
            '<span style="background:{}; padding:2px 6px; border-radius:3px; color:white; font-size:11px;">{}</span>',
            color, label
        )
    
    @admin.display(description='🏠Cozy')
    def cozy_score(self, obj):
        return self._score_display(obj, 'cozy_factor')
    
    @admin.display(description='👻Horror')
    def horror_score(self, obj):
        return self._score_display(obj, 'horror_factor')
    
    @admin.display(description='⚡Reflex')
    def reflex_score(self, obj):
        return self._score_display(obj, 'reflex_demand')
    
    def _score_display(self, obj, field):
        try:
            value = getattr(obj.metrics, field, None)
            if value is not None:
                return f"{value:.0f}"
        except GameMetric.DoesNotExist:
            pass
        return '-'


@admin.register(GameMetric)
class GameMetricAdmin(admin.ModelAdmin):
    list_display = [
        'game', 
        'cozy_factor', 
        'horror_factor', 
        'reflex_demand',
        'strategic_depth',
        'confidence_score',
        'extraction_version',
    ]
    list_filter = [
        'is_turn_based',
        'is_real_time',
        'has_permadeath',
        'has_crafting',
        'is_anime_style',
        'extraction_version',
    ]
    search_fields = ['game__name', 'game__app_id']
    list_per_page = 100


# Admin 사이트 커스터마이징
admin.site.site_header = '🎮 Hidden Gem Admin'
admin.site.site_title = 'Hidden Gem'
admin.site.index_title = 'GPT-5.4 기반 스팀 인디게임 관리 시스템'
