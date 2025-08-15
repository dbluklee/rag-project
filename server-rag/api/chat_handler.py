"""
RAG 채팅 처리 핸들러 (단순화)
"""
import asyncio
from fastapi import HTTPException

class ChatHandler:
    """RAG 채팅 처리"""
    
    def __init__(self, rag_chain, retriever, rag_model_name: str, llm_server_url: str):
        self.rag_chain = rag_chain
        self.retriever = retriever
        self.rag_model_name = rag_model_name
        self.llm_server_url = llm_server_url
        
        print(f"💬 [CHAT_HANDLER] ChatHandler 초기화 완료")
        print(f"   [CHAT_HANDLER] RAG 모델: {rag_model_name}")
        print(f"   [CHAT_HANDLER] LLM 서버: {llm_server_url}")
    
    async def process_with_rag(self, question: str) -> str:
        """RAG 파이프라인으로 질문 처리"""
        print(f"🔍 [RAG_PROCESS] RAG 처리 시작: {question[:50]}...")
        
        try:
            print(f"   [RAG_PROCESS] rag_chain.invoke 호출 중...")
            # 동기 함수를 비동기로 실행
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.rag_chain.invoke, question
            )
            print(f"   [RAG_PROCESS] 응답 생성 완료: {len(response)} 문자")
            print(f"   [RAG_PROCESS] 응답 미리보기: {response[:100]}...")
            return response
            
        except Exception as e:
            print(f"❌ [RAG_PROCESS] RAG 처리 오류: {e}")
            raise HTTPException(status_code=500, detail=f"RAG 처리 실패: {str(e)}")