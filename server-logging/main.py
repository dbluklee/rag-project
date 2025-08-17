"""
CHEESEADE RAG 로깅 API 서버 (SQLite 버전)
"""
import os
import uuid
import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# ================================
# 데이터 모델
# ================================

class RAGContext(BaseModel):
    content: str
    source_document: Optional[str] = None
    header1: Optional[str] = None
    header2: Optional[str] = None
    similarity_score: Optional[float] = None
    chunk_metadata: Optional[Dict[str, Any]] = None

class RAGLogRequest(BaseModel):
    session_id: str
    user_question: str
    contexts: List[RAGContext]
    rag_response: str
    model_used: str
    response_time_ms: int
    question_language: Optional[str] = "ko"
    response_language: Optional[str] = "ko"
    metadata: Optional[Dict[str, Any]] = None

class ConversationResponse(BaseModel):
    id: str
    session_id: str
    user_question: str
    rag_response: str
    model_used: str
    response_time_ms: int
    contexts_count: int
    created_at: str

# ================================
# SQLite 데이터베이스 관리자
# ================================

class SQLiteManager:
    def __init__(self, db_path: str = "/app/data/rag_logging.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 데이터베이스 위치: {self.db_path}")
        logger.info(f"📁 데이터 디렉토리 존재: {self.db_path.parent.exists()}")
        logger.info(f"📁 데이터 디렉토리 쓰기 가능: {os.access(self.db_path.parent, os.W_OK)}")
    
    async def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        async with aiosqlite.connect(self.db_path) as db:
            # 대화 기록 테이블
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rag_conversations (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_question TEXT NOT NULL,
                    contexts TEXT,  -- JSON 형태로 저장
                    rag_response TEXT,
                    model_used TEXT,
                    response_time_ms INTEGER,
                    question_language TEXT DEFAULT 'ko',
                    response_language TEXT DEFAULT 'ko',
                    similarity_scores TEXT,  -- JSON 배열
                    metadata TEXT,  -- JSON 형태로 저장
                    contexts_count INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 컨텍스트 상세 테이블
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rag_contexts (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    context_order INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source_document TEXT,
                    header1 TEXT,
                    header2 TEXT,
                    similarity_score REAL,
                    chunk_metadata TEXT,  -- JSON 형태
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES rag_conversations (id)
                )
            """)
            
            # 세션 정보 테이블
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_ip TEXT,
                    user_agent TEXT,
                    first_question_at TEXT NOT NULL,
                    last_question_at TEXT NOT NULL,
                    total_questions INTEGER DEFAULT 1,
                    session_metadata TEXT  -- JSON 형태
                )
            """)
            
            # 인덱스 생성
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON rag_conversations(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON rag_conversations(session_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_model ON rag_conversations(model_used)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_contexts_conversation_id ON rag_contexts(conversation_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_question ON user_sessions(last_question_at)")
            
            await db.commit()
            logger.info("✅ SQLite 데이터베이스 초기화 완료")
    
    async def save_conversation(self, log_data: RAGLogRequest) -> str:
        """대화 로그를 데이터베이스에 저장"""
        conversation_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            # 메인 대화 기록 저장
            contexts_json = json.dumps([ctx.dict() for ctx in log_data.contexts], ensure_ascii=False)
            similarity_scores = json.dumps([ctx.similarity_score for ctx in log_data.contexts if ctx.similarity_score is not None])
            metadata_json = json.dumps(log_data.metadata, ensure_ascii=False) if log_data.metadata else None
            
            await db.execute("""
                INSERT INTO rag_conversations (
                    id, session_id, user_question, contexts, rag_response,
                    model_used, response_time_ms, question_language, 
                    response_language, similarity_scores, metadata,
                    contexts_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id, log_data.session_id, log_data.user_question,
                contexts_json, log_data.rag_response, log_data.model_used,
                log_data.response_time_ms, log_data.question_language,
                log_data.response_language, similarity_scores, metadata_json,
                len(log_data.contexts), current_time, current_time
            ))
            
            # 개별 컨텍스트 저장
            for i, context in enumerate(log_data.contexts):
                context_id = str(uuid.uuid4())
                chunk_metadata_json = json.dumps(context.chunk_metadata, ensure_ascii=False) if context.chunk_metadata else None
                
                await db.execute("""
                    INSERT INTO rag_contexts (
                        id, conversation_id, context_order, content, source_document,
                        header1, header2, similarity_score, chunk_metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    context_id, conversation_id, i, context.content, context.source_document,
                    context.header1, context.header2, context.similarity_score,
                    chunk_metadata_json, current_time
                ))
            
            # 세션 정보 업데이트
            await db.execute("""
                INSERT INTO user_sessions (session_id, first_question_at, last_question_at, total_questions)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_question_at = ?,
                    total_questions = total_questions + 1
            """, (log_data.session_id, current_time, current_time, current_time))
            
            await db.commit()
            logger.info(f"✅ 대화 로그 저장 완료: {conversation_id}")
            return conversation_id
    
    async def get_conversations(self, limit: int = 100, session_id: Optional[str] = None) -> List[ConversationResponse]:
        """대화 기록 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            if session_id:
                query = """
                    SELECT id, session_id, user_question, rag_response, model_used,
                           response_time_ms, contexts_count, created_at
                    FROM rag_conversations
                    WHERE session_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """
                params = (session_id, limit)
            else:
                query = """
                    SELECT id, session_id, user_question, rag_response, model_used,
                           response_time_ms, contexts_count, created_at
                    FROM rag_conversations
                    ORDER BY created_at DESC LIMIT ?
                """
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                return [
                    ConversationResponse(
                        id=row[0],
                        session_id=row[1],
                        user_question=row[2],
                        rag_response=row[3],
                        model_used=row[4],
                        response_time_ms=row[5],
                        contexts_count=row[6] or 0,
                        created_at=row[7]
                    ) for row in rows
                ]
    
    async def get_conversation_detail(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """특정 대화 상세 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            # 메인 대화 정보
            async with db.execute("SELECT * FROM rag_conversations WHERE id = ?", (conversation_id,)) as cursor:
                conversation = await cursor.fetchone()
                if not conversation:
                    return None
            
            # 컨텍스트 정보
            async with db.execute("""
                SELECT * FROM rag_contexts 
                WHERE conversation_id = ? 
                ORDER BY context_order
            """, (conversation_id,)) as cursor:
                contexts = await cursor.fetchall()
            
            # 결과 구성
            columns = [description[0] for description in cursor.description]
            conversation_dict = dict(zip(columns, conversation))
            context_list = [dict(zip(columns, ctx)) for ctx in contexts]
            
            return {
                "conversation": conversation_dict,
                "contexts": context_list
            }
    
    async def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """통계 정보 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            # 기간 계산
            cutoff_date = datetime.now(timezone.utc).replace(day=datetime.now().day - days)
            cutoff_str = cutoff_date.isoformat()
            
            # 총 대화 수
            async with db.execute(
                "SELECT COUNT(*) FROM rag_conversations WHERE created_at >= ?", 
                (cutoff_str,)
            ) as cursor:
                total_conversations = (await cursor.fetchone())[0]
            
            # 고유 세션 수
            async with db.execute(
                "SELECT COUNT(DISTINCT session_id) FROM rag_conversations WHERE created_at >= ?",
                (cutoff_str,)
            ) as cursor:
                unique_sessions = (await cursor.fetchone())[0]
            
            # 평균 응답 시간
            async with db.execute(
                "SELECT AVG(response_time_ms) FROM rag_conversations WHERE created_at >= ?",
                (cutoff_str,)
            ) as cursor:
                avg_response_time = (await cursor.fetchone())[0] or 0.0
            
            # 인기 모델
            async with db.execute("""
                SELECT model_used, COUNT(*) as count, AVG(response_time_ms) as avg_time
                FROM rag_conversations 
                WHERE created_at >= ?
                GROUP BY model_used 
                ORDER BY count DESC
            """, (cutoff_str,)) as cursor:
                popular_models = await cursor.fetchall()
            
            return {
                "total_conversations": total_conversations,
                "unique_sessions": unique_sessions,
                "avg_response_time": round(avg_response_time, 2),
                "period_days": days,
                "popular_models": [
                    {
                        "model": row[0],
                        "count": row[1],
                        "avg_time": round(row[2], 2) if row[2] else 0.0
                    } for row in popular_models
                ]
            }
    
    async def search_conversations(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """대화 검색"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT id, session_id, user_question, rag_response, 
                       model_used, created_at
                FROM rag_conversations
                WHERE user_question LIKE ? OR rag_response LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit)) as cursor:
                rows = await cursor.fetchall()
                
                return [
                    {
                        "id": row[0],
                        "session_id": row[1],
                        "user_question": row[2],
                        "rag_response": row[3],
                        "model_used": row[4],
                        "created_at": row[5]
                    } for row in rows
                ]

# ================================
# FastAPI 앱 설정
# ================================

# SQLite 관리자 초기화
db_manager = SQLiteManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    await db_manager.init_database()
    logger.info("🚀 RAG 로깅 API 서버 시작 (SQLite)")
    yield
    # 종료 시
    logger.info("🛑 RAG 로깅 API 서버 종료")

app = FastAPI(
    title="CHEESEADE RAG Logging API",
    description="RAG 질문/답변 이력 로깅 서비스 (SQLite)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ================================
# API 엔드포인트
# ================================

@app.get("/health")
async def health_check():
    db_size = db_manager.db_path.stat().st_size if db_manager.db_path.exists() else 0
    
    # 간단한 DB 연결 테스트
    try:
        async with aiosqlite.connect(db_manager.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM rag_conversations") as cursor:
                total_conversations = (await cursor.fetchone())[0]
        db_status = "connected"
    except Exception as e:
        total_conversations = 0
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "rag-logging-api",
        "storage": "sqlite",
        "database_file": str(db_manager.db_path),
        "database_size_bytes": db_size,
        "total_conversations": total_conversations,
        "database_status": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/log")
async def log_rag_conversation(log_data: RAGLogRequest):
    try:
        conversation_id = await db_manager.save_conversation(log_data)
        
        logger.info(f"📝 로그 저장: {log_data.session_id} - {log_data.user_question[:50]}...")
        
        return {
            "status": "success",
            "conversation_id": conversation_id,
            "message": "로그가 SQLite에 성공적으로 저장되었습니다."
        }
    except Exception as e:
        logger.error(f"로그 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"로그 저장 실패: {str(e)}")

@app.get("/api/conversations", response_model=List[ConversationResponse])
async def get_conversations(limit: int = 100, session_id: Optional[str] = None):
    try:
        conversations = await db_manager.get_conversations(limit=limit, session_id=session_id)
        return conversations
    except Exception as e:
        logger.error(f"대화 기록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")

@app.get("/api/conversations/{conversation_id}")
async def get_conversation_detail(conversation_id: str):
    try:
        conversation = await db_manager.get_conversation_detail(conversation_id)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
        
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"대화 상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")

@app.get("/api/stats")
async def get_statistics(days: int = 7):
    try:
        stats = await db_manager.get_stats(days=days)
        return stats
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@app.get("/api/search")
async def search_conversations(q: str, limit: int = 50):
    try:
        results = await db_manager.search_conversations(q, limit)
        return results
    except Exception as e:
        logger.error(f"검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")

@app.get("/")
async def root():
    try:
        stats = await db_manager.get_stats(7)
        db_size = db_manager.db_path.stat().st_size if db_manager.db_path.exists() else 0
        
        return {
            "service": "CHEESEADE RAG Logging API",
            "version": "1.0.0",
            "status": "running",
            "storage_type": "sqlite",
            "database_file": str(db_manager.db_path),
            "database_size_bytes": db_size,
            "database_size_mb": round(db_size / 1024 / 1024, 2),
            "endpoints": ["/api/log", "/api/conversations", "/api/stats", "/api/search", "/health"],
            "features": [
                "SQLite 데이터베이스",
                "호스트 볼륨 저장",
                "SQL 쿼리 지원",
                "관계형 데이터 구조",
                "트랜잭션 안전성"
            ],
            "current_stats": stats
        }
    except Exception as e:
        return {
            "service": "CHEESEADE RAG Logging API",
            "version": "1.0.0",
            "status": "running",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000, log_level="info")