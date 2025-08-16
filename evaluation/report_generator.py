"""
평가 결과 보고서 생성 모듈
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import logging

class ReportGenerator:
    """평가 결과 보고서 생성 클래스"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # 출력 디렉토리
        self.output_dir = Path(config['data_paths']['output_dir'])
        self.reports_dir = self.output_dir / 'reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # 타임스탬프
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.logger.info("📝 보고서 생성기 초기화 완료")
    
    def save_json_results(self, results: Dict[str, Any], 
                         category_analysis: Dict[str, Any],
                         recommendations: Dict[str, List[str]],
                         individual_results: List[Dict[str, Any]]) -> str:
        """JSON 형식으로 전체 결과 저장"""
        self.logger.info("💾 JSON 결과 저장 중...")
        
        try:
            comprehensive_results = {
                'metadata': {
                    'evaluation_timestamp': self.timestamp,
                    'config_used': self.config,
                    'total_questions': len(individual_results),
                    'successful_evaluations': len([r for r in individual_results if r.get('success', False)]),
                    'rag_server_config': 'RAG 서버 내부 구성요소 사용 (청킹/임베딩/리트리버)'
                },
                'ragas_results': results,
                'category_analysis': category_analysis,
                'recommendations': recommendations,
                'individual_results': individual_results
            }
            
            json_path = self.reports_dir / f'evaluation_results_{self.timestamp}.json'
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(comprehensive_results, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"✅ JSON 결과 저장 완료: {json_path}")
            return str(json_path)
            
        except Exception as e:
            self.logger.error(f"❌ JSON 결과 저장 실패: {e}")
            return ""
    
    def save_excel_results(self, results: Dict[str, Any],
                          category_analysis: Dict[str, Any],
                          individual_results: List[Dict[str, Any]]) -> str:
        """Excel 형식으로 결과 저장"""
        self.logger.info("📊 Excel 결과 저장 중...")
        
        try:
            excel_path = self.reports_dir / f'evaluation_results_{self.timestamp}.xlsx'
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # 1. 요약 시트
                summary_data = []
                metrics_data = results.get('detailed_metrics', {})
                
                for metric_name, metric_info in metrics_data.items():
                    summary_data.append({
                        '메트릭': metric_name,
                        '점수': metric_info['score'],
                        '임계값': metric_info['threshold'],
                        '성능': metric_info['performance'],
                        '차이': metric_info['gap']
                    })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='요약', index=False)
                
                # 2. 개별 결과 시트
                if individual_results:
                    # 안전한 데이터 변환
                    processed_results = []
                    for result in individual_results:
                        processed_result = {}
                        for key, value in result.items():
                            if key == 'contexts' and isinstance(value, list):
                                # 리스트를 문자열로 변환
                                processed_result['contexts_text'] = ' | '.join(str(v) for v in value)
                            else:
                                processed_result[key] = value
                        processed_results.append(processed_result)
                    
                    individual_df = pd.DataFrame(processed_results)
                    
                    # 필요한 컬럼만 선택
                    columns_to_save = ['question', 'answer', 'contexts_text', 'ground_truth', 
                                     'category', 'success', 'timestamp']
                    available_columns = [col for col in columns_to_save if col in individual_df.columns]
                    
                    if available_columns:
                        individual_df[available_columns].to_excel(writer, sheet_name='개별결과', index=False)
                
                # 3. 카테고리 분석 시트
                if category_analysis:
                    category_data = []
                    for category, data in category_analysis.items():
                        category_data.append({
                            '카테고리': category,
                            '질문수': data.get('count', 0),
                            '전체점수': data.get('overall_score', 0),
                            '샘플질문': ' | '.join(data.get('sample_questions', [])[:2])
                        })
                    
                    if category_data:
                        category_df = pd.DataFrame(category_data)
                        category_df.to_excel(writer, sheet_name='카테고리분석', index=False)
                
                #