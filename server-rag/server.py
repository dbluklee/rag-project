import os
import uvicorn
import uuid
import time
import json
import requests
import torch
import asyncio

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Header, status, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain_core.runnables import RunnableParallel

from chunking.chunking_md import chunk_markdown_file
from embedding.bge_m3 import get_bge_m3_model
from retriever.retriever import get_retriever
from vector_db.milvus import MilvusVectorStore
from api.routes import router as openwebui_router

# 환경변수 가져오기
LLM_SERVER_URL = os.environ["LLM_SERVER_URL"]
RAG_MODEL_NAME = os.environ["RAG_MODEL_NAME"]
MILVUS_SERVER_IP = os.environ["MILVUS_SERVER_IP"]
MILVUS_PORT = os.environ["MILVUS_PORT"]
LLM_MODEL_NAME = os.environ["LLM_MODEL_NAME"]
COLLECTION_NAME = os.environ["COLLECTION_NAME"]

# 시스템 프롬프트 작성
system_prompt = '''Answer the user's Question from the Context.
Keep your answer ground in the facts of the Context.
If the Context doesn't contain the facts to answer, just output '답변할 수 없습니다'
Please answer in Korean.'''

# LLM 서버에 연결
try:
    print(f"🔗 LLM 서버 연결 시도: {LLM_SERVER_URL}")
    response = requests.get(f"{LLM_SERVER_URL}/api/tags", timeout=10)
    if response.status_code == 200:
        print(f"✅ LLM 서버 연결 성공: {LLM_SERVER_URL}")
    else:
        print(f"⚠️ LLM 서버 응답 오류: {response.status_code}")
        
    llm = ChatOllama(
        model=LLM_MODEL_NAME,
        base_url=LLM_SERVER_URL,
        timeout=120
    )
    print(f"✅ LLM 서버 초기화 완료")
    
except requests.exceptions.ConnectionError:
    print(f"❌ LLM 서버 연결 실패: {LLM_SERVER_URL}")
    llm = None
except Exception as e:
    print(f"❌ LLM 서버 연결 중 오류: {e}")
    llm = None
 
# RAG 프롬프트 생성
RAG_prompt = ChatPromptTemplate([
    ('system', system_prompt),
    ('user', '''Context: {context}
    ---
     Question: {question}''')
])

# 임베딩 모델 로드 (GPU 우선 사용)
if torch.cuda.is_available():
    print(f"✅ CUDA 사용 가능: {torch.cuda.get_device_name(0)}")
    print(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    device = 'cuda'
else:
    print("⚠️ CUDA 사용 불가 - CPU 사용")
    device = 'cpu'

print(f"🔧 {device}를 사용하여 임베딩 모델 로드 시도")
embedding_model = get_bge_m3_model()
print(f"✅ 임베딩 모델 로드 완료")

# 3. 문서 로드 및 청킹
markdown_path = "./docs/feature.md"

print(f"\n📝 문서 청킹 시작...")
chunks = chunk_markdown_file(markdown_path)

if len(chunks) == 0:
    print("❌ 문서 청킹 결과가 없습니다!")
    raise ValueError("문서 청킹 실패 - 처리할 수 있는 내용이 없습니다")

print(f"📊 총 청크 수: {len(chunks)}")

# 벡터 스토어 초기화
vector_store = MilvusVectorStore(
    collection_name=COLLECTION_NAME, 
    embedding_model=embedding_model,
    metric_type='IP',
    index_type='HNSW',
    milvus_host=MILVUS_SERVER_IP,  
    milvus_port=MILVUS_PORT   
)
    
# 문서를 vector DB에 추가
print(f"\n📤 {len(chunks)}개 문서를 DB에 추가합니다...")
inserted_ids = vector_store.add_documents(chunks)
print(f"✅ 삽입된 문서 수: {len(inserted_ids)}")

# top_k 타입 리트리버 생성
print(f"\n🔧 리트리버 생성 중...")
retriever = get_retriever(vector_store, retriever_type='top_k')

# RAG 체인 구성
rag_chain = (
    RunnableParallel(
        context=retriever, 
        question=RunnablePassthrough()
    )
    | RAG_prompt
    | llm
    | StrOutputParser()
)

async def process_with_rag(question: str) -> str:
    print("🔍 RAG 파이프라인 처리 시작")
    response = rag_chain.invoke(question)
    print(f"✅ RAG 응답 생성: {len(response)} 문자")
    return response

# RAG 체인으로부터 스트리밍 응답을 생성
async def stream_rag_response(question: str, model_name: str):
    try:
        print(f"🌊 스트리밍 시작: {question}")

        # 동기 스트리밍을 먼저 체크 (더 일반적)
        if hasattr(rag_chain, 'stream'):
            for chunk in rag_chain.stream(question):
                if chunk:
                    response_chunk = {
                        "id": f"chatcmpl-{uuid.uuid4()}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"
                    await asyncio.sleep(0.03)

        # 비동기 스트리밍 체크
        elif hasattr(rag_chain, 'astream'):  
            async for chunk in rag_chain.astream(question):
                if chunk:
                    response_chunk = {
                        "id": f"chatcmpl-{uuid.uuid4()}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"
                    await asyncio.sleep(0.03)
        
        # 방법 3: 스트리밍 미지원시 청크로 분할
        else:
            response_content = await asyncio.get_event_loop().run_in_executor(
                None, rag_chain.invoke, question
            )
            print(f"🔍 전체 응답: {response_content}")
            
            # 단어 단위로 분할 (더 자연스러운 스트리밍)
            words = response_content.split()
            chunk_size = 1  # 1단어씩
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i+chunk_size]
                chunk = " ".join(chunk_words)
                if i + chunk_size < len(words):
                    chunk += " "  # 마지막이 아니면 공백 추가
                
                response_chunk = {
                    "id": f"chatcmpl-{uuid.uuid4()}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(response_chunk)}\n\n"
                await asyncio.sleep(0.03) 
        
        # 스트림 종료 신호
        final_chunk = {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion.chunk", 
            "created": int(time.time()),
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        print(f"❌ 스트리밍 오류: {e}")
        # Open WebUI 호환 에러 형식
        error_response = {
            "error": {
                "message": str(e),
                "type": "internal_server_error",
                "code": "rag_error"
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"
        yield "data: [DONE]\n\n"



# FastAPI 앱 생성
app = FastAPI(title="RAG Server", description="RAG API 서버", version="1.0.0")
print(f"\n✅ FastAPI 앱 생성 \n")

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# server.py의 기존 FastAPI 앱에 추가할 부분

# ================================
# OpenWebUI API 라우터 추가
# ================================

# 라우터 등록 (FastAPI 앱 생성 후 추가)
app.include_router(openwebui_router)

print(f"✅ OpenWebUI API 라우터 등록 완료")
print(f"   사용 가능한 엔드포인트:")
print(f"     GET /api/models - 모델 목록 (인증 필요)")
print(f"     GET /api/tags - Ollama 호환 태그 (인증 필요)")
print(f"     GET /api/show?name=<model> - 모델 상세 (인증 필요)")
print(f"     GET /api/version - API 버전 (인증 불필요)")
print(f"     GET /api/health - 서버 상태 (인증 불필요)")

# ================================
# 인증 관련 추가 엔드포인트 (선택사항)
# ================================

# @app.post("/api/auth/signin")
# async def signin(credentials: dict):
#     """간단한 로그인 API (개발용)"""
#     # 실제로는 사용자 DB 확인
#     if credentials.get("email") == "dev@cheeseade.com" and credentials.get("password") == "dev123":
#         return {
#             "token": "sk-cheeseade-dev-key-001",
#             "token_type": "Bearer",
#             "user": {
#                 "id": "dev-user",
#                 "email": "dev@cheeseade.com",
#                 "name": "Developer"
#             }
#         }
    
#     raise HTTPException(status_code=401, detail="Invalid credentials")

# @app.get("/api/auth/me")
# async def get_me(current_user: dict = Depends(get_current_user)):
#     """현재 사용자 정보"""
#     return {
#         "user": current_user,
#         "authenticated": True
#     }















##############################
### Open Web UI 엔드포인트 ###
##############################

# 1. GET /api/models

# 응답 모델 정의 (OpenWebUI 형식에 맞춤)
class Model(BaseModel):
    id: str
    name: str
    # 필요에 따라 다른 필드를 추가할 수 있습니다.
    # 예: "object": "model", "owned_by": "user", "permissions": []

class ModelList(BaseModel):
    models: List[Model]

curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:3000/api/models

@app.get("/api/models", response_model=ModelList)
async def list_models():
    return ModelsResponse(
        object="list",  
        data=[
            ModelInfo(
                id=RAG_MODEL_NAME,
                object="model",  
                owned_by="CHEESEADE",
                created=int(time.time()),  
                permission=[],
                root=RAG_MODEL_NAME,
            )
        ]
    )



@app.post("/api/chat", response_model=ChatResponse)
async def chat_completions(
    request: ChatMessage,
    authorization: Optional[str] = Header(None)
):
    try:
        if authorization:
            print(f"🔑 인증: {authorization[:20]}...")
        
        print(f"\n🎯 POST : /api/chat/completions")
        print(f"   모델: {request.model}")
        print(f"   스트림: {request.stream}")
        
        user_question = request.messages[-1].content
        print(f"   질문: {user_question}")
        
        if request.stream:
            return StreamingResponse(
                stream_rag_response(user_question, request.model),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            response_content = rag_chain.invoke(user_question)
            print(f"✅ 응답: {response_content}")
            
            return ChatResponse(
                id=f"chatcmpl-{uuid.uuid4()}",
                created=int(time.time()),
                model=request.model,
                choices=[
                    ChatResponseChoice(
                        index=0,
                        message=ChatResponseMessage(role="assistant", content=response_content)
                    )
                ]
            )
    except Exception as e:
        print(f"❌ API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/tags")
async def get_models():
    """RAG 모델만 제공"""
    return {
        "models": [{
            "name": RAG_MODEL_NAME,
            "model": RAG_MODEL_NAME,
            "modified_at": "2024-01-01T00:00:00Z",
            "size": 1000000000,
            "digest": "sha256:rag001",
            "details": {
                "family": "rag-enhanced",
                "parameter_size": "RAG + 27B",
                "quantization_level": "Q4_K_M",
                "description": "CHEESEADE RAG를 활용한 전문 상담"
            }
        }]
    }

@app.get("/health")
def health_check(response: Response):
    print(f'📋 /health 응답')
    response.status_code = status.HTTP_200_OK
    return {"status": "healthy", "service": "rag-server"}

@app.get("/")
async def root():
    """루트 엔드포인트 - Open WebUI 호환"""
    return {
        "message": "CHEESEADE RAG Server",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/debug/test-retrieval")
async def test_retrieval(query: dict):
    """검색 테스트"""
    try:
        question = query.get("question", "카메라")
        docs = retriever.invoke(question)
        return {
            "question": question,
            "retrieved_docs": len(docs),
            "docs": [
                {
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in docs
            ]
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")















# # Pydantic 모델들
# class Message(BaseModel):
#     role: str
#     content: str

# class ChatRequest(BaseModel):
#     model: str
#     messages: List[Message]
#     stream: bool = False
#     max_tokens: Optional[int] = None
#     temperature: Optional[float] = None

# class ChatResponseMessage(BaseModel):
#     role: str
#     content: str

# class ChatResponseChoice(BaseModel):
#     index: int
#     message: ChatResponseMessage
#     finish_reason: Optional[str] = "stop"

# class ChatResponse(BaseModel):
#     id: str
#     object: str = "chat.completion"
#     created: int
#     model: str
#     choices: List[ChatResponseChoice]
#     usage: Optional[dict] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}



# class ModelsResponse(BaseModel):
#     object: str = "list"
#     data: List[ModelInfo]

# class ChatMessage(BaseModel):
#     message: str
#     # 필요에 따라 user_id, session_id 등 추가 필드를 정의할 수 있습니다.
#     # user_id: str | None = None