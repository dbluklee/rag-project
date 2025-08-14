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
            description"""
모델 관련 비즈니스 로직
"""
from typing import List, Optional
from ..models.openai import ModelInfo, create_model_info
from ..models.openwebui import WebUIModelInfo, create_webui_model_info

class ModelService:
    """모델 관련 서비스"""
    
    def __init__(self):
        # 실제 환경에서는 DB, 외부 API, 설정 파일 등에서 가져옴
        self._models_config = [
            {
                "id": "rag-cheeseade:latest",
                "name": "rag-cheeseade:latest",
                "owned_by": "CHEESEADE",
                "description": "CHEESEADE RAG를 활용한 전문 상담",
                "family": "rag-enhanced",
                "parameter_size": "RAG + 27B",
                "size": 2500000000  # 2.5GB
            },
            {
                "id": "gemma3:27b-it-q4_K_M",
                "name": "gemma3:27b-it-q4_K_M",
                "owned_by": "CHEESEADE",
                "description": "일반용 대화형 AI 모델",
                "family": "gemma3",
                "parameter_size": "27B",
                "size": 15000000000  # 15GB
            }
        ]
    
    def get_available_models(self) -> List[dict]:
        """사용 가능한 모델 설정 반환"""
        return self._models_config.copy()
    
    def get_model_by_id(self, model_id: str) -> Optional[dict]:
        """ID로 모델 찾기"""
        return next(
            (model for model in self._models_config if model["id"] == model_id),
            None
        )
    
    def get_openai_models(self) -> List[ModelInfo]:
        """OpenAI 형식 모델 목록"""
        models = []
        for config in self._models_config:
            model = create_model_info(
                model_id=config["id"],
                owned_by=config["owned_by"],
                root=config["id"]
            )
            models.append(model)
        return models
    
    def get_openai_model_by_id(self, model_id: str) -> Optional[ModelInfo]:
        """OpenAI 형식 특정 모델"""
        config = self.get_model_by_id(model_id)
        if not config:
            return None
        
        return create_model_info(
            model_id=config["id"],
            owned_by=config["owned_by"],
            root=config["id"]
        )
    
    def get_openwebui_models(self) -> List[WebUIModelInfo]:
        """OpenWebUI 형식 모델 목록"""
        models = []
        for config in self._models_config:
            model = create_webui_model_info(
                model_name=config["name"],
                size=config["size"],
                description=config["description"],
                family=config["family"],
                parameter_size=config["parameter_size"]
            )
            models.append(model)
        return models
    
    def get_openwebui_model_by_name(self, model_name: str) -> Optional[WebUIModelInfo]:
        """OpenWebUI 형식 특정 모델"""
        config = next(
            (model for model in self._models_config if model["name"] == model_name),
            None
        )
        if not config:
            return None
        
        return create_webui_model_info(
            model_name=config["name"],
            size=config["size"],
            description=config["description"],
            family=config["family"],
            parameter_size=config["parameter_size"]
        )
    
    def is_model_available(self, model_id: str) -> bool:
        """모델 사용 가능 여부 확인"""
        return self.get_model_by_id(model_id) is not None
    
    def add_model(self, model_config: dict) -> bool:
        """새 모델 추가 (동적 모델 관리용)"""
        if self.get_model_by_id(model_config["id"]):
            return False  # 이미 존재
        
        self._models_config.append(model_config)
        return True
    
    def remove_model(self, model_id: str) -> bool:
        """모델 제거"""
        original_count = len(self._models_config)
        self._models_config = [
            model for model in self._models_config 
            if model["id"] != model_id
        ]
        return len(self._models_config) < original_count

# 전역 모델 서비스 인스턴스
model_service = ModelService()