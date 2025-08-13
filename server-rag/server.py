import os
import uvicorn
import uuid
import time
import json
import requests
import torch
import asyncio

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Header
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
                    await asyncio.sleep(0.03)  # 작은 지연으로 스트리밍 효과
        
        # 방법 2: 스트리밍 미지원시 청크로 분할 (현재 방식 개선)
        else:
            response_content = await asyncio.get_event_loop().run_in_executor(
                None, rag_chain.invoke, question
            )
            print(f"🔍 전체 응답: {response_content}")
            
            # 단어 단위로 분할 (더 자연스러운 스트리밍)
            words = response_content.split()
            chunk_size = 1  # 3단어씩
            
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
                    await asyncio.sleep(0.03)  # 작은 지연으로 스트리밍 효과
        
        # 방법 2: 스트리밍 미지원시 청크로 분할 (현재 방식 개선)
        else:
            response_content = await asyncio.get_event_loop().run_in_executor(
                None, rag_chain.invoke, question
            )
            print(f"🔍 전체 응답: {response_content}")
            
            # 단어 단위로 분할 (더 자연스러운 스트리밍)
            words = response_content.split()
            chunk_size = 1  # 3단어씩
            
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
        yield "data: [DONE]\n\n"  # OpenAI 스타일 종료 신호
        
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
                    await asyncio.sleep(0.03)  # 작은 지연으로 스트리밍 효과
        
        # 방법 2: 스트리밍 미지원시 청크로 분할 (현재 방식 개선)
        else:
            response_content = await asyncio.get_event_loop().run_in_executor(
                None, rag_chain.invoke, question
            )
            print(f"🔍 전체 응답: {response_content}")
            
            # 단어 단위로 분할 (더 자연스러운 스트리밍)
            words = response_content.split()
            chunk_size = 1  # 3단어씩
            
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


##############################
### Open Web UI 엔드포인트 ###
##############################
'''
/api/chat/completions : 가장 중요한 엔드포인트, Open WebUI로 부터 전달받은 질문에 대한 처리를 끝내고 회신
/api/models : 현재 Open WebUI를 통해 사용 가능한 모델들의 목록을 전달
/api/tags : 사용 가능한 모델 목록 전달


'''

@app.post("/api/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
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


@app.get("/api/models", response_model=ModelsResponse)
async def list_models():
    return ModelsResponse(
        object="list",  
        data=[
            ModelInfo(
                id="rag-cheeseade",
                object="model",  
                owned_by="CHEESEADE",
                created=int(time.time()),  
                permission=[],  # 빈 리스트로 설정
                root="rag-cheeseade",  # 보통 id와 동일
            )
        ]
    )















# @app.middleware("http")
# async def api_key_middleware(request: Request, call_next):
#     """API 키 검증을 건너뛰는 미들웨어"""
#     # Authorization 헤더가 있어도 무시하고 계속 진행
#     response = await call_next(request)
#     return response

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

# class StreamChoiceDelta(BaseModel):
#     content: str

# class StreamChoice(BaseModel):
#     index: int = 0
#     delta: StreamChoiceDelta
#     finish_reason: Optional[str] = None

# class StreamResponse(BaseModel):
#     id: str
#     object: str = "chat.completion.chunk"
#     created: int
#     model: str
#     choices: List[StreamChoice]

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

# class ModelInfo(BaseModel):
#     id: str
#     object: str = "model"
#     created: int = 1677652288
#     owned_by: str = "rag-server"

# class ModelsResponse(BaseModel):
#     object: str = "list"
#     data: List[ModelInfo]






# # Open WebUI가 요청할 수 있는 엔드포인트
# @app.post("/api/chat/completions")
# async def alt_chat_completions(request: ChatRequest):
#     """대안 채팅 엔드포인트"""
#     return await openai_chat_completions(request)



# @app.post("/api/chat")
# async def chat_with_rag(request: ChatRequest):
#     """모델 선택에 따른 RAG/직접 LLM 처리"""
#     try:
#         print(f"\n🎯 채팅 요청 수신:")
#         print(f"   모델: {request.model}")
#         print(f"   메시지 수: {len(request.messages)}")
#         print(f"   스트림: {request.stream}")
        
#         user_question = request.messages[-1].content
#         print(f"   질문: {user_question[:100]}...")
        
#         # Open WebUI 내부 시스템 요청 필터링
#         if any(keyword in user_question.lower() for keyword in [
#             "### task:", "follow-up", "follow_ups", "generate", "suggest", "tags"
#         ]):
#             print("🚫 시스템 요청 감지 - 기본 응답 반환")
#             return ChatResponse(
#                 id=f"chatcmpl-{uuid.uuid4()}",
#                 created=int(time.time()),
#                 model=request.model,
#                 choices=[
#                     ChatResponseChoice(
#                         index=0,
#                         message=ChatResponseMessage(
#                             role="assistant", 
#                             content="안녕하세요! 궁금한 점이 있으시면 언제든 물어보세요."
#                         )
#                     )
#                 ]
#             )
        
#         # 모델별 처리 분기
#         if is_rag_model(request.model):
#             print("🔍 RAG 모델 선택됨 - RAG 파이프라인 처리")
#             response_content = await process_with_rag(user_question)
            
#         elif is_direct_model(request.model):
#             print("🎯 직접 LLM 모델 선택됨 - 바로 LLM 처리")
#             response_content = await process_direct_llm(user_question, request.model)
            
#         else:
#             print(f"⚠️ 알 수 없는 모델: {request.model} - 기본 RAG 처리")
#             response_content = await process_with_rag(user_question)
        
#         # 응답 검증 - 빈 응답 방지
#         if not response_content or len(response_content.strip()) < 3:
#             response_content = "안녕하세요! 무엇을 도와드릴까요?"
#             print("⚠️ 빈 응답 감지 - 기본 응답으로 대체")
        
#         print(f"✅ 최종 응답: {len(response_content)} 문자")
#         print(f"🔍 응답 내용: '{response_content[:200]}...'")
        
#         # 중요: 스트림 요청이어도 일반 응답으로 처리 (디버깅용)
#         print("📤 일반 응답 모드로 처리 (스트림 우회)")
        
#         response = ChatResponse(
#             id=f"chatcmpl-{uuid.uuid4()}",
#             created=int(time.time()),
#             model=request.model,
#             choices=[
#                 ChatResponseChoice(
#                     index=0, 
#                     message=ChatResponseMessage(
#                         role="assistant", 
#                         content=response_content  # 여기가 핵심!
#                     )
#                 )
#             ],
#             usage={
#                 "prompt_tokens": len(user_question.split()),
#                 "completion_tokens": len(response_content.split()),
#                 "total_tokens": len(user_question.split()) + len(response_content.split())
#             }
#         )
        
#         print(f"📤 응답 객체 생성 완료: content='{response.choices[0].message.content[:100]}...'")
#         return response
            
#     except Exception as e:
#         print(f"❌ Error in chat endpoint: {str(e)}")
#         import traceback
#         traceback.print_exc()
        
#         # 에러 시에도 유효한 응답 반환
#         return ChatResponse(
#             id=f"chatcmpl-{uuid.uuid4()}",
#             created=int(time.time()),
#             model=request.model,
#             choices=[
#                 ChatResponseChoice(
#                     index=0,
#                     message=ChatResponseMessage(
#                         role="assistant",
#                         content="죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요."
#                     )
#                 )
#             ]
#         )

# # 간단한 스트리밍 함수
# async def stream_rag_response_simple(response_content: str, model_name: str):
#     """개선된 스트리밍 응답 - Open WebUI 호환"""
#     try:
#         print(f"📡 스트리밍 시작: '{response_content[:50]}...'")
        
#         # 문자 단위로 스트리밍 (더 자연스러운 타이핑 효과)
#         chunk_size = 5  # 5문자씩
#         for i in range(0, len(response_content), chunk_size):
#             chunk = response_content[i:i+chunk_size]
            
#             response_chunk = {
#                 "id": f"chatcmpl-{uuid.uuid4()}",
#                 "object": "chat.completion.chunk",
#                 "created": int(time.time()),
#                 "model": model_name,
#                 "choices": [{
#                     "index": 0,
#                     "delta": {"content": chunk},
#                     "finish_reason": None
#                 }]
#             }
            
#             # 한글 깨짐 방지
#             chunk_json = json.dumps(response_chunk, ensure_ascii=False)
#             yield f"data: {chunk_json}\n\n"
            
#             # 약간의 지연으로 타이핑 효과
#             import asyncio
#             await asyncio.sleep(0.05)
        
#         # 스트림 종료 신호
#         final_chunk = {
#             "id": f"chatcmpl-{uuid.uuid4()}",
#             "object": "chat.completion.chunk", 
#             "created": int(time.time()),
#             "model": model_name,
#             "choices": [{
#                 "index": 0,
#                 "delta": {},
#                 "finish_reason": "stop"
#             }]
#         }
        
#         final_json = json.dumps(final_chunk, ensure_ascii=False)
#         yield f"data: {final_json}\n\n"
#         yield "data: [DONE]\n\n"
        
#         print(f"📡 스트리밍 완료")
        
#     except Exception as e:
#         print(f"❌ 스트리밍 오류: {e}")
#         error_response = {
#             "id": f"chatcmpl-{uuid.uuid4()}",
#             "object": "chat.completion.chunk",
#             "created": int(time.time()),
#             "model": model_name,
#             "choices": [{
#                 "index": 0,
#                 "delta": {"content": f"오류: {str(e)}"},
#                 "finish_reason": "stop"
#             }]
#         }
#         yield f"data: {json.dumps(error_response, ensure_ascii=False)}\n\n"
#         yield "data: [DONE]\n\n"

# # Open WebUI용 추가 엔드포인트들
# @app.post("/api/generate")
# async def generate(request: dict):
#     """Ollama generate API 호환"""
#     try:
#         prompt = request.get("prompt", "")
#         model = request.get("model", "rag-samsung")
#         stream = request.get("stream", False)
        
#         print(f"🎯 Generate 요청: model={model}, stream={stream}")
#         print(f"   프롬프트: {prompt}")
        
#         if stream:
#             # 스트리밍 응답
#             async def generate_stream():
#                 async for chunk in rag_chain.astream(prompt):
#                     if chunk:
#                         response = {
#                             "model": model,
#                             "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
#                             "response": chunk,
#                             "done": False
#                         }
#                         yield f"{json.dumps(response)}\n"
                
#                 # 완료 신호
#                 final_response = {
#                     "model": model,
#                     "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
#                     "response": "",
#                     "done": True
#                 }
#                 yield f"{json.dumps(final_response)}\n"
            
#             return StreamingResponse(generate_stream(), media_type="application/json")
#         else:
#             # 일반 응답
#             response_content = rag_chain.invoke(prompt)
#             return {
#                 "model": model,
#                 "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
#                 "response": response_content,
#                 "done": True
#             }
#     except Exception as e:
#         print(f"❌ Generate 오류: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/api/pull")
# async def pull_model(request: dict):
#     """모델 다운로드 (실제로는 아무것도 하지 않음)"""
#     return {
#         "status": "success",
#         "digest": "sha256:abcd1234",
#         "total": 1000000000,
#         "completed": 1000000000
#     }

# @app.delete("/api/delete")
# async def delete_model(request: dict):
#     """모델 삭제 (실제로는 아무것도 하지 않음)"""
#     return {"status": "success"}

# @app.post("/api/copy")
# async def copy_model(request: dict):
#     """모델 복사 (실제로는 아무것도 하지 않음)"""
#     return {"status": "success"}

# @app.post("/api/create")
# async def create_model(request: dict):
#     """모델 생성 (실제로는 아무것도 하지 않음)"""
#     return {"status": "success"}

# @app.post("/api/push")
# async def push_model(request: dict):
#     """모델 업로드 (실제로는 아무것도 하지 않음)"""
#     return {"status": "success"}

# @app.post("/api/show")
# async def show_model(request: dict):
#     """모델 정보 표시"""
#     return {
#         "license": "Apache 2.0",
#         "modelfile": "FROM rag-samsung:latest",
#         "parameters": "temperature 0.7",
#         "template": "{{ .Prompt }}",
#         "details": {
#             "parent_model": "",
#             "format": "gguf",
#             "family": "gemma3",
#             "families": ["gemma3"],
#             "parameter_size": "27B",
#             "quantization_level": "Q4_K_M"
#         }
#     }

# @app.get("/health")
# async def health_check():
#     return {"status": True}

# @app.get("/")
# async def root():
#     """루트 엔드포인트 - Open WebUI 호환"""
#     return {
#         "message": "Samsung RAG Server",
#         "version": "1.0.0",
#         "status": "running"
#     }

# @app.get("/api")
# async def api_root():
#     """API 루트"""
#     return {
#         "message": "Samsung RAG API",
#         "version": "1.0.0",
#         "endpoints": ["/api/tags", "/api/chat", "/api/generate"]
#     }

# @app.get("/debug/test-openwebui")
# async def test_open_webui_format():
#     """Open WebUI 형식 테스트"""
#     return {
#         "id": "chatcmpl-test123",
#         "object": "chat.completion",
#         "created": int(time.time()),
#         "model": "rag-samsung",
#         "choices": [
#             {
#                 "index": 0,
#                 "message": {
#                     "role": "assistant",
#                     "content": "테스트 응답입니다. 이것이 보이면 형식이 올바릅니다."
#                 },
#                 "finish_reason": "stop"
#             }
#         ],
#         "usage": {
#             "prompt_tokens": 10,
#             "completion_tokens": 20,
#             "total_tokens": 30
#         }
#     }

# @app.post("/debug/direct-chat")
# async def direct_chat(query: dict):
#     """직접 RAG 테스트용 엔드포인트"""
#     try:
#         question = query.get("question", "안녕")
#         print(f"\n🧪 직접 테스트: {question}")
        
#         response = rag_chain.invoke(question)
#         print(f"✅ 직접 응답: {response}")
        
#         return {
#             "question": question,
#             "response": response,
#             "length": len(response)
#         }
#     except Exception as e:
#         print(f"❌ 직접 테스트 오류: {e}")
#         return {"error": str(e)}



# @app.options("/api/chat")
# async def chat_options():
#     """CORS preflight 요청 처리"""
#     return {"message": "OK"}

# @app.get("/api/version")
# async def api_version():
#     """API 버전 정보 (Open WebUI 필수)"""
#     return {
#         "version": "0.1.0",
#         "build": "samsung-rag-2025"
#     }

# @app.get("/version")
# async def get_version_alt():
#     """대체 버전 엔드포인트"""
#     return {"version": "0.1.0"}

# # Open WebUI가 요청하는 추가 엔드포인트들
# # Open WebUI가 요청하는 추가 엔드포인트들
# @app.get("/ollama/api/tags")
# async def ollama_get_models():
#     """Open WebUI용 Ollama 태그 엔드포인트"""
#     return {
#         "models": [
#             {
#                 "name": "rag-samsung:latest",
#                 "model": "rag-samsung:latest", 
#                 "modified_at": "2024-01-01T00:00:00Z",
#                 "size": 1000000000,
#                 "digest": "sha256:abcd1234",
#                 "details": {
#                     "parent_model": "",
#                     "format": "gguf", 
#                     "family": "gemma3",
#                     "families": ["gemma3"],
#                     "parameter_size": "27B",
#                     "quantization_level": "Q4_K_M"
#                 }
#             }
#         ]
#     }

# @app.get("/ollama/api/version")
# async def ollama_get_version():
#     """Open WebUI용 Ollama 버전 엔드포인트"""
#     return {"version": "0.1.0"}

# @app.post("/ollama/api/chat")
# async def ollama_chat(request: ChatRequest):
#     """Open WebUI용 Ollama 채팅 엔드포인트"""
#     return await chat_with_rag(request)

# @app.post("/ollama/api/generate")
# async def ollama_generate(request: dict):
#     """Open WebUI용 Ollama 생성 엔드포인트"""
#     return await generate(request)

# @app.get("/api/ps")
# async def get_running_models():
#     """실행 중인 모델 목록"""
#     return {
#         "models": [
#             {
#                 "name": "rag-samsung:latest", 
#                 "model": "rag-samsung:latest",
#                 "size": 1000000000,
#                 "digest": "sha256:abcd1234",
#                 "details": {
#                     "parent_model": "",
#                     "format": "gguf",
#                     "family": "gemma3",
#                     "families": ["gemma3"],
#                     "parameter_size": "27B",
#                     "quantization_level": "Q4_K_M"
#                 },
#                 "expires_at": "2024-12-31T23:59:59Z",
#                 "size_vram": 500000000
#             }
#         ]
#     }

# @app.post("/debug/test-retrieval")
# async def test_retrieval(query: dict):
#     """검색 테스트"""
#     try:
#         question = query.get("question", "카메라")
#         docs = retriever.invoke(question)
#         return {
#             "question": question,
#             "retrieved_docs": len(docs),
#             "docs": [
#                 {
#                     "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
#                     "metadata": doc.metadata
#                 }
#                 for doc in docs
#             ]
#         }
#     except Exception as e:
#         return {"error": str(e)}

# # server.py에 추가할 엔드포인트들 (API 키 관련)

# @app.get("/api/v1/auths/api_key")
# async def get_api_key():
#     """API 키 상태 확인 (Open WebUI 호환)"""
#     return {"api_key": None, "status": "disabled"}

# @app.post("/api/v1/auths/api_key")
# async def set_api_key(request: dict):
#     """API 키 설정 (더미 엔드포인트)"""
#     return {"status": "success", "message": "API key not required"}

# @app.delete("/api/v1/auths/api_key")
# async def delete_api_key():
#     """API 키 삭제 (더미 엔드포인트)"""
#     return {"status": "success"}

# # Open WebUI 인증 관련 추가 엔드포인트
# @app.get("/api/auth")
# async def auth_status():
#     """인증 상태 확인"""
#     return {"authenticated": True, "user": "anonymous"}

# @app.get("/api/config")
# async def get_config():
#     """Open WebUI 설정 정보"""
#     return {
#         "name": "Samsung AI Assistant",
#         "version": "1.0.0",
#         "auth": False,
#         "default_models": ["rag-samsung:latest", "gemma3:27b-it-q4_K_M"],
#         "features": {
#             "enable_signup": True,
#             "enable_login": False,
#             "enable_api_key": False
#         }
#     }

# # OPTIONS 요청 처리 (CORS preflight)
# @app.options("/{full_path:path}")
# async def options_handler(full_path: str):
#     """모든 경로에 대한 OPTIONS 요청 처리"""
#     return {"message": "OK"}

# # 에러 핸들러 추가
# from fastapi import Request
# from fastapi.responses import JSONResponse

# @app.exception_handler(404)
# async def not_found_handler(request: Request, exc):
#     """404 에러를 JSON으로 반환"""
#     return JSONResponse(
#         status_code=404,
#         content={
#             "error": "Not Found",
#             "message": f"Endpoint {request.url.path} not found",
#             "available_endpoints": [
#                 "/health", "/api/tags", "/api/chat", "/api/version"
#             ]
#         }
#     )

# @app.exception_handler(500)
# async def internal_error_handler(request: Request, exc):
#     """500 에러를 JSON으로 반환"""
#     return JSONResponse(
#         status_code=500,
#         content={
#             "error": "Internal Server Error",
#             "message": str(exc) if hasattr(exc, 'detail') else "Unknown error"
#         }
#     )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # 모든 오리진 허용
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["*"],
# )

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")







# # -------------------------------------------------------------------------------
# # -------------------------------------------------------------------------------
# # -------------------------------------------------------------------------------
# # -------------------------------------------------------------------------------


# # RAG 전용 FastAPI 서버
# import os
# from fastapi import FastAPI
# from langchain_ollama import ChatOllama

# # 환경변수
# try:
#     LLM_SERVER_URL = os.environ["LLM_SERVER_URL"]
# except KeyError:
#     raise ValueError("필수 환경 변수인 'LLM_SERVER_URL'이 설정되지 않았습니다. .env 또는 .env.global 파일을 확인해주세요.")
# try:
#     RAG_MODEL_NAME = os.environ["RAG_MODEL_NAME"]
# except KeyError:
#     raise ValueError("필수 환경 변수인 'RAG_MODEL_NAME'이 설정되지 않았습니다. .env 또는 .env.global 파일을 확인해주세요.")


# app = FastAPI(title="CHEESEADE RAG Server", version="1.0.0")

# @app.get("/api/tags")
# async def get_models():
#     """RAG 모델만 제공"""
#     return {
#         "models": [{
#             "name": RAG_MODEL_NAME,
#             "model": RAG_MODEL_NAME,
#             "details": {
#                 "description": "CHEESEADE RAG를 활용한 전문 상담"
#             }
#         }]
#     }

# @app.post("/api/chat")
# async def chat_with_rag(request: ChatRequest):
#     """RAG 처리 전용"""
#     # 항상 RAG 파이프라인 사용
#     response = rag_chain.invoke(request.messages[-1].content)
#     return create_chat_response(response, RAG_MODEL_NAME)

# @app.get("/health")
# async def health_check():
#     return {"status": "healthy", "service": "rag-server"}


# @app.get("/api/tags")
# async def get_models():
#     try:
#         return {
#             "models": [
#                 {
#                     "name": "rag-samsung:latest",
#                     "model": "rag-samsung:latest",
#                     "modified_at": "2024-01-01T00:00:00Z",
#                     "size": 1000000000,
#                     "digest": "sha256:rag001",
#                     "details": {
#                         "family": "rag-enhanced",
#                         "parameter_size": "RAG + 27B",
#                         "quantization_level": "Q4_K_M",
#                         "description": "Samsung 제품 전용 RAG 어시스턴트"
#                     }
#                 },
#                 {
#                     "name": "gemma3:27b-it-q4_K_M",
#                     "model": "gemma3:27b-it-q4_K_M", 
#                     "modified_at": "2024-01-01T00:00:00Z",
#                     "size": 15000000000,
#                     "digest": "sha256:gem001",
#                     "details": {
#                         "family": "gemma3",
#                         "parameter_size": "27B",
#                         "quantization_level": "Q4_K_M",
#                         "description": "일반용 대화형 AI 모델"
#                     }
#                 }
#             ]
#         }
#     except Exception as e:
#         print(f"Error in /api/tags: {e}")
#         return {"models": []}