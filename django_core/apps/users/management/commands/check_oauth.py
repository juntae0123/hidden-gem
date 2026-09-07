"""
OAuth SocialApp 설정 점검 (Google / Steam).

왜 있나 — 2026-09-07 사고. 스팀 로그인 콜백이 500 이었고 원인은 코드가 아니라
DB 의 SocialApp 행이었다(secret 이 비어 있음). '설정했다'가 아니라 '라이브러리가
읽는 필드에 값이 있다'를 검사해야 한다.

    docker compose exec django python manage.py check_oauth
    railway run python manage.py check_oauth      # 운영 DB 대상

값은 절대 출력하지 않는다 — 길이와 앞 4글자만.
"""
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from allauth.socialaccount.models import SocialApp


def mask(value: str) -> str:
    if not value:
        return "(빈 값)"
    return f"{value[:4]}… (len={len(value)})"


# provider: (그 provider 가 실제로 읽는 필드들)
REQUIRED_FIELDS = {
    "google": ("client_id", "secret"),
    # allauth 65.x steam provider 는 app.secret 만 읽는다 (provider.py 참고)
    "steam": ("secret",),
}


class Command(BaseCommand):
    help = "SocialApp(Google/Steam) 자격증명이 라이브러리가 읽는 필드에 들어 있는지 점검"

    def handle(self, *args, **options):
        try:
            site = Site.objects.get_current()
            self.stdout.write(f"현재 Site: id={site.id} domain={site.domain}")
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"Site 조회 실패: {exc}"))
            site = None

        problems = 0
        for provider, fields in REQUIRED_FIELDS.items():
            apps = list(SocialApp.objects.filter(provider=provider))
            if not apps:
                self.stdout.write(self.style.WARNING(f"[{provider}] SocialApp 없음 → 로그인 불가"))
                problems += 1
                continue
            if len(apps) > 1:
                self.stdout.write(self.style.WARNING(f"[{provider}] SocialApp 이 {len(apps)}개 — allauth 가 어느 것을 쓸지 모른다"))
                problems += 1

            for app in apps:
                domains = [s.domain for s in app.sites.all()]
                self.stdout.write(f"[{provider}] id={app.pk} sites={domains}")
                self.stdout.write(f"          client_id={mask(app.client_id)}  secret={mask(app.secret)}")
                if site and site.domain not in domains:
                    self.stdout.write(self.style.ERROR(f"          현재 Site({site.domain}) 가 연결 안 됨"))
                    problems += 1
                for field in fields:
                    if not getattr(app, field, ""):
                        self.stdout.write(self.style.ERROR(f"          {field} 가 비어 있다 — 이 provider 는 {field} 를 읽는다"))
                        problems += 1

        if problems:
            self.stdout.write(self.style.ERROR(f"\n문제 {problems}건 — 위 항목을 고쳐야 로그인이 된다"))
        else:
            self.stdout.write(self.style.SUCCESS("\n이상 없음"))
