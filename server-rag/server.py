# RAG 전용 FastAPI 서버
import os
from fastapi import FastAPI
from langchain_ollama import ChatOllama

# 환경변수
try:
    LLM_SERVER_URL = os.environ["LLM_SERVER_URL"]
except KeyError:
    raise ValueError("필수 환경 변수인 'LLM_SERVER_URL'이 설정되지 않았습니다. .env 또는 .env.global 파일을 확인해주세요.")
try:
    RAG_MODEL_NAME = os.environ["RAG_MODEL_NAME"]
except KeyError:
    raise ValueError("필수 환경 변수인 'RAG_MODEL_NAME'이 설정되지 않았습니다. .env 또는 .env.global 파일을 확인해주세요.")


app = FastAPI(title="CHEESEADE RAG Server", version="1.0.0")

@app.get("/api/tags")
async def get_models():
    """RAG 모델만 제공"""
    return {
        "models": [{
            "name": RAG_MODEL_NAME,
            "model": RAG_MODEL_NAME,
            "details": {
                "description": "CHEESEADE RAG를 활용한 전문 상담"
            }
        }]
    }

@app.post("/api/chat")
async def chat_with_rag(request: ChatRequest):
    """RAG 처리 전용"""
    # 항상 RAG 파이프라인 사용
    response = rag_chain.invoke(request.messages[-1].content)
    return create_chat_response(response, RAG_MODEL_NAME)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-server"}