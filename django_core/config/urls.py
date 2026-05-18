# django_core/config/urls.py
"""
URL 라우팅 설정 (URL Routing Configuration)

Django 관리자 페이지만 노출하며, 게임 데이터 API는 FastAPI(포트 8000)에서 제공.
Django는 데이터 관리(Admin) 전용으로 사용.
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),  # Django Admin - 게임/유저 데이터 관리 페이지
]
