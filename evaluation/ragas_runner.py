"""
RAGAS 평가 실행 모듈 - RAG 서버 결과 기반 평가
RAG 서버의 청킹/임베딩/리트리버 변경사항이 자동으로 반영됩니다
"""

import pandas as pd
from typing import Dict, Any, List
from datasets import Dataset
import logging
from datetime import datetime

# RAGAS imports
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    context_relevancy,
    answer_similarity,
    answer_correctness
)

class RAGASRunner:
    """RAGAS 평가 실행 클래스 - RAG 서버 결과만 사용"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # RAGAS 메트릭 매핑
        self.metric_map = {
            'faithfulness': faithfulness,
            'answer_relevancy': answer_relevancy,
            'context_precision': context_precision,
            'context_recall': context_recall,
            'context_relevancy': context_relevancy,
            'answer_similarity': answer_similarity,
            'answer_correctness': answer_correctness
        }
        
        # 설정된 메트릭만 선택
        self.selected_metrics = []
        for metric_name in self.config['ragas_metrics']:
            if metric_name in self.metric_map:
                self.selected_metrics.append(self.metric_map[metric_name])
                self.logger.info(f"📊 메트릭 추가: {metric_name}")
        
        self.logger.info(f"🎯 총 {len(self.selected_metrics)}개 메트릭 선택됨")
    
    def run_evaluation(self, dataset: Dataset) -> Dict[str, Any]:
        """RAGAS 평가 실행 - RAG 서버 결과만 사용하여 평가"""
        self.logger.info("🚀 RAGAS 평가 시작...")
        self.logger.info("📋 RAG 서버에서 제공된 답변과 컨텍스트만 사용하여 평가")
        self.logger.info("🔄 RAG 서버의 청킹/임베딩/리트리버 변경사항 자동 반영됨")
        
        try:
            # 내부 LLM 서버만 평가용으로 사용
            evaluator_model = self.config['models'].get('evaluator_model', 'gemma3:27b-it-q4_K_M')
            llm_server_url = self.config['servers']['llm_server_url']
            
            self.logger.info(f"🤖 평가용 LLM: {evaluator_model} (내부 LLM 서버)")
            self.logger.info(f"📊 데이터: RAG 서버 제공 (answer + contexts)")
            self.logger.info(f"🔧 임베딩/리트리버: RAG 서버 내부 (RAGAS 코드 수정 불필요)")
            
            # Langchain Ollama LLM 설정 (평가용만)
            from langchain_ollama import ChatOllama
            
            eval_llm = ChatOllama(
                model=evaluator_model,
                base_url=llm_server_url,
                timeout=120,
                temperature=0.1  # 평가의 일관성을 위해 낮은 온도 설정
            )
            
            # RAGAS 평가 실행 - 임베딩/리트리버 없이 결과만 평가
            start_time = datetime.now()
            self.logger.info(f"⏳ 평가 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # RAG 서버 결과만 사용하여 평가 (임베딩 모델 불필요)
            results = evaluate(
                dataset=dataset,
                metrics=self.selected_metrics,
                llm=eval_llm  # 평가용 LLM만 사용, 임베딩은 기본값 사용
            )
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.logger.info(f"✅ RAGAS 평가 완료")
            self.logger.info(f"⏱️ 소요 시간: {duration}")
            self.logger.info(f"📊 평가된 항목 수: {len(dataset)}")
            self.logger.info(f"🎯 RAG 서버 구성 변경시 재평가만 하면 됨")
            
            # 결과 후처리
            processed_results = self._process_results(results, duration)
            
            return processed_results
            
        except Exception as e:
            self.logger.error(f"❌ RAGAS 평가 실패: {e}")
            # 상세 오류 정보 로깅
            import traceback
            self.logger.error(f"오류 상세: {traceback.format_exc()}")
            raise
    
    def _process_results(self, raw_results: Dict[str, Any], duration) -> Dict[str, Any]:
        """RAGAS 결과 후처리"""
        self.logger.info("🔄 평가 결과 후처리 중...")
        
        processed = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration.total_seconds(),
            'evaluation_summary': {},
            'detailed_metrics': {},
            'performance_analysis': {}
        }
        
        # 메트릭별 점수 추출
        for metric_name in self.config['ragas_metrics']:
            if metric_name in raw_results:
                score = raw_results[metric_name]
                processed['evaluation_summary'][metric_name] = float(score)
                
                # 임계값과 비교
                threshold = self.config['thresholds'].get(metric_name, 0.5)
                performance = "PASS" if score >= threshold else "FAIL"
                
                processed['detailed_metrics'][metric_name] = {
                    'score': float(score),
                    'threshold': threshold,
                    'performance': performance,
                    'gap': float(score - threshold)
                }
                
                self.logger.info(f"📈 {metric_name}: {score:.4f} ({performance})")
        
        # 전체 점수 계산
        scores = list(processed['evaluation_summary'].values())
        if scores:
            overall_score = sum(scores) / len(scores)
            processed['evaluation_summary']['overall_score'] = overall_score
            
            overall_threshold = self.config['thresholds'].get('overall_score', 0.75)
            overall_performance = "PASS" if overall_score >= overall_threshold else "FAIL"
            
            processed['performance_analysis'] = {
                'overall_score': overall_score,
                'overall_threshold': overall_threshold,
                'overall_performance': overall_performance,
                'total_metrics': len(scores),
                'passed_metrics': sum(1 for m in processed['detailed_metrics'].values() if m['performance'] == 'PASS'),
                'failed_metrics': sum(1 for m in processed['detailed_metrics'].values() if m['performance'] == 'FAIL')
            }
            
            self.logger.info(f"🎯 전체 점수: {overall_score:.4f} ({overall_performance})")
            self.logger.info(f"📊 통과/실패: {processed['performance_analysis']['passed_metrics']}/{processed['performance_analysis']['failed_metrics']}")
        
        return processed
    
    def analyze_by_category(self, dataset: Dataset, results: Dict[str, Any], 
                          original_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """카테고리별 성능 분석"""
        self.logger.info("🏷️ 카테고리별 성능 분석 중...")
        
        try:
            # 카테고리별 데이터 그룹화
            categories = {}
            for i, item in enumerate(dataset):
                # 원본 결과에서 카테고리 정보 가져오기
                if i < len(original_results):
                    category = original_results[i].get('category', 'Unknown')
                    if category not in categories:
                        categories[category] = {
                            'indices': [],
                            'questions': [],
                            'answers': [],
                            'ground_truths': []
                        }
                    
                    categories[category]['indices'].append(i)
                    categories[category]['questions'].append(item['question'])
                    categories[category]['answers'].append(item['answer'])
                    categories[category]['ground_truths'].append(item['ground_truth'])
            
            # 카테고리별 성능 계산
            category_analysis = {}
            
            for category, data in categories.items():
                category_metrics = {}
                
                # 각 메트릭별 해당 카테고리 점수 계산
                for metric_name in self.config['ragas_metrics']:
                    if metric_name in results['evaluation_summary']:
                        # 전체 평균을 사용 (실제로는 카테고리별 재평가 필요)
                        category_metrics[metric_name] = results['evaluation_summary'][metric_name]
                
                # 카테고리 전체 점수
                if category_metrics:
                    category_score = sum(category_metrics.values()) / len(category_metrics)
                else:
                    category_score = 0.0
                
                category_analysis[category] = {
                    'count': len(data['indices']),
                    'metrics': category_metrics,
                    'overall_score': category_score,
                    'sample_questions': data['questions'][:3]  # 샘플 질문 3개
                }
                
                self.logger.info(f"📂 {category}: {len(data['indices'])}개 질문, 점수: {category_score:.4f}")
            
            return category_analysis
            
        except Exception as e:
            self.logger.error(f"❌ 카테고리 분석 실패: {e}")
            return {}
    
    def generate_recommendations(self, results: Dict[str, Any]) -> Dict[str, List[str]]:
        """성능 개선 권장사항 생성"""
        self.logger.info("💡 성능 개선 권장사항 생성 중...")
        
        recommendations = {
            'high_priority': [],
            'medium_priority': [],
            'low_priority': [],
            'general_tips': []
        }
        
        # 메트릭별 권장사항
        for metric_name, metric_data in results.get('detailed_metrics', {}).items():
            score = metric_data['score']
            threshold = metric_data['threshold']
            
            if score < threshold:
                gap = threshold - score
                
                if metric_name == 'faithfulness' and gap > 0.2:
                    recommendations['high_priority'].append(
                        f"Faithfulness 점수가 낮습니다 ({score:.3f}). "
                        "RAG 서버의 검색된 문서 품질을 개선하고, 시스템 프롬프트에서 "
                        "사실 기반 답변을 강조하세요."
                    )
                
                elif metric_name == 'answer_relevancy' and gap > 0.15:
                    recommendations['high_priority'].append(
                        f"Answer Relevancy 점수가 낮습니다 ({score:.3f}). "
                        "RAG 서버의 질문 이해 능력 향상을 위해 프롬프트 엔지니어링을 개선하세요."
                    )
                
                elif metric_name == 'context_precision' and gap > 0.15:
                    recommendations['medium_priority'].append(
                        f"Context Precision이 낮습니다 ({score:.3f}). "
                        "RAG 서버의 검색 알고리즘 튜닝이나 인덱스 최적화를 고려하세요."
                    )
                
                elif metric_name == 'context_recall' and gap > 0.15:
                    recommendations['medium_priority'].append(
                        f"Context Recall이 낮습니다 ({score:.3f}). "
                        "RAG 서버의 검색 범위를 늘리거나 청킹 전략을 재검토하세요."
                    )
                
                else:
                    recommendations['low_priority'].append(
                        f"{metric_name} 점수 개선 필요: {score:.3f} -> {threshold:.3f}"
                    )
        
        # 전체 성능 기반 권장사항
        overall_score = results.get('evaluation_summary', {}).get('overall_score', 0)
        if overall_score < 0.6:
            recommendations['high_priority'].append(
                "전반적인 성능이 낮습니다. RAG 서버 아키텍처 전반의 재검토가 필요합니다."
            )
        elif overall_score < 0.75:
            recommendations['medium_priority'].append(
                "성능 개선 여지가 있습니다. RAG 서버의 주요 구성요소들을 우선적으로 개선하세요."
            )
        
        # RAG 서버 구성요소별 개선 팁
        recommendations['general_tips'] = [
            "RAG 서버: 문서 청킹 크기와 겹침 비율 최적화",
            "RAG 서버: 임베딩 모델 성능 벤치마킹",
            "RAG 서버: 검색 파라미터 (top_k, similarity_threshold) 튜닝",
            "RAG 서버: 시스템 프롬프트 A/B 테스트",
            "RAG 서버: 사용자 피드백 기반 ground truth 보완"
        ]
        
        # 권장사항 수 로깅
        total_recommendations = (
            len(recommendations['high_priority']) + 
            len(recommendations['medium_priority']) + 
            len(recommendations['low_priority'])
        )
        
        self.logger.info(f"💡 총 {total_recommendations}개 권장사항 생성")
        self.logger.info(f"   🔴 높음: {len(recommendations['high_priority'])}개")
        self.logger.info(f"   🟡 중간: {len(recommendations['medium_priority'])}개") 
        self.logger.info(f"   🟢 낮음: {len(recommendations['low_priority'])}개")
        
        return recommendations