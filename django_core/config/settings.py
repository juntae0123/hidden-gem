# django_core/config/settings.py
"""
Hidden Gem - Django 설정

v2 → v3 변경사항:
    - SOCIALACCOUNT_PROVIDERS APP 제거 (DB SocialApp만 사용)
    - MultipleObjectsReturned 에러 해결
"""

from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / '.env')

# DEBUG 기본값은 False - 환경변수를 깜빡한 운영 배포가 디버그 모드로 뜨는 사고 방지
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-secret-key-12345'  # 로컬 개발 전용
    else:
        # JWT 서명키가 기본값으로 운영에 뜨면 토큰 위조가 가능해짐 - 기동 자체를 거부
        raise RuntimeError('DJANGO_SECRET_KEY must be set when DEBUG=False')
if DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']
else:
    ALLOWED_HOSTS = [
        h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'rest_framework_simplejwt.token_blacklist',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'import_export',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.openid',   # steam provider 의존성
    'allauth.socialaccount.providers.steam',
    'apps.games',
    'apps.users',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'hidden_gem_db'),
        'USER': os.getenv('DB_USER', 'juntae'),
        'PASSWORD': os.getenv('DB_PASSWORD', '0312'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'users.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== DRF ====================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ==================== JWT ====================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,    # 추가 - 회전 후 이전 토큰 무효화
    'UPDATE_LAST_LOGIN': True,            #  추가 - 마지막 로그인 시간 기록
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ==================== django-allauth ====================
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# allauth 65.x 설정 (deprecated 경고 제거)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Google SocialApp은 Django Admin에서 DB로 관리
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'FETCH_USERINFO': True,
    }
}

SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True

# 핵심 수정: LOGIN_REDIRECT_URL은 반드시 '/' !!!
# 절대 '/api/auth/google/callback/'으로 하면 안 됨 (redirect_uri 망가짐)
LOGIN_REDIRECT_URL = '/'

# JWT 발급 어댑터
ACCOUNT_ADAPTER = 'apps.users.views.JWTAccountAdapter' 
SOCIALACCOUNT_ADAPTER = 'apps.users.views.JWTSocialAccountAdapter'

# 프런트 주소. 운영에서는 콤마로 여러 개(운영 도메인 + www)를 줄 수 있고, 그 값이 그대로
# CORS/CSRF 화이트리스트가 된다 (아래 참조).
#
# ⚠️ 2026-09-07 사고: 리다이렉트(OAuth 콜백 → 프런트)에 이 값을 **그대로** 쓰면
#    `https://a.com,https://b.com/auth/callback` 이 되어 DNS_PROBE_FINISHED_NXDOMAIN 이 난다.
#    목록은 화이트리스트용(FRONTEND_URLS), 리다이렉트는 **첫 항목**(FRONTEND_URL)만 쓴다.
FRONTEND_URLS = [
    o.strip().rstrip('/') for o in os.getenv('FRONTEND_URL', 'http://localhost:3000').split(',') if o.strip()
]
FRONTEND_URL = FRONTEND_URLS[0] if FRONTEND_URLS else 'http://localhost:3000'

# ==================== 보안 헤더 (운영 전용) / Security Headers ====================
# 개발(DEBUG=True)에서는 HTTPS가 없으므로 전부 비활성.
# 운영에서는 Railway가 HTTPS를 종단 처리하므로 프록시 헤더를 신뢰한다.
if not DEBUG:
    # 프록시(Railway) 뒤에서 HTTPS 여부 판별 / Trust proxy's protocol header
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # HTTP 요청을 HTTPS로 리다이렉트 / Force HTTPS
    SECURE_SSL_REDIRECT = True
    # 쿠키를 HTTPS에서만 전송 / Cookies over HTTPS only
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # 크로스사이트 OAuth 콜백에 세션/CSRF 쿠키가 실리도록 SameSite=None
    # Google→Django 콜백은 외부발 top-level redirect라 Lax(기본)면 쿠키가 안 실려 state 검증 실패
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"
    # JS에서 세션 쿠키 접근 차단 (XSS 완화) / Block JS access to session cookie
    SESSION_COOKIE_HTTPONLY = True
    # HSTS — 브라우저가 이 도메인은 항상 HTTPS로만 접속 / HTTP Strict Transport Security
    SECURE_HSTS_SECONDS = 31536000          # 1년
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # MIME 스니핑 차단 / Prevent MIME type sniffing
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # 클릭재킹 방어 (iframe 삽입 차단) / Clickjacking protection
    X_FRAME_OPTIONS = 'DENY'
    # 리퍼러 최소 노출 / Limit referrer leakage
    SECURE_REFERRER_POLICY = 'same-origin'
    
# ==================== CORS (보안 강화) ====================
# v3 → v4: CORS_ALLOW_ALL_ORIGINS 제거, 도메인 화이트리스트 사용

if DEBUG:
    # 개발 환경: localhost만 허용
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
else:
    # 운영: FRONTEND_URL 콤마 구분 다중 허용 + Vercel 프리뷰 정규식
    CORS_ALLOWED_ORIGINS = list(FRONTEND_URLS)   # 화이트리스트는 목록 전체
    # 2026-09-07: `.*\.vercel\.app` 은 남의 Vercel 앱도 전부 허용했다. 세션 쿠키가 SameSite=None 이라
    # 관리자가 로그인한 채 악성 vercel.app 페이지를 열면 그 페이지가 admin 응답을 읽을 수 있다.
    # 이 프로젝트의 프리뷰 URL(hidden-gem-*.vercel.app)만 허용한다.
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://hidden-gem[a-z0-9-]*\.vercel\.app$"]

# 쿠키/JWT 함께 사용하려면 필수
CORS_ALLOW_CREDENTIALS = True

# 허용 HTTP 메서드 (명시적)
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# 허용 헤더 (명시적)
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# CSRF 보안 (allauth 콜백 도메인)
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS + [
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]

# ==================== 기타 ====================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

GPT_MODELS = {
    'original':     'gpt-5.4',
    'fewshot_mini': 'gpt-4o-mini',
    'embedding':    'text-embedding-3-small',
}

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# ==================== 로깅 ====================
# ⚠️ 2026-09-07 사고: 스팀 로그인 콜백이 500 이 났는데 Railway 로그에 아무것도 안 남았다.
#    Django 기본 LOGGING 은 console 핸들러에 require_debug_true 필터가 걸려 있어서
#    DEBUG=False(운영)에서는 트레이스백을 어디에도 출력하지 않는다(메일 핸들러만 붙는다).
#    → 운영에서 500 의 원인을 보려면 stdout 핸들러를 직접 붙여야 한다.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'formatter': 'plain',
        },
    },
    'root': {
        'handlers': ['stdout'],
        'level': 'INFO',
    },
    'loggers': {
        # 500 트레이스백. DEBUG 여부와 무관하게 항상 stdout 으로.
        'django.request': {
            'handlers': ['stdout'],
            'level': 'ERROR',
            'propagate': False,
        },
        # 액세스 로그는 gunicorn 이 이미 찍으므로 중복 방지
        'django.server': {
            'handlers': ['stdout'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['stdout'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
