# fastapi_app/core/exceptions.py
"""
Hidden Gem - 커스텀 예외
"""

from typing import Optional, Dict, Any


class HiddenGemException(Exception):
    """기본 예외 클래스"""
    
    def __init__(
        self,
        message: str = "오류가 발생했습니다.",
        error_code: str = "unknown_error",
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.user_message = user_message or message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error_code": self.error_code,
            "message": self.user_message,
            "details": self.details,
        }


# 검증 관련
class QueryValidationError(HiddenGemException):
    """쿼리 검증 오류"""
    def __init__(self, message: str = "유효하지 않은 검색어입니다."):
        super().__init__(message, "query_validation_error", message)


class GameUnrelatedQueryError(HiddenGemException):
    """게임 무관 쿼리"""
    def __init__(self, message: str = "게임과 관련 없는 검색어입니다.", detected_topic: str = None):
        super().__init__(
            message,
            "game_unrelated",
            "저는 게임 추천 전문이에요! 🎮",
            {"detected_topic": detected_topic}
        )


class ProfanityDetectedError(HiddenGemException):
    """욕설 감지"""
    def __init__(self):
        super().__init__(
            "욕설이 포함된 검색어입니다.",
            "profanity_detected",
            "욕설 없이 검색해주세요 😊"
        )


# Rate Limit
class RateLimitExceededError(HiddenGemException):
    """Rate Limit 초과"""
    def __init__(self, retry_after_seconds: int = 60):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            "요청 한도 초과",
            "rate_limit_exceeded",
            f"요청이 너무 많아요. {retry_after_seconds}초 후에 다시 시도해주세요.",
            {"retry_after_seconds": retry_after_seconds}
        )


# 파싱 관련
class QueryParsingError(HiddenGemException):
    """쿼리 파싱 오류"""
    def __init__(self, message: str = "검색어를 이해하지 못했습니다."):
        super().__init__(message, "query_parsing_error", message)


class LLMServiceError(HiddenGemException):
    """LLM 서비스 오류"""
    def __init__(self, service_name: str = "LLM", error_detail: str = None):
        super().__init__(
            f"{service_name} 서비스 오류",
            "llm_service_error",
            "AI 서비스에 일시적인 문제가 있어요. 잠시 후 다시 시도해주세요.",
            {"service": service_name, "detail": error_detail}
        )


class LLMResponseInvalidError(HiddenGemException):
    """LLM 응답 무효"""
    def __init__(self, raw_response: str = None):
        super().__init__(
            "LLM 응답 파싱 실패",
            "llm_response_invalid",
            "검색어를 처리하는 중 문제가 발생했어요.",
            {"raw_response": raw_response[:200] if raw_response else None}
        )


# 검색 관련
class GameNotFoundError(HiddenGemException):
    """게임 없음"""
    def __init__(self, game_name: str = None):
        super().__init__(
            f"게임을 찾을 수 없습니다: {game_name}",
            "game_not_found",
            f"'{game_name}'을(를) 찾지 못했어요.",
            {"game_name": game_name}
        )


class NoResultsError(HiddenGemException):
    """결과 없음"""
    def __init__(self, query: str = None):
        super().__init__(
            "검색 결과가 없습니다.",
            "no_results",
            "조건에 맞는 게임을 찾지 못했어요 😢",
            {"query": query}
        )


# 유틸
def get_friendly_error_response(exc: Exception) -> Dict[str, Any]:
    """예외를 친절한 응답으로 변환"""
    if isinstance(exc, HiddenGemException):
        return exc.to_dict()
    
    return {
        "success": False,
        "error_code": "internal_error",
        "message": "알 수 없는 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
    }
