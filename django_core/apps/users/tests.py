"""
인증 흐름 회귀 테스트.

실행:
    docker compose exec django python manage.py test apps.users -v 2

여기 있는 것은 전부 2026-09-07 에 실제로 터진 사고의 재발 방지용이다.
① 스팀 콜백 500 (자격증명이 라이브러리가 읽는 필드에 없었다)
② 스팀 로그인이 회원가입 폼으로 빠짐 (자동 가입 판정이 보는 자리에 이메일이 없었다)
③ 콤마 목록 FRONTEND_URL 이 리다이렉트에 섞임
"""
import requests
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from allauth.socialaccount.internal.flows.signup import process_auto_signup
from allauth.socialaccount.models import SocialAccount, SocialLogin

from apps.users.views import JWTSocialAccountAdapter, SafeSteamCallbackView


def _request(path='/accounts/steam/callback/'):
    request = RequestFactory().get(path)
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


def _steam_sociallogin(uid='76561198000000000', personaname='TestPlayer'):
    """스팀 콜백이 만들어내는 것과 같은 모양의 SocialLogin — 이메일 없음."""
    from django.contrib.auth import get_user_model

    user = get_user_model()(username=personaname)
    account = SocialAccount(
        provider='steam',
        uid=uid,
        extra_data={'steamid': uid, 'personaname': personaname},
    )
    sociallogin = SocialLogin(user=user, account=account)
    sociallogin.email_addresses = []      # 스팀 OpenID 는 이메일을 주지 않는다
    return sociallogin


class SteamAutoSignupTest(TestCase):
    """스팀 로그인은 회원가입 폼(/accounts/3rdparty/signup/)으로 빠지지 않는다."""

    def test_pre_social_login_puts_email_where_allauth_looks(self):
        request = _request()
        sociallogin = _steam_sociallogin()

        JWTSocialAccountAdapter().pre_social_login(request, sociallogin)

        self.assertEqual(len(sociallogin.email_addresses), 1)
        self.assertEqual(
            sociallogin.email_addresses[0].email,
            'steam_76561198000000000@users.hiddengem.local',
        )
        self.assertEqual(sociallogin.user.email, sociallogin.email_addresses[0].email)

    def test_auto_signup_allowed_after_adapter_hook(self):
        """핵심 회귀: 이 판정이 False 면 사용자는 회원가입 폼을 본다."""
        request = _request()
        sociallogin = _steam_sociallogin(uid='76561198000000001')

        JWTSocialAccountAdapter().pre_social_login(request, sociallogin)
        auto_signup, resp = process_auto_signup(request, sociallogin)

        self.assertTrue(auto_signup, '스팀 자동 가입이 거부됐다 — 회원가입 폼으로 빠진다')
        self.assertIsNone(resp)

    def test_without_hook_allauth_refuses_auto_signup(self):
        """왜 훅이 필요한지 고정 — user.email 만 채우면 여전히 거부된다."""
        request = _request()
        sociallogin = _steam_sociallogin(uid='76561198000000002')
        sociallogin.user.email = 'steam_76561198000000002@users.hiddengem.local'

        auto_signup, _ = process_auto_signup(request, sociallogin)

        self.assertFalse(auto_signup)

    def test_google_untouched(self):
        """구글은 provider 가 이메일을 주므로 훅이 개입하지 않는다."""
        request = _request()
        sociallogin = _steam_sociallogin(uid='1234567890')
        sociallogin.account.provider = 'google'

        JWTSocialAccountAdapter().pre_social_login(request, sociallogin)

        self.assertEqual(sociallogin.email_addresses, [])


class SteamCallbackFailureTest(TestCase):
    """스팀 API 장애·자격증명 오류가 500 으로 새지 않는다."""

    def test_route_is_our_view(self):
        match = resolve('/accounts/steam/callback/')
        self.assertIs(match.func.view_class, SafeSteamCallbackView)

    def test_reverse_path_unchanged(self):
        """return_to 값이 바뀌면 OpenID 검증이 깨진다 — 경로 문자열 고정."""
        self.assertEqual(reverse('steam_callback'), '/accounts/steam/callback/')

    def test_steam_api_error_redirects_instead_of_500(self):
        from allauth.socialaccount.providers.openid.views import OpenIDCallbackView

        class FakeResponse:
            status_code = 403

        original = OpenIDCallbackView.get

        def boom(self, request, *args, **kwargs):
            raise requests.HTTPError('403', response=FakeResponse())

        OpenIDCallbackView.get = boom
        try:
            response = SafeSteamCallbackView.as_view()(_request())
        finally:
            OpenIDCallbackView.get = original

        self.assertEqual(response.status_code, 302)
        self.assertIn('error=steam_unavailable', response['Location'])


class FrontendUrlTest(TestCase):
    """리다이렉트에 쓰는 주소에는 콤마가 들어가면 안 된다 (2026-09-07 NXDOMAIN)."""

    def test_frontend_url_is_single_origin(self):
        self.assertNotIn(',', settings.FRONTEND_URL)
        self.assertTrue(settings.FRONTEND_URL.startswith('http'))
        self.assertFalse(settings.FRONTEND_URL.endswith('/'))

    def test_frontend_urls_is_the_list(self):
        self.assertIsInstance(settings.FRONTEND_URLS, list)
        self.assertEqual(settings.FRONTEND_URLS[0], settings.FRONTEND_URL)
