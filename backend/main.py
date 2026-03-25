import os
import json
import re
import time
import logging
from typing import List, Dict, Optional, Tuple, Set, Any
from functools import wraps
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI, APIError, RateLimitError, APITimeoutError

# ============== 로깅 설정 ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("hidden_gem")

# 환경 변수 로드
load_dotenv(find_dotenv())

# 초기화
app = FastAPI(title="Hidden Gem API", version="2.5")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL, pool_pre_ping=True, pooSl_recycle=300)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 상수 정의 (FULL) ==============
DROP_THRESHOLD = 65
DROP_THRESHOLD_FALLBACK = 55
DROP_THRESHOLD_EMERGENCY = 45
MIN_RESULTS_BEFORE_FALLBACK = 3
MIN_RESULTS_ABSOLUTE = 5
MANIAC_AVG_THRESHOLD = 65
MANIAC_S_TIER_THRESHOLD = 85
INTENT_BASE_WEIGHT = 1.5
BOOST_CAP = 1.7
MAX_TOTAL_WEIGHT = 2.55
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0

# ============== 14개 감성 지표 + 한글 매핑 (FULL) ==============
METRIC_KOREAN: Dict[str, str] = {
    "mania_score": "마니아 매력",
    "story_depth": "스토리 깊이",
    "originality": "독창성",
    "difficulty": "난이도",
    "art_style": "아트 스타일",
    "replay_value": "리플레이 가치",
    "indie_spirit": "인디 감성",
    "character_appeal": "캐릭터 매력",
    "user_friendliness": "접근성",
    "addictiveness": "중독성",
    "emotional_impact": "감정적 임팩트",
    "atmosphere_intensity": "분위기 몰입",
    "soundtrack_prominence": "사운드트랙",
    "gem_potential": "숨겨진 명작"
}

ALL_METRICS: List[str] = list(METRIC_KOREAN.keys())

# ============== 장르별 S/A/B 티어 가중치 (FULL) ==============
GENRE_WEIGHTS: Dict[str, Dict[str, List[str]]] = {
    "Action": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "art_style", "mania_score"],
        "B": ["user_friendliness", "originality", "atmosphere_intensity", "character_appeal", "soundtrack_prominence"]
    },
    "RPG": {
        "S": ["story_depth", "character_appeal"],
        "A": ["replay_value", "originality", "emotional_impact"],
        "B": ["art_style", "soundtrack_prominence", "atmosphere_intensity", "difficulty", "addictiveness"]
    },
    "Adventure": {
        "S": ["story_depth", "atmosphere_intensity"],
        "A": ["emotional_impact", "art_style", "originality"],
        "B": ["soundtrack_prominence", "character_appeal", "user_friendliness", "indie_spirit", "gem_potential"]
    },
    "Strategy": {
        "S": ["difficulty", "replay_value"],
        "A": ["originality", "addictiveness", "user_friendliness"],
        "B": ["mania_score", "story_depth", "art_style", "atmosphere_intensity", "indie_spirit"]
    },
    "Simulation": {
        "S": ["replay_value", "addictiveness"],
        "A": ["user_friendliness", "originality", "art_style"],
        "B": ["atmosphere_intensity", "mania_score", "indie_spirit", "character_appeal", "story_depth"]
    },
    "Indie": {
        "S": ["indie_spirit", "originality"],
        "A": ["art_style", "emotional_impact", "gem_potential"],
        "B": ["story_depth", "atmosphere_intensity", "soundtrack_prominence", "character_appeal", "user_friendliness"]
    },
    "Horror": {
        "S": ["atmosphere_intensity", "emotional_impact"],
        "A": ["story_depth", "soundtrack_prominence", "art_style"],
        "B": ["difficulty", "originality", "character_appeal", "mania_score", "indie_spirit"]
    },
    "Survival": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "atmosphere_intensity", "originality"],
        "B": ["user_friendliness", "indie_spirit", "mania_score", "art_style", "gem_potential"]
    },
    "Puzzle": {
        "S": ["originality", "difficulty"],
        "A": ["user_friendliness", "art_style", "addictiveness"],
        "B": ["atmosphere_intensity", "soundtrack_prominence", "indie_spirit", "replay_value", "emotional_impact"]
    },
    "Platformer": {
        "S": ["difficulty", "art_style"],
        "A": ["addictiveness", "replay_value", "originality"],
        "B": ["soundtrack_prominence", "user_friendliness", "atmosphere_intensity", "indie_spirit", "character_appeal"]
    },
    "Roguelike": {
        "S": ["difficulty", "replay_value"],
        "A": ["addictiveness", "originality", "mania_score"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit", "user_friendliness", "soundtrack_prominence"]
    },
    "Shooter": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "atmosphere_intensity", "art_style"],
        "B": ["originality", "soundtrack_prominence", "user_friendliness", "mania_score", "character_appeal"]
    },
    "Racing": {
        "S": ["addictiveness", "replay_value"],
        "A": ["difficulty", "art_style", "user_friendliness"],
        "B": ["soundtrack_prominence", "atmosphere_intensity", "originality", "mania_score", "indie_spirit"]
    },
    "Sports": {
        "S": ["replay_value", "addictiveness"],
        "A": ["user_friendliness", "difficulty", "art_style"],
        "B": ["originality", "atmosphere_intensity", "character_appeal", "soundtrack_prominence", "mania_score"]
    },
    "Fighting": {
        "S": ["difficulty", "addictiveness"],
        "A": ["character_appeal", "replay_value", "art_style"],
        "B": ["soundtrack_prominence", "originality", "atmosphere_intensity", "mania_score", "user_friendliness"]
    },
    "Visual Novel": {
        "S": ["story_depth", "emotional_impact"],
        "A": ["character_appeal", "art_style", "soundtrack_prominence"],
        "B": ["originality", "atmosphere_intensity", "user_friendliness", "indie_spirit", "gem_potential"]
    },
    "Sandbox": {
        "S": ["replay_value", "originality"],
        "A": ["addictiveness", "user_friendliness", "indie_spirit"],
        "B": ["art_style", "atmosphere_intensity", "difficulty", "mania_score", "gem_potential"]
    },
    "Management": {
        "S": ["addictiveness", "replay_value"],
        "A": ["difficulty", "originality", "user_friendliness"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit", "story_depth", "mania_score"]
    },
    "City Builder": {
        "S": ["replay_value", "addictiveness"],
        "A": ["originality", "user_friendliness", "difficulty"],
        "B": ["art_style", "atmosphere_intensity", "indie_spirit", "mania_score", "soundtrack_prominence"]
    },
    "Tower Defense": {
        "S": ["addictiveness", "difficulty"],
        "A": ["replay_value", "originality", "art_style"],
        "B": ["user_friendliness", "atmosphere_intensity", "indie_spirit", "mania_score", "soundtrack_prominence"]
    },
    "Metroidvania": {
        "S": ["difficulty", "atmosphere_intensity"],
        "A": ["art_style", "originality", "replay_value"],
        "B": ["soundtrack_prominence", "addictiveness", "indie_spirit", "story_depth", "character_appeal"]
    },
    "Souls-like": {
        "S": ["difficulty", "atmosphere_intensity"],
        "A": ["mania_score", "replay_value", "originality"],
        "B": ["art_style", "story_depth", "soundtrack_prominence", "addictiveness", "emotional_impact"]
    },
    "Card Game": {
        "S": ["replay_value", "addictiveness"],
        "A": ["originality", "difficulty", "mania_score"],
        "B": ["art_style", "user_friendliness", "indie_spirit", "story_depth", "character_appeal"]
    },
    "Casual": {
        "S": ["user_friendliness", "addictiveness"],
        "A": ["art_style", "originality", "replay_value"],
        "B": ["atmosphere_intensity", "soundtrack_prominence", "indie_spirit", "emotional_impact", "gem_potential"]
    }
}

# ============== 장르 매핑 (한글 → Steam 장르) (FULL) ==============
GENRE_MAPPING: Dict[str, List[str]] = {
    # 건설/관리 계열
    "건설": ["Simulation", "Strategy", "City Builder", "Base Building", "Management", "Sandbox"],
    "생존": ["Survival", "Crafting", "Open World Survival Craft", "Sandbox"],
    "관리": ["Management", "Simulation", "Tycoon", "Economy", "City Builder"],
    "샌드박스": ["Sandbox", "Open World", "Crafting", "Building"],
    "전략": ["Strategy", "Turn-Based Strategy", "Real-Time Strategy", "4X", "Grand Strategy"],
    "시뮬레이션": ["Simulation", "Life Sim", "Farming Sim", "Management"],
    "식민지": ["Colony Sim", "Base Building", "Simulation", "Strategy", "Survival"],
    "타이쿤": ["Tycoon", "Management", "Simulation", "Economy"],
    "농장": ["Farming Sim", "Simulation", "Life Sim", "Casual"],
    "자동화": ["Automation", "Factory", "Simulation", "Strategy"],
    "세계구축": ["Sandbox", "Building", "City Builder", "Simulation", "Open World"],
    "기지건설": ["Base Building", "Survival", "Strategy", "Simulation"],
    
    # 액션 계열
    "액션": ["Action", "Action-Adventure", "Beat 'em up", "Hack and Slash"],
    "격투": ["Fighting", "Beat 'em up", "Martial Arts", "Combat"],
    "슈팅": ["Shooter", "FPS", "Third-Person Shooter", "Top-Down Shooter"],
    "플랫폼": ["Platformer", "2D Platformer", "3D Platformer"],
    "핵앤슬래시": ["Hack and Slash", "Action", "ARPG", "Loot"],
    "전투": ["Action", "Combat", "Fighting", "Shooter"],
    
    # RPG 계열
    "rpg": ["RPG", "JRPG", "Action RPG", "Turn-Based RPG", "CRPG"],
    "롤플레잉": ["RPG", "Role-Playing", "JRPG", "CRPG"],
    "턴제": ["Turn-Based", "Turn-Based RPG", "Turn-Based Strategy", "Tactical"],
    "오픈월드": ["Open World", "Exploration", "Adventure", "Sandbox"],
    
    # 어드벤처/스토리
    "어드벤처": ["Adventure", "Action-Adventure", "Visual Novel", "Narrative"],
    "스토리": ["Adventure", "Visual Novel", "Narrative", "Story Rich"],
    "탐험": ["Exploration", "Adventure", "Open World", "Metroidvania"],
    "미스터리": ["Mystery", "Detective", "Puzzle", "Adventure"],
    
    # 공포
    "호러": ["Horror", "Psychological Horror", "Survival Horror"],
    "공포": ["Horror", "Psychological Horror", "Survival Horror"],
    
    # 인디/캐주얼
    "인디": ["Indie", "Casual", "Pixel Graphics"],
    "캐주얼": ["Casual", "Relaxing", "Family Friendly"],
    "힐링": ["Relaxing", "Casual", "Life Sim", "Cozy"],
    
    # 멀티플레이
    "멀티": ["Multiplayer", "Co-op", "Online Co-Op", "MMO", "PvP"],
    "협동": ["Co-op", "Online Co-Op", "Local Co-Op", "Multiplayer"],
    "싱글": ["Singleplayer", "Solo"],
    "pvp": ["PvP", "Competitive", "Multiplayer"],
    
    # 특수 장르
    "로그라이크": ["Roguelike", "Roguelite", "Procedural Generation"],
    "메트로배니아": ["Metroidvania", "Action", "Platformer", "Exploration"],
    "소울라이크": ["Souls-like", "Action RPG", "Difficult", "Hardcore"],
    "덱빌딩": ["Card Game", "Deck Builder", "Roguelike", "Strategy"],
    "타워디펜스": ["Tower Defense", "Strategy", "Real-Time Strategy"],
    "레이싱": ["Racing", "Driving", "Sports"],
    "퍼즐": ["Puzzle", "Puzzle Platformer", "Logic", "Brain Training"],
    "리듬": ["Rhythm", "Music", "Arcade"],
    "비주얼노벨": ["Visual Novel", "Narrative", "Story Rich", "Dating Sim"],
}

# ============== 장르 충돌 맵 (FULL) ==============
GENRE_CONFLICTS: Dict[str, List[str]] = {
    "건설": ["Fighting", "Beat 'em up", "Shooter", "Racing", "Sports", "Rhythm"],
    "생존": ["Visual Novel", "Puzzle", "Rhythm", "Sports", "Racing", "Card Game"],
    "전략": ["Platformer", "Racing", "Sports", "Fighting", "Rhythm"],
    "시뮬레이션": ["Fighting", "Beat 'em up", "Shooter", "Horror"],
    "관리": ["Action", "Fighting", "Shooter", "Horror", "Platformer"],
    "타이쿤": ["Action", "Fighting", "Horror", "Platformer", "Shooter"],
    "세계구축": ["Fighting", "Racing", "Sports", "Horror", "Visual Novel"],
    "기지건설": ["Racing", "Sports", "Rhythm", "Visual Novel", "Fighting"],
    "rpg": ["Sports", "Racing", "Rhythm", "Simulation"],
    "퍼즐": ["Shooter", "Fighting", "Hack and Slash", "Racing", "Survival"],
    "호러": ["Casual", "Family Friendly", "Cute", "Relaxing", "Sports", "Racing"],
    "캐주얼": ["Horror", "Difficult", "Hardcore", "Souls-like", "Survival Horror"],
    "힐링": ["Horror", "Difficult", "Hardcore", "Violence", "Gore"],
    "비주얼노벨": ["Action", "Shooter", "Racing", "Sports", "Survival"],
    "리듬": ["Strategy", "Survival", "Horror", "Simulation"],
    "스토리": ["Racing", "Sports", "Rhythm", "Tower Defense"],
}

# ============== 레퍼런스 게임 DB (FULL) ==============
REFERENCE_GAMES: Dict[str, Dict[str, Any]] = {
    # 건설/시뮬레이션
    "림월드": {"genres": ["Simulation", "Strategy", "Colony Sim", "Base Building", "Survival"], "keywords": ["건설", "생존", "관리", "식민지"]},
    "rimworld": {"genres": ["Simulation", "Strategy", "Colony Sim", "Base Building", "Survival"], "keywords": ["건설", "생존", "관리", "식민지"]},
    "팩토리오": {"genres": ["Simulation", "Strategy", "Automation", "Base Building", "Factory"], "keywords": ["건설", "자동화", "공장", "관리"]},
    "factorio": {"genres": ["Simulation", "Strategy", "Automation", "Base Building", "Factory"], "keywords": ["건설", "자동화", "공장", "관리"]},
    "스타듀밸리": {"genres": ["Simulation", "Farming Sim", "RPG", "Life Sim", "Relaxing"], "keywords": ["농장", "시뮬레이션", "힐링", "관리"]},
    "stardew valley": {"genres": ["Simulation", "Farming Sim", "RPG", "Life Sim", "Relaxing"], "keywords": ["농장", "시뮬레이션", "힐링", "관리"]},
    "시티즈 스카이라인": {"genres": ["City Builder", "Simulation", "Management", "Building"], "keywords": ["건설", "도시", "관리", "시뮬레이션"]},
    "cities skylines": {"genres": ["City Builder", "Simulation", "Management", "Building"], "keywords": ["건설", "도시", "관리", "시뮬레이션"]},
    "플래닛 코스터": {"genres": ["Simulation", "Management", "Building", "Tycoon"], "keywords": ["건설", "관리", "놀이공원", "타이쿤"]},
    "planet coaster": {"genres": ["Simulation", "Management", "Building", "Tycoon"], "keywords": ["건설", "관리", "놀이공원", "타이쿤"]},
    "두 포인트 호스피탈": {"genres": ["Simulation", "Management", "Tycoon", "Strategy"], "keywords": ["관리", "병원", "타이쿤", "시뮬레이션"]},
    "two point hospital": {"genres": ["Simulation", "Management", "Tycoon", "Strategy"], "keywords": ["관리", "병원", "타이쿤", "시뮬레이션"]},
    "oxygen not included": {"genres": ["Simulation", "Colony Sim", "Survival", "Strategy", "Base Building"], "keywords": ["생존", "건설", "관리", "식민지"]},
    "dwarf fortress": {"genres": ["Simulation", "Colony Sim", "Strategy", "Roguelike", "Base Building"], "keywords": ["건설", "관리", "식민지", "전략"]},
    "frostpunk": {"genres": ["Simulation", "Strategy", "City Builder", "Survival", "Post-apocalyptic"], "keywords": ["건설", "생존", "관리", "전략"]},
    "banished": {"genres": ["Simulation", "City Builder", "Strategy", "Survival"], "keywords": ["건설", "생존", "관리", "마을"]},
    
    # 생존
    "발하임": {"genres": ["Survival", "Open World", "Co-op", "Crafting", "Action"], "keywords": ["생존", "건설", "협동", "바이킹"]},
    "valheim": {"genres": ["Survival", "Open World", "Co-op", "Crafting", "Action"], "keywords": ["생존", "건설", "협동", "바이킹"]},
    "서브노티카": {"genres": ["Survival", "Open World", "Adventure", "Crafting", "Exploration"], "keywords": ["생존", "탐험", "바다", "건설"]},
    "subnautica": {"genres": ["Survival", "Open World", "Adventure", "Crafting", "Exploration"], "keywords": ["생존", "탐험", "바다", "건설"]},
    "테라리아": {"genres": ["Sandbox", "Survival", "Crafting", "2D", "Action", "Adventure"], "keywords": ["샌드박스", "건설", "탐험", "생존"]},
    "terraria": {"genres": ["Sandbox", "Survival", "Crafting", "2D", "Action", "Adventure"], "keywords": ["샌드박스", "건설", "탐험", "생존"]},
    "돈스타브": {"genres": ["Survival", "Indie", "Adventure", "Crafting"], "keywords": ["생존", "인디", "어려움", "탐험"]},
    "don't starve": {"genres": ["Survival", "Indie", "Adventure", "Crafting"], "keywords": ["생존", "인디", "어려움", "탐험"]},
    "the forest": {"genres": ["Survival", "Horror", "Open World", "Crafting"], "keywords": ["생존", "공포", "건설", "탐험"]},
    "rust": {"genres": ["Survival", "Multiplayer", "Open World", "Crafting", "PvP"], "keywords": ["생존", "멀티", "pvp", "건설"]},
    "ark": {"genres": ["Survival", "Open World", "Dinosaurs", "Multiplayer", "Crafting"], "keywords": ["생존", "공룡", "건설", "멀티"]},
    
    # 액션/RPG
    "할로우나이트": {"genres": ["Action", "Metroidvania", "Platformer", "Indie", "Souls-like"], "keywords": ["액션", "탐험", "보스전", "분위기"]},
    "hollow knight": {"genres": ["Action", "Metroidvania", "Platformer", "Indie", "Souls-like"], "keywords": ["액션", "탐험", "보스전", "분위기"]},
    "엘든링": {"genres": ["Action RPG", "Souls-like", "Open World", "Difficult", "Dark Fantasy"], "keywords": ["액션", "어려움", "오픈월드", "보스전"]},
    "elden ring": {"genres": ["Action RPG", "Souls-like", "Open World", "Difficult", "Dark Fantasy"], "keywords": ["액션", "어려움", "오픈월드", "보스전"]},
    "다크소울": {"genres": ["Action RPG", "Souls-like", "Difficult", "Dark Fantasy"], "keywords": ["액션", "어려움", "보스전", "분위기"]},
    "dark souls": {"genres": ["Action RPG", "Souls-like", "Difficult", "Dark Fantasy"], "keywords": ["액션", "어려움", "보스전", "분위기"]},
    "하데스": {"genres": ["Action", "Roguelike", "Indie", "Hack and Slash", "Mythology"], "keywords": ["액션", "로그라이크", "반복", "스토리"]},
    "hades": {"genres": ["Action", "Roguelike", "Indie", "Hack and Slash", "Mythology"], "keywords": ["액션", "로그라이크", "반복", "스토리"]},
    "데드셀": {"genres": ["Action", "Roguelike", "Metroidvania", "Indie", "Difficult"], "keywords": ["액션", "로그라이크", "어려움", "플랫폼"]},
    "dead cells": {"genres": ["Action", "Roguelike", "Metroidvania", "Indie", "Difficult"], "keywords": ["액션", "로그라이크", "어려움", "플랫폼"]},
    "셀레스트": {"genres": ["Platformer", "Indie", "Difficult", "Pixel Graphics"], "keywords": ["플랫폼", "어려움", "인디", "스토리"]},
    "celeste": {"genres": ["Platformer", "Indie", "Difficult", "Pixel Graphics"], "keywords": ["플랫폼", "어려움", "인디", "스토리"]},
    
    # 전략
    "문명": {"genres": ["Strategy", "4X", "Turn-Based Strategy", "Historical"], "keywords": ["전략", "턴제", "문명", "역사"]},
    "civilization": {"genres": ["Strategy", "4X", "Turn-Based Strategy", "Historical"], "keywords": ["전략", "턴제", "문명", "역사"]},
    "크루세이더 킹즈": {"genres": ["Strategy", "Grand Strategy", "RPG", "Medieval"], "keywords": ["전략", "중세", "역사", "관리"]},
    "crusader kings": {"genres": ["Strategy", "Grand Strategy", "RPG", "Medieval"], "keywords": ["전략", "중세", "역사", "관리"]},
    "토탈워": {"genres": ["Strategy", "Real-Time Strategy", "Turn-Based Strategy", "War"], "keywords": ["전략", "전쟁", "역사", "전투"]},
    "total war": {"genres": ["Strategy", "Real-Time Strategy", "Turn-Based Strategy", "War"], "keywords": ["전략", "전쟁", "역사", "전투"]},
    "스타크래프트": {"genres": ["Strategy", "Real-Time Strategy", "Sci-fi", "Competitive"], "keywords": ["전략", "RTS", "SF", "멀티"]},
    "starcraft": {"genres": ["Strategy", "Real-Time Strategy", "Sci-fi", "Competitive"], "keywords": ["전략", "RTS", "SF", "멀티"]},
    "엑스컴": {"genres": ["Strategy", "Turn-Based", "Tactical", "Sci-fi"], "keywords": ["전략", "턴제", "전술", "SF"]},
    "xcom": {"genres": ["Strategy", "Turn-Based", "Tactical", "Sci-fi"], "keywords": ["전략", "턴제", "전술", "SF"]},
    
    # 스토리/어드벤처
    "디스코 엘리시움": {"genres": ["RPG", "Narrative", "Detective", "Indie", "Story Rich"], "keywords": ["스토리", "선택", "탐정", "대화"]},
    "disco elysium": {"genres": ["RPG", "Narrative", "Detective", "Indie", "Story Rich"], "keywords": ["스토리", "선택", "탐정", "대화"]},
    "디비니티 오리지널 신": {"genres": ["RPG", "Turn-Based", "Co-op", "Fantasy", "Story Rich"], "keywords": ["rpg", "턴제", "협동", "스토리"]},
    "divinity original sin": {"genres": ["RPG", "Turn-Based", "Co-op", "Fantasy", "Story Rich"], "keywords": ["rpg", "턴제", "협동", "스토리"]},
    "발더스 게이트": {"genres": ["RPG", "Turn-Based", "Fantasy", "Story Rich", "D&D"], "keywords": ["rpg", "스토리", "판타지", "선택"]},
    "baldur's gate": {"genres": ["RPG", "Turn-Based", "Fantasy", "Story Rich", "D&D"], "keywords": ["rpg", "스토리", "판타지", "선택"]},
    "위쳐": {"genres": ["RPG", "Action RPG", "Open World", "Story Rich", "Fantasy"], "keywords": ["rpg", "스토리", "오픈월드", "판타지"]},
    "witcher": {"genres": ["RPG", "Action RPG", "Open World", "Story Rich", "Fantasy"], "keywords": ["rpg", "스토리", "오픈월드", "판타지"]},
    
    # 로그라이크/카드
    "슬레이 더 스파이어": {"genres": ["Card Game", "Roguelike", "Deck Builder", "Strategy", "Indie"], "keywords": ["덱빌딩", "로그라이크", "전략", "카드"]},
    "slay the spire": {"genres": ["Card Game", "Roguelike", "Deck Builder", "Strategy", "Indie"], "keywords": ["덱빌딩", "로그라이크", "전략", "카드"]},
    "인스크립션": {"genres": ["Card Game", "Horror", "Roguelike", "Puzzle", "Indie"], "keywords": ["카드", "공포", "퍼즐", "인디"]},
    "inscryption": {"genres": ["Card Game", "Horror", "Roguelike", "Puzzle", "Indie"], "keywords": ["카드", "공포", "퍼즐", "인디"]},
    "몬스터 트레인": {"genres": ["Card Game", "Roguelike", "Strategy", "Tower Defense"], "keywords": ["덱빌딩", "로그라이크", "전략", "카드"]},
    "monster train": {"genres": ["Card Game", "Roguelike", "Strategy", "Tower Defense"], "keywords": ["덱빌딩", "로그라이크", "전략", "카드"]},
    
    # 호러
    "레지던트 이블": {"genres": ["Horror", "Survival Horror", "Action", "Zombie"], "keywords": ["공포", "생존", "좀비", "액션"]},
    "resident evil": {"genres": ["Horror", "Survival Horror", "Action", "Zombie"], "keywords": ["공포", "생존", "좀비", "액션"]},
    "아웃라스트": {"genres": ["Horror", "Survival Horror", "Indie", "First-Person"], "keywords": ["공포", "인디", "생존", "분위기"]},
    "outlast": {"genres": ["Horror", "Survival Horror", "Indie", "First-Person"], "keywords": ["공포", "인디", "생존", "분위기"]},
    "암네시아": {"genres": ["Horror", "Survival Horror", "Adventure", "Atmospheric"], "keywords": ["공포", "분위기", "탐험", "퍼즐"]},
    "amnesia": {"genres": ["Horror", "Survival Horror", "Adventure", "Atmospheric"], "keywords": ["공포", "분위기", "탐험", "퍼즐"]},
}

# ============== 제외 장르 ==============
EXCLUDED_GENRES: List[str] = [
    "Utilities", "Software", "Video Production", "Photo Editing",
    "Audio Production", "Design & Illustration", "Web Publishing",
    "Education", "Accounting", "Animation & Modeling", "Game Development",
    "Tutorial", "Documentary"
]

# ============== 요청 모델 ==============
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    include_maniac: bool = False

# ============== Intent 객체 타입 ==============
@dataclass
class IntentObject:
    id: str
    name: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "name": self.name}

@dataclass
class ExtractedIntent:
    metrics: List[str] = field(default_factory=list)
    required_genres: Set[str] = field(default_factory=set)
    preferred_keywords: List[str] = field(default_factory=list)
    negative_genres: Set[str] = field(default_factory=set)
    reference_game: Optional[str] = None
    genre_strictness: float = 0.5
    core_keywords: List[str] = field(default_factory=list)
    
    def get_intent_objects(self) -> List[Dict[str, str]]:
        """metrics를 객체 배열로 변환"""
        return [{"id": m, "name": METRIC_KOREAN.get(m, m)} for m in self.metrics]

# ============== 재시도 데코레이터 ==============
def retry_on_failure(max_retries: int = MAX_RETRIES, delay_base: float = RETRY_DELAY_BASE):
    """OpenAI API 호출 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except RateLimitError as e:
                    last_exception = e
                    wait_time = delay_base * (2 ** attempt)
                    logger.warning(f"Rate limit hit, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                except APITimeoutError as e:
                    last_exception = e
                    wait_time = delay_base * (attempt + 1)
                    logger.warning(f"API timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                except APIError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay_base
                        logger.warning(f"API error: {e}, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise
            
            logger.error(f"All {max_retries} retries failed for {func.__name__}")
            if last_exception:
                raise last_exception
            return None
        return wrapper
    return decorator

# ============== 레퍼런스 게임 추출 ==============
def extract_reference_game(query: str) -> Optional[Dict]:
    """쿼리에서 레퍼런스 게임 추출"""
    query_lower = query.lower()
    patterns = [
        r"(.+?)\s*같은", r"(.+?)\s*같이", r"(.+?)\s*처럼", 
        r"(.+?)\s*스타일", r"(.+?)\s*비슷한", r"(.+?)\s*느낌"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            game_name = match.group(1).strip()
            for ref_name, ref_data in REFERENCE_GAMES.items():
                if ref_name in game_name or game_name in ref_name:
                    return {"name": ref_name, **ref_data}
    
    for ref_name, ref_data in REFERENCE_GAMES.items():
        if ref_name in query_lower:
            return {"name": ref_name, **ref_data}
    
    return None

# ============== 장르 키워드 추출 ==============
def extract_genre_keywords(query: str) -> Tuple[Set[str], List[str]]:
    """쿼리에서 장르 키워드 추출"""
    query_lower = query.lower()
    required_genres = set()
    preferred_keywords = []
    
    for keyword, genres in GENRE_MAPPING.items():
        if keyword in query_lower:
            required_genres.update(genres)
            preferred_keywords.append(keyword)
    
    return required_genres, preferred_keywords

# ============== 부정 장르 추출 ==============
def extract_negative_genres(query: str, required_keywords: List[str]) -> Set[str]:
    """충돌하는 장르 추출"""
    negative_genres = set()
    
    for keyword in required_keywords:
        if keyword in GENRE_CONFLICTS:
            negative_genres.update(GENRE_CONFLICTS[keyword])
    
    return negative_genres

# ============== GPT로 지표 + 키워드 추출 ==============
@retry_on_failure()
def extract_metrics_with_gpt(query: str) -> Tuple[List[str], List[str]]:
    """GPT로 감성 지표 + 핵심 키워드 추출 (재시도 포함)"""
    prompt = f"""사용자의 게임 검색 쿼리를 분석하세요.

쿼리: "{query}"

다음을 JSON으로 반환:
1. intents: 관련된 감성 지표 (최대 4개)
   - 사용 가능: {', '.join(ALL_METRICS)}
2. core_keywords: 검색의 핵심 키워드 (최대 3개, 게임 장르/특징 관련)

예시: {{"intents": ["story_depth", "emotional_impact"], "core_keywords": ["스토리", "감동", "rpg"]}}
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "게임 검색 분석 전문가. JSON만 출력."},
                {"role": "user", "content": prompt}
            ],
            timeout=15.0
        )
        result = json.loads(response.choices[0].message.content)
        
        intents = result.get("intents", [])
        if isinstance(intents, str):
            intents = [intents]
        valid_intents = [i for i in intents if i in ALL_METRICS][:4]
        
        core_keywords = result.get("core_keywords", [])
        if isinstance(core_keywords, str):
            core_keywords = [core_keywords]
        
        return valid_intents, core_keywords[:3]
    except Exception as e:
        logger.warning(f"GPT metrics extraction failed: {e}")
        return [], []

# ============== 고도화된 Intent 추출 ==============
def extract_user_intent_v2(query: str) -> ExtractedIntent:
    """고도화된 Intent 추출"""
    intent = ExtractedIntent()
    
    # 1. 레퍼런스 게임
    ref_game = extract_reference_game(query)
    if ref_game:
        intent.reference_game = ref_game["name"]
        intent.required_genres.update(ref_game.get("genres", []))
        intent.preferred_keywords.extend(ref_game.get("keywords", []))
    
    # 2. 장르 키워드
    genres, keywords = extract_genre_keywords(query)
    intent.required_genres.update(genres)
    intent.preferred_keywords.extend(keywords)
    intent.preferred_keywords = list(set(intent.preferred_keywords))
    
    # 3. 부정 장르
    intent.negative_genres = extract_negative_genres(query, intent.preferred_keywords)
    
    # 4. 엄격도 계산
    if any(w in query for w in ["꼭", "정확히", "딱", "반드시", "only"]):
        intent.genre_strictness = 0.9
    elif ref_game or len(intent.required_genres) >= 3:
        intent.genre_strictness = 0.7
    else:
        intent.genre_strictness = 0.5
    
    # 5. GPT로 감성 지표 + 핵심 키워드
    try:
        metrics, core_keywords = extract_metrics_with_gpt(query)
        intent.metrics = metrics
        intent.core_keywords = core_keywords if core_keywords else intent.preferred_keywords[:3]
    except Exception as e:
        logger.warning(f"GPT extraction failed, using fallback: {e}")
        intent.metrics = []
        intent.core_keywords = intent.preferred_keywords[:3]
    
    # 6. 핵심 키워드 보충 (GPT가 실패했거나 부족할 때)
    if not intent.core_keywords:
        words = query.replace(",", " ").split()
        intent.core_keywords = [w for w in words if len(w) >= 2][:3]
    
    return intent

# ============== 장르 매칭 점수 계산 ==============
def calculate_genre_match_score(game_genres: str, intent: ExtractedIntent) -> Tuple[float, str]:
    """
    장르 매칭 점수 계산 (0.3 ~ 1.5)
    
    - 완벽 매칭: 1.3 ~ 1.5
    - 부분 매칭: 0.8 ~ 1.2
    - 불일치: 0.3 ~ 0.7
    """
    if not intent.required_genres and not intent.negative_genres:
        return 1.0, ""
    
    game_genre_lower = game_genres.lower()
    
    # 필수 장르 매칭 점수
    match_count = 0
    for g in intent.required_genres:
        if g.lower() in game_genre_lower:
            match_count += 1
    
    match_ratio = match_count / len(intent.required_genres) if intent.required_genres else 1.0
    
    # 부정 장르 매칭 (페널티)
    negative_count = 0
    for g in intent.negative_genres:
        if g.lower() in game_genre_lower:
            negative_count += 1
    
    penalty = 0.15 * negative_count * intent.genre_strictness
    
    # 기본 배율 계산 (0.5 ~ 1.0 범위)
    base_multiplier = 0.5 + (match_ratio * 0.5)
    
    # 엄격 모드에서 매칭 실패 시 추가 페널티
    if intent.genre_strictness > 0.7 and match_ratio < 0.3:
        base_multiplier = max(0.3, base_multiplier - 0.2)
    
    # 페널티 적용
    final_multiplier = max(0.3, min(1.5, base_multiplier - penalty))
    
    # 완벽 매칭 보너스
    if match_ratio >= 0.6 and negative_count == 0:
        final_multiplier = min(1.5, final_multiplier + 0.3)
    
    # 이유 생성
    if final_multiplier < 0.5:
        reason = f"⚠️ 장르 불일치 (일치율: {match_ratio:.0%})"
    elif final_multiplier >= 1.2:
        reason = "🎯 장르 완벽 매칭!"
    elif negative_count > 0:
        reason = f"⚡ 일부 장르 충돌 ({negative_count}개)"
    else:
        reason = ""
    
    return final_multiplier, reason

# ============== 가중치 맵 생성 ==============
def get_genre_weight_map(genres: str) -> Dict[str, float]:
    """장르별 S/A/B 티어 가중치 적용"""
    weight_map = {m: 1.0 for m in ALL_METRICS}
    for genre in [g.strip() for g in genres.split(",")]:
        for gk, tc in GENRE_WEIGHTS.items():
            if gk.lower() in genre.lower():
                for m in tc.get("S", []):
                    weight_map[m] = max(weight_map[m], 1.5)
                for m in tc.get("A", []):
                    weight_map[m] = max(weight_map[m], 1.3)
                for m in tc.get("B", []):
                    weight_map[m] = max(weight_map[m], 1.1)
    return weight_map

def get_s_tier_metrics(genres: str) -> List[str]:
    """장르별 S티어 지표 추출"""
    s_tier = set()
    for genre in [g.strip() for g in genres.split(",")]:
        for gk, tc in GENRE_WEIGHTS.items():
            if gk.lower() in genre.lower():
                s_tier.update(tc.get("S", []))
    return list(s_tier)

# ============== 동적 부스팅 적용 ==============
def apply_dynamic_boosting(
    scores: Dict[str, int], 
    weight_map: Dict[str, float], 
    user_intents: List[str]
) -> Tuple[Dict[str, float], Dict[str, Any], Optional[str]]:
    """사용자 Intent에 따른 동적 가중치 부스팅"""
    boost_details = {}
    boost_reason = None
    
    if not user_intents:
        return weight_map, boost_details, boost_reason
    
    boosted_map = weight_map.copy()
    max_boost_metric, max_boost_value = None, 0
    
    for metric in user_intents:
        if metric in boosted_map:
            original = weight_map.get(metric, 1.0)
            boosted_map[metric] = original * INTENT_BASE_WEIGHT
            boost_details[metric] = {"original": original, "after_base": boosted_map[metric]}
    
    group_a = [m for m in user_intents if m in scores]
    group_b = [m for m in ALL_METRICS if m not in user_intents and m in scores]
    
    if group_a and len(group_b) >= 2:
        group_a_avg = sum(scores[m] * boosted_map[m] for m in group_a) / len(group_a)
        group_b_sorted = sorted([scores[m] * boosted_map[m] for m in group_b], reverse=True)
        group_b_2nd = group_b_sorted[1] if len(group_b_sorted) > 1 else group_b_sorted[0]
        
        if group_a_avg < group_b_2nd and group_a_avg > 0:
            additional_boost = min(BOOST_CAP, max(1.0, group_b_2nd / group_a_avg))
            for metric in group_a:
                final_weight = min(MAX_TOTAL_WEIGHT, boosted_map[metric] * additional_boost)
                boosted_map[metric] = final_weight
                boost_details[metric]["additional_boost"] = round(additional_boost, 2)
                boost_details[metric]["final_weight"] = round(final_weight, 2)
                if final_weight > max_boost_value:
                    max_boost_value, max_boost_metric = final_weight, metric
    
    if max_boost_metric and max_boost_value > 1.5:
        metric_name = METRIC_KOREAN.get(max_boost_metric, max_boost_metric)
        boost_reason = f"🚀 [{metric_name}] 취향 집중 반영 (가중치 {max_boost_value:.2f}배)"
    
    return boosted_map, boost_details, boost_reason

# ============== 최종 점수 계산 ==============
def calculate_final_score(
    scores: Dict[str, int],
    genres: str,
    intent: ExtractedIntent,
    drop_threshold: int = DROP_THRESHOLD
) -> Tuple[float, str, Dict, Optional[str], float, str]:
    """최종 점수 계산 (장르 매칭 포함)"""
    weight_map = get_genre_weight_map(genres)
    boosted_map, boost_details, boost_reason = apply_dynamic_boosting(scores, weight_map, intent.metrics)
    
    # 장르 매칭 점수
    genre_multiplier, genre_reason = calculate_genre_match_score(genres, intent)
    
    # 가중 평균 계산
    weighted_scores, total_weight = [], 0
    for metric in ALL_METRICS:
        if metric in scores:
            w = boosted_map.get(metric, 1.0)
            weighted_scores.append(scores[metric] * w)
            total_weight += w
    
    base_score = sum(weighted_scores) / total_weight if total_weight > 0 else 50
    
    # 장르 배율 적용 (최소 0.5배로 제한하여 너무 낮아지지 않게)
    adjusted_genre_mult = max(0.5, genre_multiplier)
    base_score *= adjusted_genre_mult
    
    # 시너지 보너스
    synergy_bonus = 0
    s_tier_metrics = get_s_tier_metrics(genres)
    
    if s_tier_metrics:
        s_tier_scores = [scores.get(m, 0) for m in s_tier_metrics]
        if all(s >= MANIAC_S_TIER_THRESHOLD for s in s_tier_scores):
            synergy_bonus += 4 if intent.metrics else 8
    
    if intent.metrics:
        intent_scores = [scores.get(m, 0) for m in intent.metrics]
        if all(s >= 80 for s in intent_scores):
            synergy_bonus += len(intent.metrics) * 3
    
    # 장르 완벽 매칭 보너스
    if genre_multiplier >= 1.2:
        synergy_bonus += 5
    
    final_score = base_score + synergy_bonus
    
    # 상태 분류
    if final_score < drop_threshold:
        if s_tier_metrics:
            s_tier_scores = [scores.get(m, 0) for m in s_tier_metrics]
            plain_avg = sum(scores.values()) / len(scores) if scores else 0
            if all(s >= MANIAC_S_TIER_THRESHOLD for s in s_tier_scores) and plain_avg < MANIAC_AVG_THRESHOLD:
                status = "MANIAC"
            else:
                status = "DROP"
        else:
            status = "DROP"
    else:
        status = "GEM"
    
    return final_score, status, boost_details, boost_reason, genre_multiplier, genre_reason

# ============== 장르 제외 체크 ==============
def is_excluded_genre(genres: str) -> bool:
    """유틸리티/소프트웨어 장르 제외"""
    if not genres:
        return False
    return any(ex.lower() in genres.lower() for ex in EXCLUDED_GENRES)

# ============== DB row → scores 딕셔너리 ==============
def parse_scores_from_row(row) -> Dict[str, int]:
    """DB 결과 row에서 점수 딕셔너리 추출"""
    return {
        "mania_score": row[5] or 50,
        "story_depth": row[6] or 50,
        "originality": row[7] or 50,
        "difficulty": row[8] or 50,
        "art_style": row[9] or 50,
        "replay_value": row[10] or 50,
        "indie_spirit": row[11] or 50,
        "character_appeal": row[12] or 50,
        "user_friendliness": row[13] or 50,
        "addictiveness": row[14] or 50,
        "emotional_impact": row[15] or 50,
        "atmosphere_intensity": row[16] or 50,
        "soundtrack_prominence": row[17] or 50,
        "gem_potential": row[18] or 50
    }

# ============== 후보 처리 ==============
def process_candidates(
    candidates: List,
    intent: ExtractedIntent,
    drop_threshold: int
) -> Tuple[List[Dict], List[Dict]]:
    """후보 게임들을 처리하여 GEM/MANIAC 분류"""
    gems, maniacs = [], []
    
    for row in candidates:
        genres = row[2] or ""
        if is_excluded_genre(genres):
            continue
        
        scores = parse_scores_from_row(row)
        similarity = float(row[19]) if len(row) > 19 else 0.0
        
        final_score, status, boost_details, boost_reason, genre_mult, genre_reason = calculate_final_score(
            scores, genres, intent, drop_threshold
        )
        
        game_result = {
            "app_id": row[0],
            "name": row[1],
            "genres": genres,
            "developer": row[3] or "Unknown",
            "description": row[4] or "",
            "final_score": round(final_score, 2),
            "status": status,
            "similarity": round(similarity, 4),
            "matched_intents": intent.metrics,
            "boost_reason": boost_reason,
            "boost_info": boost_details,
            "scores": scores,
            "genre_match": {
                "multiplier": round(genre_mult, 2),
                "reason": genre_reason,
                "is_match": genre_mult >= 0.8
            }
        }
        
        if status == "GEM":
            gems.append(game_result)
        elif status == "MANIAC":
            maniacs.append(game_result)
    
    return gems, maniacs

# ============== 임베딩 생성 (재시도 포함) ==============
@retry_on_failure()
def create_query_embedding(query: str) -> List[float]:
    """쿼리 임베딩 생성"""
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
        timeout=15.0
    )
    return embed_response.data[0].embedding

# ============== 벡터 검색 실행 ==============
def execute_vector_search(query_vector: List[float], limit: int = 100) -> List:
    """pgvector 벡터 유사도 검색"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential,
                       1 - (embedding <=> CAST(:vec AS vector)) as similarity
                FROM games
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :lim
            """), {"vec": str(query_vector), "lim": limit})
            return list(result)
    except SQLAlchemyError as e:
        logger.error(f"Vector search failed: {e}")
        return []

# ============== 인기 게임 가져오기 (최후의 보루) ==============
def get_popular_games(limit: int = 10, genre_filter: Optional[Set[str]] = None) -> List[Dict]:
    """gem_potential 높은 인기 게임 반환"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential
                FROM games
                WHERE gem_potential >= 70
                ORDER BY gem_potential DESC
                LIMIT :lim
            """), {"lim": limit * 3})
            
            games = []
            for row in result:
                genres = row[2] or ""
                
                # 제외 장르 체크
                if is_excluded_genre(genres):
                    continue
                
                # 장르 필터가 있으면 적용
                if genre_filter:
                    genre_lower = genres.lower()
                    if not any(g.lower() in genre_lower for g in genre_filter):
                        continue
                
                scores = parse_scores_from_row(row)
                games.append({
                    "app_id": row[0],
                    "name": row[1],
                    "genres": genres,
                    "developer": row[3] or "Unknown",
                    "description": row[4] or "",
                    "final_score": float(row[18] or 70),
                    "status": "GEM",
                    "similarity": 0.0,
                    "matched_intents": [],
                    "boost_reason": None,
                    "boost_info": {},
                    "scores": scores,
                    "genre_match": {"multiplier": 1.0, "reason": "🌟 인기 명작", "is_match": True},
                    "is_popular_fallback": True
                })
                
                if len(games) >= limit:
                    break
            
            return games
    except Exception as e:
        logger.error(f"Failed to get popular games: {e}")
        return []

# ============== 3단계 무적 Fallback 검색 ==============
def hybrid_search_with_fallback(
    query: str,
    intent: ExtractedIntent,
    top_k: int = 10,
    include_maniac: bool = False
) -> Dict:
    """
    3단계 Fallback 전략
    
    1단계: 전체 쿼리 벡터 검색 (DROP_THRESHOLD=65)
    2단계: 핵심 키워드 검색 + 기준 완화 (DROP_THRESHOLD=55)
    3단계: 인기 게임 강제 반환 (DROP_THRESHOLD=45 또는 무조건)
    """
    search_stage = 1
    fallback_message = None
    error_log = []
    all_candidates = []
    
    # ========== 1단계: 전체 쿼리 검색 ==========
    logger.info(f"[Stage 1] Full query: '{query}'")
    try:
        query_vector = create_query_embedding(query)
        candidates = execute_vector_search(query_vector, limit=100)
        all_candidates.extend(candidates)
        
        gems, maniacs = process_candidates(candidates, intent, DROP_THRESHOLD)
        
        if len(gems) >= MIN_RESULTS_BEFORE_FALLBACK:
            gems.sort(key=lambda x: x["final_score"], reverse=True)
            maniacs.sort(key=lambda x: x["final_score"], reverse=True)
            
            return {
                "success": True,
                "search_stage": search_stage,
                "gems": gems[:top_k],
                "maniacs": maniacs[:5] if include_maniac else [],
                "total_candidates": len(candidates),
                "fallback_message": None,
                "error_log": error_log
            }
        
        error_log.append(f"1단계: {len(gems)}개 결과 (기준 미달)")
        logger.info(f"[Stage 1] Insufficient: {len(gems)} gems")
        
    except Exception as e:
        logger.warning(f"[Stage 1] Failed: {e}")
        error_log.append(f"1단계 실패: {str(e)[:50]}")
        gems, maniacs = [], []
    
    # ========== 2단계: 핵심 키워드 검색 + 기준 완화 ==========
    search_stage = 2
    
    # 핵심 키워드 조합
    if intent.core_keywords:
        simplified_query = " ".join(intent.core_keywords)
    elif intent.preferred_keywords:
        simplified_query = " ".join(intent.preferred_keywords[:2]) + " 게임"
    else:
        simplified_query = query[:20] + " 게임 추천"
    
    logger.info(f"[Stage 2] Simplified: '{simplified_query}'")
    
    try:
        query_vector = create_query_embedding(simplified_query)
        candidates_2 = execute_vector_search(query_vector, limit=100)
        
        # 기존 후보와 중복 제거 후 합치기
        existing_ids = {c[0] for c in all_candidates}
        new_candidates = [c for c in candidates_2 if c[0] not in existing_ids]
        all_candidates.extend(new_candidates)
        
        # 완화된 Intent로 재처리
        intent_relaxed = ExtractedIntent()
        intent_relaxed.metrics = intent.metrics
        intent_relaxed.required_genres = intent.required_genres
        intent_relaxed.genre_strictness = 0.3  # 엄격도 대폭 완화
        
        gems_2, maniacs_2 = process_candidates(all_candidates, intent_relaxed, DROP_THRESHOLD_FALLBACK)
        
        # 기존 결과와 합치기
        existing_gem_ids = {g["app_id"] for g in gems}
        for g in gems_2:
            if g["app_id"] not in existing_gem_ids:
                g["fallback_rescued"] = True
                gems.append(g)
                existing_gem_ids.add(g["app_id"])
        
        if len(gems) >= MIN_RESULTS_BEFORE_FALLBACK:
            gems.sort(key=lambda x: x["final_score"], reverse=True)
            maniacs.extend([m for m in maniacs_2 if m["app_id"] not in {x["app_id"] for x in maniacs}])
            maniacs.sort(key=lambda x: x["final_score"], reverse=True)
            
            return {
                "success": True,
                "search_stage": search_stage,
                "gems": gems[:top_k],
                "maniacs": maniacs[:5] if include_maniac else [],
                "total_candidates": len(all_candidates),
                "fallback_message": "💡 검색 결과가 적어 기준을 완화하여 추가 발굴했습니다",
                "simplified_query": simplified_query,
                "error_log": error_log
            }
        
        error_log.append(f"2단계: {len(gems)}개 결과 (여전히 부족)")
        logger.info(f"[Stage 2] Still insufficient: {len(gems)} gems")
        
    except Exception as e:
        logger.warning(f"[Stage 2] Failed: {e}")
        error_log.append(f"2단계 실패: {str(e)[:50]}")
    
    # ========== 3단계: 무적 Fallback ==========
    search_stage = 3
    logger.info("[Stage 3] Emergency fallback - popular games")
    
    try:
        # 장르 필터 적용하여 인기 게임 가져오기
        genre_filter = intent.required_genres if intent.required_genres else None
        popular_games = get_popular_games(limit=top_k, genre_filter=genre_filter)
        
        # 장르 필터로 못 찾으면 필터 없이 재시도
        if len(popular_games) < MIN_RESULTS_ABSOLUTE:
            popular_games = get_popular_games(limit=top_k, genre_filter=None)
        
        # 기존 gems와 합치기
        existing_ids = {g["app_id"] for g in gems}
        for pg in popular_games:
            if pg["app_id"] not in existing_ids and len(gems) < top_k:
                pg["fallback_rescued"] = True
                gems.append(pg)
                existing_ids.add(pg["app_id"])
        
        # 여전히 부족하면 모든 후보를 최저 기준으로 재처리
        if len(gems) < MIN_RESULTS_ABSOLUTE and all_candidates:
            intent_emergency = ExtractedIntent()
            intent_emergency.metrics = []
            intent_emergency.genre_strictness = 0.0
            
            gems_emergency, _ = process_candidates(all_candidates, intent_emergency, DROP_THRESHOLD_EMERGENCY)
            
            for g in gems_emergency:
                if g["app_id"] not in existing_ids and len(gems) < top_k:
                    g["fallback_rescued"] = True
                    g["emergency_rescue"] = True
                    gems.append(g)
                    existing_ids.add(g["app_id"])
        
        gems.sort(key=lambda x: x["final_score"], reverse=True)
        
        # 최소 결과 보장
        if len(gems) == 0:
            gems = get_popular_games(limit=top_k)
        
        fallback_message = "🔥 검색 조건에 맞는 게임을 찾기 어려워, 인기 명작들을 추천해 드립니다"
        if intent.required_genres:
            genre_str = ", ".join(list(intent.required_genres)[:3])
            fallback_message = f"🔥 '{genre_str}' 관련 인기 명작들을 추천해 드립니다"
        
        return {
            "success": True,
            "search_stage": search_stage,
            "gems": gems[:top_k],
            "maniacs": maniacs[:5] if include_maniac else [],
            "total_candidates": len(all_candidates) if all_candidates else len(gems),
            "fallback_message": fallback_message,
            "is_recommendation_mode": True,
            "error_log": error_log
        }
        
    except Exception as e:
        logger.error(f"[Stage 3] Also failed: {e}")
        error_log.append(f"3단계 실패: {str(e)[:50]}")
        
        # 최후의 최후: 아무거나라도 반환
        return {
            "success": False,
            "search_stage": search_stage,
            "gems": get_popular_games(limit=top_k) or [],
            "maniacs": [],
            "total_candidates": 0,
            "fallback_message": "😢 검색에 문제가 발생했지만, 인기 게임을 추천해 드립니다",
            "is_recommendation_mode": True,
            "error_log": error_log
        }

# ============== API 엔드포인트 ==============

@app.get("/")
def root():
    """API 상태 확인"""
    return {
        "message": "Hidden Gem API v2.5 - Zero Empty Results",
        "version": "2.5",
        "features": [
            "3-Stage Fallback (Never Empty)",
            "OpenAI Auto-Retry",
            "Genre Conflict Detection",
            "Intent Objects with Korean Names",
            "Core Keyword Extraction"
        ]
    }

@app.get("/health")
def health_check():
    """헬스 체크"""
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM games")).scalar()
        return {"status": "healthy", "game_count": count, "version": "2.5"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/top")
def get_top_games(limit: int = 20):
    """잠재력 높은 게임 TOP N"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description, gem_potential
                FROM games
                ORDER BY gem_potential DESC
                LIMIT :limit
            """), {"limit": limit})
            games = [
                {
                    "app_id": r[0],
                    "name": r[1],
                    "genres": r[2],
                    "developer": r[3],
                    "description": r[4],
                    "gem_potential": r[5]
                }
                for r in result
            ]
        return {"games": games}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/{app_id}")
def get_game_detail(app_id: str):
    """게임 상세 정보"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT app_id, name, genres, developer, description,
                       mania_score, story_depth, originality, difficulty, art_style,
                       replay_value, indie_spirit, character_appeal, user_friendliness,
                       addictiveness, emotional_impact, atmosphere_intensity,
                       soundtrack_prominence, gem_potential
                FROM games WHERE app_id = :aid
            """), {"aid": app_id})
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Game not found")
            return {
                "app_id": row[0],
                "name": row[1],
                "genres": row[2],
                "developer": row[3],
                "description": row[4],
                "scores": parse_scores_from_row(row)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
def hybrid_search(request: SearchRequest):
    """
    🔥 v2.5 하이브리드 검색 API
    
    - 3단계 무적 Fallback (절대 0개 결과 없음)
    - Intent를 객체 배열로 반환 (한글 지원)
    - 장르 매칭 강화
    """
    try:
        # Intent 추출
        intent = extract_user_intent_v2(request.query)
        
        # 3단계 Fallback 검색
        search_result = hybrid_search_with_fallback(
            query=request.query,
            intent=intent,
            top_k=request.top_k,
            include_maniac=request.include_maniac
        )
        
        # Intent를 객체 배열로 변환
        intent_objects = intent.get_intent_objects()
        
        return {
            "query": request.query,
            "intents": intent_objects,  # 🆕 객체 배열: [{"id": "story_depth", "name": "스토리 깊이"}, ...]
            "gems": search_result["gems"],
            "maniacs": search_result["maniacs"],
            "total_candidates": search_result["total_candidates"],
            "algorithm_version": "v2.5",
            "fallback_activated": search_result["search_stage"] > 1,
            "fallback_message": search_result["fallback_message"],
            "search_stage": search_result["search_stage"],
            "genre_analysis": {
                "required_genres": list(intent.required_genres)[:10],
                "negative_genres": list(intent.negative_genres)[:10],
                "preferred_keywords": intent.preferred_keywords[:5],
                "core_keywords": intent.core_keywords,
                "reference_game": intent.reference_game,
                "strictness": intent.genre_strictness
            },
            "is_recommendation_mode": search_result.get("is_recommendation_mode", False)
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        
        # 최후의 보루: 인기 게임 반환
        try:
            popular = get_popular_games(limit=request.top_k)
            return {
                "query": request.query,
                "intents": [],
                "gems": popular if popular else [],
                "maniacs": [],
                "total_candidates": len(popular) if popular else 0,
                "algorithm_version": "v2.5",
                "fallback_activated": True,
                "fallback_message": "🔥 검색 중 오류가 발생하여 인기 명작을 추천해 드립니다",
                "search_stage": 3,
                "is_recommendation_mode": True,
                "error": str(e)[:100]
            }
        except Exception as inner_e:
            logger.error(f"Even fallback failed: {inner_e}")
            raise HTTPException(
                status_code=500,
                detail="검색 서비스에 일시적인 문제가 발생했습니다."
            )

@app.get("/games/filter")
def filter_games(
    min_gem: int = 0,
    max_gem: int = 100,
    genre: Optional[str] = None,
    limit: int = 20
):
    """필터링 검색"""
    try:
        query = """
            SELECT app_id, name, genres, developer, description, gem_potential
            FROM games
            WHERE gem_potential BETWEEN :min AND :max
        """
        params: Dict[str, Any] = {"min": min_gem, "max": max_gem, "limit": limit}
        
        if genre:
            query += " AND genres ILIKE :genre"
            params["genre"] = f"%{genre}%"
        
        query += " ORDER BY gem_potential DESC LIMIT :limit"
        
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            games = [
                {
                    "app_id": r[0],
                    "name": r[1],
                    "genres": r[2],
                    "developer": r[3],
                    "description": r[4],
                    "gem_potential": r[5]
                }
                for r in result
            ]
        return {"games": games, "count": len(games)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debug/intent")
def debug_intent(request: SearchRequest):
    """Intent 추출 디버깅"""
    intent = extract_user_intent_v2(request.query)
    return {
        "query": request.query,
        "metrics": intent.metrics,
        "intent_objects": intent.get_intent_objects(),
        "required_genres": list(intent.required_genres),
        "preferred_keywords": intent.preferred_keywords,
        "negative_genres": list(intent.negative_genres),
        "core_keywords": intent.core_keywords,
        "reference_game": intent.reference_game,
        "genre_strictness": intent.genre_strictness
    }

# ============== 서버 실행 ==============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
