# fastapi_app/core/exceptions.py
"""
Hidden Gem - 커스텀 예외

비즈니스 예외는 HTTP 200으로 반환하고
error_code로 클라이언트가 구분하도록 설계
"""

from typing import Optional, Dict, Any


class HiddenGemException(Exception):
    """
    기본 예외 클래스
    
    모든 비즈니스 예외의 부모 클래스
    to_dict()로 API 응답 형식 생성
    """
    
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
        """API 응답용 딕셔너리 변환"""
        return {
            "success": False,
            "error_code": self.error_code,
            "message": self.user_message,
            "details": self.details,
        }


# ============================================================
# 검증 관련 예외
# ============================================================

class QueryValidationError(HiddenGemException):
    """쿼리 검증 오류"""
    def __init__(self, message: str = "유효하지 않은 검색어입니다.", suggestion: str = None):
        details = {"suggestion": suggestion} if suggestion else {}
        super().__init__(
            message=message,
            error_code="query_validation_error",
            user_message=message,
            details=details
        )


class GameUnrelatedQueryError(HiddenGemException):
    """게임 무관 쿼리"""
    def __init__(
        self, 
        message: str = "게임과 관련 없는 검색어입니다.", 
        detected_topic: str = None
    ):
        super().__init__(
            message=message,
            error_code="game_unrelated",
            user_message="저는 게임 추천 전문이에요! 🎮 어떤 게임을 찾으시나요?",
            details={"detected_topic": detected_topic}
        )


class ProfanityDetectedError(HiddenGemException):
    """욕설 감지"""
    def __init__(self):
        super().__init__(
            message="욕설이 포함된 검색어입니다.",
            error_code="profanity_detected",
            user_message="욕설 없이 검색해주세요 😊"
        )


# ============================================================
# Rate Limit 관련 예외
# ============================================================

class RateLimitExceededError(HiddenGemException):
    """Rate Limit 초과"""
    def __init__(self, retry_after_seconds: int = 60):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            message="요청 한도 초과",
            error_code="rate_limit_exceeded",
            user_message=f"요청이 너무 많아요. {retry_after_seconds}초 후에 다시 시도해주세요.",
            details={"retry_after_seconds": retry_after_seconds}
        )


# ============================================================
# 파싱 관련 예외
# ============================================================

class QueryParsingError(HiddenGemException):
    """쿼리 파싱 오류"""
    def __init__(self, message: str = "검색어를 이해하지 못했습니다."):
        super().__init__(
            message=message,
            error_code="query_parsing_error",
            user_message=message
        )


class LLMServiceError(HiddenGemException):
    """LLM 서비스 오류"""
    def __init__(self, service_name: str = "LLM", error_detail: str = None):
        super().__init__(
            message=f"{service_name} 서비스 오류: {error_detail}",
            error_code="llm_service_error",
            user_message="AI 서비스에 일시적인 문제가 있어요. 잠시 후 다시 시도해주세요.",
            details={"service": service_name, "detail": error_detail}
        )


class LLMResponseInvalidError(HiddenGemException):
    """LLM 응답 무효"""
    def __init__(self, raw_response: str = None):
        super().__init__(
            message="LLM 응답 파싱 실패",
            error_code="llm_response_invalid",
            user_message="검색어를 처리하는 중 문제가 발생했어요.",
            details={"raw_response": raw_response[:200] if raw_response else None}
        )


# ============================================================
# 검색 관련 예외
# ============================================================

class GameNotFoundError(HiddenGemException):
    """게임 없음"""
    def __init__(self, game_name: str = None):
        super().__init__(
            message=f"게임을 찾을 수 없습니다: {game_name}",
            error_code="game_not_found",
            user_message=f"'{game_name}'을(를) 찾지 못했어요.",
            details={"game_name": game_name}
        )


class NoResultsError(HiddenGemException):
    """결과 없음"""
    def __init__(self, query: str = None, suggestions: list = None):
        super().__init__(
            message="검색 결과가 없습니다.",
            error_code="no_results",
            user_message="조건에 맞는 게임을 찾지 못했어요 😢",
            details={
                "query": query,
                "suggestions": suggestions or ["다른 키워드로 검색해보세요"]
            }
        )


# ============================================================
# 데이터베이스 관련 예외
# ============================================================

class DatabaseError(HiddenGemException):
    """데이터베이스 오류"""
    def __init__(self, operation: str = "query", detail: str = None):
        super().__init__(
            message=f"Database {operation} failed: {detail}",
            error_code="database_error",
            user_message="데이터 처리 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.",
            details={"operation": operation}
        )


# ============================================================
# 유틸리티 함수
# ============================================================

def get_friendly_error_response(exc: Exception) -> Dict[str, Any]:
    """
    예외를 친절한 API 응답으로 변환
    
    Args:
        exc: Exception 객체
        
    Returns:
        API 응답용 딕셔너리
    """
    # HiddenGemException 계열은 to_dict() 사용
    if isinstance(exc, HiddenGemException):
        return exc.to_dict()
    
    # 알 수 없는 예외는 일반 메시지
    return {
        "success": False,
        "error_code": "internal_error",
        "message": "알 수 없는 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
        "details": {
            "type": type(exc).__name__,
            # 프로덕션에서는 detail 제거 고려
        }
    }
