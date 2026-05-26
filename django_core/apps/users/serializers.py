# django_core/apps/users/serializers.py
"""
유저 직렬화 (User Serializers)

JWT 인증 후 프론트에 유저 정보 전달용.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    User info serializer for frontend consumption.
    Korean: 프론트 전달용 유저 정보 직렬화.
    """
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'nickname',
            'steam_id',
            'total_searches',
            'total_clicks',
            'total_ratings',
            'last_active_at',
            'date_joined',
        ]
        read_only_fields = fields