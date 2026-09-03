# django_core/apps/users/serializers.py
"""
유저 직렬화 (User Serializers)
JWT 인증 후 프론트에 유저 정보 전달용 + 온보딩 입력 검증.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    User info serializer for frontend consumption.
    Korean: 프론트 전달용 유저 정보 직렬화. 온보딩 상태/항목 포함.
    """
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'nickname',
            'gender',
            'age_group',
            'onboarding_completed',
            'steam_id',
            'total_searches',
            'total_clicks',
            'total_ratings',
            'last_active_at',
            'date_joined',
        ]
        read_only_fields = fields


class OnboardingSerializer(serializers.ModelSerializer):
    """
    Onboarding input validation (write-only).
    Korean: 온보딩 입력 검증. 필수=gender/age_group, 선택=nickname.
    이름(first_name)은 구글 로그인에서 채워지나, 폼에서 수정 허용.
    """
    first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )

    class Meta:
        model = User
        fields = ['first_name', 'nickname', 'gender', 'age_group']

    def validate_gender(self, value):
        """성별 필수 — 빈 값 거부."""
        if not value:
            raise serializers.ValidationError("성별은 필수입니다.")
        return value

    def validate_age_group(self, value):
        """나이대 필수 — 빈 값 거부."""
        if not value:
            raise serializers.ValidationError("나이대는 필수입니다.")
        return value