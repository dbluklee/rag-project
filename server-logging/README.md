# CHEESEADE RAG 시스템 with 로깅

RAG (Retrieval-Augmented Generation) 기반 AI 상담 시스템과 질문/답변 이력 로깅 시스템

## 📋 시스템 구성

### 핵심 서비스
- **WebUI**: 사용자 인터페이스 (Open WebUI)
- **RAG Server**: 문서 검색 및 AI 응답 생성
- **LLM Server**: 언어 모델 추론 (Ollama)
- **Milvus**: 벡터 데이터베이스
- **Logging Server**: 질문/답변 이력 로깅 (PostgreSQL + FastAPI)

### 시스템 아키텍처
```
사용자 → WebUI → RAG Server → LLM Server
                      ↓           ↑
                 Milvus DB   Logging DB
```

## 🚀 빠른 시작

### 1. 시스템 배포
```bash
# 전체 시스템 배포 (로깅 포함)
./deploy.sh

# 상태 확인
./health-check.sh
```

### 2. 로깅만 별도 시작/중지
```bash
# 로깅 시스템만 시작
cd server-logging
./start-logging.sh

# 로깅 시스템만 중지
docker compose down
```

## 📊 로깅 시스템 기능

### 자동 수집 데이터
- ✅ 사용자 질문
- ✅ 검색된 컨텍스트들 (문서 조각)
- ✅ RAG 시스템 응답
- ✅ 응답 시간
- ✅ 사용된 모델명
- ✅ 세션 추적
- ✅ 유사도 점수
- ✅ 메타데이터 (IP, User-Agent 등)

### API 엔드포인트

#### 📝 로그 저장
```bash
POST /api/log
Content-Type: application/json

{
  "session_id": "session_123",
  "user_question": "갤럭시 S24 카메라 성능은?",
  "contexts": [
    {
      "content": "갤럭시 S24는 200MP 메인 카메라...",
      "source_document": "galaxy_s24.md",
      "header1": "Galaxy S24",
      "header2": "카메라",
      "similarity_score": 0.92
    }
  ],
  "rag_response": "갤럭시 S24는 뛰어난 카메라 성능을...",
  "model_used": "rag-cheeseade:latest",
  "response_time_ms": 1500
}
```

#### 📋 대화 조회
```bash
# 최근 대화 100개
GET /api/conversations?limit=100

# 특정 세션의 대화
GET /api/conversations?session_id=session_123

# 특정 대화 상세
GET /api/conversations/{conversation_id}
```

#### 📊 통계 정보
```bash
# 최근 7일 통계
GET /api/stats

# 최근 30일 통계
GET /api/stats?days=30
```

#### 🔍 검색
```bash
# 대화 내용 검색
GET /api/search?q=카메라&limit=20
```

#### 📤 데이터 내보내기
```bash
# JSON 형태로 내보내기
GET /api/export?format=json&days=30

# CSV 형태로 내보내기
GET /api/export?format=csv&days=30
```

## 🌐 접속 정보

### 서비스 URL
- **WebUI**: http://112.148.37.41:1885
- **RAG API**: http://112.148.37.41:1886
- **LLM API**: http://112.148.37.41:1884
- **로깅 API**: http://112.148.37.41:1889
- **Milvus Admin**: http://112.148.37.41:9001
- **pgAdmin**: http://112.148.37.41:8080 (선택적)

### API 문서
- **RAG API 문서**: http://112.148.37.41:1886/docs
- **로깅 API 문서**: http://112.148.37.41:1889/docs

## 🗄️ 데이터베이스 정보

### PostgreSQL 연결 정보
```
호스트: 112.148.37.41:5432
사용자: raguser
비밀번호: ragpass123
데이터베이스: rag_logging
```

### pgAdmin 로그인
```
이메일: admin@cheeseade.com
비밀번호: admin123
```

## 📈 사용 예시

### 1. 로깅 상태 확인
```bash
curl http://112.148.37.41:1889/health
```

### 2. 최근 통계 조회
```bash
curl http://112.148.37.41:1889/api/stats | jq
```

### 3. 질문 검색
```bash
curl "http://112.148.37.41:1889/api/search?q=갤럭시&limit=10" | jq
```

### 4. 데이터 백업
```bash
# PostgreSQL 백업
docker exec cheeseade-logging-db pg_dump -U raguser rag_logging > backup_$(date +%Y%m%d).sql

# JSON 형태로 내보내기
curl "http://112.148.37.41:1889/api/export?format=json&days=30" > conversations_backup.json
```

## 🔧 관리 명령어

### 로그 확인
```bash
# 모든 서비스 로그
./monitoring/logs-collect.sh

# 개별 서비스 로그
docker compose -f server-logging/docker-compose.yml logs -f
docker compose -f server-rag/docker-compose.yml logs -f
```

### 서비스 재시작
```bash
# 전체 시스템 재시작
./stop.sh && ./deploy.sh

# 로깅 서버만 재시작
cd server-logging
docker compose restart
```

### 데이터베이스 초기화
```bash
cd server-logging
./start-logging.sh --reset-db
```

## ⚙️ 환경 설정

### 로깅 활성화/비활성화
`.env.global` 파일에서 설정:
```bash
# 로깅 활성화
ENABLE_LOGGING=true

# 로깅 비활성화
ENABLE_LOGGING=false
```

### 로그 보존 기간
```bash
# 90일 후 자동 삭제
LOG_RETENTION_DAYS=90
```

## 📊 대시보드 쿼리 예시

### 일별 질문 수
```sql
SELECT DATE(created_at) as date, COUNT(*) as questions
FROM rag_conversations 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at) 
ORDER BY date DESC;
```

### 인기 키워드
```sql
SELECT word, COUNT(*) as frequency
FROM (
    SELECT unnest(string_to_array(regexp_replace(user_question, '[^\w\s가-힣]', '', 'g'), ' ')) as word
    FROM rag_conversations 
    WHERE created_at >= NOW() - INTERVAL '7 days'
) words
WHERE length(word) >= 2
GROUP BY word
HAVING COUNT(*) >= 3
ORDER BY frequency DESC
LIMIT 20;
```

### 평균 응답 시간
```sql
SELECT 
    model_used,
    AVG(response_time_ms) as avg_response_time,
    COUNT(*) as total_questions
FROM rag_conversations 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY model_used;
```

## 🚨 트러블슈팅

### 로깅 서버 연결 실패
```bash
# PostgreSQL 상태 확인
docker exec cheeseade-logging-db pg_isready -U raguser

# API 서버 로그 확인
docker logs cheeseade-logging-api

# 포트 확인
netstat -tlnp | grep 1889
```

### 데이터베이스 용량 관리
```bash
# 데이터베이스 크기 확인
docker exec cheeseade-logging-db psql -U raguser -d rag_logging -c "
SELECT pg_size_pretty(pg_database_size('rag_logging')) as db_size;
"

# 오래된 데이터 정리 (30일 이상)
docker exec cheeseade-logging-db psql -U raguser -d rag_logging -c "
DELETE FROM rag_conversations WHERE created_at < NOW() - INTERVAL '30 days';
"
```

### 성능 최적화
```bash
# 인덱스 재구축
docker exec cheeseade-logging-db psql -U raguser -d rag_logging -c "REINDEX DATABASE rag_logging;"

# 통계 업데이트
docker exec cheeseade-logging-db psql -U raguser -d rag_logging -c "ANALYZE;"
```

## 📝 참고사항

- 로깅은 RAG 서버에서 자동으로 수행됩니다
- 모든 API 호출이 백그라운드에서 기록됩니다
- 개인정보는 IP 주소 정도만 수집됩니다
- 데이터는 90일 후 자동 삭제됩니다
- pgAdmin을 통해 시각적으로 데이터를 확인할 수 있습니다

## 📞 지원

문제 발생 시:
1. `./health-check.sh` 실행
2. `./monitoring/logs-collect.sh` 로그 수집
3. 시스템 재시작: `./stop.sh && ./deploy.sh`