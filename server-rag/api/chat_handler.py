"""
OpenWebUI 채팅 처리 모듈
"""
import uuid
import time
import json
import asyncio
import requests
from typing import Optional, AsyncGenerator
from fastapi import HTTPException

from .models import ChatRequest, ChatResponse, ChatResponseChoice, ChatResponseMessage

class ChatHandler:
    """채팅 요청 처리 핸들러"""
    
    def __init__(self, rag_chain, retriever, rag_model_name: str, llm_server_url: str):
        self.rag_chain = rag_chain
        self.retriever = retriever
        self.rag_model_name = rag_model_name
        self.llm_server_url = llm_server_url
        
        print(f"💬 ChatHandler 초기화")
        print(f"   RAG 모델: {rag_model_name}")
        print(f"   LLM 서버: {llm_server_url}")
    
    async def process_with_rag(self, question: str) -> str:
        """RAG 파이프라인으로 질문 처리"""
        print(f"🔍 RAG 파이프라인 처리: {question}")
        
        try:
            # 동기 함수를 비동기로 실행
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.rag_chain.invoke, question
            )
            print(f"✅ RAG 응답 생성: {len(response)} 문자")
            return response
        except Exception as e:
            print(f"❌ RAG 처리 오류: {e}")
            raise HTTPException(status_code=500, detail=f"RAG 처리 실패: {str(e)}")
    
    async def stream_rag_response(self, question: str, model_name: str) -> AsyncGenerator[str, None]:
        """스트리밍 RAG 응답 생성"""
        try:
            print(f"🌊 스트리밍 시작: {question}")

            # 동기 스트리밍을 먼저 체크 (더 일반적)
            if hasattr(self.rag_chain, 'stream'):
                for chunk in self.rag_chain.stream(question):
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
            elif hasattr(self.rag_chain, 'astream'):  
                async for chunk in self.rag_chain.astream(question):
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
            
            # 스트리밍 미지원시 청크로 분할
            else:
                response_content = await asyncio.get_event_loop().run_in_executor(
                    None, self.rag_chain.invoke, question
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
            # OpenWebUI 호환 에러 형식
            error_response = {
                "error": {
                    "message": str(e),
                    "type": "internal_server_error",
                    "code": "rag_error"
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"
            yield "data: [DONE]\n\n"
    
    async def proxy_to_llm(self, request: ChatRequest) -> dict:
        """일반 LLM으로 프록시 (논스트리밍)"""
        print(f"🔄 일반 LLM으로 프록시: {request.model}")
        
        # Ollama API로 요청 전달
        ollama_request = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "stream": False
        }
        
        try:
            proxy_response = requests.post(
                f"{self.llm_server_url}/v1/chat/completions",
                json=ollama_request,
                timeout=120
            )
            
            if proxy_response.status_code == 200:
                return proxy_response.json()
            else:
                raise HTTPException(
                    status_code=proxy_response.status_code,
                    detail=f"LLM server error: {proxy_response.text}"
                )
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 프록시 요청 오류: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to connect to LLM server: {str(e)}"
            )
    
    async def proxy_stream_to_llm(self, request: ChatRequest) -> AsyncGenerator[bytes, None]:
        """일반 LLM으로 스트리밍 프록시"""
        print(f"🌊 일반 LLM 스트리밍 프록시: {request.model}")
        
        # Ollama API로 요청 전달
        ollama_request = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "stream": True
        }
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.llm_server_url}/v1/chat/completions",
                    json=ollama_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    async for chunk in response.content.iter_chunked(1024):
                        yield chunk
        except Exception as e:
            print(f"❌ 프록시 스트림 오류: {e}")
            error_chunk = {
                "error": {
                    "message": f"Proxy error: {str(e)}",
                    "type": "proxy_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n".encode()
    
    async def handle_chat_request(self, request: ChatRequest) -> dict:
        """채팅 요청 처리 (메인 핸들러)"""
        user_question = request.messages[-1].content
        print(f"💬 채팅 요청 처리: {request.model}")
        print(f"   질문: {user_question}")
        
        # 모델이 RAG 모델인지 확인
        if request.model == self.rag_model_name:
            # RAG 사용
            response_content = await self.process_with_rag(user_question)
            
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
            ).dict()
        else:
            # 일반 LLM 사용 (프록시)
            return await self.proxy_to_llm(request)
    
    def test_retrieval(self, question: str) -> dict:
        """검색 기능 테스트"""
        print(f"🧪 검색 테스트: {question}")
        
        try:
            docs = self.retriever.invoke(question)
            
            response_docs = []
            for doc in docs:
                doc_data = {
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata,
                    "score": doc.metadata.get("score", 0.0)
                }
                response_docs.append(doc_data)
            
            print(f"   검색 결과: {len(docs)}개 문서")
            
            return {
                "question": question,
                "retrieved_docs": len(docs),
                "docs": response_docs
            }
            
        except Exception as e:
            print(f"❌ 검색 테스트 오류: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"검색 테스트 실패: {str(e)}"
            )