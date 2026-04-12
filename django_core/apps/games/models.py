# django_core/apps/games/models.py
"""
Hidden Gem - 게임 & 52개 지표 모델

데이터 출처:
- 4,190개 원본: GPT-5.4 Batch API로 추출 (고품질)
- 신규 게임: 4,190개 데이터 기반 Few-Shot으로 저비용 고품질 분석
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Game(models.Model):
    """Steam 게임 기본 정보"""
    
    app_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True, blank=True, default='')
    genres = models.CharField(max_length=500, blank=True, default='')
    developer = models.CharField(max_length=255, blank=True, default='')
    publisher = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(blank=True, default='')
    short_description = models.TextField(blank=True, default='')
    header_image = models.URLField(max_length=500, blank=True, default='')
    release_date = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # 분석 상태
    is_analyzed = models.BooleanField(default=False, help_text="분석 완료 여부")
    analysis_method = models.CharField(
        max_length=50, 
        default='pending',
        choices=[
            ('gpt5.4_batch', 'GPT-5.4 Batch (원본 4,190개)'),
            ('fewshot_5.4based', 'Few-Shot (5.4 데이터 기반)'),
            ('manual', '수동 입력'),
            ('pending', '대기 중'),
        ]
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'games'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app_id']),
            models.Index(fields=['is_analyzed', 'analysis_method']),
        ]

    def __str__(self):
        return f"[{self.app_id}] {self.name}"


class GameMetric(models.Model):
    """
    52개 지표 + AI 생성 콘텐츠
    
    - 원본 4,190개: GPT-5.4 Batch로 추출한 고품질 데이터
    - 신규 게임: 원본 4,190개를 Few-Shot 예시로 활용하여 저렴한 모델로 5.4급 품질 생성
    """
    
    game = models.OneToOneField(
        Game, 
        on_delete=models.CASCADE, 
        related_name='metrics', 
        primary_key=True
    )
    
    # ========== VIBE (7개) - 게임 분위기/톤 ==========
    cozy_factor = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="아늑함/편안함 (동물의 숲, 스타듀밸리)"
    )
    horror_factor = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="공포 강도"
    )
    gore_level = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="고어/잔인함 수준"
    )
    humor_rating = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="유머/코믹 요소"
    )
    dark_fantasy_vibe = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="다크 판타지 분위기"
    )
    epic_scale = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="서사적 규모감"
    )
    melancholy = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="우울함/멜랑콜리"
    )
    
    # ========== DEMANDS (5개) - 플레이어에게 요구하는 것 ==========
    reflex_demand = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="반사신경 요구도"
    )
    strategic_depth = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="전략적 깊이"
    )
    grind_factor = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="노가다/반복 요소"
    )
    time_pressure = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="시간 압박감"
    )
    learning_curve = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="학습 곡선 (높을수록 어려움)"
    )
    
    # ========== MECHANICS (11개) - 게임 메커니즘 ==========
    freedom_level = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="자유도"
    )
    action_pacing = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="액션 템포 (높을수록 빠름)"
    )
    rng_dependency = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="운/랜덤 의존도"
    )
    growth_reward = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="성장 보상감"
    )
    exploration_reward = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="탐험 보상감"
    )
    management_complexity = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="관리 복잡도"
    )
    stealth_importance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="스텔스 중요도"
    )
    session_length = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="세션 길이 (1=짧음, 10=매우 김)"
    )
    narrative_linearity = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="서사 선형성 (1=비선형, 10=완전 선형)"
    )
    puzzle_complexity = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="퍼즐 복잡도"
    )
    platforming_precision = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="플랫포밍 정밀도 요구"
    )
    
    # ========== SOCIAL (5개) - 소셜/멀티플레이 ==========
    coop_synergy = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="협동 시너지"
    )
    competitive_stress = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="경쟁 스트레스"
    )
    npc_interaction = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="NPC 상호작용 깊이"
    )
    user_creation = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="유저 창작 요소"
    )
    multiplayer_scale = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="멀티플레이어 규모"
    )
    
    # ========== PRESENTATION (5개) - 연출/프레젠테이션 ==========
    lore_richness = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="세계관/로어 깊이"
    )
    choice_consequence = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="선택의 결과 중요도"
    )
    visual_spectacle = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="시각적 화려함"
    )
    environmental_storytelling = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="환경 스토리텔링"
    )
    soundtrack_impact = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="사운드트랙 영향력"
    )
    
    # ========== TAGS (9개) - Boolean ==========
    is_turn_based = models.BooleanField(default=False, help_text="턴제 게임")
    is_real_time = models.BooleanField(default=False, help_text="실시간 게임")
    is_first_person = models.BooleanField(default=False, help_text="1인칭 시점")
    is_third_person = models.BooleanField(default=False, help_text="3인칭 시점")
    has_permadeath = models.BooleanField(default=False, help_text="영구 사망")
    has_base_building = models.BooleanField(default=False, help_text="기지 건설")
    has_crafting = models.BooleanField(default=False, help_text="제작 시스템")
    is_anime_style = models.BooleanField(default=False, help_text="애니메이션 스타일")
    is_retro_aesthetic = models.BooleanField(default=False, help_text="레트로 미학")
    
    # ========== CONTENT - AI 생성 텍스트 콘텐츠 ==========
    marketing_hook = models.TextField(blank=True, default='', help_text="마케팅 훅 (홍보 문구)")
    one_line_summary = models.TextField(blank=True, default='', help_text="한 줄 요약")
    target_personas = models.JSONField(default=list, blank=True, help_text="타겟 페르소나")
    not_for_personas = models.JSONField(default=list, blank=True, help_text="비추천 페르소나")
    similar_games = models.JSONField(default=list, blank=True, help_text="유사 게임")
    unique_selling_points = models.JSONField(default=list, blank=True, help_text="핵심 셀링 포인트")
    
    # ========== REASONING - AI 분석 근거 ==========
    analysis_summary = models.TextField(blank=True, default='', help_text="분석 요약")
    genre_classification = models.CharField(max_length=255, blank=True, default='', help_text="장르 분류")
    core_loop = models.TextField(blank=True, default='', help_text="핵심 게임 루프")
    metric_justifications = models.JSONField(default=dict, blank=True, help_text="지표별 판단 근거")
    confidence_score = models.FloatField(null=True, blank=True, help_text="분석 신뢰도 (0~1)")
    data_limitations = models.TextField(blank=True, default='', help_text="데이터 한계점")
    
    # ========== 원본 데이터 보관 ==========
    raw_content = models.JSONField(default=dict, blank=True, help_text="content 원본 JSON")
    raw_reasoning = models.JSONField(default=dict, blank=True, help_text="reasoning 원본 JSON")
    
    # ========== META ==========
    extraction_version = models.CharField(
        max_length=50, 
        default='gpt5.4-batch-v1',
        help_text="추출 버전 (gpt5.4-batch-v1, fewshot-v1 등)"
    )
    extracted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'game_metrics'
        verbose_name = '게임 지표'
        verbose_name_plural = '게임 지표들'

    def __str__(self):
        return f"Metrics: {self.game.name}"
