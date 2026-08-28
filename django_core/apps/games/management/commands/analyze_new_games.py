# django_core/apps/games/management/commands/analyze_new_games.py
"""
신규 게임 Few-Shot 분석 (저비용으로 GPT-5.4급 품질)

전략:
1. 신규 게임의 장르/설명으로 4,190개 중 유사한 게임 5개 찾기
2. 유사 게임들의 GPT-5.4 분석 결과를 Few-Shot 예시로 제공
3. 저렴한 모델(gpt-4o-mini)로 동일 형식의 분석 결과 생성
4. 결과: GPT-5.4급 품질을 1/60 비용으로!

사용법:
    python manage.py analyze_new_games --app-id 12345
    python manage.py analyze_new_games --pending --limit 50
    python manage.py analyze_new_games --pending --dry-run
"""

import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from openai import OpenAI
from apps.games.models import Game, GameMetric


class Command(BaseCommand):
    help = '신규 게임을 GPT-5.4 데이터 기반 Few-Shot으로 분석 (저비용 고품질)'

    def add_arguments(self, parser):
        parser.add_argument('--app-id', type=int, help='특정 게임 하나만 분석')
        parser.add_argument('--pending', action='store_true', help='미분석 게임 전체')
        parser.add_argument('--limit', type=int, default=10, help='최대 처리 개수')
        parser.add_argument('--dry-run', action='store_true', help='실제 API 호출 없이 테스트')
        parser.add_argument('--model', type=str, default='gpt-4o-mini', help='사용할 모델')

    def handle(self, *args, **options):
        """
        커맨드 메인 실행 (Command Entry Point)

        단일 게임(--app-id) 또는 미분석 전체(--pending)를 대상으로 Few-Shot 분석.
        각 게임에 대해: 유사 게임 탐색 → GPT 분석 → DB 저장 3단계 실행.
        --dry-run이면 유사 게임 탐색만 수행하고 실제 API 호출은 건너뜀.
        """
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = options['model']

        # 분석 대상 선택 - 단일 게임 또는 미분석 전체
        if options['app_id']:
            games = Game.objects.filter(app_id=options['app_id'])
        elif options['pending']:
            games = Game.objects.filter(
                Q(is_analyzed=False) | Q(analysis_method='pending')
            )[:options['limit']]
        else:
            self.stdout.write(self.style.ERROR('--app-id 또는 --pending 옵션 필요'))
            return
        
        total = games.count()
        self.stdout.write(f'''
{'='*60}
신규 게임 Few-Shot 분석 (GPT-5.4 품질)
{'='*60}
분석 대상: {total}개
사용 모델: {self.model}
전략: 4,190개 GPT-5.4 데이터 기반 Few-Shot
{'='*60}
        ''')
        
        success, failed = 0, 0
        
        for i, game in enumerate(games, 1):
            self.stdout.write(f'\n[{i}/{total}] [{game.app_id}] {game.name}')
            
            if options['dry_run']:
                similar = self._find_similar_games(game)
                self.stdout.write(f'   유사 게임: {[g.name[:20] for g in similar]}')
                continue
            
            try:
                # 1. 유사 게임 찾기 (GPT-5.4로 분석된 것 중에서)
                similar_games = self._find_similar_games(game, top_k=5)
                self.stdout.write(f'   유사 게임 {len(similar_games)}개 발견')
                
                # 2. Few-Shot 분석
                result = self._analyze_with_fewshot(game, similar_games)
                
                # 3. 저장
                self._save_result(game, result)
                
                success += 1
                self.stdout.write(self.style.SUCCESS(f'   분석 완료!'))
                
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f'   실패: {e}'))
        
        self.stdout.write(f'''
{'='*60}
완료!
   성공: {success}개
   실패: {failed}개
{'='*60}
        ''')

    def _find_similar_games(self, game, top_k=5):
        """
        신규 게임의 Few-Shot 예시용 유사 게임 탐색 (Similar Game Finder)

        GPT-5.4로 분석된 4,190개 원본 중에서 장르 일치 게임을 우선 탐색.
        장르 일치 top_k개 확보 실패 시 전체 분석 완료 게임에서 폴백.

        Note:
            현재는 장르 텍스트 매칭만 사용하며, 향후 임베딩 + pgvector로
            의미적 유사도 기반 탐색으로 개선 예정.

        Args:
            game: 분석할 신규 게임 Game 인스턴스
            top_k: 반환할 유사 게임 수 (기본 5)

        Returns:
            유사 게임 Game 인스턴스 리스트 (metrics 포함)
        """
        genres = game.genres.split(',')[0].strip() if game.genres else ''

        similar = Game.objects.filter(
            is_analyzed=True,
            analysis_method='gpt5.4_batch',  # 원본 고품질 데이터만 사용
        ).exclude(
            app_id=game.app_id
        ).select_related('metrics')

        if genres:
            genre_matched = similar.filter(genres__icontains=genres)[:top_k]
            if genre_matched.count() >= top_k:
                return list(genre_matched)

        # 장르 매칭 부족 시 폴백: 전체 분석 완료 게임에서 상위 top_k
        return list(similar[:top_k])

    def _analyze_with_fewshot(self, game, similar_games):
        """
        Few-Shot 방식으로 신규 게임 분석 (Few-Shot Analysis)

        GPT-5.4 원본 분석 결과를 예시로 제공하여 저렴한 모델(gpt-4o-mini)로
        동일 품질의 분석 결과를 생성. 1/60 비용으로 GPT-5.4급 품질 달성.

        Args:
            game: 분석할 신규 게임
            similar_games: _find_similar_games()에서 찾은 유사 게임들

        Returns:
            GPT가 생성한 분석 결과 딕셔너리 (metrics, tags, content, reasoning 포함)
        """
        examples = self._build_examples(similar_games)
        
        prompt = f"""당신은 Steam 인디게임 분석 전문가입니다.

아래는 이미 분석된 유사한 게임들의 예시입니다. 이 형식과 기준을 참고하여 새 게임을 분석해주세요.

{examples}

---

## 분석할 새 게임

- **이름**: {game.name}
- **장르**: {game.genres}
- **설명**: {game.description[:1000] if game.description else '설명 없음'}

---

## 출력 형식

위 예시들과 **완전히 동일한 JSON 구조**로 출력하세요.
모든 점수는 0~10 사이 정수입니다.
한국어로 작성하세요.

```json
{{
  "metrics": {{
    "vibe": {{
      "cozy_factor": 0,
      "horror_factor": 0,
      "gore_level": 0,
      "humor_rating": 0,
      "dark_fantasy_vibe": 0,
      "epic_scale": 0,
      "melancholy": 0
    }},
    "demands": {{
      "reflex_demand": 0,
      "strategic_depth": 0,
      "grind_factor": 0,
      "time_pressure": 0,
      "learning_curve": 0
    }},
    "mechanics": {{
      "freedom_level": 0,
      "action_pacing": 0,
      "rng_dependency": 0,
      "growth_reward": 0,
      "exploration_reward": 0,
      "management_complexity": 0,
      "stealth_importance": 0,
      "session_length": 0,
      "narrative_linearity": 0,
      "puzzle_complexity": 0,
      "platforming_precision": 0
    }},
    "social": {{
      "coop_synergy": 0,
      "competitive_stress": 0,
      "npc_interaction": 0,
      "user_creation": 0,
      "multiplayer_scale": 0
    }},
    "presentation": {{
      "lore_richness": 0,
      "choice_consequence": 0,
      "visual_spectacle": 0,
      "environmental_storytelling": 0,
      "soundtrack_impact": 0
    }}
  }},
  "tags": {{
    "is_turn_based": false,
    "is_real_time": false,
    "is_first_person": false,
    "is_third_person": false,
    "has_permadeath": false,
    "has_base_building": false,
    "has_crafting": false,
    "is_anime_style": false,
    "is_retro_aesthetic": false
  }},
  "content": {{
    "marketing_hook": "이 게임의 핵심 매력을 한 문장으로",
    "one_line_summary": "게임 한 줄 요약",
    "target_personas": ["이 게임을 좋아할 사람 유형"],
    "not_for_personas": ["이 게임을 싫어할 사람 유형"],
    "similar_games": ["유사한 게임 이름"],
    "unique_selling_points": ["이 게임만의 특별한 점"]
  }},
  "reasoning": {{
    "analysis_summary": "분석 요약",
    "genre_classification": "장르 분류",
    "core_loop": "핵심 게임 루프 설명",
    "confidence_score": 0.8
  }}
}}
```"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2500,
        )
        
        content = response.choices[0].message.content
        return json.loads(content)

    def _build_examples(self, similar_games):
        """
        유사 게임의 GPT-5.4 분석 결과를 Few-Shot 예시 텍스트로 포맷 (Example Builder)

        각 게임의 지표/태그/콘텐츠를 JSON 형식으로 직렬화하여 프롬프트에 삽입.
        GPT가 이 예시들의 패턴을 학습하여 동일한 형식과 수준으로 신규 게임을 분석.

        Args:
            similar_games: 유사 게임 Game 인스턴스 리스트

        Returns:
            예시 텍스트 문자열 (프롬프트에 직접 삽입됨)
        """
        examples = ""
        
        for i, game in enumerate(similar_games, 1):
            try:
                m = game.metrics
                
                examples += f"""
### 예시 {i}: {game.name}
- 장르: {game.genres}
- 설명: {game.description[:300] if game.description else ''}...

분석 결과:
```json
{{
  "metrics": {{
    "vibe": {{
      "cozy_factor": {m.cozy_factor or 0},
      "horror_factor": {m.horror_factor or 0},
      "gore_level": {m.gore_level or 0},
      "humor_rating": {m.humor_rating or 0},
      "dark_fantasy_vibe": {m.dark_fantasy_vibe or 0},
      "epic_scale": {m.epic_scale or 0},
      "melancholy": {m.melancholy or 0}
    }},
    "demands": {{
      "reflex_demand": {m.reflex_demand or 0},
      "strategic_depth": {m.strategic_depth or 0},
      "grind_factor": {m.grind_factor or 0},
      "time_pressure": {m.time_pressure or 0},
      "learning_curve": {m.learning_curve or 0}
    }},
    "mechanics": {{
      "freedom_level": {m.freedom_level or 0},
      "action_pacing": {m.action_pacing or 0},
      "rng_dependency": {m.rng_dependency or 0},
      "growth_reward": {m.growth_reward or 0},
      "exploration_reward": {m.exploration_reward or 0},
      "management_complexity": {m.management_complexity or 0},
      "stealth_importance": {m.stealth_importance or 0},
      "session_length": {m.session_length or 0},
      "narrative_linearity": {m.narrative_linearity or 0},
      "puzzle_complexity": {m.puzzle_complexity or 0},
      "platforming_precision": {m.platforming_precision or 0}
    }},
    "social": {{
      "coop_synergy": {m.coop_synergy or 0},
      "competitive_stress": {m.competitive_stress or 0},
      "npc_interaction": {m.npc_interaction or 0},
      "user_creation": {m.user_creation or 0},
      "multiplayer_scale": {m.multiplayer_scale or 0}
    }},
    "presentation": {{
      "lore_richness": {m.lore_richness or 0},
      "choice_consequence": {m.choice_consequence or 0},
      "visual_spectacle": {m.visual_spectacle or 0},
      "environmental_storytelling": {m.environmental_storytelling or 0},
      "soundtrack_impact": {m.soundtrack_impact or 0}
    }}
  }},
  "tags": {{
    "is_turn_based": {str(m.is_turn_based).lower()},
    "is_real_time": {str(m.is_real_time).lower()},
    "is_first_person": {str(m.is_first_person).lower()},
    "is_third_person": {str(m.is_third_person).lower()},
    "has_permadeath": {str(m.has_permadeath).lower()},
    "has_base_building": {str(m.has_base_building).lower()},
    "has_crafting": {str(m.has_crafting).lower()},
    "is_anime_style": {str(m.is_anime_style).lower()},
    "is_retro_aesthetic": {str(m.is_retro_aesthetic).lower()}
  }},
  "content": {{
    "marketing_hook": "{(m.marketing_hook or '')[:150]}",
    "one_line_summary": "{(m.one_line_summary or '')[:150]}"
  }}
}}
```"""
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'   예시 생성 실패: {e}'))
                continue
        return examples     

def _save_result(self, game, result):
    """분석 결과 저장"""
    m = result.get('metrics', {})
    t = result.get('tags', {})
    c = result.get('content', {})
    r = result.get('reasoning', {})
    
    vibe = m.get('vibe', {})
    demands = m.get('demands', {})
    mechanics = m.get('mechanics', {})
    social = m.get('social', {})
    presentation = m.get('presentation', {})
    
    with transaction.atomic():
        GameMetric.objects.filter(game=game).delete()
        
        metric = GameMetric(
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
            marketing_hook=c.get('marketing_hook', ''),
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
            extraction_version=f'fewshot-{self.model}-v1',
        )
        metric.save()
        
        # Game 상태 업데이트
        game.is_analyzed = True
        game.analysis_method = 'fewshot_5.4based'
        game.save()
