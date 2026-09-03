# django_core/apps/games/models.py
"""
Hidden Gem - 게임 & 60개 지표 모델

데이터 출처:
- 4,190개 원본: GPT-5.4 Batch API로 추출 (고품질)
- 신규 게임: 4,190개 데이터 기반 Few-Shot으로 저비용 고품질 분석

지표 구성:
- 수치 지표 49개 (기존 31개 + 신규 18개)
- 태그 9개 (Boolean)
- 평가 2개 (gem_potential, confidence_score)
- 총 60개
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
    
    # ========== 스팀 데이터 (FastAPI와 동기화) ==========
    steam_positive_ratio = models.FloatField(
        null=True, blank=True,
        verbose_name="스팀 긍정 비율",
        help_text="0.0 ~ 1.0"
    )
    review_count = models.IntegerField(
        default=0,
        verbose_name="리뷰 수"
    )
    is_free = models.BooleanField(
        default=False,
        verbose_name="무료 게임"
    )
    is_indie = models.BooleanField(
        default=True,
        verbose_name="인디 게임"
    )
    is_early_access = models.BooleanField(
        default=False,
        verbose_name="얼리 액세스"
    )
    
    # ========== AI 생성 콘텐츠 ==========
    ai_curation_summary = models.TextField(
        blank=True, default='',
        verbose_name="AI 큐레이션 요약",
        help_text="게임의 핵심 매력 한 줄 평"
    )
    marketing_hook = models.TextField(
        blank=True, default='',
        verbose_name="마케팅 훅"
    )
    one_line_summary = models.TextField(
        blank=True, default='',
        verbose_name="한 줄 요약"
    )
    target_personas = models.JSONField(
        default=list, blank=True,
        verbose_name="타겟 페르소나"
    )
    not_for_personas = models.JSONField(
        default=list, blank=True,
        verbose_name="비추천 페르소나"
    )
    similar_games = models.JSONField(
        default=list, blank=True,
        verbose_name="유사 게임"
    )
    unique_selling_points = models.JSONField(
        default=list, blank=True,
        verbose_name="핵심 셀링 포인트"
    )
    
    # ========== 분석 상태 ==========
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
    analyzed_at = models.DateTimeField(null=True, blank=True)
    
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
    60개 지표: 49개 수치 + 9개 태그 + 2개 평가
    
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
    
    # ========== MECHANICS (9개) - 게임 메커니즘 (기존) ==========
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
    
    # ========== MECHANICS EXTRA (2개) - 게임 메커니즘 (기존 확장) ==========
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
    
    # ========== SYSTEM/UX (7개) - 신규 ==========
    build_variety = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="빌드 다양성"
    )
    progression_clarity = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="진행 명확성"
    )
    save_flexibility = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="저장 유연성"
    )
    difficulty_accessibility = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="난이도 접근성"
    )
    tutorial_quality = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="튜토리얼 품질"
    )
    ui_ux_polish = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="UI/UX 완성도"
    )
    modding_support = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="모딩 지원"
    )
    
    # ========== ART/AUDIO (3개) - 신규 ==========
    art_style_uniqueness = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="아트 스타일 독창성"
    )
    audio_design = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="오디오 디자인"
    )
    animation_quality = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="애니메이션 품질"
    )
    
    # ========== OTHER (2개) - 신규 ==========
    world_reactivity = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="월드 반응성"
    )
    community_dependency = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="커뮤니티 의존도"
    )
    
    # ========== NEW (4개) - 신규 ==========
    narrative_depth = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="서사 깊이"
    )
    replay_value = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="리플레이 가치"
    )
    endgame_content = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="엔드게임 콘텐츠"
    )
    monetization_fairness = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="과금 공정성"
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
    
    # ========== AI 평가 (2개) ==========
    gem_potential = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="AI 평가 잠재력 (0~10)"
    )
    confidence_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="분석 신뢰도 (0~1)"
    )
    
    # ========== REASONING - AI 분석 근거 ==========
    analysis_summary = models.TextField(blank=True, default='', help_text="분석 요약")
    genre_classification = models.CharField(max_length=255, blank=True, default='', help_text="장르 분류")
    core_loop = models.TextField(blank=True, default='', help_text="핵심 게임 루프")
    metric_justifications = models.JSONField(default=dict, blank=True, help_text="지표별 판단 근거")
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
