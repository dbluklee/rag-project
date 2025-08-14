"""
OpenWebUI API 서비스 로직
"""
import os
from typing import List, Optional
from .models import WebUIModelInfo, create_webui_model_info

class ModelService:
    """모델 관련 서비스 (OpenWebUI 전용)"""
    
    def __init__(self):
        # 환경변수에서 모델 정보 가져오기
        self.rag_model_name = os.environ["RAG_MODEL_NAME"]
        self.llm_model_name = os.environ["LLM_MODEL_NAME"]
        
        print(f"🔧 ModelService 초기화")
        print(f"   RAG 모델: {self.rag_model_name}")
        print(f"   LLM 모델: {self.llm_model_name}")
    
    def get_openwebui_models(self) -> List[WebUIModelInfo]:
        """OpenWebUI 형식 모델 목록"""
        models = []
        
        # RAG 모델
        rag_model = create_webui_model_info(
            model_name=self.rag_model_name,
            size=2500000000,  # 2.5GB
            description="CHEESEADE RAG를 활용한 전문 상담",
            family="rag-enhanced",
            parameter_size="RAG + 27B"
        )
        models.append(rag_model)
        
        # LLM 모델
        llm_model = create_webui_model_info(
            model_name=self.llm_model_name,
            size=15000000000,  # 15GB
            description="일반용 대화형 AI 모델",
            family="gemma3", 
            parameter_size="27B"
        )
        models.append(llm_model)
        
        return models
    
    def get_openwebui_model_by_name(self, model_name: str) -> Optional[WebUIModelInfo]:
        """특정 모델 검색"""
        models = self.get_openwebui_models()
        return next((model for model in models if model.name == model_name), None)
    
    def is_model_available(self, model_name: str) -> bool:
        """모델 사용 가능 여부"""
        return self.get_openwebui_model_by_name(model_name) is not None