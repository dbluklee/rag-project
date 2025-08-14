"""
CHEESEADE RAG Server - 메인 서버
주요 기능: 환경설정, 모델 초기화, 청킹, 임베딩, 리트리버, RAG 구성, FastAPI 실행
"""
import os
import uvicorn
import requests
import torch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain_core.runnables import RunnableParallel

from chunking.chunking_md import chunk_markdown_file
from embedding.bge_m3 import get_bge_m3_model
from retriever.retriever import get_retriever
from vector_db.milvus import MilvusVectorStore

# API 모듈들 import
from api.routes import router as api_router, set_chat_handler
from api.chat_handler import ChatHandler

# ================================
# 환경변수 설정
# ================================

print("🔧 환경변수 로드 중...")
LLM_SERVER_URL = os.environ["LLM_SERVER_URL"]
RAG_MODEL_NAME = os.environ["RAG_MODEL_NAME"]
MILVUS_SERVER_IP = os.environ["MILVUS_SERVER_IP"]
MILVUS_PORT = os.environ["MILVUS_PORT"]
LLM_MODEL_NAME = os.environ["LLM_MODEL_NAME"]
collection_name = os.environ["COMPANY_NAME"].lower+'_'+os.environ["METRIC_TYPE"].lower+'_'+os.environ["INDEX_TYPE"].lower

print(f"✅ 환경변수 설정 완료")
print(f"   LLM 서버: {LLM_SERVER_URL}")
print(f"   RAG 모델: {RAG_MODEL_NAME}")
print(f"   LLM 모델: {LLM_MODEL_NAME}")
print(f"   Milvus: {MILVUS_SERVER_IP}:{MILVUS_PORT}")
print(f"   컬렉션: {collection_name}")

# ================================
# LLM 서버 연결 및 초기화
# ================================

print(f"\n🔗 LLM 서버 연결 시도...")
try:
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
    print(f"✅ LLM 초기화 완료: {LLM_MODEL_NAME}")
    
except requests.exceptions.ConnectionError:
    print(f"❌ LLM 서버 연결 실패: {LLM_SERVER_URL}")
    llm = None
except Exception as e:
    print(f"❌ LLM 서버 연결 중 오류: {e}")
    llm = None

# ================================
# 임베딩 모델 로드
# ================================

print(f"\n🤖 임베딩 모델 로드 중...")
if torch.cuda.is_available():
    print(f"✅ CUDA 사용 가능: {torch.cuda.get_device_name(0)}")
    print(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    device = 'cuda'
else:
    print("⚠️ CUDA 사용 불가 - CPU 사용")
    device = 'cpu'

print(f"🔧 {device}를 사용하여 임베딩 모델 로드")
embedding_model = get_bge_m3_model()
print(f"✅ 임베딩 모델 로드 완료")

# ================================
# 문서 청킹
# ================================

print(f"\n📝 문서 청킹 시작...")
markdown_path = "./docs/feature.md"
chunks = chunk_markdown_file(markdown_path)

if len(chunks) == 0:
    print("❌ 문서 청킹 결과가 없습니다!")
    raise ValueError("문서 청킹 실패 - 처리할 수 있는 내용이 없습니다")

print(f"✅ 청킹 완료: {len(chunks)}개 청크")

# ================================
# 벡터 스토어 초기화 및 문서 추가
# ================================

print(f"\n🗄️ 벡터 스토어 초기화...")
vector_store = MilvusVectorStore(
    collection_name=collection_name, 
    embedding_model=embedding_model,
    metric_type=METRIC_TYPE,
    index_type=INDEX_TYPE,
    milvus_host=MILVUS_SERVER_IP,  
    milvus_port=MILVUS_PORT   
)

print(f"\n📤 문서를 벡터 DB에 추가...")
inserted_ids = vector_store.add_documents(chunks)
print(f"✅ 벡터 DB 추가 완료: {len(inserted_ids)}개 문서")

# ================================
# 리트리버 생성
# ================================

print(f"\n🔍 리트리버 생성...")
retriever = get_retriever(vector_store, retriever_type='top_k')
print(f"✅ 리트리버 생성 완료")

# ================================
# RAG 체인 구성
# ================================

print(f"\n🔗 RAG 체인 구성...")

# 시스템 프롬프트
system_prompt = '''Answer the user's Question from the Context.
Keep your answer ground in the facts of the Context.
If the Context doesn't contain the facts to answer, just output '답변할 수 없습니다'
Please answer in Korean.'''

# RAG 프롬프트 템플릿
RAG_prompt = ChatPromptTemplate([
    ('system', system_prompt),
    ('user', '''Context: {context}
    ---
     Question: {question}''')
])

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

print(f"✅ RAG 체인 구성 완료")

# ================================
# 채팅 핸들러 초기화
# ================================

print(f"\n💬 채팅 핸들러 초기화...")
chat_handler = ChatHandler(
    rag_chain=rag_chain,
    retriever=retriever,
    rag_model_name=RAG_MODEL_NAME,
    llm_server_url=LLM_SERVER_URL
)

# API 라우터에 채팅 핸들러 설정
set_chat_handler(chat_handler)
print(f"✅ 채팅 핸들러 설정 완료")

# ================================
# FastAPI 앱 생성 및 설정
# ================================

print(f"\n🚀 FastAPI 앱 생성...")
app = FastAPI(
    title="CHEESEADE RAG Server", 
    description="RAG API 서버 with OpenWebUI 호환", 
    version="1.0.0"
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router)

print(f"✅ FastAPI 설정 완료")

# ================================
# 루트 엔드포인트
# ================================

@app.get("/")
async def root():
    """시스템 정보 및 상태"""
    return {
        "message": "CHEESEADE RAG Server",
        "version": "1.0.0",
        "status": "running",
        "system": {
            "llm_model": LLM_MODEL_NAME,
            "rag_model": RAG_MODEL_NAME,
            "embedding_device": device,
            "documents_loaded": len(chunks),
            "vector_collection": collection_name
        },
        "endpoints": {
            "chat": "/api/chat/completions",
            "models": "/api/models", 
            "tags": "/api/tags",
            "health": "/health",
            "debug": "/debug/test-retrieval"
        },
        "features": [
            "RAG (Retrieval-Augmented Generation)",
            "OpenAI Compatible API",
            "Ollama Compatible API", 
            "OpenWebUI Compatible API",
            "Streaming Support"
        ]
    }

# ================================
# 서버 실행
# ================================

if __name__ == "__main__":
    print(f"\n🎯 서버 시작 준비 완료!")
    print(f"📊 시스템 요약:")
    print(f"   🤖 LLM 모델: {LLM_MODEL_NAME}")
    print(f"   🔍 RAG 모델: {RAG_MODEL_NAME}")
    print(f"   📄 로드된 문서: {len(chunks)}개")
    print(f"   💾 벡터 컬렉션: {collection_name}")
    print(f"   🖥️ 임베딩 디바이스: {device}")
    print(f"\n🌐 서버 주소: http://0.0.0.0:8000")
    print(f"📖 API 문서: http://0.0.0.0:8000/docs")
    print