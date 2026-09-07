# django_core/apps/users/views.py
"""
Hidden Gem 유저 인증 뷰 (User Auth Views)

v11 → v12 정석:
    - get_login_redirect_url은 account adapter 메서드 (socialaccount 아님!)
    - JWTAccountAdapter (account) + nickname은 socialaccount adapter
    - allauth 65.x 정확한 hook 사용
"""
import logging
import os

from django.conf import settings

import requests
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.steam.views import SteamOpenIDCallbackView
from apps.users.serializers import UserSerializer, OnboardingSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

# 리다이렉트에는 **단일 주소**만 쓴다. 환경변수는 콤마 목록일 수 있어(CORS 화이트리스트 겸용)
# settings 가 첫 항목만 골라둔 값을 가져온다 — 직접 os.getenv 하면 콤마가 URL 에 섞인다 (2026-09-07 사고).
FRONTEND_URL = settings.FRONTEND_URL


class JWTAccountAdapter(DefaultAccountAdapter):
    """
    Account adapter — 로그인 후 리다이렉트 처리.

    get_login_redirect_url은 account adapter 메서드!
    (socialaccount adapter 아님)
    """

    def get_login_redirect_url(self, request):
        """
        로그인 성공 후 → JWT 발급 → 프론트 /auth/callback.
        """
        user = request.user

        if not user or not user.is_authenticated:
            logger.warning("[OAuth] get_login_redirect_url: 인증 안 됨")
            return f"{FRONTEND_URL}/login?error=not_authenticated"

        # JWT 발급
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        logger.info(f"[OAuth] 로그인 성공 + JWT 발급: {user.email}")

        # 토큰은 fragment(#)로 전달 - 쿼리스트링과 달리 서버 로그/Referer에 남지 않음
        return (
            f"{FRONTEND_URL}/auth/callback"
            f"#access={access_token}"
            f"&refresh={refresh_token}"
        )


class JWTSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Social account adapter — 유저 저장 + 닉네임 + 에러 처리.

    get_callback_url 절대 오버라이드 X (redirect_uri 보호)
    """

    # 스팀 계정에 붙일 합성 이메일. 스팀 OpenID 는 이메일을 주지 않는다.
    STEAM_EMAIL_DOMAIN = 'users.hiddengem.local'

    @classmethod
    def _steam_email(cls, uid):
        return f'steam_{uid}@{cls.STEAM_EMAIL_DOMAIN}'

    def pre_social_login(self, request, sociallogin):
        """스팀 로그인이 회원가입 폼으로 빠지지 않게 한다.

        allauth 의 자동 가입 판정(process_auto_signup_email)은 `user.email` 이 아니라
        **`sociallogin.email_addresses`** 를 본다. 비어 있고 EMAIL_REQUIRED 면 자동 가입을
        포기하고 `/accounts/3rdparty/signup/` 폼을 띄운다.
        (EMAIL_REQUIRED 기본값은 ACCOUNT_SIGNUP_FIELDS=['email*'] 에서 True 로 유도된다)

        populate_user 에서 user.email 만 채웠던 게 부족했던 이유가 이것 —
        판정이 보는 자리에 넣어야 한다. 실수 기록: 2026-09-07.

        EMAIL_REQUIRED 를 끄는 방법도 있지만, 그러면 이메일을 안 주는 **모든** provider 가
        조용히 자동 가입된다. 스팀에만 한정해 합성 주소를 붙인다.
        """
        super().pre_social_login(request, sociallogin)

        if sociallogin.is_existing or sociallogin.account.provider != 'steam':
            return
        if sociallogin.email_addresses:
            return

        email = self._steam_email(sociallogin.account.uid)
        sociallogin.email_addresses = [
            EmailAddress(email=email, verified=False, primary=True)
        ]
        if sociallogin.user and not sociallogin.user.email:
            sociallogin.user.email = email

        # 이 줄이 로그에 없으면 훅이 안 탄 것이다 — 배포 여부부터 본다.
        logger.info(
            "[Steam] 신규 가입 — 합성 이메일을 email_addresses 에 주입 (uid=%s)",
            sociallogin.account.uid,
        )

    def populate_user(self, request, sociallogin, data):
        """Steam은 이메일을 제공하지 않으므로 합성 이메일로 자동 가입을 통과시킨다.

        (ACCOUNT_SIGNUP_FIELDS의 email 필수 조건 + auto signup 판정이
        user.email 기준이라, 여기서 채워야 가입 폼으로 빠지지 않음)
        """
        user = super().populate_user(request, sociallogin, data)
        if sociallogin.account.provider == 'steam' and not user.email:
            user.email = self._steam_email(sociallogin.account.uid)
        return user

    def save_user(self, request, sociallogin, form=None):
        """유저 저장 + 프로필(Google name / Steam personaname)에서 닉네임 세팅."""
        user = super().save_user(request, sociallogin, form)
        extra_data = sociallogin.account.extra_data

        if not user.nickname:
            user.nickname = (
                extra_data.get('name')
                or extra_data.get('given_name')
                or extra_data.get('personaname')
                or user.email.split('@')[0]
            )
            user.save(update_fields=['nickname'])

        logger.info(f"[OAuth] 유저 저장: {user.email} (nickname: {user.nickname})")
        return user

    def on_authentication_error(
        self,
        request,
        provider_id,
        error=None,
        exception=None,
        extra_context=None,
    ):
        """인증 실패 → 프론트 로그인 페이지로."""
        logger.error(
            f"[OAuth] 인증 실패: provider={provider_id}, "
            f"error={error}, exception={exception}"
        )
        return redirect(f"{FRONTEND_URL}/login?error=auth_failed")


class SafeSteamCallbackView(SteamOpenIDCallbackView):
    """스팀 콜백 — Steam Web API 가 실패해도 500 대신 로그인 화면으로 돌려보낸다.

    allauth 의 SteamOpenIDProvider.sociallogin_from_response 는 OpenID 검증 직후
    GetPlayerSummaries 를 호출하고 resp.raise_for_status() 를 그대로 던진다.
    그 예외를 감싸는 곳이 없어서, 키가 틀리거나 스팀이 잠시 죽으면 콜백이 500 이 된다.

    2026-09-07 사고: SocialApp.secret 이 비어 있어(키를 client_id 에만 넣었다)
    Steam API 가 403 → 콜백 500. 원인은 자격증명이었지만, 스팀 장애 때도 같은 500 이
    나므로 여기서 한 번 잡아 사용자에게는 "다시 시도" 화면을 준다.
    """

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except requests.RequestException as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            logger.error(
                "[Steam] 콜백 실패 — Steam API 응답 %s (%s). "
                "SocialApp.secret(=Steam Web API Key) 설정을 먼저 확인한다.",
                status, type(exc).__name__,
            )
            return redirect(f"{FRONTEND_URL}/login?error=steam_unavailable")
        except (KeyError, ValueError) as exc:
            logger.error(
                "[Steam] 콜백 응답 해석 실패 — %s: %s", type(exc).__name__, exc
            )
            return redirect(f"{FRONTEND_URL}/login?error=steam_unavailable")

    post = get


class UserMeView(APIView):
    """현재 로그인 유저 정보 조회 — JWT 인증 필요."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    
class OnboardingView(APIView):
    """
    Save onboarding data (name/nickname/gender/age_group).
    Korean: 온보딩 데이터 저장 — JWT 인증 필요.
    저장 성공 시 onboarding_completed=True 설정.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        data = serializer.validated_data

        # 이름(선택): 들어오면 갱신
        if data.get('first_name'):
            user.first_name = data['first_name']
        # 닉네임(선택): 들어오면 갱신
        if data.get('nickname'):
            user.nickname = data['nickname']
        # 성별/나이대(필수)
        user.gender = data['gender']
        user.age_group = data['age_group']
        user.onboarding_completed = True
        user.save(update_fields=[
            'first_name', 'nickname', 'gender',
            'age_group', 'onboarding_completed',
        ])

        logger.info(
            f"[Onboarding] 완료: {user.email} "
            f"(gender={user.gender}, age={user.age_group})"
        )
        return Response(UserSerializer(user).data)

class RecentGamesView(APIView):
    """
    User's recently viewed games (from detail_view actions).
    Korean: 최근 본 게임 — UserAction의 detail_view를 시간순으로,
            중복 제거 후 게임 정보와 함께 반환 (최근 12개).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.users.models import UserAction
        from apps.games.models import Game

        # 내 detail_view 액션을 최신순으로 (중복 app_id는 최신 것만)
        app_ids = []
        actions = (
            UserAction.objects
            .filter(
                user=request.user,
                action_type='detail_view',
                app_id__isnull=False,
            )
            .order_by('-created_at')
            .values_list('app_id', flat=True)
        )
        for aid in actions:
            if aid not in app_ids:
                app_ids.append(aid)
            if len(app_ids) >= 12:  # 최근 12개까지
                break

        if not app_ids:
            return Response({"games": []})

        # 게임 정보 조회 후 최신순 정렬 유지
        games = Game.objects.filter(app_id__in=app_ids)
        game_map = {g.app_id: g for g in games}

        result = []
        for aid in app_ids:
            g = game_map.get(aid)
            if not g:
                continue
            result.append({
                "app_id": g.app_id,
                "name": g.name,
                "header_image": g.header_image,
                "genres": g.genres,
            })

        return Response({"games": result})

class FavoriteToggleView(APIView):
    """
    Toggle favorite — add if absent, remove if present.
    Korean: 찜 토글 — 없으면 추가, 있으면 삭제. 로그인 유저 전용.
    반환: {"favorited": true/false} (토글 후 상태).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.users.models import Favorite

        app_id = request.data.get('app_id')
        if app_id is None:
            return Response({"detail": "app_id는 필수입니다."}, status=400)

        try:
            app_id = int(app_id)
        except (ValueError, TypeError):
            return Response({"detail": "app_id가 올바르지 않습니다."}, status=400)

        # 이미 찜했으면 삭제, 아니면 추가 (토글)
        existing = Favorite.objects.filter(user=request.user, app_id=app_id).first()
        if existing:
            existing.delete()
            return Response({"favorited": False})
        else:
            Favorite.objects.create(user=request.user, app_id=app_id)
            return Response({"favorited": True})


class FavoriteListView(APIView):
    """
    List user's favorited games with game info.
    Korean: 내 찜 목록 — 게임 정보(이름/이미지/장르) 조인해서 최신순 반환.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.users.models import Favorite
        from apps.games.models import Game

        # 내 찜 app_id들 (최신순)
        favs = list(
            Favorite.objects
            .filter(user=request.user)
            .order_by('-created_at')
            .values_list('app_id', flat=True)
        )
        if not favs:
            return Response({"favorites": [], "app_ids": []})

        # 게임 정보 조회 후 찜 순서(최신순) 유지
        games = Game.objects.filter(app_id__in=favs)
        game_map = {g.app_id: g for g in games}

        result = []
        for aid in favs:
            g = game_map.get(aid)
            if not g:
                continue
            result.append({
                "app_id": g.app_id,
                "name": g.name,
                "header_image": g.header_image,
                "genres": g.genres,
            })

        # app_ids도 같이 반환 (store 동기화용 — 게임 정보 없어도 찜 상태는 유지)
        return Response({"favorites": result, "app_ids": favs})

class TastePreferenceView(APIView):
    """
    Get/save user's taste preferences (genres + metric scores).
    Korean: 취향 설정 조회/저장 — 선호 장르 + 지표별 선호 점수.
    GET: 현재 저장된 취향 반환. POST: 취향 저장.
    수집만 — 추천 반영은 데이터 축적 후 별도.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """저장된 취향 조회 / Return saved preferences."""
        user = request.user
        return Response({
            "preferred_genres":   user.preferred_genres or [],
            "metric_preferences": user.metric_preferences or {},
        })

    def post(self, request):
        """취향 저장 / Save preferences (genres + metric scores)."""
        user = request.user
        genres = request.data.get('preferred_genres', [])
        metrics = request.data.get('metric_preferences', {})

        # 타입 검증 — genres는 리스트, metrics는 dict
        if not isinstance(genres, list):
            return Response({"detail": "preferred_genres는 배열이어야 합니다."}, status=400)
        if not isinstance(metrics, dict):
            return Response({"detail": "metric_preferences는 객체여야 합니다."}, status=400)

        # metric 점수 검증 (1~5 정수만 허용)
        clean_metrics = {}
        for key, val in metrics.items():
            try:
                score = int(val)
                if 1 <= score <= 5:
                    clean_metrics[str(key)] = score
            except (ValueError, TypeError):
                continue  # 잘못된 값은 무시

        user.preferred_genres = [str(g) for g in genres]
        user.metric_preferences = clean_metrics
        user.save(update_fields=['preferred_genres', 'metric_preferences'])

        return Response({
            "preferred_genres":   user.preferred_genres,
            "metric_preferences": user.metric_preferences,
        })
    
class DeleteAccountView(APIView):
    """
    Delete account with anonymization (PIPA/GDPR compliant).
    Korean: 회원 탈퇴 — 개인정보는 삭제, 행동/설문 데이터는 익명화(user 연결만 끊음).
    Favorite(개인 취향)는 삭제. UserAction/GameSurvey는 SET_NULL로 익명 유지.
    되돌릴 수 없음.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        from apps.users.models import Favorite

        user = request.user

        # 1) 개인 취향인 찜은 삭제 (익명화 대상 아님)
        Favorite.objects.filter(user=user).delete()

        # 2) 유저 삭제
        # - UserAction.user → SET_NULL (행동 로그 익명 유지)
        # - GameSurvey.user → SET_NULL (설문 익명 유지, Community Validation 데이터 보존)
        # - CustomUser의 개인정보(이메일/닉네임/성별/나이/취향)는 레코드째 삭제
        user_email = user.email  # 로그용
        user.delete()

        logger.info(f"[DeleteAccount] 탈퇴 완료 (익명화): {user_email}")

        return Response({"success": True, "message": "탈퇴가 완료되었습니다."})

class PendingSurveyView(APIView):
    """
    Find one game eligible for survey (viewed + steam-clicked >= 7 days ago, not yet surveyed).
    Korean: 설문 대상 게임 1개 조회.
    조건: detail_view + steam_click 둘 다 했고, steam_click이 7일 이상 지났고,
          아직 설문 안 한 게임 중 가장 최근 것 하나.
    없으면 {"survey": null}.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import timedelta
        from django.utils import timezone
        from apps.users.models import UserAction, GameSurvey
        from apps.games.models import Game

        user = request.user
        cutoff = timezone.now() - timedelta(days=7)

        # 1) 이미 설문한 게임 app_id 집합 (제외용)
        surveyed = set(
            GameSurvey.objects.filter(user=user).values_list('app_id', flat=True)
        )

        # 2) 7일 이상 전에 steam_click 한 게임들 (최신순)
        steam_clicks = (
            UserAction.objects
            .filter(
                user=user,
                action_type='steam_click',
                app_id__isnull=False,
                created_at__lte=cutoff,
            )
            .order_by('-created_at')
            .values_list('app_id', 'created_at')
        )

        # 3) detail_view 도 한 게임만 (둘 다 한 게 진짜 관심)
        viewed_apps = set(
            UserAction.objects
            .filter(user=user, action_type='detail_view', app_id__isnull=False)
            .values_list('app_id', flat=True)
        )

        # 4) 조건 통과하는 첫 게임 하나
        target_app_id = None
        for app_id, _ts in steam_clicks:
            if app_id in surveyed:
                continue
            if app_id not in viewed_apps:
                continue
            target_app_id = app_id
            break

        if target_app_id is None:
            return Response({"survey": None})

        # 5) 게임 정보 (설문 카드에 표시용)
        game = Game.objects.filter(app_id=target_app_id).first()
        if not game:
            return Response({"survey": None})

        return Response({
            "survey": {
                "app_id": game.app_id,
                "name": game.name,
                "header_image": game.header_image,
                "genres": game.genres,
            }
        })
    
class SubmitSurveyView(APIView):
    """
    Save survey response — GameSurvey (step1) + MetricRating[] (step2).
    Korean: 설문 응답 저장. played=False면 GameSurvey만,
            played=True면 지표별 MetricRating까지.
    중복 방지: 같은 유저+게임 이미 있으면 무시(200).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.db import IntegrityError, transaction
        from apps.users.models import GameSurvey, MetricRating

        user = request.user
        data = request.data

        app_id = data.get('app_id')
        played = data.get('played')

        # 필수 검증
        if app_id is None or played is None:
            return Response(
                {"detail": "app_id와 played는 필수입니다."},
                status=400,
            )

        try:
            with transaction.atomic():
                survey = GameSurvey.objects.create(
                    user=user,
                    app_id=int(app_id),
                    played=bool(played),
                )
                # played=True면 지표 평가 저장
                if played:
                    ratings = data.get('ratings', [])
                    for r in ratings:
                        MetricRating.objects.create(
                            survey=survey,
                            metric=str(r['metric']),
                            our_score=float(r['our_score']),
                            user_score=int(r['user_score']),
                        )
        except IntegrityError:
            # UniqueConstraint(user, app_id) — 이미 설문함
            return Response({"detail": "이미 설문한 게임입니다.", "duplicate": True})
        except (KeyError, ValueError, TypeError) as e:
            return Response({"detail": f"잘못된 데이터: {e}"}, status=400)

        return Response({"success": True, "survey_id": survey.id})


class SteamLibraryView(APIView):
    """
    Get the user's Steam library (top games by playtime).
    Korean: Steam 연동 유저의 보유 게임 조회 — 플레이타임 상위 + 우리 DB 보유 여부.
    상태 저장 없음(마이그레이션 불필요): 호출 시 Steam API에서 직접 조회.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from allauth.socialaccount.models import SocialAccount
        from apps.games.models import Game

        account = SocialAccount.objects.filter(
            user=request.user, provider='steam'
        ).first()
        if account is None:
            return Response({'steam_linked': False, 'top_games': []})

        api_key = os.getenv('STEAM_API_KEY', '')
        if not api_key:
            return Response(
                {'detail': 'STEAM_API_KEY not configured'}, status=503
            )

        try:
            resp = requests.get(
                'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/',
                params={
                    'key': api_key,
                    'steamid': account.uid,
                    'include_appinfo': 1,
                    'include_played_free_games': 1,
                    'format': 'json',
                },
                timeout=10,
            )
            resp.raise_for_status()
            games = resp.json().get('response', {}).get('games', [])
        except (requests.RequestException, ValueError):
            logger.warning('[Steam] GetOwnedGames 실패 (uid=%s)', account.uid)
            return Response({'detail': 'steam_api_unavailable'}, status=502)

        # 프로필이 비공개면 games가 비어서 옴
        top = sorted(games, key=lambda g: g.get('playtime_forever', 0), reverse=True)[:10]
        top_ids = [g['appid'] for g in top]
        in_db = set(
            Game.objects.filter(app_id__in=top_ids).values_list('app_id', flat=True)
        )

        return Response({
            'steam_linked': True,
            'library_count': len(games),
            'top_games': [
                {
                    'app_id': g['appid'],
                    'name': g.get('name', f"App {g['appid']}"),
                    'playtime_hours': round(g.get('playtime_forever', 0) / 60, 1),
                    'in_db': g['appid'] in in_db,
                }
                for g in top
            ],
        })
