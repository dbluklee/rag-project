"""
Ollama API
공식 문서 : https://github.com/ollama/ollama/blob/main/docs/api.md

"""
import json
import time
import asyncio
import requests
import traceback
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 라우터 생성
router = APIRouter()

# 전역 채팅 핸들러 (server.py에서 설정)
chat_handler = None

def set_chat_handler(handler):
    """채팅 핸들러 설정"""
    global chat_handler
    chat_handler = handler
    print(f"✅ [SET_HANDLER] 채팅 핸들러 설정 완료")
    print(f"   [SET_HANDLER] RAG 모델명: {getattr(handler, 'rag_model_name', 'UNKNOWN')}")
    print(f"   [SET_HANDLER] LLM 서버 URL: {getattr(handler, 'llm_server_url', 'UNKNOWN')}")

# ================================
# Ollama API 모델 정의 (최소한)
# ================================

class OllamaMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str
    images: Optional[List[str]] = None

class OllamaChatRequest(BaseModel):
    model: str
    messages: List[OllamaMessage]
    stream: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None

class OllamaGenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None
    system: Optional[str] = None

# ================================
# 핵심 API 엔드포인트
# ================================

@router.post("/api/chat")
async def chat_ollama(request: OllamaChatRequest):
    """
    Ollama 채팅 API
    POST /api/chat
    """
    print(f"\n🎯 [CHAT_START] POST /api/chat 시작")
    print(f"   [CHAT_START] 모델: {request.model}")
    print(f"   [CHAT_START] 스트림: {request.stream}")
    print(f"   [CHAT_START] 메시지 수: {len(request.messages)}")
    
    # 채팅 핸들러 확인
    if not chat_handler:
        print(f"❌ [CHAT_ERROR] 채팅 핸들러가 초기화되지 않음")
        raise HTTPException(status_code=503, detail="Chat handler not initialized")
    
    print(f"✅ [CHAT_CHECK] 채팅 핸들러 확인됨")
    
    # 메시지 출력
    for i, msg in enumerate(request.messages):
        print(f"   [CHAT_MSG_{i}] {msg.role}: {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
    
    # 가장 최근 사용자 메시지 가져오기
    print(f"🔍 [CHAT_PARSE] 사용자 메시지 찾는 중...")
    user_message = next((msg for msg in reversed(request.messages) if msg.role == "user"), None)
    
    if not user_message:
        print(f"❌ [CHAT_ERROR] 사용자 메시지를 찾을 수 없음")
        raise HTTPException(status_code=400, detail="No user message found")
    
    question = user_message.content
    print(f"✅ [CHAT_PARSE] 사용자 질문: {question}")
    
    try:
        print(f"🔍 [CHAT_MODEL_CHECK] 모델 확인 중...")
        print(f"   [CHAT_MODEL_CHECK] 요청 모델: {request.model}")
        print(f"   [CHAT_MODEL_CHECK] RAG 모델: {chat_handler.rag_model_name}")
        
        # RAG 모델인지 확인
        if request.model == chat_handler.rag_model_name:
            print(f"✅ [CHAT_RAG] RAG 모델로 처리 시작")
            
            if request.stream:
                print(f"🌊 [CHAT_RAG_STREAM] 스트리밍 모드로 처리")
                return StreamingResponse(
                    rag_chat_stream(question, request.model),
                    media_type="application/x-ndjson"
                )
            else:
                print(f"📝 [CHAT_RAG_SYNC] 논스트리밍 모드로 처리")
                print(f"   [CHAT_RAG_SYNC] RAG 처리 시작...")
                response_content = await chat_handler.process_with_rag(question)
                print(f"   [CHAT_RAG_SYNC] RAG 응답 길이: {len(response_content)} 문자")
                print(f"   [CHAT_RAG_SYNC] RAG 응답 미리보기: {response_content[:200]}...")
                
                response = create_chat_response(request.model, response_content)
                print(f"✅ [CHAT_RAG_SYNC] 응답 생성 완료")
                return response
        else:
            print(f"🔄 [CHAT_PROXY] 일반 LLM으로 프록시 처리")
            print(f"   [CHAT_PROXY] LLM 서버 URL: {chat_handler.llm_server_url}")
            
            result = await proxy_chat_to_ollama(request)
            print(f"✅ [CHAT_PROXY] 프록시 완료")
            return result
            
    except Exception as e:
        print(f"❌ [CHAT_EXCEPTION] 채팅 처리 중 예외 발생")
        print(f"   [CHAT_EXCEPTION] 에러: {str(e)}")
        print(f"   [CHAT_EXCEPTION] 상세: {traceback.format_exc()}")
        
        error_response = create_chat_error_response(request.model, str(e))
        print(f"   [CHAT_EXCEPTION] 에러 응답 생성됨")
        return error_response

@router.post("/api/generate")
async def generate_ollama(request: OllamaGenerateRequest):
    """
    Ollama 생성 API
    POST /api/generate
    """
    print(f"\n🎯 [GENERATE_START] POST /api/generate 시작")
    print(f"   [GENERATE_START] 모델: {request.model}")
    print(f"   [GENERATE_START] 스트림: {request.stream}")
    print(f"   [GENERATE_START] 프롬프트: {request.prompt[:100]}{'...' if len(request.prompt) > 100 else ''}")
    
    # 채팅 핸들러 확인
    if not chat_handler:
        print(f"❌ [GENERATE_ERROR] 채팅 핸들러가 초기화되지 않음")
        raise HTTPException(status_code=503, detail="Chat handler not initialized")
    
    print(f"✅ [GENERATE_CHECK] 채팅 핸들러 확인됨")
    
    try:
        print(f"🔍 [GENERATE_MODEL_CHECK] 모델 확인 중...")
        print(f"   [GENERATE_MODEL_CHECK] 요청 모델: {request.model}")
        print(f"   [GENERATE_MODEL_CHECK] RAG 모델: {chat_handler.rag_model_name}")
        
        # RAG 모델인지 확인
        if request.model == chat_handler.rag_model_name:
            print(f"✅ [GENERATE_RAG] RAG 모델로 처리 시작")
            
            if request.stream:
                print(f"🌊 [GENERATE_RAG_STREAM] 스트리밍 모드로 처리")
                return StreamingResponse(
                    rag_generate_stream(request.prompt, request.model),
                    media_type="application/x-ndjson"
                )
            else:
                print(f"📝 [GENERATE_RAG_SYNC] 논스트리밍 모드로 처리")
                print(f"   [GENERATE_RAG_SYNC] RAG 처리 시작...")
                response_content = await chat_handler.process_with_rag(request.prompt)
                print(f"   [GENERATE_RAG_SYNC] RAG 응답 길이: {len(response_content)} 문자")
                print(f"   [GENERATE_RAG_SYNC] RAG 응답 미리보기: {response_content[:200]}...")
                
                response = create_generate_response(request.model, response_content)
                print(f"✅ [GENERATE_RAG_SYNC] 응답 생성 완료")
                return response
        else:
            print(f"🔄 [GENERATE_PROXY] 일반 LLM으로 프록시 처리")
            print(f"   [GENERATE_PROXY] LLM 서버 URL: {chat_handler.llm_server_url}")
            
            result = await proxy_generate_to_ollama(request)
            print(f"✅ [GENERATE_PROXY] 프록시 완료")
            return result
            
    except Exception as e:
        print(f"❌ [GENERATE_EXCEPTION] 생성 처리 중 예외 발생")
        print(f"   [GENERATE_EXCEPTION] 에러: {str(e)}")
        print(f"   [GENERATE_EXCEPTION] 상세: {traceback.format_exc()}")
        
        error_response = create_generate_error_response(request.model, str(e))
        print(f"   [GENERATE_EXCEPTION] 에러 응답 생성됨")
        return error_response

# ================================
# 헬퍼 함수들
# ================================

def create_chat_response(model: str, content: str, done: bool = True):
    """Ollama 채팅 응답 생성"""
    print(f"🔧 [CREATE_CHAT_RESP] 채팅 응답 생성 중...")
    print(f"   [CREATE_CHAT_RESP] 모델: {model}")
    print(f"   [CREATE_CHAT_RESP] 내용 길이: {len(content)} 문자")
    print(f"   [CREATE_CHAT_RESP] 완료 상태: {done}")
    
    response = {
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "message": {
            "role": "assistant",
            "content": content
        },
        "done": done,
        "total_duration": 1000000000,
        "load_duration": 100000000,
        "prompt_eval_count": 10,
        "prompt_eval_duration": 200000000,
        "eval_count": len(content.split()),
        "eval_duration": 500000000
    }
    
    print(f"✅ [CREATE_CHAT_RESP] 채팅 응답 생성 완료")
    return response

def create_generate_response(model: str, content: str, done: bool = True):
    """Ollama 생성 응답 생성"""
    print(f"🔧 [CREATE_GEN_RESP] 생성 응답 생성 중...")
    print(f"   [CREATE_GEN_RESP] 모델: {model}")
    print(f"   [CREATE_GEN_RESP] 내용 길이: {len(content)} 문자")
    print(f"   [CREATE_GEN_RESP] 완료 상태: {done}")
    
    response = {
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "response": content,
        "done": done,
        "context": [],
        "total_duration": 1000000000,
        "load_duration": 100000000,
        "prompt_eval_count": 10,
        "prompt_eval_duration": 200000000,
        "eval_count": len(content.split()),
        "eval_duration": 500000000
    }
    
    print(f"✅ [CREATE_GEN_RESP] 생성 응답 생성 완료")
    return response

def create_chat_error_response(model: str, error: str):
    """Ollama 채팅 에러 응답"""
    print(f"❌ [CREATE_CHAT_ERROR] 채팅 에러 응답 생성")
    print(f"   [CREATE_CHAT_ERROR] 모델: {model}")
    print(f"   [CREATE_CHAT_ERROR] 에러: {error}")
    
    return {
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "message": {
            "role": "assistant",
            "content": f"Error: {error}"
        },
        "done": True
    }

def create_generate_error_response(model: str, error: str):
    """Ollama 생성 에러 응답"""
    print(f"❌ [CREATE_GEN_ERROR] 생성 에러 응답 생성")
    print(f"   [CREATE_GEN_ERROR] 모델: {model}")
    print(f"   [CREATE_GEN_ERROR] 에러: {error}")
    
    return {
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "response": f"Error: {error}",
        "done": True
    }

# ================================
# 스트리밍 함수들
# ================================

async def rag_chat_stream(question: str, model: str):
    """RAG 채팅 스트리밍 (Ollama 형식)"""
    print(f"🌊 [RAG_CHAT_STREAM] 스트리밍 시작")
    print(f"   [RAG_CHAT_STREAM] 질문: {question}")
    print(f"   [RAG_CHAT_STREAM] 모델: {model}")
    
    try:
        print(f"   [RAG_CHAT_STREAM] RAG 처리 시작...")
        # RAG 응답 생성
        response_content = await chat_handler.process_with_rag(question)
        print(f"   [RAG_CHAT_STREAM] RAG 응답 완료: {len(response_content)} 문자")
        print(f"   [RAG_CHAT_STREAM] 응답 미리보기: {response_content[:100]}...")
        
        # 단어별로 분할해서 스트리밍
        words = response_content.split()
        chunk_size = 2  # 2단어씩
        total_chunks = (len(words) + chunk_size - 1) // chunk_size
        
        print(f"   [RAG_CHAT_STREAM] 스트리밍 청크 수: {total_chunks}")
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i+chunk_size]
            chunk = " ".join(chunk_words)
            if i + chunk_size < len(words):
                chunk += " "
            
            chunk_num = i // chunk_size + 1
            print(f"   [RAG_CHAT_STREAM] 청크 {chunk_num}/{total_chunks}: '{chunk}'")
            
            # Ollama 채팅 스트리밍 형식
            chunk_response = {
                "model": model,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "message": {
                    "role": "assistant",
                    "content": chunk
                },
                "done": False
            }
            
            yield json.dumps(chunk_response) + "\n"
            await asyncio.sleep(0.03)
        
        print(f"   [RAG_CHAT_STREAM] 모든 청크 전송 완료")
        
        # 종료 응답
        final_response = {
            "model": model,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "message": {
                "role": "assistant",
                "content": ""
            },
            "done": True,
            "total_duration": 1000000000,
            "load_duration": 100000000,
            "prompt_eval_count": len(question.split()),
            "prompt_eval_duration": 200000000,
            "eval_count": len(response_content.split()),
            "eval_duration": 500000000
        }
        
        print(f"   [RAG_CHAT_STREAM] 종료 응답 전송")
        yield json.dumps(final_response) + "\n"
        print(f"✅ [RAG_CHAT_STREAM] 스트리밍 완료")
        
    except Exception as e:
        print(f"❌ [RAG_CHAT_STREAM] 스트리밍 오류: {str(e)}")
        print(f"   [RAG_CHAT_STREAM] 상세: {traceback.format_exc()}")
        
        error_response = create_chat_error_response(model, str(e))
        yield json.dumps(error_response) + "\n"

async def rag_generate_stream(prompt: str, model: str):
    """RAG 생성 스트리밍 (Ollama 형식)"""
    print(f"🌊 [RAG_GEN_STREAM] 스트리밍 시작")
    print(f"   [RAG_GEN_STREAM] 프롬프트: {prompt}")
    print(f"   [RAG_GEN_STREAM] 모델: {model}")
    
    try:
        print(f"   [RAG_GEN_STREAM] RAG 처리 시작...")
        # RAG 응답 생성
        response_content = await chat_handler.process_with_rag(prompt)
        print(f"   [RAG_GEN_STREAM] RAG 응답 완료: {len(response_content)} 문자")
        print(f"   [RAG_GEN_STREAM] 응답 미리보기: {response_content[:100]}...")
        
        # 단어별로 분할해서 스트리밍
        words = response_content.split()
        chunk_size = 2
        total_chunks = (len(words) + chunk_size - 1) // chunk_size
        
        print(f"   [RAG_GEN_STREAM] 스트리밍 청크 수: {total_chunks}")
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i+chunk_size]
            chunk = " ".join(chunk_words)
            if i + chunk_size < len(words):
                chunk += " "
            
            chunk_num = i // chunk_size + 1
            print(f"   [RAG_GEN_STREAM] 청크 {chunk_num}/{total_chunks}: '{chunk}'")
            
            # Ollama 생성 스트리밍 형식
            chunk_response = {
                "model": model,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "response": chunk,
                "done": False
            }
            
            yield json.dumps(chunk_response) + "\n"
            await asyncio.sleep(0.03)
        
        print(f"   [RAG_GEN_STREAM] 모든 청크 전송 완료")
        
        # 종료 응답
        final_response = {
            "model": model,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "response": "",
            "done": True,
            "context": [],
            "total_duration": 1000000000,
            "load_duration": 100000000,
            "prompt_eval_count": len(prompt.split()),
            "prompt_eval_duration": 200000000,
            "eval_count": len(response_content.split()),
            "eval_duration": 500000000
        }
        
        print(f"   [RAG_GEN_STREAM] 종료 응답 전송")
        yield json.dumps(final_response) + "\n"
        print(f"✅ [RAG_GEN_STREAM] 스트리밍 완료")
        
    except Exception as e:
        print(f"❌ [RAG_GEN_STREAM] 스트리밍 오류: {str(e)}")
        print(f"   [RAG_GEN_STREAM] 상세: {traceback.format_exc()}")
        
        error_response = create_generate_error_response(model, str(e))
        yield json.dumps(error_response) + "\n"

# ================================
# 프록시 함수들
# ================================

async def proxy_chat_to_ollama(request: OllamaChatRequest):
    """채팅을 LLM 서버로 프록시"""
    print(f"🔄 [PROXY_CHAT] LLM 서버로 프록시 시작")
    print(f"   [PROXY_CHAT] 대상 URL: {chat_handler.llm_server_url}/api/chat")
    print(f"   [PROXY_CHAT] 요청 모델: {request.model}")
    
    try:
        request_data = request.dict()
        print(f"   [PROXY_CHAT] 요청 데이터 크기: {len(json.dumps(request_data))} bytes")
        
        print(f"   [PROXY_CHAT] HTTP 요청 전송 중...")
        response = requests.post(
            f"{chat_handler.llm_server_url}/api/chat",
            json=request_data,
            timeout=120
        )
        
        print(f"   [PROXY_CHAT] HTTP 응답 수신: {response.status_code}")
        print(f"   [PROXY_CHAT] 응답 크기: {len(response.content)} bytes")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"   [PROXY_CHAT] JSON 파싱 성공")
            print(f"   [PROXY_CHAT] 응답 필드: {list(response_data.keys())}")
            print(f"✅ [PROXY_CHAT] 프록시 성공")
            return response_data
        else:
            print(f"❌ [PROXY_CHAT] HTTP 에러: {response.status_code}")
            print(f"   [PROXY_CHAT] 에러 내용: {response.text[:200]}")
            return create_chat_error_response(request.model, f"LLM server error: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"❌ [PROXY_CHAT] 타임아웃 에러")
        return create_chat_error_response(request.model, "Request timeout")
    except requests.exceptions.ConnectionError:
        print(f"❌ [PROXY_CHAT] 연결 에러")
        return create_chat_error_response(request.model, "Connection error")
    except Exception as e:
        print(f"❌ [PROXY_CHAT] 예외 발생: {str(e)}")
        print(f"   [PROXY_CHAT] 상세: {traceback.format_exc()}")
        return create_chat_error_response(request.model, f"Proxy error: {str(e)}")

async def proxy_generate_to_ollama(request: OllamaGenerateRequest):
    """생성을 LLM 서버로 프록시"""
    print(f"🔄 [PROXY_GEN] LLM 서버로 프록시 시작")
    print(f"   [PROXY_GEN] 대상 URL: {chat_handler.llm_server_url}/api/generate")
    print(f"   [PROXY_GEN] 요청 모델: {request.model}")
    
    try:
        request_data = request.dict()
        print(f"   [PROXY_GEN] 요청 데이터 크기: {len(json.dumps(request_data))} bytes")
        
        print(f"   [PROXY_GEN] HTTP 요청 전송 중...")
        response = requests.post(
            f"{chat_handler.llm_server_url}/api/generate",
            json=request_data,
            timeout=120
        )
        
        print(f"   [PROXY_GEN] HTTP 응답 수신: {response.status_code}")
        print(f"   [PROXY_GEN] 응답 크기: {len(response.content)} bytes")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"   [PROXY_GEN] JSON 파싱 성공")
            print(f"   [PROXY_GEN] 응답 필드: {list(response_data.keys())}")
            print(f"✅ [PROXY_GEN] 프록시 성공")
            return response_data
        else:
            print(f"❌ [PROXY_GEN] HTTP 에러: {response.status_code}")
            print(f"   [PROXY_GEN] 에러 내용: {response.text[:200]}")
            return create_generate_error_response(request.model, f"LLM server error: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"❌ [PROXY_GEN] 타임아웃 에러")
        return create_generate_error_response(request.model, "Request timeout")
    except requests.exceptions.ConnectionError:
        print(f"❌ [PROXY_GEN] 연결 에러")
        return create_generate_error_response(request.model, "Connection error")
    except Exception as e:
        print(f"❌ [PROXY_GEN] 예외 발생: {str(e)}")
        print(f"   [PROXY_GEN] 상세: {traceback.format_exc()}")
        return create_generate_error_response(request.model, f"Proxy error: {str(e)}")

@router.get("/api/ps")
async def list_running_models():
    """
    실행 중인 모델 목록 API (Ollama 형식)
    GET /api/ps
    """
    print(f"🔄 [PS] 실행 중인 모델 목록 요청")
    
    try:
        # 환경변수에서 모델 정보 가져오기
        import os
        rag_model_name = os.environ.get("RAG_MODEL_NAME", "rag-cheeseade:latest")
        llm_model_name = os.environ.get("LLM_MODEL_NAME", "gemma3:27b-it-q4_K_M")
        
        print(f"   [PS] RAG 모델: {rag_model_name}")
        print(f"   [PS] LLM 모델: {llm_model_name}")
        
        # 채팅 핸들러 상태 확인
        handler_loaded = chat_handler is not None
        print(f"   [PS] 채팅 핸들러 로드됨: {handler_loaded}")
        
        # 현재 시간 계산
        current_time = time.time()
        load_time = current_time - 3600  # 1시간 전에 로드되었다고 가정
        
        models = []
        
        # RAG 모델이 로드된 것으로 표시 (항상 로드된 상태)
        if handler_loaded:
            models.append({
                "name": rag_model_name,
                "model": rag_model_name,
                "size": 2500000000,
                "digest": f"sha256:{abs(hash(rag_model_name)):064x}",
                "details": {
                    "parent_model": "",
                    "format": "gguf",
                    "family": "rag-enhanced",
                    "families": ["rag-enhanced"],
                    "parameter_size": "RAG+27B",
                    "quantization_level": "Q4_K_M"
                },
                "expires_at": "2024-12-01T23:59:59.999999999Z",  # 만료 시간
                "size_vram": 2147483648  # VRAM 사용량 (2GB)
            })
            print(f"   [PS] RAG 모델 활성 상태로 추가")
        
        # LLM 서버 상태 확인
        try:
            print(f"   [PS] LLM 서버 상태 확인 중...")
            llm_ps_response = requests.get(
                f"{chat_handler.llm_server_url}/api/ps",
                timeout=5
            )
            print(f"   [PS] LLM 서버 응답: {llm_ps_response.status_code}")
            
            if llm_ps_response.status_code == 200:
                llm_data = llm_ps_response.json()
                print(f"   [PS] LLM 서버 실행 모델: {len(llm_data.get('models', []))}개")
                
                # LLM 서버의 실행 중인 모델들 추가
                for llm_model in llm_data.get('models', []):
                    models.append(llm_model)
                    print(f"   [PS] LLM 모델 추가: {llm_model.get('name', 'unknown')}")
            else:
                print(f"   [PS] LLM 서버 응답 오류: {llm_ps_response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"   [PS] LLM 서버 연결 실패: {str(e)}")
            # LLM 서버 연결 실패해도 기본 모델은 표시
        except Exception as e:
            print(f"   [PS] LLM 서버 확인 중 오류: {str(e)}")
        
        # Ollama /api/ps 표준 응답 형식
        response = {
            "models": models
        }
        
        print(f"✅ [PS] 실행 중인 모델 목록 응답: {len(models)}개 모델")
        for i, model in enumerate(models):
            model_name = model.get('name', 'unknown')
            model_size = model.get('size_vram', model.get('size', 0))
            print(f"   [PS] 모델 {i+1}: {model_name} (VRAM: {model_size//1024//1024}MB)")
        
        return response
        
    except Exception as e:
        print(f"❌ [PS] 실행 모델 목록 오류: {str(e)}")
        print(f"   [PS] 상세: {traceback.format_exc()}")
        
        # 에러 시에도 Ollama 형식 유지
        return {
            "models": []
        }

# ================================
# 헬스체크 및 모델 정보 엔드포인트
# ================================

@router.get("/health")
async def health_check():
    """
    헬스체크 API
    GET /health
    """
    print(f"🏥 [HEALTH] 헬스체크 요청")
    
    try:
        # 기본 상태 확인
        print(f"   [HEALTH] 채팅 핸들러 상태 확인...")
        handler_status = "initialized" if chat_handler else "not_initialized"
        print(f"   [HEALTH] 핸들러 상태: {handler_status}")
        
        # 환경변수 확인
        import os
        rag_model = os.environ.get("RAG_MODEL_NAME", "unknown")
        llm_model = os.environ.get("LLM_MODEL_NAME", "unknown")
        print(f"   [HEALTH] RAG 모델: {rag_model}")
        print(f"   [HEALTH] LLM 모델: {llm_model}")
        
        health_data = {
            "status": "healthy" if chat_handler else "degraded",
            "service": "cheeseade-rag-server",
            "timestamp": int(time.time()),
            "chat_handler": handler_status,
            "models": {
                "rag_model": rag_model,
                "llm_model": llm_model
            }
        }
        
        print(f"✅ [HEALTH] 헬스체크 응답 생성 완료")
        return health_data
        
    except Exception as e:
        print(f"❌ [HEALTH] 헬스체크 오류: {str(e)}")
        print(f"   [HEALTH] 상세: {traceback.format_exc()}")
        
        return {
            "status": "unhealthy",
            "service": "cheeseade-rag-server", 
            "timestamp": int(time.time()),
            "error": str(e)
        }

@router.get("/api/tags")
async def list_local_models():
    """
    로컬 모델 목록 API (Ollama 형식)
    GET /api/tags
    """
    print(f"📋 [TAGS] Ollama 모델 목록 요청")
    
    try:
        # 환경변수에서 모델 정보 가져오기
        import os
        rag_model_name = os.environ.get("RAG_MODEL_NAME", "rag-cheeseade:latest")
        llm_model_name = os.environ.get("LLM_MODEL_NAME", "gemma3:27b-it-q4_K_M")
        
        print(f"   [TAGS] RAG 모델: {rag_model_name}")
        print(f"   [TAGS] LLM 모델: {llm_model_name}")
        
        # Ollama 정확한 /api/tags 응답 형식
        models = [
            {
                "name": rag_model_name,
                "model": rag_model_name,
                "modified_at": "2024-12-01T00:00:00.000000000Z",
                "size": 2500000000,
                "digest": f"sha256:{abs(hash(rag_model_name)):064x}",
                "details": {
                    "parent_model": "",
                    "format": "gguf",
                    "family": "rag-enhanced",
                    "families": ["rag-enhanced"],
                    "parameter_size": "RAG+27B",
                    "quantization_level": "Q4_K_M"
                }
            },
            {
                "name": llm_model_name,
                "model": llm_model_name,
                "modified_at": "2024-12-01T00:00:00.000000000Z",
                "size": 15000000000,
                "digest": f"sha256:{abs(hash(llm_model_name)):064x}",
                "details": {
                    "parent_model": "",
                    "format": "gguf", 
                    "family": "gemma3",
                    "families": ["gemma3"],
                    "parameter_size": "27B",
                    "quantization_level": "Q4_K_M"
                }
            }
        ]
        
        # Ollama 표준 응답 형식
        response = {
            "models": models
        }
        
        print(f"✅ [TAGS] Ollama 모델 목록 응답 생성: {len(models)}개 모델")
        for i, model in enumerate(models):
            print(f"   [TAGS] 모델 {i+1}: {model['name']} ({model['details']['parameter_size']})")
        
        return response
        
    except Exception as e:
        print(f"❌ [TAGS] 모델 목록 오류: {str(e)}")
        print(f"   [TAGS] 상세: {traceback.format_exc()}")
        
        # 에러 시에도 Ollama 형식 유지
        return {
            "models": []
        }

# ================================
# 기본 엔드포인트 (최소한)
# ================================

@router.get("/")
async def root():
    """루트 엔드포인트"""
    print(f"🏠 [ROOT] 루트 엔드포인트 호출됨")
    return "Ollama is running"