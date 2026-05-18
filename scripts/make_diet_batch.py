#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

NEW_METRICS_TO_EXTRACT: List[str] = [
    "build_variety",
    "progression_clarity",
    "save_flexibility",
    "difficulty_accessibility",
    "tutorial_quality",
    "ui_ux_polish",
    "modding_support",
    "art_style_uniqueness",
    "audio_design",
    "animation_quality",
    "puzzle_complexity",
    "platforming_precision",
    "world_reactivity",
    "community_dependency",
    "narrative_depth",
    "replay_value",
    "endgame_content",
    "monetization_fairness",
]

assert len(NEW_METRICS_TO_EXTRACT) == 18

SYSTEM_PROMPT = """너는 게임 분석 전문가야. 아래 게임 정보를 바탕으로 18개 지표를 0-10점으로 평가해줘.

## 평가 지표 (모두 0-10점, 정수로)

### 시스템/UX (7개)
- build_variety: 빌드/캐릭터 조합의 다양성 (0=획일적, 10=무한 조합)
- progression_clarity: 진행 목표의 명확성 (0=막막함, 10=명확한 가이드)
- save_flexibility: 저장 시스템 유연성 (0=체크포인트만, 10=언제든 저장)
- difficulty_accessibility: 난이도 옵션/접근성 (0=고정 난이도, 10=다양한 옵션)
- tutorial_quality: 튜토리얼/온보딩 품질 (0=없거나 불친절, 10=완벽한 안내)
- ui_ux_polish: UI/UX 완성도 (0=조잡함, 10=세련됨)
- modding_support: 모딩/커스텀 지원 (0=미지원, 10=풍부한 모딩 생태계)

### 아트/오디오 (3개)
- art_style_uniqueness: 아트 스타일 독창성 (0=무난함, 10=강렬한 개성)
- audio_design: 효과음/환경음 디자인 (0=빈약, 10=몰입감 극대화)
- animation_quality: 애니메이션 품질 (0=어색함, 10=자연스럽고 역동적)

### 메카닉 (2개)
- puzzle_complexity: 퍼즐 복잡도 (0=퍼즐 없음, 10=고난도 두뇌 싸움)
- platforming_precision: 플랫포밍 정밀도 요구 (0=플랫포밍 없음, 10=프레임 단위 정밀 조작)

### 기타 (2개)
- world_reactivity: 월드/NPC가 플레이어 행동에 반응하는 정도 (0=무반응, 10=살아있는 세계)
- community_dependency: 커뮤니티/공략 의존도 (0=솔플 가능, 10=위키 필수)

### 신규 보완 (4개)
- narrative_depth: 서사/스토리텔링 깊이 (0=스토리 없음, 10=문학적 깊이)
- replay_value: 회차 플레이 가치 (0=1회성, 10=무한 리플레이)
- endgame_content: 엔드게임/후반 콘텐츠 양 (0=엔딩 후 끝, 10=끝없는 콘텐츠)
- monetization_fairness: 과금 공정성 (0=P2W, 5=유료게임, 10=완전 공정)

## 출력 형식 (JSON만, 다른 텍스트 금지)
{"build_variety": 5, "progression_clarity": 7, "save_flexibility": 6, "difficulty_accessibility": 4, "tutorial_quality": 5, "ui_ux_polish": 6, "modding_support": 2, "art_style_uniqueness": 7, "audio_design": 6, "animation_quality": 5, "puzzle_complexity": 3, "platforming_precision": 1, "world_reactivity": 4, "community_dependency": 3, "narrative_depth": 6, "replay_value": 7, "endgame_content": 5, "monetization_fairness": 8}

정보가 부족하면 5(중립값)로 설정해. 반드시 18개 필드 모두 포함할 것."""


def extract_diet_text(data: Dict[str, Any]) -> str:
    """
    게임 데이터에서 GPT 프롬프트용 압축 텍스트 생성 (Diet Text Extractor)

    원본 JSONL의 핵심 정보만 추출하여 토큰 절약.
    포함 항목: 이름, 분석요약, 코어루프, 마케팅훅, 한줄요약, 높은 지표(≥7), 활성 태그

    Args:
        data: 게임 JSONL 레코드 딕셔너리

    Returns:
        줄바꿈으로 구분된 핵심 정보 텍스트 (GPT 프롬프트의 user 파트)
    """
    texts = []

    name = data.get("name", "Unknown")
    app_id = data.get("app_id", 0)
    texts.append(f"게임: {name} (app_id: {app_id})")

    reasoning = data.get("reasoning", {})
    if reasoning.get("analysis_summary"):
        texts.append(f"분석 요약: {reasoning['analysis_summary']}")
    if reasoning.get("core_loop"):
        texts.append(f"코어 루프: {reasoning['core_loop']}")
    if reasoning.get("genre_classification"):
        texts.append(f"장르: {reasoning['genre_classification']}")

    content = data.get("content", {})

    # marketing_hook은 dict 또는 str 형태 모두 처리
    hook = content.get("marketing_hook", "")
    if isinstance(hook, dict):
        hook_text = hook.get("primary", "") or hook.get("emotional", "") or hook.get("mechanical", "")
        if hook_text:
            texts.append(f"마케팅 훅: {hook_text}")
    elif hook:
        texts.append(f"마케팅 훅: {hook}")

    if content.get("one_line_summary"):
        texts.append(f"한줄 요약: {content['one_line_summary']}")

    usps = content.get("unique_selling_points", [])
    if usps:
        texts.append(f"USP: {', '.join(usps[:3])}")  # 최대 3개로 토큰 절약

    # 높은 지표(≥7)만 포함 - 게임 개성을 효율적으로 전달
    metrics = data.get("metrics", {})
    metric_summary = []
    for category in ["vibe", "demands", "mechanics", "social", "presentation"]:
        cat_data = metrics.get(category, {})
        if cat_data:
            sorted_items = sorted(cat_data.items(), key=lambda x: x[1] if x[1] is not None else 0, reverse=True)[:3]
            for k, v in sorted_items:
                if v is not None and v >= 7:
                    metric_summary.append(f"{k}={v}")

    if metric_summary:
        texts.append(f"주요 지표: {', '.join(metric_summary)}")

    # 활성화된 Boolean 태그만 포함
    tags = data.get("tags", {})
    active_tags = [k for k, v in tags.items() if v]
    if active_tags:
        texts.append(f"태그: {', '.join(active_tags)}")

    return "\n".join(texts)


def create_batch_request(app_id: int, diet_text: str) -> Dict[str, Any]:
    """
    OpenAI Batch API 단일 요청 객체 생성 (Batch Request Builder)

    Batch API 형식: custom_id + method + url + body 구조.
    custom_id = "diet-{app_id}" 형식으로 merge_metrics.py에서 app_id 역추출 가능.

    Args:
        app_id: Steam App ID (결과 매핑용)
        diet_text: extract_diet_text()로 생성한 압축 게임 정보 텍스트

    Returns:
        Batch API 요청 딕셔너리 (JSONL 한 줄로 직렬화됨)
    """
    return {
        "custom_id": f"diet-{app_id}",  # 응답에서 app_id 식별용
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-5.4",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": diet_text}
            ],
            "temperature": 0.3,            # 낮은 온도로 일관된 JSON 출력 유도
            "max_completion_tokens": 500,  # 18개 지표 JSON은 500토큰이면 충분
            "response_format": {"type": "json_object"}  # JSON 강제 출력
        }
    }


def main():
    """
    Batch 요청 파일 생성 메인 로직 (Batch Request File Generator)

    원본 merged_games.jsonl을 읽어 각 게임의 핵심 정보(diet_text)를 추출하고
    Batch API 형식의 단일 JSONL 파일로 저장. 이후 split_batch.py로 분할.
    --preview로 실제 GPT에 보내는 텍스트를 미리 확인 가능.
    """
    parser = argparse.ArgumentParser(description="토큰 다이어트 Batch 요청 파일 생성")
    parser.add_argument("--input", "-i", type=str, required=True, help="기존 merged_games.jsonl 경로")
    parser.add_argument("--output", "-o", type=str, default="diet_batch_requests.jsonl", help="출력 Batch 요청 파일 경로")
    parser.add_argument("--limit", type=int, default=0, help="처리할 최대 게임 수 (0=전체)")
    parser.add_argument("--preview", action="store_true", help="첫 3개만 미리보기 후 종료")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"입력 파일 없음: {input_path}")
        return 1
    
    print(f"입력: {input_path}")
    print(f"출력: {output_path}")
    print(f"추출 지표: {len(NEW_METRICS_TO_EXTRACT)}개")
    print(f"모델: gpt-5.4")
    
    games_data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if args.limit and i >= args.limit:
                break
            if line.strip():
                try:
                    games_data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 오류 (line {i+1}): {e}")
    
    print(f"로드된 게임: {len(games_data)}개")
    
    if args.preview:
        print("\n미리보기 (첫 3개):\n")
        for data in games_data[:3]:
            app_id = data.get("app_id", 0)
            name = data.get("name", "Unknown")
            diet_text = extract_diet_text(data)
            print(f"=== [{app_id}] {name} ===")
            print(diet_text)
            print(f"토큰 예상: ~{len(diet_text.split())} words\n")
        print("미리보기 완료. --preview 옵션 제거 후 실행하세요.")
        return 0
    
    requests = []
    errors = 0
    
    for i, data in enumerate(games_data):
        app_id = data.get("app_id")
        if not app_id:
            errors += 1
            continue
        try:
            diet_text = extract_diet_text(data)
            request = create_batch_request(app_id, diet_text)
            requests.append(request)
        except Exception as e:
            print(f"요청 생성 실패 [{app_id}]: {e}")
            errors += 1
    
    with open(output_path, "w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")
    
    file_size = output_path.stat().st_size / 1024 / 1024
    
    print(f"\nBatch 요청 파일 생성 완료!")
    print(f"생성된 요청: {len(requests)}개")
    print(f"에러: {errors}개")
    print(f"파일 크기: {file_size:.2f} MB")
    print(f"출력 파일: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
