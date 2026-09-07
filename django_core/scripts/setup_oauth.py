"""
OAuth Initial Setup Script (Google + Steam)
Korean: OAuth 초기 설정 (Site + SocialApp) 자동화.

사용법:
    docker exec hidden_gem_django python scripts/setup_oauth.py

필요 환경변수:
    GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
    STEAM_API_KEY  (https://steamcommunity.com/dev/apikey 에서 발급)
    SITE_DOMAIN    (운영에서만 - 미설정 시 localhost:8001)
"""
import os
import sys
import django

# Django 환경 설정
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


def setup_site():
    """
    Update Site 1 to localhost:8001.
    Korean: Site 1을 localhost:8001로 업데이트.
    """
    # 운영에서는 SITE_DOMAIN 환경변수로 지정 (예: hidden-gem.up.railway.app)
    domain = os.getenv('SITE_DOMAIN', 'localhost:8001')
    site, created = Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': domain,
            'name': 'Hidden Gem',
        }
    )
    action = 'created' if created else 'updated'
    print(f"[OK] Site {action}: {site.domain} ({site.name})")
    return site


def setup_google_app(site):
    """
    Register Google SocialApp.
    Korean: Google SocialApp 등록 + Site 연결.
    """
    client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        print("[ERROR] GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set")
        return None

    app, created = SocialApp.objects.update_or_create(
        provider='google',
        defaults={
            'name': 'Google',
            'client_id': client_id,
            'secret': client_secret,
        }
    )
    app.sites.add(site)

    action = 'created' if created else 'updated'
    print(f"[OK] Google SocialApp {action}")
    print(f"     client_id: {client_id[:20]}...")
    print(f"     sites: {[s.domain for s in app.sites.all()]}")
    return app


def setup_steam_app(site):
    """
    Register Steam SocialApp (OpenID).
    Korean: Steam SocialApp 등록.

    ⚠️ 2026-09-07 사고: 키를 client_id 에만 넣었더니 스팀 콜백이 500 이 났다.
       allauth 65.x 의 SteamOpenIDProvider.sociallogin_from_response 는
       `steam_api_key = self.app.secret` — **secret 필드**를 읽는다.
       (client_id 는 안 읽는다. 키가 빈 채로 Steam API 를 때려 403 → raise_for_status → 500)
       라이브러리가 실제로 읽는 필드에 넣는다. 두 필드 모두 채워 두는 편이 안전하다.
    """
    api_key = os.getenv('STEAM_API_KEY', '')

    if not api_key:
        print("[SKIP] STEAM_API_KEY not set — Steam login disabled")
        return None

    app, created = SocialApp.objects.update_or_create(
        provider='steam',
        defaults={
            'name': 'Steam',
            'client_id': api_key,
            'secret': api_key,   # allauth 가 읽는 쪽은 이것
        }
    )
    app.sites.add(site)

    action = 'created' if created else 'updated'
    print(f"[OK] Steam SocialApp {action}")
    print(f"     sites: {[s.domain for s in app.sites.all()]}")
    return app


if __name__ == '__main__':
    print("=" * 60)
    print("OAuth Initial Setup (Google + Steam)")
    print("=" * 60)

    site = setup_site()
    google_app = setup_google_app(site)
    steam_app = setup_steam_app(site)

    print("=" * 60)
    if google_app:
        print("[OK] Google ready")
        print("     redirect URI: http://localhost:8001/accounts/google/login/callback/")
    else:
        print("[WARNING] Check GOOGLE_CLIENT_ID/SECRET in .env")
    if steam_app:
        print("[OK] Steam ready")
        print("     login URL: http://localhost:8001/accounts/steam/login/")
    else:
        print("[WARNING] STEAM_API_KEY not set — Steam login skipped")
    print("  Test: http://localhost:3000/login")
    print("=" * 60)
