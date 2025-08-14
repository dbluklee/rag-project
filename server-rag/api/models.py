"""
OpenWebUI API 호환 Pydantic 모델들
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time

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
# 헬퍼 함수들
# ================================

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