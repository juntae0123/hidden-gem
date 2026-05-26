"""
Google OAuth Initial Setup Script
Korean: Google OAuth 초기 설정 (Site + SocialApp) 자동화.

사용법:
    docker exec hidden_gem_django python scripts/setup_oauth.py
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
    site, created = Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': 'localhost:8001',
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


if __name__ == '__main__':
    print("=" * 60)
    print("Google OAuth Initial Setup")
    print("=" * 60)

    site = setup_site()
    app = setup_google_app(site)

    print("=" * 60)
    if app:
        print("[SUCCESS] Setup complete!")
        print("")
        print("Next steps:")
        print("  1. Check Google Cloud Console redirect URI:")
        print("     http://localhost:8001/accounts/google/login/callback/")
        print("  2. Test login:")
        print("     http://localhost:3000/login")
    else:
        print("[WARNING] Check GOOGLE_CLIENT_ID/SECRET in .env")
    print("=" * 60)
