# fastapi_app/core/security.py
"""
Hidden Gem - 보안 필터
Prompt Injection, Jailbreak 시도 차단

공격 패턴:
1. 시스템 프롬프트 무시 지시
2. 역할 변경 시도
3. 악성 코드 실행 시도
4. 정보 유출 시도
"""

import re
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class SecurityCheckResult:
    """보안 검사 결과"""
    is_safe: bool
    threat_type: Optional[str] = None
    threat_details: Optional[str] = None
    sanitized_input: Optional[str] = None


class PromptInjectionFilter:
    """
    Prompt Injection 방어 필터
    
    차단 대상:
    1. 시스템 지시 무시/변경 시도
    2. 역할 탈취 시도
    3. 프롬프트 누출 시도
    4. 코드 실행 시도
    5. 다단계 주입 시도
    """
    
    # ============================================================
    # 위협 패턴 정의
    # ============================================================
    
    # 시스템 프롬프트 무시/변경 시도
    SYSTEM_OVERRIDE_PATTERNS = [
        # 영어
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
        r"disregard\s+(all\s+)?(previous|above|prior)",
        r"forget\s+(everything|all|your)\s*(instructions?|rules?|training)?",
        r"new\s+instructions?\s*:",
        r"system\s*:\s*",
        r"override\s+(system|previous|all)",
        r"bypass\s+(restrictions?|filters?|rules?)",
        r"act\s+as\s+if\s+you\s+(have\s+)?no\s+restrictions?",
        
        # 한국어
        r"이전\s*(지시|명령|규칙).*무시",
        r"(시스템|이전)\s*(프롬프트|지시).*잊어",
        r"새로운\s*지시\s*:",
        r"규칙.*무시.*해",
        r"제한.*없이.*답변",
    ]
    
    # 역할 변경 시도
    ROLE_HIJACK_PATTERNS = [
        r"you\s+are\s+(now|no longer)",
        r"pretend\s+(to\s+be|you\s+are)",
        r"act\s+as\s+(if\s+you\s+were|a)",
        r"role\s*play\s+as",
        r"from\s+now\s+on.*you\s+are",
        r"let'?s\s+play\s+a\s+game",
        r"imagine\s+you\s+are",
        
        # DAN (Do Anything Now) 공격
        r"dan\s*mode",
        r"jailbreak",
        r"do\s+anything\s+now",
        r"developer\s+mode",
        r"sudo\s+mode",
        
        # 한국어
        r"너는\s*이제.*(?:이다|야)",
        r"역할.*맡아",
        r"~인\s*척",
        r"개발자\s*모드",
    ]
    
    # 프롬프트 누출 시도
    PROMPT_LEAK_PATTERNS = [
        r"(show|tell|reveal|display|print|output)\s*(me\s+)?(your|the|system)\s*(prompt|instructions?)",
        r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?)",
        r"repeat\s+(your|the|all)\s*(system\s+)?(instructions?|prompts?)",
        r"(초기|시스템)\s*프롬프트.*알려",
        r"지시\s*내용.*보여",
    ]
    
    # 코드 실행 시도
    CODE_INJECTION_PATTERNS = [
        r"```\s*(python|javascript|bash|shell|sql|exec)",
        r"eval\s*\(",
        r"exec\s*\(",
        r"import\s+os",
        r"subprocess",
        r"__import__",
        r";\s*(rm|del|drop|delete)\s",
        r"<script",
        r"javascript:",
    ]
    
    # 다단계 주입 (Indirect Injection)
    MULTI_STAGE_PATTERNS = [
        r"\[INST\]",
        r"\[/INST\]",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"###\s*(Human|Assistant|System)\s*:",
        r"Human:",
        r"Assistant:",
        r"\n\n---\n\n",  # 구분자 삽입 시도
    ]
    
    # 민감 정보 요청
    SENSITIVE_INFO_PATTERNS = [
        r"(api|secret|password|token|key)\s*(key|word|token)?",
        r"환경\s*변수",
        r"서버\s*(정보|주소|ip)",
        r"데이터베이스\s*(정보|연결|접속)",
    ]
    
    def __init__(self):
        """패턴 컴파일"""
        self._patterns = {
            "system_override": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.SYSTEM_OVERRIDE_PATTERNS],
            "role_hijack": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.ROLE_HIJACK_PATTERNS],
            "prompt_leak": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.PROMPT_LEAK_PATTERNS],
            "code_injection": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.CODE_INJECTION_PATTERNS],
            "multi_stage": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.MULTI_STAGE_PATTERNS],
            "sensitive_info": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.SENSITIVE_INFO_PATTERNS],
        }
    
    def check(self, text: str) -> SecurityCheckResult:
        """
        텍스트 보안 검사
        
        Args:
            text: 검사할 텍스트
            
        Returns:
            SecurityCheckResult: 검사 결과
        """
        
        if not text:
            return SecurityCheckResult(is_safe=True, sanitized_input=text)
        
        # 각 카테고리 검사
        for threat_type, patterns in self._patterns.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    return SecurityCheckResult(
                        is_safe=False,
                        threat_type=threat_type,
                        threat_details=f"Pattern matched: {match.group()}",
                    )
        
        # 추가 휴리스틱 검사
        
        # 1. 비정상적으로 긴 입력
        if len(text) > 2000:
            return SecurityCheckResult(
                is_safe=False,
                threat_type="length_anomaly",
                threat_details="Input too long (>2000 chars)",
            )
        
        # 2. 특수 문자 비율 이상
        special_ratio = len(re.findall(r'[^\w\s가-힣]', text)) / max(len(text), 1)
        if special_ratio > 0.3:
            return SecurityCheckResult(
                is_safe=False,
                threat_type="special_char_anomaly",
                threat_details=f"Too many special characters ({special_ratio:.2%})",
            )
        
        # 3. 반복 패턴 감지
        if self._has_suspicious_repetition(text):
            return SecurityCheckResult(
                is_safe=False,
                threat_type="repetition_anomaly",
                threat_details="Suspicious repetition detected",
            )
        
        # 안전
        return SecurityCheckResult(
            is_safe=True,
            sanitized_input=self._sanitize(text),
        )
    
    def _has_suspicious_repetition(self, text: str) -> bool:
        """의심스러운 반복 패턴 감지"""
        # 같은 단어 5회 이상 연속
        words = text.lower().split()
        if len(words) < 5:
            return False
        
        for i in range(len(words) - 4):
            if len(set(words[i:i+5])) == 1:
                return True
        
        return False
    
    def _sanitize(self, text: str) -> str:
        """위험 요소 제거 (경미한 것만)"""
        # 코드 블록 마커 제거
        sanitized = re.sub(r'```\w*', '', text)
        
        # HTML 태그 제거
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
        
        # 연속 공백 정리
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized


# 싱글톤
prompt_injection_filter = PromptInjectionFilter()
