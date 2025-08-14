"""
OpenWebUI/Ollama 호환 API 모델들
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time

# ================================
# Chat Completion 관련 모델들
# ================================

class Message(BaseModel):
    """채팅 메시지"""
    role: str
    content: str

class ChatRequest(BaseModel):
    """채팅 요청"""
    model: str
    messages: List[Message]
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class ChatResponseMessage(BaseModel):
    """채팅 응답 메시지"""
    role: str = "assistant"
    content: str

class ChatResponseChoice(BaseModel):
    """채팅 응답 선택지"""
    index: int = 0
    message: ChatResponseMessage
    finish_reason: Optional[str] = "stop"

class ChatResponse(BaseModel):
    """채팅 응답"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatResponseChoice]
    usage: Optional[dict] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

# ================================
# OpenAI 호환 모델들
# ================================

class ModelInfo(BaseModel):
    """OpenAI 호환 모델 정보"""
    id: str
    object: str = "model"
    created: int
    owned_by: str
    permission: List[Dict[str, Any]] = []
    root: str

class ModelsResponse(BaseModel):
    """OpenAI 호환 모델 목록 응답"""
    object: str = "list"
    data: List[ModelInfo]

# ================================
# OpenWebUI/Ollama 호환 모델들
# ================================

class WebUIModelInfo(BaseModel):
    """OpenWebUI 호환 모델 정보"""
    name: str
    model: str  # OpenWebUI에서 사용하는 필드
    modified_at: str
    size: int
    digest: str
    details: Dict[str, Any]

class WebUIModelsResponse(BaseModel):
    """OpenWebUI 호환 모델 목록 응답"""
    models: List[WebUIModelInfo]

# ================================
# 디버그/테스트 모델들
# ================================

class RetrievalTestRequest(BaseModel):
    """검색 테스트 요청"""
    question: str

class RetrievalTestResponse(BaseModel):
    """검색 테스트 응답"""
    question: str
    retrieved_docs: int
    docs: List[Dict[str, Any]]

# ================================
# 헬퍼 함수들
# ================================

def create_model_info(
    model_id: str,
    owned_by: str = "CHEESEADE",
    root: Optional[str] = None
) -> ModelInfo:
    """OpenAI 모델 정보 생성 헬퍼"""
    return ModelInfo(
        id=model_id,
        object="model",
        created=int(time.time()),
        owned_by=owned_by,
        permission=[],
        root=root or model_id
    )

def create_webui_model_info(
    model_name: str,
    size: int = 1000000000,
    digest: Optional[str] = None,
    description: str = "",
    family: str = "general",
    parameter_size: str = "unknown"
) -> WebUIModelInfo:
    """OpenWebUI 모델 정보 생성 헬퍼"""
    return WebUIModelInfo(
        name=model_name,
        model=model_name,
        modified_at="2024-01-01T00:00:00Z",
        size=size,
        digest=digest or f"sha256:{abs(hash(model_name)):x}",
        details={
            "parent_model": "",
            "format": "gguf",
            "family": family,
            "families": [family],
            "parameter_size": parameter_size,
            "quantization_level": "Q4_K_M",
            "description": description
        }
    )