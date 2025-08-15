# server-rag/api/chat_handler.py
"""
RAG 채팅 처리 핸들러
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
        print(f"💬 ChatHandler 초기화 완료")
    
    async def process_with_rag(self, question: str) -> str:
        """RAG 파이프라인으로 질문 처리"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.rag_chain.invoke, question
            )
            return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RAG 처리 실패: {str(e)}")