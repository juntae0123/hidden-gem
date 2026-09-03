# fastapi_app/services/query_validator.py
"""
Hidden Gem - 쿼리 검증기 (프로덕션 레벨)

Features:
1. 한국어/영어 욕설 100개+ 패턴
2. 변형 욕설 감지 (ㅅㅂ, 시1발, s1bal 등)
3. 게임 무관 쿼리 필터링
4. 스팸/도배 감지
5. Prompt Injection 방어 연동
"""

import re
from typing import Optional, List, Set
from dataclasses import dataclass
from enum import Enum

from core.security import prompt_injection_filter


class ValidationResult(str, Enum):
    """검증 결과"""
    VALID = "valid"
    EMPTY = "empty"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    PROFANITY = "profanity"
    IRRELEVANT = "irrelevant"
    SPAM = "spam"
    SECURITY_BLOCKED = "security_blocked"


@dataclass
class ValidationResponse:
    """검증 응답"""
    is_valid: bool
    result: ValidationResult
    message: str
    suggestion: Optional[str] = None
    sanitized_query: Optional[str] = None


class QueryValidator:
    """
    프로덕션 레벨 쿼리 검증기
    """
    
    # ============================================================
    # 한국어 욕설 패턴 (변형 포함)
    # ============================================================
    KOREAN_PROFANITY = [
        # 시발 계열
        r'[시씨쉬슈스][바빠발벌팔펄불뻘][ㄹ래럴놈년]?',
        r'ㅅ[ㅂㅃ]',
        r'ㅆ[ㅂㅃ]',
        r'시[0-9]?발',
        r'씨[0-9]?발',
        r'씨[0-9]?팔',
        r'시[0-9]?팔',
        r'씹',
        r'좆|줫|졷',
        
        # 병신 계열
        r'[병뼝븅빙][신싄씬]',
        r'ㅂ[ㅅㅆ]',
        r'병[0-9]?신',
        r'멍청이',
        r'바보',
        r'븅신',
        r'빙신',
        
        # 새끼 계열
        r'[새섀쌔][끼키기꺄캬]',
        r'ㅅㄲ',
        r'색[히끼]',
        r'개[새섀쌔]끼',
        r'개[새섀쌔][0-9]?끼',
        
        # 지랄 계열
        r'[지니][랄럴롤뢀]',
        r'ㅈㄹ',
        r'지[0-9]?랄',
        
        # 개- 접두사 (욕설 강조)
        r'개[같갓갘]은',
        r'개[꼴곬]',
        r'개[소쏘][리]',
        r'개[년늠놈]',
        r'개[쓰레기]',
        r'개[돼지]',
        r'개[병빙][신싄]',
        
        # 년/놈
        r'[니너][년놈]',
        r'[미친][년놈]',
        r'[씹][년놈]',
        r'[걸레]',
        
        # 엿/염병
        r'[엿옃][먹머][어억]',
        r'[염옘][병뼝]',
        r'[엿옃][같갓]',
        
        # 닥쳐/꺼져
        r'[닥닭][[쳐처]',
        r'[꺼꺼져][져저]',
        r'[입닥][다물어]',
        
        # 존나/개나
        r'[존졸쫀][나낰]',
        r'ㅈㄴ',
        r'존[0-9]?나',
        
        # 미친
        r'[미띠][친틴씬]',
        r'ㅁㅊ',
        r'미[0-9]?친',
        r'또[라랑]이',
        r'돌[아았]이',
        r'정[신싄]병',
        r'정신[이]?나[간갔]',
        
        # 꼬추/자지/보지
        r'[꼬꼬][추츄]',
        r'[자쟈][지즤]',
        r'[보뽀][지즤]',
        r'[음정]핵',
        r'[고환불알]',
        
        # 기타
        r'[애에][미]',
        r'[느금][마]',
        r'[니애비]',
        r'[니에미]',
        r'[니애미]',
        r'[느개비]',
        r'[한남][충]',
        r'[김치][녀년]',
        r'[틀딱]',
        r'[급식충]',
        r'[노답]',
        r'[또라이]',
    ]
    
    # ============================================================
    # 영어 욕설 패턴
    # ============================================================
    ENGLISH_PROFANITY = [
        # F-word 계열
        r'\bf+u+c+k+\w*',
        r'\bf+[uv]+[ck]+\w*',
        r'\bfk+\b',
        r'\bfuk\w*',
        r'\bfvck\w*',
        r'\bph+u+c*k*\w*',
        r'\bfcuk\w*',
        r'\bf\*+[ck]\w*',
        
        # S-word
        r'\bs+h+[i1]+t+\w*',
        r'\bsh\*+t\w*',
        r'\bsht\b',
        r'\b5h1t\w*',
        
        # B-word
        r'\bb+[i1]+t+c+h+\w*',
        r'\bb\*+tch\w*',
        r'\bbiatch\w*',
        
        # A-word
        r'\ba+s+s+h+o+l+e+\w*',
        r'\ba+s+s+\b',
        r'\bass\w*',
        
        # D-word
        r'\bd+[i1]+c+k+\w*',
        r'\bd\*+ck\w*',
        
        # C-word
        r'\bc+u+n+t+\w*',
        
        # 기타
        r'\bdamn\w*',
        r'\bbastard\w*',
        r'\bmoron\w*',
        r'\bidiot\w*',
        r'\bstfu\b',
        r'\bwtf\b',
        r'\bstupid\w*',
        r'\bdumbass\w*',
        r'\bjackass\w*',
        r'\bpussy\w*',
        r'\bcock\w*',
        r'\bwh+ore\w*',
        r'\bslut\w*',
        r'\bretard\w*',
        r'\bn+[i1]+g+[gae]+[r]?\w*',  # N-word (심각)
        r'\bfag+[got]*\w*',
    ]
    
    # ============================================================
    # 게임 관련 키워드
    # ============================================================
    GAME_KEYWORDS = {
        # 직접적인 게임 언급
        '게임', '추천', '플레이', '스팀', 'steam', '닌텐도', 'nintendo',
        '플스', 'playstation', '엑박', 'xbox', 'pc게임', '모바일게임',
        
        # 장르
        '인디', 'indie', '액션', 'action', 'rpg', '롤플레잉',
        '퍼즐', 'puzzle', '어드벤처', 'adventure', '시뮬', 'simulation',
        '로그라이크', 'roguelike', '로그라이트', 'roguelite',
        '메트로베니아', 'metroidvania', '소울라이크', 'soulslike',
        '플랫포머', 'platformer', '슈터', 'shooter', 'fps', 'tps',
        '전략', 'strategy', 'rts', '턴제', 'turn-based',
        '생존', 'survival', '샌드박스', 'sandbox', '오픈월드', 'open world',
        '호러', 'horror', '공포', '스릴러', 'thriller',
        '힐링', '감성', '코지', 'cozy', '캐주얼', 'casual',
        '하드코어', 'hardcore', '협동', 'coop', '멀티', 'multiplayer',
        
        # 게임 요소
        '스토리', 'story', '그래픽', 'graphics', '사운드', 'ost',
        '타격감', '전투', 'combat', '보스', 'boss', '던전', 'dungeon',
        '퀘스트', 'quest', '레벨', 'level', '스킬', 'skill',
        '아이템', 'item', '장비', 'equipment', '캐릭터', 'character',
        
        # 게임명 (인기 게임)
        'hades', '하데스', 'stardew', '스타듀', 'hollow knight', '할로우',
        'celeste', '셀레스트', 'undertale', '언더테일', 'terraria', '테라리아',
        'elden ring', '엘든링', 'dark souls', '다크소울',
        'minecraft', '마인크래프트', '마크',
    }
    
    # ============================================================
    # 게임 무관 패턴
    # ============================================================
    IRRELEVANT_PATTERNS = [
        # 날씨
        r'오늘\s*날씨', r'내일\s*날씨', r'weather',
        r'비\s*(오|올|와)', r'눈\s*(오|올|와)',
        
        # 음식/요리
        r'맛집', r'레시피', r'recipe', r'요리\s*법',
        r'뭐\s*먹', r'배고[파프]', r'식당', r'카페',
        
        # 주식/경제
        r'주식', r'코인', r'비트코인', r'투자',
        r'stock', r'bitcoin', r'crypto',
        
        # 코딩/개발 (게임 개발 제외)
        r'파이썬', r'자바스크립트', r'python', r'javascript',
        r'코딩\s*(하|배우|공부)', r'프로그래밍\s*(하|배우)',
        r'에러\s*(났|뜨|해결)', r'버그\s*(났|뜨|해결)',
        
        # 쇼핑
        r'어디서\s*사', r'얼마[야에]', r'가격',
        r'구매', r'구입', r'주문',
        
        # 여행
        r'여행\s*(가|갈|추천)', r'비행기', r'호텔',
        r'travel', r'flight', r'hotel',
        
        # 연예/가십
        r'아이돌', r'연예인', r'드라마',
        r'웹툰', r'만화\s*추천',
        
        # 학업/시험
        r'시험', r'공부', r'숙제', r'과제',
        r'대학', r'취업', r'면접',
        
        # 건강/의료
        r'아[파픈]', r'병원', r'약국',
        r'증상', r'치료', r'의사',
        
        # 뉴스/정치 (민감)
        r'대통령', r'정치', r'선거',
        r'국회', r'정부', r'뉴스',
        
        # 종교 (단, "신작"은 게임 관련)
        r'교회\s*가', r'절\s*가', r'성당\s*가',
        r'기도', r'예배', r'하나님', r'부처님',
        r'종교\s*(가입|추천)',
    ]
    
    # ============================================================
    # 스팸/도배 패턴
    # ============================================================
    SPAM_PATTERNS = [
        r'(.)\1{5,}',  # 같은 문자 6회 이상 반복
        r'(..)\1{4,}',  # 같은 2글자 5회 이상 반복
        r'(ㅋ|ㅎ|ㅠ|ㅜ|ㄱ){7,}',  # 자음 7회 이상
        r'(\d{3,}-?){3,}',  # 전화번호 패턴
        r'https?://\S{50,}',  # 긴 URL
        r'[A-Z]{10,}',  # 대문자 10개 이상 연속
    ]
    
    def __init__(self):
        """패턴 컴파일"""
        self._korean_profanity_re = [
            re.compile(p, re.IGNORECASE) for p in self.KOREAN_PROFANITY
        ]
        self._english_profanity_re = [
            re.compile(p, re.IGNORECASE) for p in self.ENGLISH_PROFANITY
        ]
        self._irrelevant_re = [
            re.compile(p, re.IGNORECASE) for p in self.IRRELEVANT_PATTERNS
        ]
        self._spam_re = [
            re.compile(p) for p in self.SPAM_PATTERNS
        ]
        self._game_keywords_lower = {kw.lower() for kw in self.GAME_KEYWORDS}
    
    def validate(self, query: str) -> ValidationResponse:
        """
        쿼리 검증 메인 함수
        
        검증 순서:
        1. 빈 문자열 체크
        2. 길이 체크
        3. 보안 체크 (Prompt Injection)
        4. 스팸 체크
        5. 욕설 체크 (정제 시도)
        6. 게임 관련성 체크
        """
        
        # 1. 빈 문자열
        if not query or not query.strip():
            return ValidationResponse(
                is_valid=False,
                result=ValidationResult.EMPTY,
                message="검색어를 입력해주세요.",
                suggestion="예: '힐링 게임 추천', 'Hades 같은 거'"
            )
        
        query = query.strip()
        
        # 2. 길이 체크
        if len(query) < 2:
            return ValidationResponse(
                is_valid=False,
                result=ValidationResult.TOO_SHORT,
                message="검색어가 너무 짧아요.",
                suggestion="2글자 이상 입력해주세요."
            )
        
        if len(query) > 500:
            return ValidationResponse(
                is_valid=False,
                result=ValidationResult.TOO_LONG,
                message="검색어가 너무 길어요.",
                suggestion="500자 이내로 입력해주세요."
            )
        
        # 3. 보안 체크
        security_check = prompt_injection_filter.check(query)
        if not security_check.is_safe:
            return ValidationResponse(
                is_valid=False,
                result=ValidationResult.SECURITY_BLOCKED,
                message="유효하지 않은 검색어입니다.",
                suggestion="일반적인 검색어로 다시 시도해주세요."
            )
        
        # 4. 스팸 체크
        if self._is_spam(query):
            return ValidationResponse(
                is_valid=False,
                result=ValidationResult.SPAM,
                message="스팸으로 감지되었습니다.",
                suggestion="정상적인 검색어를 입력해주세요."
            )
        
        # 5. 욕설 체크
        profanity_found, sanitized = self._check_and_sanitize_profanity(query)
        
        if profanity_found:
            # 정제 후에도 의미 있는 내용이 있는지 확인
            if len(sanitized.strip()) < 2:
                return ValidationResponse(
                    is_valid=False,
                    result=ValidationResult.PROFANITY,
                    message="욕설 없이 검색해주세요 😊",
                    suggestion="예: '재밌는 게임 추천'"
                )
            
            # 정제된 쿼리로 계속 진행
            query = sanitized
        
        # 6. 게임 관련성 체크
        is_irrelevant = self._is_irrelevant(query)
        has_game_keyword = self._has_game_keyword(query)
        
        # "신작 게임" 같은 경우 게임 관련으로 처리
        if is_irrelevant and not has_game_keyword:
            # "신작", "신비한" 등은 게임 문맥에서 허용
            if not self._is_game_context(query):
                return ValidationResponse(
                    is_valid=False,
                    result=ValidationResult.IRRELEVANT,
                    message="저는 게임 추천 전문이에요! 🎮",
                    suggestion="어떤 게임을 찾으시나요?"
                )
        
        # 유효한 쿼리
        return ValidationResponse(
            is_valid=True,
            result=ValidationResult.VALID,
            message="유효한 검색어",
            sanitized_query=query
        )
    
    def _is_spam(self, text: str) -> bool:
        """스팸 여부 확인"""
        return any(p.search(text) for p in self._spam_re)
    
    def _check_and_sanitize_profanity(self, text: str) -> tuple:
        """
        욕설 체크 및 정제
        
        Returns:
            (욕설_발견_여부, 정제된_텍스트)
        """
        found = False
        sanitized = text
        
        # 한국어 욕설
        for pattern in self._korean_profanity_re:
            if pattern.search(sanitized):
                found = True
                sanitized = pattern.sub('', sanitized)
        
        # 영어 욕설
        for pattern in self._english_profanity_re:
            if pattern.search(sanitized):
                found = True
                sanitized = pattern.sub('', sanitized)
        
        # 정리
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return found, sanitized
    
    def _is_irrelevant(self, text: str) -> bool:
        """게임 무관 여부"""
        return any(p.search(text) for p in self._irrelevant_re)
    
    def _has_game_keyword(self, text: str) -> bool:
        """게임 키워드 포함 여부"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self._game_keywords_lower)
    
    def _is_game_context(self, text: str) -> bool:
        """
        게임 문맥인지 확인
        
        예: "신작 게임", "신비한 분위기 게임" → True
             "하나님을 믿으세요" → False
        """
        game_context_patterns = [
            r'신작.{0,5}(게임|인디|출시)',
            r'신비.{0,5}(게임|분위기|세계)',
            r'새로운.{0,5}게임',
            r'최신.{0,5}게임',
        ]
        
        for pattern in game_context_patterns:
            if re.search(pattern, text):
                return True
        
        return False


# 싱글톤
query_validator = QueryValidator()
