#!/bin/bash
# OpenWebUI 특화 진단 및 해결

echo "🔍 OpenWebUI 특화 진단"
echo "========================================"

# 1. WebUI 컨테이너 상세 상태
echo "1️⃣ WebUI 컨테이너 상세 확인"
echo "----------------------------------------"
echo "🔍 WebUI 컨테이너 로그 (최근 20줄):"
docker logs --tail 20 cheeseade-webui | tail -10

echo ""
echo "🔍 WebUI 환경변수:"
docker exec cheeseade-webui env | grep -E "OLLAMA|WEBUI|AUTH" | head -5

echo ""

# 2. WebUI 내부에서 RAG 서버 접근 테스트
echo "2️⃣ WebUI → RAG 서버 연결 테스트"
echo "----------------------------------------"
echo "🧪 WebUI 컨테이너 내부에서 RAG 서버 접근:"

# WebUI 컨테이너 내부에서 RAG 서버에 접근해보기
rag_internal_test=$(docker exec cheeseade-webui curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://112.148.37.41:1886/health" 2>/dev/null)
echo "   내부 → RAG Health: $rag_internal_test"

rag_models_internal=$(docker exec cheeseade-webui curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://112.148.37.41:1886/api/models" 2>/dev/null)
echo "   내부 → RAG Models: $rag_models_internal"

echo ""

# 3. WebUI 설정 상태 확인
echo "3️⃣ WebUI 설정 확인"
echo "----------------------------------------"
echo "🔍 현재 WebUI .env 파일:"
if [ -f "server-webui/.env" ]; then
    cat server-webui/.env
else
    echo "   .env 파일 없음"
fi

echo ""

# 4. WebUI API 엔드포인트 직접 테스트
echo "4️⃣ WebUI API 엔드포인트 테스트"
echo "----------------------------------------"
echo "🧪 WebUI 메인 페이지:"
webui_main=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://112.148.37.41:1885/" 2>/dev/null)
echo "   메인 페이지: $webui_main"

echo ""
echo "🧪 WebUI API 테스트:"
webui_api=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://112.148.37.41:1885/api/v1/models" 2>/dev/null)
echo "   /api/v1/models: $webui_api"

echo ""

# 5. 네트워크 연결 문제 확인
echo "5️⃣ 네트워크 연결 문제 진단"
echo "----------------------------------------"
echo "🔍 Docker 네트워크 확인:"
docker network ls | grep -E "cheeseade|webui|rag"

echo ""
echo "🔍 컨테이너 간 네트워크 연결:"
# WebUI에서 RAG 컨테이너로의 내부 네트워크 연결 확인
rag_container_ip=$(docker inspect cheeseade-rag-server | grep '"IPAddress"' | tail -1 | cut -d'"' -f4)
echo "   RAG 컨테이너 IP: $rag_container_ip"

if [ -n "$rag_container_ip" ]; then
    webui_to_rag_internal=$(docker exec cheeseade-webui curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://$rag_container_ip:8000/health" 2>/dev/null)
    echo "   WebUI → RAG (내부 IP): $webui_to_rag_internal"
fi

echo ""

# 6. 실제 500 에러 재현 테스트
echo "6️⃣ 500 에러 재현 테스트"
echo "----------------------------------------"
echo "🧪 OpenWebUI가 사용하는 정확한 API 호출 재현:"

# OpenWebUI가 실제로 보내는 형식으로 테스트
webui_style_request=$(curl -s -X POST "http://112.148.37.41:1886/api/chat" \
  -H "Content-Type: application/json" \
  -H "User-Agent: OpenWebUI" \
  -d '{
    "model": "rag-cheeseade:latest",
    "messages": [{"role": "user", "content": "안녕하세요"}],
    "stream": false,
    "options": {}
  }' 2>/dev/null)

echo "OpenWebUI 스타일 요청 결과:"
if echo "$webui_style_request" | grep -q "500\|Internal Server Error"; then
    echo "   ❌ 500 에러 재현됨:"
    echo "$webui_style_request" | head -5
elif echo "$webui_style_request" | grep -q -E "choices|content|message"; then
    echo "   ✅ 정상 응답"
    echo "   응답: $(echo "$webui_style_request" | jq -r '.choices[0].message.content // .message.content // .content' 2>/dev/null | head -1)"
else
    echo "   ⚠️ 예상과 다른 응답:"
    echo "$webui_style_request" | head -5
fi

echo ""

# 7. WebUI 재시작 및 캐시 초기화
echo "7️⃣ 즉시 해결 방법"
echo "----------------------------------------"

echo "🔧 방법 1: WebUI 컨테이너만 재시작"
echo "   cd server-webui"
echo "   docker compose restart"

echo ""
echo "🔧 방법 2: WebUI 완전 초기화"
echo "   cd server-webui"
echo "   docker compose down"
echo "   mv data data_backup_$(date +%H%M%S)"
echo "   mkdir -p data config"
echo "   docker compose up -d"

echo ""
echo "🔧 방법 3: 브라우저 완전 초기화"
echo "   1. 시크릿/인코그니토 모드로 접속"
echo "   2. 또는 다른 브라우저 사용"
echo "   3. F12 → Application → Storage → Clear All"

echo ""
echo "🔧 방법 4: WebUI 설정 재구성"
echo "   1. Settings → Connections"
echo "   2. 기존 연결 모두 삭제"
echo "   3. 새로 추가:"
echo "      • LLM Server: http://112.148.37.41:1884"
echo "      • RAG Server: http://112.148.37.41:1886"

echo ""
echo "🔧 방법 5: 전체 재배포 (최후 수단)"
echo "   ./stop.sh && ./deploy.sh"

echo ""
echo "========================================"
echo "✅ OpenWebUI 진단 완료!"
echo ""
echo "💡 가장 가능성 높은 원인:"
echo "   - WebUI 브라우저 캐시 문제"
echo "   - WebUI 컨테이너 내부 설정 충돌"
echo "   - OpenWebUI ↔ RAG 서버 간 API 형식 불일치"
