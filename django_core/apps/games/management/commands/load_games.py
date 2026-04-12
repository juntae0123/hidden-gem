# django_core/apps/games/management/commands/load_games.py
"""
4,190개 GPT-5.4 Batch 데이터 적재 스크립트

사용법:
    python manage.py load_games --input ../data/merged/merged_games.jsonl
    python manage.py load_games --input ../data/merged/merged_games.jsonl --dry-run
    python manage.py load_games --input ../data/merged/merged_games.jsonl --update
"""

import json
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.games.models import Game, GameMetric


class Command(BaseCommand):
    help = 'GPT-5.4로 추출한 4,190개 게임 데이터를 DB에 적재'

    def add_arguments(self, parser):
        parser.add_argument('--input', '-i', type=str, required=True, help='JSONL 파일 경로')
        parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 검증만')
        parser.add_argument('--update', action='store_true', help='기존 데이터 업데이트')
        parser.add_argument('--batch-size', type=int, default=100, help='배치 크기')
        parser.add_argument('--limit', type=int, default=0, help='처리할 최대 개수 (0=전체)')

    def handle(self, *args, **options):
        input_path = Path(options['input'])
        
        if not input_path.exists():
            raise CommandError(f'❌ 파일 없음: {input_path}')
        
        self.stdout.write(f'📂 파일: {input_path}')
        self.stdout.write(f'📊 파일 크기: {input_path.stat().st_size / 1024 / 1024:.1f} MB')
        
        # 기존 데이터 조회
        existing_ids = set(Game.objects.values_list('app_id', flat=True))
        self.stdout.write(f'📊 기존 DB: {len(existing_ids)}개')
        
        # 파일 읽기
        games_data = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if options['limit'] and i >= options['limit']:
                    break
                if line.strip():
                    games_data.append(json.loads(line))
        
        self.stdout.write(f'📊 파일 내 게임: {len(games_data)}개')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - 저장하지 않음'))
            self._validate_data(games_data)
            return
        
        # 적재 시작
        start_time = time.time()
        created, updated, skipped, errors = 0, 0, 0, 0
        
        batch_games = []
        batch_metrics_data = []
        
        for data in games_data:
            app_id = data.get('app_id')
            
            if not app_id:
                errors += 1
                continue
            
            # 이미 존재하는 경우
            if app_id in existing_ids:
                if options['update']:
                    try:
                        self._update_game(app_id, data)
                        updated += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'업데이트 실패 [{app_id}]: {e}'))
                        errors += 1
                else:
                    skipped += 1
                continue
            
            # 새 게임 준비
            game = Game(
                app_id=app_id,
                name=data.get('name', ''),
                genres=data.get('genres', ''),
                developer=data.get('developer', ''),
                description=data.get('description', ''),
                is_analyzed=True,
                analysis_method='gpt5.4_batch',
                is_active=True,
            )
            batch_games.append(game)
            batch_metrics_data.append(data)
            existing_ids.add(app_id)
            
            # 배치 저장
            if len(batch_games) >= options['batch_size']:
                saved = self._save_batch(batch_games, batch_metrics_data)
                created += saved
                batch_games, batch_metrics_data = [], []
                self.stdout.write(f'  ✅ {created}개 저장됨...')
        
        # 남은 배치 저장
        if batch_games:
            saved = self._save_batch(batch_games, batch_metrics_data)
            created += saved
        
        elapsed = time.time() - start_time
        
        self.stdout.write(self.style.SUCCESS(f'''
{'='*60}
✅ GPT-5.4 데이터 적재 완료!

   📊 결과:
   - 생성: {created}개
   - 업데이트: {updated}개  
   - 스킵 (이미 존재): {skipped}개
   - 에러: {errors}개
   
   ⏱️ 소요시간: {elapsed:.1f}초
   🚀 처리속도: {len(games_data)/elapsed:.1f} games/sec
{'='*60}
        '''))

    def _save_batch(self, games, metrics_data):
        """배치 저장"""
        with transaction.atomic():
            created_games = Game.objects.bulk_create(games)
            
            metrics = []
            for game, data in zip(created_games, metrics_data):
                metric = self._create_metric(game, data)
                metrics.append(metric)
            
            GameMetric.objects.bulk_create(metrics)
        
        return len(created_games)

    def _create_metric(self, game, data):
        """GameMetric 생성 - GPT-5.4 데이터 전체 매핑"""
        m = data.get('metrics', {})
        t = data.get('tags', {})
        c = data.get('content', {})
        r = data.get('reasoning', {})
        
        vibe = m.get('vibe', {})
        demands = m.get('demands', {})
        mechanics = m.get('mechanics', {})
        social = m.get('social', {})
        presentation = m.get('presentation', {})
        
        # marketing_hook 처리 (dict일 수 있음)
        hook = c.get('marketing_hook', '')
        if isinstance(hook, dict):
            hook = hook.get('primary', '') or hook.get('emotional', '') or json.dumps(hook, ensure_ascii=False)
        
        return GameMetric(
            game=game,
            
            # VIBE (7개)
            cozy_factor=vibe.get('cozy_factor'),
            horror_factor=vibe.get('horror_factor'),
            gore_level=vibe.get('gore_level'),
            humor_rating=vibe.get('humor_rating'),
            dark_fantasy_vibe=vibe.get('dark_fantasy_vibe'),
            epic_scale=vibe.get('epic_scale'),
            melancholy=vibe.get('melancholy'),
            
            # DEMANDS (5개)
            reflex_demand=demands.get('reflex_demand'),
            strategic_depth=demands.get('strategic_depth'),
            grind_factor=demands.get('grind_factor'),
            time_pressure=demands.get('time_pressure'),
            learning_curve=demands.get('learning_curve'),
            
            # MECHANICS (11개)
            freedom_level=mechanics.get('freedom_level'),
            action_pacing=mechanics.get('action_pacing'),
            rng_dependency=mechanics.get('rng_dependency'),
            growth_reward=mechanics.get('growth_reward'),
            exploration_reward=mechanics.get('exploration_reward'),
            management_complexity=mechanics.get('management_complexity'),
            stealth_importance=mechanics.get('stealth_importance'),
            session_length=mechanics.get('session_length'),
            narrative_linearity=mechanics.get('narrative_linearity'),
            puzzle_complexity=mechanics.get('puzzle_complexity'),
            platforming_precision=mechanics.get('platforming_precision'),
            
            # SOCIAL (5개)
            coop_synergy=social.get('coop_synergy'),
            competitive_stress=social.get('competitive_stress'),
            npc_interaction=social.get('npc_interaction'),
            user_creation=social.get('user_creation'),
            multiplayer_scale=social.get('multiplayer_scale'),
            
            # PRESENTATION (5개)
            lore_richness=presentation.get('lore_richness'),
            choice_consequence=presentation.get('choice_consequence'),
            visual_spectacle=presentation.get('visual_spectacle'),
            environmental_storytelling=presentation.get('environmental_storytelling'),
            soundtrack_impact=presentation.get('soundtrack_impact'),
            
            # TAGS (9개)
            is_turn_based=t.get('is_turn_based', False),
            is_real_time=t.get('is_real_time', False),
            is_first_person=t.get('is_first_person', False),
            is_third_person=t.get('is_third_person', False),
            has_permadeath=t.get('has_permadeath', False),
            has_base_building=t.get('has_base_building', False),
            has_crafting=t.get('has_crafting', False),
            is_anime_style=t.get('is_anime_style', False),
            is_retro_aesthetic=t.get('is_retro_aesthetic', False),
            
            # CONTENT (AI 생성 텍스트)
            marketing_hook=hook,
            one_line_summary=c.get('one_line_summary', ''),
            target_personas=c.get('target_personas', []),
            not_for_personas=c.get('not_for_personas', []),
            similar_games=c.get('similar_games', []),
            unique_selling_points=c.get('unique_selling_points', []),
            
            # REASONING (분석 근거)
            analysis_summary=r.get('analysis_summary', ''),
            genre_classification=r.get('genre_classification', ''),
            core_loop=r.get('core_loop', ''),
            metric_justifications=r.get('metric_justifications', {}),
            confidence_score=r.get('confidence_score'),
            data_limitations=r.get('data_limitations', ''),
            
            # 원본 보관
            raw_content=c,
            raw_reasoning=r,
            
            # META
            extraction_version='gpt5.4-batch-v1',
        )

    def _update_game(self, app_id, data):
        """기존 게임 업데이트"""
        game = Game.objects.get(app_id=app_id)
        
        # Game 필드 업데이트
        if data.get('name'):
            game.name = data['name']
        if data.get('genres'):
            game.genres = data['genres']
        if data.get('description'):
            game.description = data['description']
        game.is_analyzed = True
        game.analysis_method = 'gpt5.4_batch'
        game.save()
        
        # Metric 업데이트 (삭제 후 재생성)
        GameMetric.objects.filter(game=game).delete()
        metric = self._create_metric(game, data)
        metric.save()

    def _validate_data(self, games_data):
        """데이터 검증"""
        valid, invalid = 0, 0
        
        for data in games_data[:10]:  # 샘플 10개만
            app_id = data.get('app_id')
            metrics = data.get('metrics', {})
            
            has_vibe = bool(metrics.get('vibe'))
            has_demands = bool(metrics.get('demands'))
            
            if app_id and has_vibe and has_demands:
                valid += 1
                self.stdout.write(f'  ✅ [{app_id}] {data.get("name", "")[:30]}')
            else:
                invalid += 1
                self.stdout.write(self.style.ERROR(f'  ❌ [{app_id}] 데이터 불완전'))
        
        self.stdout.write(f'\n샘플 검증: {valid}/10 정상')
