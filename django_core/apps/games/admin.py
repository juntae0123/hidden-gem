# django_core/apps/games/admin.py
"""
Hidden Gem - Django Admin 커스터마이징 (Admin Customization)

게임(Game)과 지표(GameMetric) 모델의 관리자 페이지 설정.
- GameAdmin: 게임 목록/검색/필터 + 지표 인라인 편집
- GameMetricAdmin: 지표 단독 조회/필터
- django-import-export 연동으로 JSONL/CSV 가져오기/내보내기 지원

Usage:
    /admin/games/game/       → 게임 목록 및 관리
    /admin/games/gamemetric/ → 지표 단독 관리
"""

from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from .models import Game, GameMetric


class GameMetricInline(admin.StackedInline):
    """
    게임 상세 페이지 내 지표 인라인 편집 위젯 (Metric Inline Editor)

    Game 수정 폼 하단에 60개 지표를 섹션별 접기/펼치기(collapse)로 표시.
    can_delete=False: 인라인에서 지표 삭제 불가 (실수 방지)
    """
    model = GameMetric
    can_delete = False
    
    fieldsets = (
        ('VIBE (분위기)', {
            'fields': (
                ('cozy_factor', 'horror_factor', 'gore_level', 'humor_rating'),
                ('dark_fantasy_vibe', 'epic_scale', 'melancholy'),
            ),
            'classes': ('collapse',),
        }),
        ('DEMANDS (요구도)', {
            'fields': (
                ('reflex_demand', 'strategic_depth', 'grind_factor'),
                ('time_pressure', 'learning_curve'),
            ),
            'classes': ('collapse',),
        }),
        ('MECHANICS (메커니즘)', {
            'fields': (
                ('freedom_level', 'action_pacing', 'rng_dependency'),
                ('growth_reward', 'exploration_reward', 'management_complexity'),
                ('stealth_importance', 'session_length', 'narrative_linearity'),
                ('puzzle_complexity', 'platforming_precision'),
            ),
            'classes': ('collapse',),
        }),
        ('SOCIAL (소셜)', {
            'fields': (
                ('coop_synergy', 'competitive_stress', 'npc_interaction'),
                ('user_creation', 'multiplayer_scale'),
            ),
            'classes': ('collapse',),
        }),
        ('PRESENTATION (연출)', {
            'fields': (
                ('lore_richness', 'choice_consequence', 'visual_spectacle'),
                ('environmental_storytelling', 'soundtrack_impact'),
            ),
            'classes': ('collapse',),
        }),
        ('TAGS', {
            'fields': (
                ('is_turn_based', 'is_real_time', 'is_first_person', 'is_third_person'),
                ('has_permadeath', 'has_base_building', 'has_crafting'),
                ('is_anime_style', 'is_retro_aesthetic'),
            ),
        }),
        ('AI 콘텐츠', {
            'fields': ('marketing_hook', 'one_line_summary', 'target_personas', 'similar_games'),
            'classes': ('collapse',),
        }),
        ('분석 정보', {
            'fields': ('confidence_score', 'extraction_version', 'analysis_summary'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Game)
class GameAdmin(ImportExportModelAdmin):
    """
    게임 관리자 클래스 (Game Admin)

    ImportExportModelAdmin 상속으로 CSV/JSONL 가져오기/내보내기 지원.
    select_related('metrics')로 목록 조회 시 N+1 쿼리 방지.

    주요 기능:
        - list_editable: 목록에서 is_active 직접 토글
        - method_badge: 분석 방법을 색상 뱃지로 시각화
        - cozy/horror/reflex 점수 컬럼으로 핵심 지표 한눈에 확인
    """
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
    list_editable = ['is_active']   # 목록에서 바로 활성화/비활성화 토글 가능
    inlines = [GameMetricInline]

    def get_queryset(self, request):
        """목록 조회 시 metrics를 함께 로드 - N+1 쿼리 방지 (select_related)"""
        return super().get_queryset(request).select_related('metrics')

    @admin.display(description='게임명')
    def name_display(self, obj):
        """35자 초과 게임명 말줄임 표시"""
        name = obj.name[:35] + '...' if len(obj.name) > 35 else obj.name
        return name

    @admin.display(description='장르')
    def genres_short(self, obj):
        """25자 초과 장르 말줄임 표시"""
        return obj.genres[:25] + '...' if len(obj.genres) > 25 else obj.genres

    @admin.display(description='분석방법')
    def method_badge(self, obj):
        """
        분석 방법을 색상 뱃지 HTML로 렌더링 (Analysis Method Badge)

        색상 의미:
            녹색  = gpt5.4_batch (원본 4,190개 고품질 데이터)
            파랑  = fewshot_5.4based (Few-Shot 저비용 분석)
            회색  = manual (수동 입력)
            빨강  = pending (미분석 대기 중)
        """
        colors = {
            'gpt5.4_batch': '#28a745',      # 녹색 - 원본 배치 분석
            'fewshot_5.4based': '#17a2b8',  # 파랑 - Few-Shot 분석
            'manual': '#6c757d',            # 회색 - 수동 입력
            'pending': '#dc3545',           # 빨강 - 미분석
        }
        color = colors.get(obj.analysis_method, '#6c757d')
        label = obj.get_analysis_method_display()[:12]
        return format_html(
            '<span style="background:{}; padding:2px 6px; border-radius:3px; color:white; font-size:11px;">{}</span>',
            color, label
        )

    @admin.display(description='Cozy')
    def cozy_score(self, obj):
        """아늑함 지표 점수 표시"""
        return self._score_display(obj, 'cozy_factor')

    @admin.display(description='Horror')
    def horror_score(self, obj):
        """공포 지표 점수 표시"""
        return self._score_display(obj, 'horror_factor')

    @admin.display(description='Reflex')
    def reflex_score(self, obj):
        """반사신경 요구도 점수 표시"""
        return self._score_display(obj, 'reflex_demand')

    def _score_display(self, obj, field):
        """
        지표 점수 안전 조회 헬퍼 (Safe Score Display Helper)

        metrics 관계가 없거나 해당 필드가 null이면 '-' 반환.
        GameMetric.DoesNotExist는 metrics가 없는 게임 처리용.
        """
        try:
            value = getattr(obj.metrics, field, None)
            if value is not None:
                return f"{value:.0f}"
        except GameMetric.DoesNotExist:
            pass
        return '-'


@admin.register(GameMetric)
class GameMetricAdmin(admin.ModelAdmin):
    """
    게임 지표 단독 관리자 (GameMetric Admin)

    60개 지표를 직접 조회/수정할 때 사용.
    태그(Boolean)와 추출 버전으로 필터링하여 데이터 품질 검수에 활용.
    """
    list_display = [
        'game',
        'cozy_factor',
        'horror_factor',
        'reflex_demand',
        'strategic_depth',
        'confidence_score',
        'extraction_version',  # 데이터 출처 추적용 (gpt5.4-batch-v1, fewshot-v1 등)
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
admin.site.site_header = 'Hidden Gem Admin'
admin.site.site_title = 'Hidden Gem'
admin.site.index_title = 'GPT-5.4 기반 스팀 인디게임 관리 시스템'
