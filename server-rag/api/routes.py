"""
OpenWebUI/Ollama 호환 API 라우터
"""
import uuid
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends, status, Response
from fastapi.responses import StreamingResponse

from .models import (
    ModelsResponse, WebUIModelsResponse, 
    ChatRequest, ChatResponse, ChatResponseChoice, ChatResponseMessage,
    RetrievalTestRequest, RetrievalTestResponse
)
from .services import model_service
from .auth import get_current_user_optional

# 라우터 생성
router = APIRouter()

# 전역 채팅 핸들러 (server.py에서 설정)
chat_handler = None

def set_chat_handler(handler):
    """채팅 핸들러 설정 (server.py에서 호출)"""
    global chat_handler
    chat_handler = handler
    print(f"✅ 채팅 핸들러 설정 완료")

# ================================
# OpenAI 호환 엔드포인트
# ================================

@router.get("/api/models", response_model=ModelsResponse)
async def list_openai_models(
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """OpenAI 형식 모델 목록"""
    print(f"📋 GET /api/models 요청")
    if current_user:
        print(f"   사용자: {current_user.get('name', 'Unknown')}")
    
    models = model_service.get_openai_models()
    print(f"   반환된 모델 수: {len(models)}")
    
    return ModelsResponse(
        object="list",
        data=models
    )

# ================================
# OpenWebUI/Ollama 호환 엔드포인트
# ================================

@router.get("/api/tags", response_model=WebUIModelsResponse)
async def list_webui_models(
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Ollama/OpenWebUI 형식 모델 목록"""
    print(f"📋 GET /api/tags 요청")
    if current_user:
        print(f"   사용자: {current_user.get('name', 'Unknown')}")
    
    models = model_service.get_openwebui_models()
    print(f"   반환된 모델 수: {len(models)}")
    
    return WebUIModelsResponse(models=models)

@router.get("/api/show")
async def show_model(
    name: str,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """특정 모델 정보 (Ollama 호환)"""
    print(f"📋 GET /api/show?name={name} 요청")
    if current_user:
        print(f"   사용자: {current_user.get('name', 'Unknown')}")
    
    model = model_service.get_openwebui_model_by_name(name)
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{name}' not found"
        )
    
    print(f"   모델 발견: {model.name}")
    return model

# ================================
# 시스템 정보 엔드포인트
# ================================

@router.get("/api/version")
async def get_version():
    """API 버전 정보 (인증 불필요)"""
    print(f"📋 GET /api/version 요청")
    return {
        "version": "1.0.0",
        "api_version": "1.0",
        "service": "CHEESEADE RAG Server",
        "compatible": ["OpenAI", "Ollama", "OpenWebUI"]
    }

@router.get("/health")
async def health_check(response: Response):
    """서버 상태 확인 (인증 불필요)"""
    print(f"📋 GET /health 요청")
    response.status_code = status.HTTP_200_OK
    return {
        "status": "healthy",
        "service": "rag-server",
        "timestamp": int(time.time()),
        "models_available": len(model_service.get_available_models())
    }

# ================================
# 채팅 완료 엔드포인트 (메인 기능)
# ================================

@router.post("/api/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    """OpenAI 호환 채팅 완료 API"""
    if not chat_handler:
        raise HTTPException(
            status_code=503,
            detail="Chat handler not initialized"
        )
    
    try:
        if authorization:
            print(f"🔑 인증: {authorization[:20]}...")
        
        print(f"\n🎯 POST /api/chat/completions")
        print(f"   모델: {request.model}")
        print(f"   스트림: {request.stream}")
        
        # 가장 최근 사용자 메시지 가져오기
        user_question = request.messages[-1].content
        print(f"   질문: {user_question}")
        
        # 모델이 RAG 모델인지 확인
        if request.model == chat_handler.rag_model_name:
            # RAG 사용
            if request.stream:
                return StreamingResponse(
                    chat_handler.stream_rag_response(user_question, request.model),
                    media_type="text/plain",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    }
                )
            else:
                response_dict = await chat_handler.handle_chat_request(request)
                return ChatResponse(**response_dict)
        else:
            # 일반 LLM 사용 (Ollama로 프록시)
            if request.stream:
                return StreamingResponse(
                    chat_handler.proxy_stream_to_llm(request),
                    media_type="text/plain",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    }
                )
            else:
                response_dict = await chat_handler.proxy_to_llm(request)
                return response_dict
        
    except Exception as e:
        print(f"❌ API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/chat")
async def chat_simple(request: dict):
    """간단한 채팅 엔드포인트 (호환성용)"""
    print(f"🎯 POST /api/chat (간단한 형식)")
    
    if not chat_handler:
        raise HTTPException(
            status_code=503,
            detail="Chat handler not initialized"
        )
    
    # 간단한 형식을 표준 형식으로 변환
    if "message" in request:
        # {"message": "질문"} 형식
        question = request["message"]
        model = request.get("model", chat_handler.rag_model_name)
        
        chat_request = ChatRequest(
            model=model,
            messages=[{"role": "user", "content": question}],
            stream=request.get("stream", False)
        )
        
        return await chat_completions(chat_request)
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid request format. Expected 'message' field."
        )

# ================================
# 디버그/테스트 엔드포인트
# ================================

@router.post("/debug/test-retrieval", response_model=RetrievalTestResponse)
async def test_retrieval(request: RetrievalTestRequest):
    """검색 기능 테스트"""
    if not chat_handler:
        raise HTTPException(
            status_code=503,
            detail="Chat handler not initialized"
        )
    
    print(f"🧪 POST /debug/test-retrieval 요청: {request.question}")
    
    try:
        result = chat_handler.test_retrieval(request.question)
        return RetrievalTestResponse(**result)
        
    except Exception as e:
        print(f"❌ 검색 테스트 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검색 테스트 실패: {str(e)}"
        )

# ================================
# 루트 엔드포인트
# ================================

@router.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "CHEESEADE RAG Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "models": "/api/models",
            "tags": "/api/tags", 
            "show": "/api/show?name=<model>",
            "version": "/api/version",
            "health": "/health"
        }
    }