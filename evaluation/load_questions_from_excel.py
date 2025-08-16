#!/usr/bin/env python3
"""
기존 엑셀 파일에서 1000개 질문 로드 및 평가용 형식으로 변환
"""

import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import sys

def load_and_convert_questions(excel_path: str, output_path: str = None) -> pd.DataFrame:
    """기존 엑셀 파일에서 질문을 로드하고 평가용 형식으로 변환"""
    
    print(f"📄 엑셀 파일 로드 중: {excel_path}")
    
    try:
        # 엑셀 파일 읽기
        if excel_path.endswith('.xlsx'):
            df = pd.read_excel(excel_path, engine='openpyxl')
        elif excel_path.endswith('.xls'):
            df = pd.read_excel(excel_path, engine='xlrd')
        else:
            raise ValueError("엑셀 파일만 지원됩니다 (.xlsx, .xls)")
        
        print(f"✅ 원본 데이터 로드 완료: {len(df)}개 행")
        print(f"📊 컬럼: {list(df.columns)}")
        
        # 컬럼 이름 정규화 및 매핑
        df.columns = df.columns.str.strip().str.lower()
        
        # 가능한 컬럼 이름 매핑
        column_mapping = {
            # 질문 컬럼 가능한 이름들
            'question': 'question',
            'questions': 'question', 
            '질문': 'question',
            'query': 'question',
            'q': 'question',
            
            # 답변 컬럼 가능한 이름들  
            'answer': 'expected_answer',
            'answers': 'expected_answer',
            'expected_answer': 'expected_answer',
            'ground_truth': 'expected_answer',
            '답변': 'expected_answer',
            '정답': 'expected_answer',
            'response': 'expected_answer',
            'a': 'expected_answer',
            
            # 카테고리 컬럼 가능한 이름들
            'category': 'category',
            'categories': 'category',
            '카테고리': 'category',
            'type': 'category',
            'class': 'category',
            'tag': 'category',
            'topic': 'category',
            '분류': 'category'
        }
        
        # 컬럼 매핑 적용
        available_columns = {}
        for orig_col in df.columns:
            if orig_col in column_mapping:
                available_columns[column_mapping[orig_col]] = orig_col
        
        print(f"🔍 발견된 컬럼 매핑:")
        for target, orig in available_columns.items():
            print(f"   {target} ← {orig}")
        
        # 필수 컬럼 확인
        if 'question' not in available_columns:
            print(f"❌ 질문 컬럼을 찾을 수 없습니다.")
            print(f"사용 가능한 컬럼: {list(df.columns)}")
            print(f"질문 컬럼으로 사용할 수 있는 이름: question, questions, 질문, query")
            return None
        
        # 새로운 DataFrame 생성
        converted_data = []
        
        for idx, row in df.iterrows():
            # 기본 데이터
            question_text = str(row[available_columns['question']]).strip()
            
            # 빈 질문 스킵
            if not question_text or question_text.lower() in ['nan', 'none', '']:
                continue
            
            # 답변 처리
            if 'expected_answer' in available_columns:
                expected_answer = str(row[available_columns['expected_answer']]).strip()
                if expected_answer.lower() in ['nan', 'none', '']:
                    expected_answer = "답변 정보가 없습니다."
            else:
                # 답변이 없는 경우 기본값 생성
                expected_answer = "문의해주신 내용에 대해 정확한 정보를 제공해드리겠습니다."
            
            # 카테고리 처리
            if 'category' in available_columns:
                category = str(row[available_columns['category']]).strip()
                if category.lower() in ['nan', 'none', '']:
                    category = "일반"
            else:
                # 카테고리가 없는 경우 질문 내용으로 추정
                category = categorize_question(question_text)
            
            # 추가 메타데이터
            converted_item = {
                'id': idx + 1,
                'question': question_text,
                'expected_answer': expected_answer,
                'category': category,
                'difficulty': estimate_difficulty(question_text),
                'priority': '중간',
                'created_date': '2024-12-01',
                'tags': f"{category}, 삼성, 스마트폰",
                'source': 'excel_import',
                'original_row': idx + 1
            }
            
            # 원본 데이터의 추가 컬럼들 보존
            for col in df.columns:
                if col not in [available_columns.get('question'), 
                              available_columns.get('expected_answer'), 
                              available_columns.get('category')]:
                    converted_item[f'original_{col}'] = row[col]
            
            converted_data.append(converted_item)
        
        if not converted_data:
            print("❌ 변환할 수 있는 유효한 질문이 없습니다.")
            return None
        
        # DataFrame 생성
        result_df = pd.DataFrame(converted_data)
        
        print(f"✅ 데이터 변환 완료: {len(result_df)}개 질문")
        
        # 카테고리별 통계
        print(f"\n📊 카테고리별 분포:")
        category_counts = result_df['category'].value_counts()
        for category, count in category_counts.head(10).items():
            print(f"   • {category}: {count}개")
        
        # 1000개로 제한 (너무 많은 경우)
        if len(result_df) > 1000:
            print(f"⚠️ 질문이 {len(result_df)}개로 많아서 1000개로 샘플링합니다.")
            # 카테고리별 비례 샘플링
            result_df = stratified_sample(result_df, 1000)
            print(f"✅ 1000개로 샘플링 완료")
        
        # 부족한 경우 경고
        elif len(result_df) < 100:
            print(f"⚠️ 질문이 {len(result_df)}개로 적습니다. 최소 100개 이상을 권장합니다.")
        
        # 출력 파일 저장
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Excel 저장
            result_df.to_excel(output_path, index=False, engine='openpyxl')
            print(f"💾 변환된 데이터 저장: {output_path}")
            
            # CSV 백업도 저장
            csv_path = output_path.with_suffix('.csv')
            result_df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"💾 CSV 백업 저장: {csv_path}")
        
        return result_df
        
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        import traceback
        print(f"상세 오류: {traceback.format_exc()}")
        return None

def categorize_question(question: str) -> str:
    """질문 내용을 바탕으로 카테고리 추정"""
    question_lower = question.lower()
    
    # 키워드 기반 카테고리 분류
    category_keywords = {
        '카메라 기능': ['카메라', '촬영', '화소', '줌', '플래시', '동영상', '사진'],
        '디스플레이': ['화면', '디스플레이', '해상도', '밝기', '색상', '터치'],
        '성능': ['프로세서', 'cpu', 'ram', '메모리', '저장', '속도', '성능'],
        '배터리': ['배터리', '충전', '사용시간', '절전'],
        '디자인': ['무게', '두께', '색상', '디자인', '재질', '방수'],
        '연결성': ['5g', 'wifi', '블루투스', 'nfc', 'usb'],
        '소프트웨어': ['안드로이드', 'ui', '앱', '소프트웨어', '운영체제'],
        '가격_정책': ['가격', '할인', '비용', '결제', '이벤트'],
        'A/S_보증': ['보증', 'a/s', '수리', '서비스'],
        '액세서리': ['케이스', '액세서리', '이어폰', '충전기']
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in question_lower for keyword in keywords):
            return category
    
    return '일반'

def estimate_difficulty(question: str) -> str:
    """질문 복잡도를 바탕으로 난이도 추정"""
    question_length = len(question)
    
    # 복잡한 키워드가 있는지 확인
    complex_keywords = ['비교', '차이', '분석', '상세', '자세히', '어떻게', '왜']
    has_complex = any(keyword in question for keyword in complex_keywords)
    
    if question_length > 50 or has_complex:
        return '어려움'
    elif question_length > 20:
        return '보통'
    else:
        return '쉬움'

def stratified_sample(df: pd.DataFrame, target_size: int) -> pd.DataFrame:
    """카테고리별 비례 샘플링"""
    try:
        # 카테고리별 비율 계산
        category_counts = df['category'].value_counts()
        total_count = len(df)
        
        sampled_dfs = []
        remaining_size = target_size
        
        for i, (category, count) in enumerate(category_counts.items()):
            if i == len(category_counts) - 1:  # 마지막 카테고리
                sample_size = remaining_size
            else:
                sample_size = int((count / total_count) * target_size)
                remaining_size -= sample_size
            
            category_df = df[df['category'] == category]
            if len(category_df) <= sample_size:
                sampled_dfs.append(category_df)
            else:
                sampled_df = category_df.sample(n=sample_size, random_state=42)
                sampled_dfs.append(sampled_df)
        
        result = pd.concat(sampled_dfs, ignore_index=True)
        # ID 재부여
        result['id'] = range(1, len(result) + 1)
        
        return result
        
    except Exception as e:
        print(f"⚠️ 샘플링 실패, 단순 샘플링 사용: {e}")
        return df.sample(n=min(target_size, len(df)), random_state=42).reset_index(drop=True)

def main():
    parser = argparse.ArgumentParser(description='엑셀 파일에서 평가용 질문 데이터 로드')
    parser.add_argument('excel_path', help='입력 엑셀 파일 경로')
    parser.add_argument('--output', '-o', default='evaluation/data/questions_1000.xlsx',
                       help='출력 파일 경로 (기본: evaluation/data/questions_1000.xlsx)')
    parser.add_argument('--preview', '-p', action='store_true',
                       help='변환 결과 미리보기만 수행')
    
    args = parser.parse_args()
    
    # 파일 존재 확인
    if not Path(args.excel_path).exists():
        print(f"❌ 파일이 존재하지 않습니다: {args.excel_path}")
        return 1
    
    print("📝 엑셀 파일에서 평가용 질문 데이터 로드")
    print("=" * 50)
    
    # 데이터 로드 및 변환
    if args.preview:
        df = load_and_convert_questions(args.excel_path)
        if df is not None:
            print(f"\n📋 변환 결과 미리보기 (상위 5개):")
            for i in range(min(5, len(df))):
                row = df.iloc[i]
                print(f"   {i+1}. [{row['category']}] {row['question']}")
                print(f"      답변: {row['expected_answer'][:100]}...")
                print()
    else:
        df = load_and_convert_questions(args.excel_path, args.output)
        if df is not None:
            print(f"\n🎯 변환 완료!")
            print(f"   📄 출력 파일: {args.output}")
            print(f"   📊 총 질문 수: {len(df)}개")
            print(f"\n다음 명령으로 평가를 실행할 수 있습니다:")
            print(f"   python3 evaluation/run_evaluation.py")
        else:
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())