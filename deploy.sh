#!/bin/bash
echo "🚀 치즈에이드 RAG 시스템 배포 시작"

# 환경변수 로드
if [ -f ".env.global" ]; then
    set -a
    source .env.global 
    set +a 
    echo "✅ 전역 환경변수 로드됨"
else
    echo "⚠️ .env.global 파일이 없습니다."
    exit 1
fi

export WEBUI_SERVER_URL="http://${WEBUI_SERVER_IP}:${WEBUI_PORT}"
export RAG_SERVER_URL="http://${RAG_SERVER_IP}:${RAG_PORT}"
export MILVUS_SERVER_URL="http://${MILVUS_SERVER_IP}:${MILVUS_PORT}"
export LLM_SERVER_URL="http://${LLM_SERVER_IP}:${LLM_PORT}"

echo "✅ 서버 URL 설정:"
echo "   WebUI: $WEBUI_SERVER_URL"
echo "   RAG: $RAG_SERVER_URL" 
echo "   LLM: $LLM_SERVER_URL"
echo "   Milvus: $MILVUS_SERVER_URL"

echo "📁 필요한 디렉토리 생성..."

# 각 서버별 데이터 디렉토리 생성 (로그 등)
mkdir -p server-rag/logs  
mkdir -p server-llm/logs



# docs/ 폴더 내용 확인
DOC_COUNT=$(find server-rag/docs -type f 2>/dev/null | wc -l)
if [ "$DOC_COUNT" -eq 0 ]; then
    echo "❌ docs/ 폴더에 파일이 없습니다!"
    echo "server-rag/docs/ 폴더에 문서를 추가하세요"
    exit 1
fi

echo "✅ RAG를 위한 $DOC_COUNT 개의 문서 파일 확인됨"

# 기존 컨테이너와 이미지 정리
echo ""
echo "🧹 기존 컨테이너 및 이미지 정리 중..."
docker compose -f server-milvus/docker-compose.yml down --remove-orphans 2>/dev/null || true
docker compose -f server-llm/docker-compose.yml down --remove-orphans 2>/dev/null || true
docker compose -f server-rag/docker-compose.yml down --remove-orphans 2>/dev/null || true
docker compose -f server-webui/docker-compose.yml down --remove-orphans 2>/dev/null || true

# 배포 순서 (의존성 고려) - 완전히 캐시 없는 재빌드
echo ""
echo "1️⃣ Milvus Server 시작 (캐시 없는 재빌드)..."
cd server-milvus 
docker compose up -d --build --force-recreate --no-cache --remove-orphans 
pwd
cd ..
pwd
sleep 5

echo "2️⃣ LLM Server 시작 (캐시 없는 재빌드)..."
cd server-llm 
docker compose up -d --build --force-recreate --no-cache --remove-orphans 
pwd
cd ..
pwd
sleep 5

echo "3️⃣ RAG Server 시작 (캐시 없는 재빌드)..."
cd server-rag 
docker compose up -d --build --force-recreate --no-cache --remove-orphans
cd ..
sleep 5

echo "4️⃣ WebUI Server 시작 (캐시 없는 재빌드)..."
cd server-webui 
docker compose up -d --build --force-recreate --no-cache --remove-orphans
cd ..


echo ""
echo "✅ 모든 서버 시작 완료!"
echo ""
echo "📊 다음 단계:"
echo "   1. 상태 확인: ./health-check.sh"
echo "   2. 브라우저에서 접속: http://${WEBUI_SERVER_IP}:${WEBUI_PORT}"
echo "   3. 모델 선택:"
echo "      - ${RAG_MODEL_NAME} (CHEESEADE RAG를 활용한 전문 상담)"
echo "      - ${LLM_MODEL_NAME} (일반 대화)"
echo ""

