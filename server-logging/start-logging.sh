#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 CHEESEADE RAG 로깅 시스템 시작"
echo "========================================"

# 환경변수 확인
if [ -f "../.env.global" ]; then
    source ../.env.global
    echo "✅ 전역 환경변수 로드됨"
else
    echo -e "${RED}❌ .env.global 파일이 없습니다.${NC}"
    exit 1
fi

# 필요한 디렉토리 생성
echo "📁 필요한 디렉토리 생성..."
mkdir -p postgres-data pgadmin-data logs

# 기존 컨테이너 중지
echo "🛑 기존 로깅 컨테이너 중지..."
docker compose down 2>/dev/null || true

# PostgreSQL 초기화 (선택사항)
if [ "$1" = "--reset-db" ]; then
    echo -e "${YELLOW}⚠️ 데이터베이스를 초기화합니다...${NC}"
    read -p "모든 로깅 데이터가 삭제됩니다. 계속하시겠습니까? (y/N): " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        rm -rf postgres-data/*
        echo "✅ 데이터베이스 초기화 완료"
    else
        echo "데이터베이스 초기화 취소"
        exit 0
    fi
fi

# Docker 빌드 및 시작
echo "🔧 Docker 컨테이너 빌드 및 시작..."
if docker compose up -d --build; then
    echo -e "${GREEN}✅ 로깅 시스템 시작 완료!${NC}"
else
    echo -e "${RED}❌ 로깅 시스템 시작 실패${NC}"
    exit 1
fi

# 헬스체크 대기
echo "⏳ 서비스 준비 대기 중..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    echo -n "   시도 $attempt/$max_attempts: "
    
    # PostgreSQL 헬스체크
    if docker exec cheeseade-logging-db pg_isready -U raguser -d rag_logging >/dev/null 2>&1; then
        echo -n "DB(✅) "
    else
        echo -e "${YELLOW}DB 준비 중...${NC}"
        sleep 3
        attempt=$((attempt + 1))
        continue
    fi
    
    # API 서버 헬스체크
    if curl -s --connect-timeout 3 "http://${LOGGING_SERVER_IP}:${LOGGING_PORT}/health" >/dev/null 2>&1; then
        echo -e "${GREEN}API(✅)${NC}"
        echo -e "${GREEN}✅ 모든 서비스 준비 완료!${NC}"
        break
    else
        echo -e "${YELLOW}API 준비 중...${NC}"
    fi
    
    sleep 3
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo -e "${RED}❌ 서비스 준비 타임아웃${NC}"
    echo "로그를 확인하세요: docker compose logs"
    exit 1
fi

# 서비스 상태 확인
echo ""
echo "📊 서비스 상태:"
echo "----------------------------------------"
docker compose ps

echo ""
echo "🌐 접속 정보:"
echo "----------------------------------------"
echo "📊 로깅 API:     http://${LOGGING_SERVER_IP}:${LOGGING_PORT}"
echo "📖 API 문서:     http://${LOGGING_SERVER_IP}:${LOGGING_PORT}/docs"
echo "🗄️ pgAdmin:      http://${LOGGING_SERVER_IP}:8080 (선택적)"
echo "   ├─ 이메일:    admin@cheeseade.com"
echo "   └─ 비밀번호:  admin123"

echo ""
echo "📋 데이터베이스 연결 정보 (pgAdmin용):"
echo "   호스트:      postgres"
echo "   포트:        5432"
echo "   사용자:      raguser"
echo "   비밀번호:    ragpass123"
echo "   데이터베이스: rag_logging"

echo ""
echo "🧪 API 테스트:"
echo "----------------------------------------"
echo "# 헬스체크"
echo "curl http://${LOGGING_SERVER_IP}:${LOGGING_PORT}/health"
echo ""
echo "# 통계 조회"
echo "curl http://${LOGGING_SERVER_IP}:${LOGGING_PORT}/api/stats"
echo ""
echo "# 최근 대화 조회"
echo "curl http://${LOGGING_SERVER_IP}:${LOGGING_PORT}/api/conversations?limit=10"

echo ""
echo "🔧 관리 명령어:"
echo "----------------------------------------"
echo "로그 확인:      docker compose logs -f"
echo "DB 백업:        docker exec cheeseade-logging-db pg_dump -U raguser rag_logging > backup.sql"
echo "서비스 중지:    docker compose down"
echo "DB 초기화:      ./start-logging.sh --reset-db"
echo "pgAdmin 시작:   docker compose --profile admin up -d"

echo ""
echo -e "${GREEN}🎉 RAG 로깅 시스템이 성공적으로 시작되었습니다!${NC}"
echo ""