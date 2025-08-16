def get_retrieved_contexts(self, question: str) -> List[str]:
        """검색된 컨텍스트 가져오기"""
        try:
            # 디버그 API 사용하여 검색 결과 가져오기
            debug_payload = {"question": question}
            
            response = requests.post(
                f"{self.rag_server_url}/debug/test-retrieval",
                json=debug_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                contexts = []
                
                # 검색된 문서에서 컨텍스트 추출
                retrieved_docs = result.get('retrieved_docs', [])
                for doc in retrieved_docs:
                    if isinstance(doc, dict):
                        content = doc.get('page_content', '')
                        if content:
                            contexts.append(content)
                    elif isinstance(doc, str):
                        contexts.append(doc)
                
                return contexts[:4]  # 상위 4개만
            else:
                self.logger.warning(f"컨텍스트 검색 실패: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.warning(f"컨텍스트 검색 오류: {e}")
            return []
    
    def get_rag_embeddings_for_ragas(self):
        """RAGAS 평가용 임베딩 래퍼 생성"""
        return RAGServerEmbeddingsWrapper(
            rag_server_url=self.rag_server_url,
            logger=self.logger
        )


class RAGServerEmbeddingsWrapper:
    """RAG 서버의 임베딩을 RAGAS에서 사용하기 위한 래퍼"""
    
    def __init__(self, rag_server_url: str, logger):
        self.rag_server_url = rag_server_url
        self.logger = logger
        
        # 실제 RAG 서버 임베딩 모델과 동일한 모델 로드
        # 이렇게 하면 RAG 서버의 청킹/임베딩/리트리버 변경이 자동으로 반영됨
        try:
            from embedding.bge_m3 import get_bge_m3_model
            self.embedding_model = get_bge_m3_model()
            self.logger.info("✅ RAG 서버와 동일한 임베딩 모델 로드 완료")
        except Exception as e:
            self.logger.error(f"❌ 임베딩 모델 로드 실패: {e}")
            raise
    
    def embed_documents(self, texts):
        """문서 임베딩 (RAG 서버와 동일한 모델 사용)"""
        try:
            return self.embedding_model.embed_documents(texts)
        except Exception as e:
            self.logger.error(f"❌ 문서 임베딩 실패: {e}")
            raise
    
    def embed_query(self, text):
        """쿼리 임베딩 (RAG 서버와 동일한 모델 사용)"""
        try:
            return self.embedding_model.embed_query(text)
        except Exception as e:
            self.logger.error(f"❌ 쿼리 임베딩 실패: {e}")
            raise"""
CHEESEADE RAG 시스템 평가기
RAGAS를 사용한 종합적인 성능 평가
"""

import os
import yaml
import asyncio
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tqdm import tqdm
import json

# RAGAS 관련
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
from datasets import Dataset

class CheeseadeRAGEvaluator:
    """CHEESEADE RAG 시스템 평가 클래스"""
    
    def __init__(self, config_path: str = "evaluation/config.yaml"):
        """평가기 초기화"""
        self.config = self._load_config(config_path)
        self.setup_logging()
        self.setup_directories()
        
        # 서버 연결 정보
        self.rag_server_url = self.config['servers']['rag_server_url']
        self.llm_server_url = self.config['servers']['llm_server_url']
        
        # 모델 정보
        self.rag_model_name = self.config['models']['rag_model_name']
        self.llm_model_name = self.config['models']['llm_model_name']
        
        # 평가 결과 저장용
        self.evaluation_results = {}
        self.individual_results = []
        
        self.logger.info("🚀 CHEESEADE RAG 평가기 초기화 완료")
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"✅ 설정 파일 로드 완료: {config_path}")
            return config
        except Exception as e:
            print(f"❌ 설정 파일 로드 실패: {e}")
            raise
    
    def setup_logging(self):
        """로깅 설정"""
        log_config = self.config['logging']
        
        # 로그 디렉토리 생성
        log_dir = Path(self.config['data_paths']['logs_dir'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 로거 설정
        self.logger = logging.getLogger('CheeseadeRAGEvaluator')
        self.logger.setLevel(getattr(logging, log_config['level']))
        
        # 포매터
        formatter = logging.Formatter(log_config['format'])
        
        # 파일 핸들러
        if log_config['file_handler']:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"evaluation_{timestamp}.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # 콘솔 핸들러
        if log_config['console_handler']:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def setup_directories(self):
        """필요한 디렉토리 생성"""
        directories = [
            self.config['data_paths']['output_dir'],
            self.config['data_paths']['logs_dir'],
            "evaluation/data",
            "evaluation/results/charts",
            "evaluation/results/reports"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        self.logger.info("📁 디렉토리 설정 완료")
    
    def check_server_health(self) -> bool:
        """서버 상태 확인"""
        self.logger.info("🔍 서버 상태 확인 중...")
        
        # RAG 서버 확인
        try:
            rag_response = requests.get(
                f"{self.rag_server_url}/health",
                timeout=self.config['servers']['health_check_timeout']
            )
            if rag_response.status_code != 200:
                self.logger.error(f"❌ RAG 서버 상태 이상: {rag_response.status_code}")
                return False
            self.logger.info("✅ RAG 서버 정상")
        except Exception as e:
            self.logger.error(f"❌ RAG 서버 연결 실패: {e}")
            return False
        
        # LLM 서버 확인  
        try:
            llm_response = requests.get(
                f"{self.llm_server_url}/api/tags",
                timeout=self.config['servers']['health_check_timeout']
            )
            if llm_response.status_code != 200:
                self.logger.error(f"❌ LLM 서버 상태 이상: {llm_response.status_code}")
                return False
            self.logger.info("✅ LLM 서버 정상")
        except Exception as e:
            self.logger.error(f"❌ LLM 서버 연결 실패: {e}")
            return False
        
        return True
    
    def load_questions(self) -> pd.DataFrame:
        """평가용 질문 데이터 로드"""
        questions_file = self.config['data_paths']['questions_file']
        
        try:
            if questions_file.endswith('.xlsx'):
                df = pd.read_excel(questions_file)
            elif questions_file.endswith('.csv'):
                df = pd.read_csv(questions_file)
            else:
                raise ValueError("지원하지 않는 파일 형식")
            
            # 필수 컬럼 확인
            required_columns = ['question', 'expected_answer', 'category']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"필수 컬럼 누락: {missing_columns}")
            
            # 샘플링 (설정에 따라)
            sample_size = self.config['evaluation'].get('sample_size')
            if sample_size and sample_size < len(df):
                df = df.sample(n=sample_size, random_state=42)
                self.logger.info(f"📊 {sample_size}개 질문으로 샘플링")
            
            self.logger.info(f"📄 총 {len(df)}개 질문 로드 완료")
            return df
            
        except Exception as e:
            self.logger.error(f"❌ 질문 데이터 로드 실패: {e}")
            raise
    
    def get_rag_answer(self, question: str) -> Tuple[str, List[str]]:
        """RAG 시스템에서 답변 및 컨텍스트 가져오기"""
        try:
            # RAG 채팅 API 호출
            chat_payload = {
                "model": self.rag_model_name,
                "messages": [
                    {"role": "user", "content": question}
                ],
                "stream": False
            }
            
            response = requests.post(
                f"{self.rag_server_url}/api/chat",
                json=chat_payload,
                timeout=self.config['evaluation']['timeout_per_question']
            )
            
            if response.status_code != 200:
                raise Exception(f"API 에러: {response.status_code}")
            
            result = response.json()
            answer = result.get('message', {}).get('content', '')
            
            # 컨텍스트 검색 (별도 API)
            contexts = self.get_retrieved_contexts(question)
            
            return answer, contexts
            
        except Exception as e:
            self.logger.warning(f"⚠️ RAG 답변 생성 실패: {e}")
            return f"Error: {str(e)}", []
    
    def get_rag_embeddings(self) -> Any:
        """RAG 서버의 임베딩 모델 가져오기"""
        try:
            # RAG 서버의 임베딩 API를 통해 임베딩 가져오기
            # 이것은 실제로는 RAG 서버의 임베딩 모델과 동일한 모델을 로드
            from embedding.bge_m3 import get_bge_m3_model
            return get_bge_m3_model()
        except Exception as e:
            self.logger.error(f"❌ RAG 서버 임베딩 모델 로드 실패: {e}")
            raise
        """검색된 컨텍스트 가져오기"""
        try:
            # 디버그 API 사용하여 검색 결과 가져오기
            debug_payload = {"question": question}
            
            response = requests.post(
                f"{self.rag_server_url}/debug/test-retrieval",
                json=debug_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                contexts = []
                
                # 검색된 문서에서 컨텍스트 추출
                retrieved_docs = result.get('retrieved_docs', [])
                for doc in retrieved_docs:
                    if isinstance(doc, dict):
                        content = doc.get('page_content', '')
                        if content:
                            contexts.append(content)
                    elif isinstance(doc, str):
                        contexts.append(doc)
                
                return contexts[:4]  # 상위 4개만
            else:
                self.logger.warning(f"컨텍스트 검색 실패: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.warning(f"컨텍스트 검색 오류: {e}")
            return []
    
    def process_single_question(self, row: pd.Series) -> Dict[str, Any]:
        """단일 질문 처리"""
        question = row['question']
        expected_answer = row['expected_answer']
        category = row.get('category', 'Unknown')
        
        try:
            # RAG 시스템에서 답변 및 컨텍스트 가져오기
            answer, contexts = self.get_rag_answer(question)
            
            # 결과 구성
            result = {
                'question': question,
                'answer': answer,
                'contexts': contexts,
                'ground_truth': expected_answer,
                'category': category,
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 질문 처리 실패: {question[:50]}... | 오류: {e}")
            return {
                'question': question,
                'answer': f"Error: {str(e)}",
                'contexts': [],
                'ground_truth': expected_answer,
                'category': category,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'error': str(e)
            }
    
    def process_questions_batch(self, questions_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """질문 배치 처리"""
        self.logger.info(f"🔄 {len(questions_df)}개 질문 처리 시작...")
        
        results = []
        batch_size = self.config['evaluation']['batch_size']
        max_workers = self.config['evaluation']['max_workers']
        
        # 배치별 처리
        for i in range(0, len(questions_df), batch_size):
            batch = questions_df.iloc[i:i+batch_size]
            self.logger.info(f"📦 배치 {i//batch_size + 1}/{(len(questions_df)-1)//batch_size + 1} 처리 중...")
            
            # 병렬 처리
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for _, row in batch.iterrows():
                    future = executor.submit(self.process_single_question, row)
                    futures.append(future)
                
                # 결과 수집 (진행률 표시)
                for future in tqdm(as_completed(futures), total=len(futures), desc="질문 처리"):
                    try:
                        result = future.result(timeout=self.config['evaluation']['timeout_per_question'])
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"배치 처리 오류: {e}")
                        # 에러 결과도 추가
                        results.append({
                            'question': 'Unknown',
                            'answer': f"Batch Error: {str(e)}",
                            'contexts': [],
                            'ground_truth': '',
                            'category': 'Error',
                            'success': False,
                            'error': str(e)
                        })
        
        self.logger.info(f"✅ 총 {len(results)}개 질문 처리 완료")
        return results
    
    def prepare_ragas_dataset(self, results: List[Dict[str, Any]]) -> Dataset:
        """RAGAS 평가용 데이터셋 준비"""
        self.logger.info("📊 RAGAS 데이터셋 준비 중...")
        
        # 성공한 결과만 필터링
        valid_results = [r for r in results if r.get('success', False)]
        self.logger.info(f"✅ 유효한 결과: {len(valid_results)}/{len(results)}개")
        
        # RAGAS 형식으로 변환
        dataset_dict = {
            'question': [],
            'answer': [],
            'contexts': [],
            'ground_truth': []
        }
        
        for result in valid_results:
            dataset_dict['question'].append(result['question'])
            dataset_dict['answer'].append(result['answer'])
            dataset_dict['contexts'].append(result['contexts'] or ['No context retrieved'])
            dataset_dict['ground_truth'].append(result['ground_truth'])
        
        dataset = Dataset.from_dict(dataset_dict)
        self.logger.info(f"🎯 RAGAS 데이터셋 생성 완료: {len(dataset)}개 항목")
        
        return dataset