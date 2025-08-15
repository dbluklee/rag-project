# server-rag/api/router.py
"""
FastAPI 라우터 정의 - OpenWebUI 호환성 개선
"""
import os
import time
from fastapi import APIRouter
from .models import OllamaChatRequest, OllamaGenerateRequest
from .endpoints import (
    handle_chat_request, handle_generate_request,
    get_model_list, get_health_status, get_chat_handler
)

router = APIRouter()

# ================================
# 핵심 채팅/생성 API
# ================================

@router.post("/api/chat")
async def chat_ollama(request: OllamaChatRequest):
    """Ollama 채팅 API"""
    return await handle_chat_request(request)

@router.post("/api/generate")
async def generate_ollama(request: OllamaGenerateRequest):
    """Ollama 생성 API"""
    return await handle_generate_request(request)

# ================================
# 모델 관리 API (OpenWebUI 필수)
# ================================

@router.get("/api/tags")
async def list_local_models():
    """로컬 모델 목록"""
    return get_model_list()

@router.get("/api/models")
async def list_models_alt():
    """모델 목록 API (/api/tags의 별칭)"""
    return get_model_list()

@router.get("/api/ps")
async def list_running_models():
    """실행 중인 모델 목록"""
    try:
        models = get_model_list()["models"]
        
        # ps용 형식으로 변환
        running_models = []
        for model in models:
            running_models.append({
                **model,
                "expires_at": "2024-12-01T23:59:59.999999999Z",
                "size_vram": 2147483648
            })
        
        return {"models": running_models}
    except Exception as e:
        print(f"❌ 실행 모델 목록 오류: {str(e)}")
        return {"models": []}

@router.get("/api/version")
async def get_version():
    """Ollama 버전 정보 API"""
    return {
        "version": "0.1.16"  # OpenWebUI가 요구하는 최소 버전
    }

@router.get("/api/show")
async def show_model(name: str = None):
    """모델 상세 정보 API"""
    if not name:
        return {"error": "model name required"}
    
    rag_model_name = os.environ.get("RAG_MODEL_NAME", "rag-cheeseade:latest")
    llm_model_name = os.environ.get("LLM_MODEL_NAME", "gemma3:27b-it-q4_K_M")
    
    if name == rag_model_name:
        return {
            "modelfile": f"FROM {rag_model_name}",
            "parameters": {
                "temperature": 0.7,
                "top_k": 40,
                "top_p": 0.9
            },
            "template": "{{ .System }}{{ .Prompt }}",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "rag-enhanced",
                "families": ["rag-enhanced"],
                "parameter_size": "RAG+27B",
                "quantization_level": "Q4_K_M"
            }
        }
    elif name == llm_model_name:
        return {
            "modelfile": f"FROM {llm_model_name}",
            "parameters": {
                "temperature": 0.7,
                "top_k": 40,
                "top_p": 0.9
            },
            "template": "{{ .System }}{{ .Prompt }}",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "gemma3",
                "families": ["gemma3"],
                "parameter_size": "27B",
                "quantization_level": "Q4_K_M"
            }
        }
    else:
        return {"error": f"model '{name}' not found"}


# ================================
# 상태 및 정보 API
# ================================

@router.get("/health")
async def health_check():
    """헬스체크"""
    try:
        return get_health_status()
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "cheeseade-rag-server", 
            "timestamp": int(time.time()),
            "error": str(e)
        }

@router.get("/api")
async def api_info():
    """API 정보"""
    return {
        "message": "CHEESEADE RAG Server API",
        "version": "1.0.0",
        "ollama_compatible": True,
        "endpoints": [
            "/api/tags", "/api/models", "/api/ps", "/api/version",
            "/api/show", "/api/chat", "/api/generate",
            "/health"
        ]
    }

@router.get("/")
async def root():
    """루트 엔드포인트"""
    return "Ollama is running"