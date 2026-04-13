
# fastapi_app/services/fallback_handler.py
"""
Hidden Gem - 폴백 핸들러 (프로덕션 레벨)

Features:
1. 인기 게임 15개+
2. 게임명 교정 50개+
3. Levenshtein 거리 기반 유사 이름 추천
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class FallbackGame:
    """추천 게임"""
    app_id: int
    name: str
    genres: str
    reason: str


@dataclass
class FallbackResponse:
    """폴백 응답"""
    fallback_type: str
    message: str
    suggestion: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    corrected_name: Optional[str] = None
    similar_names: List[str] = field(default_factory=list)
    recommended_games: List[FallbackGame] = field(default_factory=list)


# ============================================================
# 인기 게임 데이터베이스 (15개+)
# ============================================================

POPULAR_GAMES: List[FallbackGame] = [
    # 액션/로그라이크
    FallbackGame(1145360, "Hades", "액션, 로그라이크", "타격감과 스토리의 완벽한 조화"),
    FallbackGame(250900, "The Binding of Isaac: Rebirth", "액션, 로그라이크", "중독성 강한 로그라이크"),
    FallbackGame(588650, "Dead Cells", "액션, 로그라이크", "쾌적한 액션의 정수"),
    
    # 힐링/시뮬
    FallbackGame(413150, "Stardew Valley", "시뮬레이션, 농사", "힐링 농사 게임의 대명사"),
    FallbackGame(824600, "DAVE THE DIVER", "어드벤처, 시뮬", "낮에는 다이빙, 밤에는 초밥집"),
    
    # 메트로배니아
    FallbackGame(367520, "Hollow Knight", "액션, 메트로배니아", "우울한 아름다움의 걸작"),
    FallbackGame(387290, "Ori and the Blind Forest", "플랫포머, 메트로배니아", "감동적인 비주얼 명작"),
    
    # 플랫포머
    FallbackGame(504230, "Celeste", "플랫포머", "정밀 플랫포머의 걸작"),
    FallbackGame(268910, "Cuphead", "액션, 플랫포머", "1930년대 카툰풍 슈팅"),
    
    # 샌드박스/서바이벌
    FallbackGame(105600, "Terraria", "샌드박스, 어드벤처", "무한한 자유도의 2D 세계"),
    FallbackGame(892970, "Valheim", "서바이벌, 협동", "바이킹 테마 협동 서바이벌"),
    
    # RPG/스토리
    FallbackGame(391540, "Undertale", "RPG", "선택이 중요한 감동 RPG"),
    FallbackGame(1817070, "Baldur's Gate 3", "RPG, 턴제", "역대급 CRPG"),
    FallbackGame(1245620, "ELDEN RING", "액션 RPG", "광활한 오픈월드 소울라이크"),
    
    # 전략/관리
    FallbackGame(294100, "RimWorld", "시뮬레이션, 전략", "우주 식민지 관리 시뮬"),
    FallbackGame(427520, "Factorio", "자동화, 전략", "공장 자동화의 끝판왕"),
]


# ============================================================
# 게임명 교정 사전 (50개+)
# ============================================================

GAME_NAME_CORRECTIONS: Dict[str, str] = {
    # Hades
    "하데스": "Hades", "헤이데스": "Hades", "해이디스": "Hades",
    "하데스2": "Hades II", "하데스 2": "Hades II",
    
    # Stardew Valley
    "스타듀": "Stardew Valley", "스타듀밸리": "Stardew Valley",
    "스타듀 밸리": "Stardew Valley", "스듀": "Stardew Valley",
    "스타듀벨리": "Stardew Valley",
    
    # Hollow Knight
    "할로우나이트": "Hollow Knight", "할로우 나이트": "Hollow Knight",
    "홀로나이트": "Hollow Knight", "홀로우나이트": "Hollow Knight",
    "할나": "Hollow Knight",
    
    # Celeste
    "셀레스트": "Celeste", "셀레스테": "Celeste", "셀레": "Celeste",
    
    # Dead Cells
    "데드셀": "Dead Cells", "데드셀즈": "Dead Cells",
    "데드 셀": "Dead Cells", "데셀": "Dead Cells",
    
    # Undertale
    "언더테일": "Undertale", "언더테이블": "Undertale", "언테": "Undertale",
    
    # Terraria
    "테라리아": "Terraria", "테라": "Terraria",
    
    # Dark Souls
    "다크소울": "Dark Souls", "다크 소울": "Dark Souls",
    "닼소": "Dark Souls", "다소": "Dark Souls",
    "다크소울3": "Dark Souls III", "다크소울 3": "Dark Souls III",
    
    # Elden Ring
    "엘든링": "ELDEN RING", "엘든 링": "ELDEN RING",
    "엘든": "ELDEN RING", "엘링": "ELDEN RING",
    
    # Sekiro
    "세키로": "Sekiro", "쎄키로": "Sekiro",
    
    # Cuphead
    "컵헤드": "Cuphead", "컵 헤드": "Cuphead",
    
    # The Binding of Isaac
    "아이작": "The Binding of Isaac", "이삭": "The Binding of Isaac",
    "아이작의 번제": "The Binding of Isaac",
    
    # Slay the Spire
    "슬레이더스파이어": "Slay the Spire", "슬더스": "Slay the Spire",
    "슬레이 더 스파이어": "Slay the Spire",
    
    # Vampire Survivors
    "뱀서": "Vampire Survivors", "뱀파이어서바이버": "Vampire Survivors",
    "뱀파이어 서바이버즈": "Vampire Survivors",
    
    # Disco Elysium
    "디스코엘리시움": "Disco Elysium", "디엘": "Disco Elysium",
    
    # Risk of Rain
    "리스크오브레인": "Risk of Rain 2", "리오레": "Risk of Rain 2",
    
    # Portal
    "포탈": "Portal", "포탈2": "Portal 2", "포털": "Portal",
    
    # Minecraft
    "마인크래프트": "Minecraft", "마크": "Minecraft",
    
    # Subnautica
    "서브노티카": "Subnautica", "섭노티카": "Subnautica",
    
    # Valheim
    "발하임": "Valheim", "발헤임": "Valheim",
    
    # Deep Rock Galactic
    "딥락": "Deep Rock Galactic", "딥락갤럭틱": "Deep Rock Galactic",
    
    # It Takes Two
    "잇테이크투": "It Takes Two", "잇테익투": "It Takes Two",
    
    # Overcooked
    "오버쿡": "Overcooked", "오버쿡드": "Overcooked",
    
    # Don't Starve
    "돈스타브": "Don't Starve", "돈스": "Don't Starve",
    
    # RimWorld
    "림월드": "RimWorld", "림 월드": "RimWorld",
    
    # Factorio
    "팩토리오": "Factorio", "펙토리오": "Factorio",
    
    # Balatro
    "발라트로": "Balatro",
    
    # Lethal Company
    "리썰컴퍼니": "Lethal Company", "리썰 컴퍼니": "Lethal Company",
}


class FallbackHandler:
    """폴백 핸들러"""
    
    def __init__(self):
        self.popular_games = POPULAR_GAMES
        self.corrections = GAME_NAME_CORRECTIONS
    
    def handle_empty_results(
        self,
        original_query: str,
        strict_conditions: Optional[List[str]] = None,
    ) -> FallbackResponse:
        """검색 결과 없음"""
        
        suggestions = []
        if strict_conditions:
            suggestions.append(f"'{', '.join(strict_conditions[:2])}' 조건을 완화해보세요")
        
        suggestions.extend([
            "다른 키워드로 검색해보세요!",
            "예: '힐링 게임', 'Hades 같은 거'",
        ])
        
        # 쿼리에 맞는 추천
        recommended = self._get_relevant_games(original_query)
        
        return FallbackResponse(
            fallback_type="empty_results",
            message="조건에 맞는 게임을 찾지 못했어요 😢",
            suggestion=suggestions[0] if suggestions else None,
            suggestions=suggestions,
            recommended_games=recommended,
        )
    
    def handle_game_not_found(self, game_name: str) -> FallbackResponse:
        """게임 찾기 실패"""
        
        # 1. 교정 시도
        corrected = self._try_correct(game_name)
        if corrected:
            return FallbackResponse(
                fallback_type="name_corrected",
                message=f"'{game_name}' → '{corrected}'로 검색할게요!",
                corrected_name=corrected,
            )
        
        # 2. 유사 이름 추천
        similar = self._find_similar_names(game_name)
        if similar:
            return FallbackResponse(
                fallback_type="similar_names",
                message=f"'{game_name}'을(를) 찾지 못했어요",
                suggestion=f"혹시 '{similar[0]}'을(를) 찾으셨나요?",
                similar_names=similar,
            )
        
        # 3. 일반 추천
        return FallbackResponse(
            fallback_type="game_not_found",
            message=f"'{game_name}'을(를) 찾지 못했어요",
            suggestions=[
                "정확한 영문 게임명으로 검색해보세요",
                "또는 '액션 로그라이크' 같이 장르로 검색해보세요",
            ],
            recommended_games=self.popular_games[:5],
        )
    
    def handle_parsing_failure(self) -> FallbackResponse:
        """파싱 실패"""
        return FallbackResponse(
            fallback_type="parsing_failure",
            message="검색어를 이해하지 못했어요 😅",
            suggestions=[
                "예: '스토리 좋은 RPG'",
                "예: 'Hades 같은 게임'",
                "예: '2인 협동 퍼즐'",
            ],
            recommended_games=self.popular_games[:5],
        )
    
    def _try_correct(self, name: str) -> Optional[str]:
        """게임명 교정"""
        normalized = name.lower().strip()
        
        # 직접 매칭
        if normalized in self.corrections:
            return self.corrections[normalized]
        
        # 키 순회
        for key, value in self.corrections.items():
            if key.lower() == normalized:
                return value
        
        return None
    
    def _find_similar_names(self, name: str, max_results: int = 3) -> List[str]:
        """유사 이름 찾기 (Levenshtein)"""
        
        candidates = []
        name_lower = name.lower()
        
        all_names = set(self.corrections.keys()) | set(self.corrections.values())
        
        for candidate in all_names:
            dist = self._levenshtein(name_lower, candidate.lower())
            if dist <= 3:  # 편집 거리 3 이내
                canonical = self.corrections.get(candidate.lower(), candidate)
                if canonical not in [c[1] for c in candidates]:
                    candidates.append((dist, canonical))
        
        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates[:max_results]]
    
    def _levenshtein(self, s1: str, s2: str) -> int:
        """Levenshtein 거리"""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        
        return prev_row[-1]
    
    def _get_relevant_games(self, query: str, max_results: int = 5) -> List[FallbackGame]:
        """쿼리에 맞는 게임 추천"""
        
        query_lower = query.lower()
        
        # 키워드 → 장르 매핑
        keyword_map = {
            "힐링": ["시뮬레이션", "농사"],
            "액션": ["액션", "로그라이크"],
            "공포": ["호러"],
            "스토리": ["RPG", "어드벤처"],
            "협동": ["협동"],
            "퍼즐": ["퍼즐", "플랫포머"],
            "전략": ["전략", "시뮬레이션"],
        }
        
        matched_genres = set()
        for kw, genres in keyword_map.items():
            if kw in query_lower:
                matched_genres.update(genres)
        
        if matched_genres:
            filtered = [
                g for g in self.popular_games
                if any(genre in g.genres for genre in matched_genres)
            ]
            if len(filtered) >= max_results:
                return filtered[:max_results]
        
        return self.popular_games[:max_results]


# 싱글톤
fallback_handler = FallbackHandler()
