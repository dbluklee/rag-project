#!/bin/bash
echo "🚀 치즈에이드 RAG 시스템 배포 시작"

# 환경변수 로드
if [ -f ".env.global" ]; then
    source .env.global
    echo "✅ 전역 환경변수 로드됨"
else
    echo "⚠️ .env.global 파일이 없습니다."
    exit 1
fi

export WEBUI_SERVER_URL="http://${WEBUI_SERVER_IP}:${WEBUI_PORT}"
export RAG_SERVER_URL="http://${RAG_SERVER_IP}:${RAG_PORT}"
export MILVUS_SERVER_URL="http://${MILVUS_SERVER_IP}:${MILVUS_PORT}"
export LLM_SERVER_URL="http://${LLM_SERVER_IP}:${LLM_PORT}"


echo "📁 필요한 디렉토리 생성..."

# 각 서버별 데이터 디렉토리 생성 (로그 등)
# mkdir -p server-webui/data
mkdir -p server-rag/logs  
# mkdir -p server-milvus/volumes/{milvus,etcd,minio}
# mkdir -p server-llm/models
mkdir -p server-llm/logs



# docs/ 폴더 내용 확인
DOC_COUNT=$(find server-rag/docs -type f 2>/dev/null | wc -l)
if [ "$DOC_COUNT" -eq 0 ]; then
    echo ""
    echo "❌ FATAL: docs/ 폴더에 파일이 없습니다!"
    echo ""
    echo "🔧 해결 방법:"
    echo "   RAG를 위한 문서들을 server-rag/docs/ 폴더에 추가하세요"
    echo ""
    exit 1
fi

echo "✅ RAG를 위한 $DOC_COUNT 개의 문서 파일 확인됨"

# 배포 순서 (의존성 고려)
echo ""
echo "1️⃣ Milvus Server 시작..."
cd server-milvus && docker compose up -d && cd ..
sleep 5

echo "2️⃣ LLM Server 시작..."
cd server-llm && docker compose up -d && cd ..
sleep 5

echo "3️⃣ RAG Server 시작..."
cd server-rag && docker compose up -d && cd ..
sleep 5

echo "4️⃣ WebUI Server 시작..."
cd server-webui && docker compose up -d && cd ..

echo ""
echo "✅ 모든 서버 시작 완료!"
echo ""
echo "📊 다음 단계:"
echo "   1. 상태 확인: ./health-check.sh"
echo "   2. 브라우저에서 접속: http://${WEBUI_SERVER_IP}:${WEBUI_PORT}"
echo "   3. 모델 선택:"
echo "      - rag-cheeseade:latest (CHEESEADE RAG를 활용한 전문 상담)"
echo "      - gemma3:27b-it-q4_K_M (일반 대화)"
echo ""

