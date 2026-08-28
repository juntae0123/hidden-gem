# embeddings/batch_merger.py
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

class BatchMerger:
    """17개 배치 결과를 하나로 병합"""
    
    def __init__(self, batch_dir: str = "data/batches"):
        # 현재 실행 위치 기준으로 절대 경로 확보
        base_dir = Path.cwd()
        self.batch_dir = base_dir / batch_dir
        self.output_dir = base_dir / "data/merged"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def find_batch_files(self) -> List[Path]:
        """배치 결과 파일들 찾기 (모든 jsonl 파일 허용)"""
        if not self.batch_dir.exists():
            print(f"폴더를 찾을 수 없습니다: {self.batch_dir.absolute()}")
            return []

        # data/batches 폴더 안의 모든 .jsonl 파일을 찾음
        files = list(self.batch_dir.glob("*.jsonl"))
        
        print(f"확인된 경로: {self.batch_dir.absolute()}")
        print(f"발견된 배치 파일: {len(files)}개")
        for f in files:
            print(f"   - {f.name}")
        
        return files
    
    def parse_batch_file(self, filepath: Path) -> List[Dict]:
        """단일 배치 파일 파싱"""
        results = []
        errors = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                    
                    if 'response' in data and 'body' in data['response']:
                        custom_id = data.get('custom_id', '')
                        content = data['response']['body']['choices'][0]['message']['content']
                        
                        parsed = self._parse_content(content)
                        parsed['_meta'] = {
                            'custom_id': custom_id,
                            'source_file': filepath.name,
                            'line_num': line_num
                        }
                        results.append(parsed)
                        
                    elif 'metrics' in data or 'app_id' in data:
                        results.append(data)
                        
                except Exception as e:
                    errors.append({
                        'file': filepath.name,
                        'line': line_num,
                        'error': str(e)
                    })
        
        print(f"   {filepath.name}: {len(results)}개 성공, {len(errors)}개 에러")
        return results, errors
    
    def _parse_content(self, content: str) -> Dict:
        """GPT 응답 content 파싱"""
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        return json.loads(content.strip())
    
    def merge_all(self) -> Dict[str, Any]:
        """모든 배치 병합"""
        files = self.find_batch_files()
        
        if not files:
            return {}
        
        all_results = []
        all_errors = []
        duplicate_check = {} 
        
        print("\n병합 시작...")
        
        for filepath in files:
            results, errors = self.parse_batch_file(filepath)
            
            for item in results:
                app_id = None
                if '_meta' in item and 'custom_id' in item['_meta']:
                    # 멘티님 데이터 형태인 'request-3115220' 에서 숫자만 추출하도록 수정
                    custom_id = item['_meta']['custom_id']
                    match = re.search(r'\d+', custom_id)
                    if match:
                        app_id = match.group()
                elif 'app_id' in item:
                    app_id = str(item['app_id'])
                
                if app_id:
                    if app_id in duplicate_check:
                        continue
                    duplicate_check[app_id] = True
                    item['app_id'] = int(app_id) if app_id.isdigit() else app_id
                
                all_results.append(item)
            
            all_errors.extend(errors)
        
        print(f"\n병합 결과:")
        print(f"   - 총 게임: {len(all_results)}개")
        print(f"   - 에러: {len(all_errors)}개")
        
        return {
            'games': all_results,
            'errors': all_errors,
            'stats': {
                'total': len(all_results),
                'errors': len(all_errors),
                'merged_at': datetime.now().isoformat()
            }
        }
    
    def save_merged(self, data: Dict, format: str = 'both') -> Dict[str, Path]:
        """병합 결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved = {}
        
        if format in ['jsonl', 'both']:
            jsonl_path = self.output_dir / f"merged_games.jsonl"
            with open(jsonl_path, 'w', encoding='utf-8') as f:
                for game in data['games']:
                    f.write(json.dumps(game, ensure_ascii=False) + '\n')
            print(f"JSONL 저장: {jsonl_path}")
            
        return saved

def main():
    # 경로를 명시적으로 설정
    merger = BatchMerger(batch_dir="data/batches")
    data = merger.merge_all()
    
    if data and data.get('games'):
        merger.save_merged(data, format='jsonl')
        print("\n완벽하게 합쳐졌습니다! data/merged 폴더를 확인하세요.")
    else:
        print("\n병합 실패: 데이터를 찾을 수 없습니다.")

if __name__ == '__main__':
    main()