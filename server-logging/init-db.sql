-- RAG 로깅 데이터베이스 초기화 스크립트 (간소화 버전)

-- 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- RAG 질문 이력 테이블
CREATE TABLE rag_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255),  -- 세션/대화 식별자
    user_question TEXT NOT NULL,  -- 사용자 질문
    contexts JSONB,  -- 검색된 컨텍스트들 (JSON 배열)
    rag_response TEXT,  -- RAG 서버 응답
    model_used VARCHAR(100),  -- 사용된 모델명
    response_time_ms INTEGER,  -- 응답 시간 (밀리초)
    question_language VARCHAR(10),  -- 질문 언어 (ko, en 등)
    response_language VARCHAR(10),  -- 응답 언어
    similarity_scores JSONB,  -- 컨텍스트별 유사도 점수
    metadata JSONB,  -- 추가 메타데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 컨텍스트 상세 정보 테이블 (정규화)
CREATE TABLE rag_contexts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES rag_conversations(id) ON DELETE CASCADE,
    context_order INTEGER NOT NULL,  -- 컨텍스트 순서
    content TEXT NOT NULL,  -- 컨텍스트 내용
    source_document VARCHAR(255),  -- 원본 문서명
    header1 VARCHAR(255),  -- 문서 헤더1
    header2 VARCHAR(255),  -- 문서 헤더2
    similarity_score FLOAT,  -- 유사도 점수
    chunk_metadata JSONB,  -- 청크 메타데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 사용자 세션 정보 테이블
CREATE TABLE user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_ip VARCHAR(45),  -- IPv6 지원
    user_agent TEXT,
    first_question_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_question_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    total_questions INTEGER DEFAULT 1,
    session_metadata JSONB
);

-- 기본 인덱스 생성 (성능 최적화)
CREATE INDEX idx_conversations_created_at ON rag_conversations(created_at);
CREATE INDEX idx_conversations_session_id ON rag_conversations(session_id);
CREATE INDEX idx_conversations_model ON rag_conversations(model_used);

CREATE INDEX idx_contexts_conversation_id ON rag_contexts(conversation_id);
CREATE INDEX idx_contexts_source ON rag_contexts(source_document);
CREATE INDEX idx_contexts_similarity ON rag_contexts(similarity_score);

CREATE INDEX idx_sessions_last_question ON user_sessions(last_question_at);

-- 트리거: updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$ language 'plpgsql';

CREATE TRIGGER update_conversations_updated_at 
    BEFORE UPDATE ON rag_conversations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 트리거: 세션 정보 자동 업데이트
CREATE OR REPLACE FUNCTION update_session_stats()
RETURNS TRIGGER AS $
BEGIN
    INSERT INTO user_sessions (session_id, last_question_at, total_questions)
    VALUES (NEW.session_id, NEW.created_at, 1)
    ON CONFLICT (session_id) DO UPDATE SET
        last_question_at = NEW.created_at,
        total_questions = user_sessions.total_questions + 1;
    RETURN NEW;
END;
$ language 'plpgsql';

CREATE TRIGGER update_session_on_question 
    AFTER INSERT ON rag_conversations 
    FOR EACH ROW EXECUTE FUNCTION update_session_stats();

-- 샘플 데이터 삽입 (테스트용)
INSERT INTO rag_conversations (
    session_id, 
    user_question, 
    contexts, 
    rag_response, 
    model_used, 
    response_time_ms,
    question_language,
    response_language,
    similarity_scores,
    metadata
) VALUES (
    'session_001',
    '갤럭시 S24의 카메라 기능은 어떤가요?',
    '[
        {
            "content": "갤럭시 S24는 200MP 메인 카메라를 탑재했습니다.",
            "source": "galaxy_s24_specs.md",
            "header1": "Galaxy S24",
            "header2": "카메라"
        }
    ]'::jsonb,
    '갤럭시 S24는 200MP 메인 카메라를 탑재하여 고화질 촬영이 가능합니다.',
    'rag-cheeseade:latest',
    1500,
    'ko',
    'ko',
    '[0.92]'::jsonb,
    '{"user_ip": "192.168.1.100", "user_agent": "Mozilla/5.0"}'::jsonb
);

-- 권한 설정
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO raguser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO raguser;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO raguser;

-- 설정 완료 로그
SELECT 'RAG 로깅 데이터베이스 초기화 완료!' as status;