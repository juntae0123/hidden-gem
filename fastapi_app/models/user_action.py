"""
UserAction SQLAlchemy ORM Model

Korean: 유저 행동 로그 ORM — Django user_actions 테이블과 동일 스키마 매핑.

Phase 1.5: 수집만
Phase 2+:  user_id 추가 + 취향 학습 시작
"""

from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class UserAction(Base):
    """
    User behavior log for taste learning.
    Korean: 취향 학습용 유저 행동 로그 — Django user_actions 테이블 매핑.

    created_at: DB DEFAULT 없음 (Django 앱 레벨 관리)
                → INSERT 시 Python에서 직접 주입
    """

    __tablename__ = "user_actions"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id     = Column(BigInteger, nullable=True, index=True)
    session_id  = Column(String(64), nullable=False, index=True)
    app_id      = Column(Integer, nullable=True, index=True)
    action_type = Column(String(30), nullable=False, index=True)
    context     = Column(JSONB, default=dict, nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False)  # INSERT 시 직접 주입

    __table_args__ = (
        Index("idx_ua_session_time", "session_id", "created_at"),
        Index("idx_ua_app_action",   "app_id",     "action_type"),
        Index("idx_ua_user_time",    "user_id",    "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserAction id={self.id} type={self.action_type} app={self.app_id}>"