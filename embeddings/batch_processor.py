"""
Hidden Gem - Batch API Result Processor
========================================
GPT Batch API 결과를 파싱하고 DB에 저장

사용법:
    cd Hidden-Gem-project
    source .venv/Scripts/activate
    python -m embeddings.batch_processor data/batch_output.jsonl
"""

import os
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from tqdm import tqdm

# ============== 경로 설정 ==============
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError("❌ .env에 DATABASE_URL이 없습니다!")

engine = create_engine(DB_URL)


# ============== Batch 결과 파싱 ==============
def parse_batch_result(result_file: str) -> Dict[str, Dict]:
    """Batch API 결과 JSONL 파싱"""
    results = {}
    success_count = 0
    error_count = 0
    
    print(f"📂 파일 읽는 중: {result_file}")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                item = json.loads(line)
                custom_id = item.get("custom_id", "")
                
                # game-123 형식에서 ID 추출
                game_id = custom_id.replace("game-", "")
                
                # 응답 파싱
                response = item.get("response", {})
                status_code = response.get("status_code")
                
                if status_code == 200:
                    body = response.get("body", {})
                    choices = body.get("choices", [])
                    
                    if choices:
                        content = choices[0].get("message", {}).get("content", "{}")
                        
                        try:
                            parsed = json.loads(content)
                            results[game_id] = {
                                "success": True,
                                "data": parsed,
                                "usage": body.get("usage", {})
                            }
                            success_count += 1
                        except json.JSONDecodeError as e:
                            results[game_id] = {
                                "success": False, 
                                "error": f"JSON parse error: {e}"
                            }
                            error_count += 1
                    else:
                        results[game_id] = {"success": False, "error": "No choices"}
                        error_count += 1
                else:
                    error_msg = response.get("error", {}).get("message", "Unknown error")
                    results[game_id] = {"success": False, "error": error_msg}
                    error_count += 1
                    
            except Exception as e:
                print(f"   ⚠️ Line {line_num} 파싱 실패: {e}")
                error_count += 1
    
    print(f"✅ 파싱 완료: 성공 {success_count}, 실패 {error_count}")
    return results


# ============== DB 업데이트 ==============
def update_db_with_results(results: Dict[str, Dict]) -> tuple:
    """파싱된 결과를 DB에 업데이트"""
    success_count = 0
    error_count = 0
    
    print(f"\n📤 DB 업데이트 중... ({len(results)}개)")
    
    with engine.begin() as conn:
        for game_id, result in tqdm(results.items(), desc="업데이트"):
            if not result.get("success"):
                error_count += 1
                continue
            
            data = result.get("data", {})
            
            try:
                # JSONB 컬럼에 저장
                conn.execute(text("""
                    UPDATE games SET
                        metrics = :metrics,
                        tags = :tags,
                        content = :content,
                        reasoning = :reasoning,
                        extraction_meta = :meta
                    WHERE id = :game_id
                """), {
                    "game_id": int(game_id),
                    "metrics": json.dumps(data.get("metrics", {}), ensure_ascii=False),
                    "tags": json.dumps(data.get("tags", {}), ensure_ascii=False),
                    "content": json.dumps(data.get("content", {}), ensure_ascii=False),
                    "reasoning": json.dumps(data.get("reasoning", {}), ensure_ascii=False),
                    "meta": json.dumps({
                        "extracted_at": datetime.now().isoformat(),
                        "prompt_version": "v5.0",
                        "usage": result.get("usage", {})
                    }, ensure_ascii=False)
                })
                success_count += 1
                
            except Exception as e:
                print(f"\n   ⚠️ game_id={game_id} 업데이트 실패: {e}")
                error_count += 1
    
    return success_count, error_count


# ============== 결과 검증 ==============
def validate_results(results: Dict[str, Dict]) -> None:
    """결과 품질 검증"""
    print("\n🔍 결과 품질 검증 중...")
    
    total = len(results)
    success = sum(1 for r in results.values() if r.get("success"))
    
    # 샘플 확인
    success_samples = [r for r in results.values() if r.get("success")][:3]
    
    print(f"\n📊 통계:")
    print(f"   총 결과: {total}")
    print(f"   성공: {success} ({success/total*100:.1f}%)")
    print(f"   실패: {total - success}")
    
    if success_samples:
        print(f"\n📋 샘플 결과 (첫 번째):")
        sample = success_samples[0].get("data", {})
        
        # metrics 확인
        metrics = sample.get("metrics", {})
        if metrics:
            vibe = metrics.get("vibe", {})
            print(f"   cozy_factor: {vibe.get('cozy_factor', 'N/A')}")
            print(f"   horror_factor: {vibe.get('horror_factor', 'N/A')}")
        
        # content 확인
        content = sample.get("content", {})
        if content:
            hook = content.get("marketing_hook", {})
            print(f"   marketing_hook: {hook.get('primary', 'N/A')[:30]}...")
        
        # confidence 확인
        reasoning = sample.get("reasoning", {})
        print(f"   confidence_score: {reasoning.get('confidence_score', 'N/A')}")


# ============== 메인 함수 ==============
def main():
    parser = argparse.ArgumentParser(
        description="Hidden Gem - Batch API 결과 처리기"
    )
    parser.add_argument(
        "result_file", 
        help="Batch API 결과 JSONL 파일 경로"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="DB 업데이트 없이 파싱만 수행"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔄 Hidden Gem - Batch 결과 처리기")
    print("=" * 60)
    print(f"📂 결과 파일: {args.result_file}")
    print(f"📁 프로젝트 루트: {PROJECT_ROOT}")
    print(f"🔗 DB: {DB_URL[:30]}...")
    print("=" * 60)
    
    # 1. 파일 존재 확인
    result_path = Path(args.result_file)
    if not result_path.exists():
        # data/ 폴더에서도 찾아보기
        result_path = DATA_DIR / args.result_file
        if not result_path.exists():
            print(f"❌ 파일을 찾을 수 없습니다: {args.result_file}")
            return
    
    # 2. 결과 파싱
    results = parse_batch_result(str(result_path))
    
    if not results:
        print("❌ 파싱된 결과가 없습니다!")
        return
    
    # 3. 결과 검증
    validate_results(results)
    
    # 4. DB 업데이트 (dry-run 아닐 때만)
    if args.dry_run:
        print("\n⚠️ Dry-run 모드: DB 업데이트 건너뜀")
    else:
        confirm = input("\n🔥 DB에 업데이트하시겠습니까? (y/n): ").strip().lower()
        if confirm == 'y':
            success, errors = update_db_with_results(results)
            
            print("\n" + "=" * 60)
            print("✅ 처리 완료!")
            print(f"   성공: {success}개")
            print(f"   실패: {errors}개")
            print("=" * 60)
        else:
            print("❌ 취소됨")


if __name__ == "__main__":
    main()
