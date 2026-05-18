# django_core/apps/games/management/commands/load_games.py
"""
4,190개 GPT-5.4 Batch 데이터 적재 스크립트 (60개 지표 버전)

사용법:
    python manage.py load_games --input ../data/final/final_master_games.jsonl
    python manage.py load_games --input ../data/final/final_master_games.jsonl --dry-run
    python manage.py load_games --input ../data/final/final_master_games.jsonl --update
"""

import json
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.games.models import Game, GameMetric


class Command(BaseCommand):
    help = 'GPT-5.4로 추출한 4,190개 게임 데이터를 DB에 적재 (60개 지표)'

    def add_arguments(self, parser):
        parser.add_argument('--input', '-i', type=str, required=True, help='JSONL 파일 경로')
        parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 검증만')
        parser.add_argument('--update', action='store_true', help='기존 데이터 업데이트')
        parser.add_argument('--batch-size', type=int, default=100, help='배치 크기')
        parser.add_argument('--limit', type=int, default=0, help='처리할 최대 개수 (0=전체)')

    def handle(self, *args, **options):
        """
        커맨드 메인 실행 (Command Entry Point)

        JSONL 파일을 읽어 Game + GameMetric 레코드를 DB에 적재.
        중복 app_id는 --update 옵션 없으면 스킵, --dry-run이면 검증만 수행.
        bulk_create로 배치 단위 처리하여 개별 INSERT 대비 성능 대폭 향상.
        """
        input_path = Path(options['input'])

        if not input_path.exists():
            raise CommandError(f'파일 없음: {input_path}')

        self.stdout.write(f'파일: {input_path}')
        self.stdout.write(f'파일 크기: {input_path.stat().st_size / 1024 / 1024:.1f} MB')

        # 기존 app_id 세트를 메모리에 로드 - DB 조회 없이 중복 체크
        existing_ids = set(Game.objects.values_list('app_id', flat=True))
        self.stdout.write(f'기존 DB: {len(existing_ids)}개')

        games_data = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if options['limit'] and i >= options['limit']:
                    break
                if line.strip():
                    games_data.append(json.loads(line))

        self.stdout.write(f'파일 내 게임: {len(games_data)}개')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - 저장하지 않음'))
            self._validate_data(games_data)
            return

        start_time = time.time()
        created, updated, skipped, errors = 0, 0, 0, 0

        batch_games = []
        batch_metrics_data = []

        for data in games_data:
            app_id = data.get('app_id')

            if not app_id:
                errors += 1
                continue

            if app_id in existing_ids:
                if options['update']:
                    try:
                        self._update_game(app_id, data)
                        updated += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'업데이트 실패 [{app_id}]: {e}'))
                        errors += 1
                else:
                    skipped += 1  # --update 없으면 기존 게임 스킵
                continue

            game = self._create_game(data)
            batch_games.append(game)
            batch_metrics_data.append(data)
            existing_ids.add(app_id)  # 메모리 세트에 즉시 추가 (같은 파일 내 중복 방지)

            # batch_size 도달 시 배치 저장 후 초기화
            if len(batch_games) >= options['batch_size']:
                saved = self._save_batch(batch_games, batch_metrics_data)
                created += saved
                batch_games, batch_metrics_data = [], []
                self.stdout.write(f'  {created}개 저장됨...')

        # 마지막 남은 배치 처리
        if batch_games:
            saved = self._save_batch(batch_games, batch_metrics_data)
            created += saved
        
        elapsed = time.time() - start_time
        
        self.stdout.write(self.style.SUCCESS(f'''
============================================================
GPT-5.4 데이터 적재 완료!

   결과:
   - 생성: {created}개
   - 업데이트: {updated}개  
   - 스킵 (이미 존재): {skipped}개
   - 에러: {errors}개
   
   소요시간: {elapsed:.1f}초
   처리속도: {len(games_data)/elapsed:.1f} games/sec
============================================================
        '''))

    def _create_game(self, data):
        """
        JSONL 데이터로 Game 모델 인스턴스 생성 (Game Instance Factory)

        bulk_create 전 메모리 객체를 만드는 단계. DB 저장은 _save_batch에서 일괄 처리.
        marketing_hook은 dict/str 두 형태로 올 수 있어 타입 분기 처리.
        """
        c = data.get('content', {})

        # marketing_hook이 dict 형태로 온 경우 (GPT-5.4 배치 일부 레코드) 문자열로 정규화
        hook = c.get('marketing_hook', '')
        if isinstance(hook, dict):
            hook = hook.get('primary', '') or hook.get('emotional', '') or json.dumps(hook, ensure_ascii=False)
        
        return Game(
            app_id=data.get('app_id'),
            name=data.get('name', ''),
            genres=data.get('genres', ''),
            developer=data.get('developer', ''),
            publisher=data.get('publisher', ''),
            description=data.get('description', ''),
            short_description=data.get('short_description', ''),
            header_image=data.get('header_image', ''),
            release_date=self._parse_date(data.get('release_date')),
            price=data.get('price'),
            steam_positive_ratio=data.get('steam_positive_ratio'),
            review_count=data.get('review_count', 0),
            is_free=data.get('is_free', False),
            is_indie=data.get('is_indie', True),
            is_early_access=data.get('is_early_access', False),
            ai_curation_summary=c.get('one_line_summary', ''),
            marketing_hook=hook,
            one_line_summary=c.get('one_line_summary', ''),
            target_personas=c.get('target_personas', []),
            not_for_personas=c.get('not_for_personas', []),
            similar_games=c.get('similar_games', []),
            unique_selling_points=c.get('unique_selling_points', []),
            is_analyzed=True,
            analysis_method='gpt5.4_batch',
            is_active=True,
        )

    def _parse_date(self, date_val):
        """
        다양한 날짜 문자열 형식을 파싱 (Multi-format Date Parser)

        Steam API는 날짜를 여러 형식으로 반환하므로 순서대로 시도.
        파싱 실패 시 None 반환하여 DB에 null로 저장.

        지원 형식: '%Y-%m-%d', '%b %d, %Y', '%d %b, %Y'
        """
        if not date_val:
            return None
        if isinstance(date_val, str):
            try:
                from datetime import datetime
                for fmt in ['%Y-%m-%d', '%b %d, %Y', '%d %b, %Y']:
                    try:
                        return datetime.strptime(date_val, fmt).date()
                    except ValueError:
                        continue
            except Exception:
                pass
        return None

    def _save_batch(self, games, metrics_data):
        """
        Game + GameMetric 배치 저장 (Atomic Batch Save)

        단일 트랜잭션으로 Game과 GameMetric을 함께 저장.
        bulk_create로 N개 INSERT를 단일 쿼리로 처리 (성능 최적화).
        트랜잭션 실패 시 해당 배치 전체 롤백.

        Returns:
            실제 저장된 게임 수
        """
        with transaction.atomic():
            created_games = Game.objects.bulk_create(games)

            # bulk_create 후 DB가 할당한 PK를 사용해 GameMetric 생성
            metrics = []
            for game, data in zip(created_games, metrics_data):
                metric = self._create_metric(game, data)
                metrics.append(metric)

            GameMetric.objects.bulk_create(metrics)

        return len(created_games)

    def _get_metric(self, sources, key, default=None):
        """
        여러 소스에서 지표 값을 찾는 Fallback 로직 (Multi-source Metric Lookup)

        GPT-5.4 배치 데이터는 신규 지표 위치가 불일치할 수 있어
        여러 소스를 우선순위 순으로 탐색.

        Args:
            sources: 딕셔너리 리스트 (우선순위 높은 것부터 - 예: [extended, metrics, data])
            key: 찾을 지표명
            default: 모든 소스에서 찾지 못하면 반환할 기본값 (None)

        Returns:
            첫 번째로 발견한 non-None 값 또는 default
        """
        for source in sources:
            if source and key in source and source[key] is not None:
                return source[key]
        return default

    def _create_metric(self, game, data):
        """
        JSONL 데이터로 GameMetric 인스턴스 생성 (Metric Instance Factory)

        49개 수치 지표 + 9개 Boolean 태그 + 2개 AI 평가 값을 JSONL에서 추출.
        신규 18개 지표는 Fallback 로직(_get_metric)으로 여러 위치에서 탐색.

        데이터 구조:
            data.metrics.vibe      → cozy_factor, horror_factor, ...
            data.metrics.demands   → reflex_demand, strategic_depth, ...
            data.metrics.extended  → 신규 18개 지표 (build_variety, narrative_depth, ...)
            data.tags              → is_turn_based, has_crafting, ...
            data.reasoning         → analysis_summary, gem_potential, confidence_score
        """
        m = data.get('metrics', {})
        t = data.get('tags', {})
        r = data.get('reasoning', {})
        c = data.get('content', {})

        # 기존 5개 카테고리 딕셔너리 추출
        vibe = m.get('vibe', {})
        demands = m.get('demands', {})
        mechanics = m.get('mechanics', {})
        social = m.get('social', {})
        presentation = m.get('presentation', {})

        # 신규 지표 소스 (우선순위: extended > metrics 루트 > data 루트)
        extended = m.get('extended', {})
        new_sources = [extended, m, data]  # Fallback 순서
        
        return GameMetric(
            game=game,
            
            # ===== VIBE (7개) =====
            cozy_factor=vibe.get('cozy_factor'),
            horror_factor=vibe.get('horror_factor'),
            gore_level=vibe.get('gore_level'),
            humor_rating=vibe.get('humor_rating'),
            dark_fantasy_vibe=vibe.get('dark_fantasy_vibe'),
            epic_scale=vibe.get('epic_scale'),
            melancholy=vibe.get('melancholy'),
            
            # ===== DEMANDS (5개) =====
            reflex_demand=demands.get('reflex_demand'),
            strategic_depth=demands.get('strategic_depth'),
            grind_factor=demands.get('grind_factor'),
            time_pressure=demands.get('time_pressure'),
            learning_curve=demands.get('learning_curve'),
            
            # ===== MECHANICS 기존 (9개) =====
            freedom_level=mechanics.get('freedom_level'),
            action_pacing=mechanics.get('action_pacing'),
            rng_dependency=mechanics.get('rng_dependency'),
            growth_reward=mechanics.get('growth_reward'),
            exploration_reward=mechanics.get('exploration_reward'),
            management_complexity=mechanics.get('management_complexity'),
            stealth_importance=mechanics.get('stealth_importance'),
            session_length=mechanics.get('session_length'),
            narrative_linearity=mechanics.get('narrative_linearity'),
            
            # ===== MECHANICS EXTRA (2개) - Fallback 적용 =====
            puzzle_complexity=self._get_metric(new_sources, 'puzzle_complexity'),
            platforming_precision=self._get_metric(new_sources, 'platforming_precision'),
            
            # ===== SOCIAL (5개) =====
            coop_synergy=social.get('coop_synergy'),
            competitive_stress=social.get('competitive_stress'),
            npc_interaction=social.get('npc_interaction'),
            user_creation=social.get('user_creation'),
            multiplayer_scale=social.get('multiplayer_scale'),
            
            # ===== PRESENTATION (5개) =====
            lore_richness=presentation.get('lore_richness'),
            choice_consequence=presentation.get('choice_consequence'),
            visual_spectacle=presentation.get('visual_spectacle'),
            environmental_storytelling=presentation.get('environmental_storytelling'),
            soundtrack_impact=presentation.get('soundtrack_impact'),
            
            # ===== SYSTEM/UX (7개 - 신규) - Fallback 적용 =====
            build_variety=self._get_metric(new_sources, 'build_variety'),
            progression_clarity=self._get_metric(new_sources, 'progression_clarity'),
            save_flexibility=self._get_metric(new_sources, 'save_flexibility'),
            difficulty_accessibility=self._get_metric(new_sources, 'difficulty_accessibility'),
            tutorial_quality=self._get_metric(new_sources, 'tutorial_quality'),
            ui_ux_polish=self._get_metric(new_sources, 'ui_ux_polish'),
            modding_support=self._get_metric(new_sources, 'modding_support'),
            
            # ===== ART/AUDIO (3개 - 신규) - Fallback 적용 =====
            art_style_uniqueness=self._get_metric(new_sources, 'art_style_uniqueness'),
            audio_design=self._get_metric(new_sources, 'audio_design'),
            animation_quality=self._get_metric(new_sources, 'animation_quality'),
            
            # ===== OTHER (2개 - 신규) - Fallback 적용 =====
            world_reactivity=self._get_metric(new_sources, 'world_reactivity'),
            community_dependency=self._get_metric(new_sources, 'community_dependency'),
            
            # ===== NEW (4개 - 신규) - Fallback 적용 =====
            narrative_depth=self._get_metric(new_sources, 'narrative_depth'),
            replay_value=self._get_metric(new_sources, 'replay_value'),
            endgame_content=self._get_metric(new_sources, 'endgame_content'),
            monetization_fairness=self._get_metric(new_sources, 'monetization_fairness'),
            
            # ===== TAGS (9개) =====
            is_turn_based=t.get('is_turn_based', False),
            is_real_time=t.get('is_real_time', False),
            is_first_person=t.get('is_first_person', False),
            is_third_person=t.get('is_third_person', False),
            has_permadeath=t.get('has_permadeath', False),
            has_base_building=t.get('has_building', False) or t.get('has_base_building', False),
            has_crafting=t.get('has_crafting', False),
            is_anime_style=t.get('is_anime_style', False),
            is_retro_aesthetic=t.get('is_retro_aesthetic', False),
            
            # ===== EVAL (2개) =====
            gem_potential=self._get_metric([m, r, data], 'gem_potential'),
            confidence_score=self._get_metric([r, m, data], 'confidence_score'),
            
            # ===== REASONING =====
            analysis_summary=r.get('analysis_summary', ''),
            genre_classification=r.get('genre_classification', ''),
            core_loop=r.get('core_loop', ''),
            metric_justifications=r.get('metric_justifications', {}),
            data_limitations=r.get('data_limitations', ''),
            
            # ===== 원본 보관 =====
            raw_content=c,
            raw_reasoning=r,
            
            # ===== META =====
            extraction_version='gpt5.4-batch-v1',
        )

    def _update_game(self, app_id, data):
        """
        기존 게임 데이터 업데이트 (--update 옵션 사용 시 호출)

        AI 생성 콘텐츠(marketing_hook, one_line_summary 등)와 기본 메타데이터를 갱신.
        지표(GameMetric)는 기존 것을 삭제하고 새로 생성 (전체 교체 방식).
        """
        game = Game.objects.get(app_id=app_id)
        c = data.get('content', {})
        
        hook = c.get('marketing_hook', '')
        if isinstance(hook, dict):
            hook = hook.get('primary', '') or json.dumps(hook, ensure_ascii=False)
        
        if data.get('name'):
            game.name = data['name']
        if data.get('genres'):
            game.genres = data['genres']
        if data.get('description'):
            game.description = data['description']
        
        game.marketing_hook = hook
        game.one_line_summary = c.get('one_line_summary', '')
        game.target_personas = c.get('target_personas', [])
        game.not_for_personas = c.get('not_for_personas', [])
        game.similar_games = c.get('similar_games', [])
        game.unique_selling_points = c.get('unique_selling_points', [])
        game.is_analyzed = True
        game.analysis_method = 'gpt5.4_batch'
        game.save()
        
        GameMetric.objects.filter(game=game).delete()
        metric = self._create_metric(game, data)
        metric.save()

    def _validate_data(self, games_data):
        """
        데이터 구조 사전 검증 (--dry-run 시 호출)

        처음 10개 샘플에 대해 기본 필드와 신규 18개 지표 존재 여부를 확인.
        신규 지표를 15개 이상 가진 레코드는 OK, 미달이면 WARN으로 출력.
        """
        valid, invalid = 0, 0
        extended_found, extended_missing = 0, 0
        
        new_metrics = [
            'build_variety', 'progression_clarity', 'save_flexibility',
            'difficulty_accessibility', 'tutorial_quality', 'ui_ux_polish',
            'modding_support', 'art_style_uniqueness', 'audio_design',
            'animation_quality', 'puzzle_complexity', 'platforming_precision',
            'world_reactivity', 'community_dependency', 'narrative_depth',
            'replay_value', 'endgame_content', 'monetization_fairness'
        ]
        
        for data in games_data[:10]:
            app_id = data.get('app_id')
            metrics = data.get('metrics', {})
            extended = metrics.get('extended', {})
            
            has_vibe = bool(metrics.get('vibe'))
            
            # 신규 지표 찾기 (어디서든)
            found_new = 0
            for nm in new_metrics:
                if extended.get(nm) is not None:
                    found_new += 1
                elif metrics.get(nm) is not None:
                    found_new += 1
                elif data.get(nm) is not None:
                    found_new += 1
            
            if app_id and has_vibe:
                valid += 1
                if found_new >= 15:
                    extended_found += 1
                    self.stdout.write(f'  OK [{app_id}] {data.get("name", "")[:30]} (신규: {found_new}/18)')
                else:
                    extended_missing += 1
                    self.stdout.write(self.style.WARNING(f'  WARN [{app_id}] {data.get("name", "")[:30]} (신규: {found_new}/18)'))
            else:
                invalid += 1
                self.stdout.write(self.style.ERROR(f'  FAIL [{app_id}] 기본 데이터 불완전'))
        
        self.stdout.write(f'\n샘플 검증 결과:')
        self.stdout.write(f'  - 정상: {valid}/10')
        self.stdout.write(f'  - 신규 지표 충분: {extended_found}/10')
        self.stdout.write(f'  - 신규 지표 부족: {extended_missing}/10')
