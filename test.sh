#!/bin/bash
# API 헤더 에러 즉시 해결

echo "🔧 API 헤더 에러 해결"
echo "========================================"

# 1. 현재 에러 상황 확인
echo "1️⃣ 현재 에러 확인"
echo "----------------------------------------"
echo "📋 채팅 API 테스트:"
curl -s -X POST "http://112.148.37.41:1886/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "테스트", "model": "rag-cheeseade:latest"}' | jq . 2>/dev/null || \
curl -s -X POST "http://112.148.37.41:1886/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "테스트", "model": "rag-cheeseade:latest"}'

echo ""

# 2. 인증 없는 엔드포인트 테스트 (정상 확인)
echo "2️⃣ 인증 없는 엔드포인트 (정상 동작 확인)"
echo "----------------------------------------"
echo "📋 헬스체크:"
curl -s "http://112.148.37.41:1886/health" | jq . 2>/dev/null || curl -s "http://112.148.37.41:1886/health"

echo ""
echo "📋 모델 목록:"
curl -s "http://112.148.37.41:1886/api/models" | jq . 2>/dev/null || curl -s "http://112.148.37.41:1886/api/models"

echo ""

# 3. 임시 해결 방법 (인증 헤더 없이 테스트)
echo "3️⃣ 대안 채팅 API 테스트"
echo "----------------------------------------"
echo "📋 OpenAI 형식 채팅 API:"
curl -s -X POST "http://112.148.37.41:1886/api/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-cheeseade:latest",
    "messages": [{"role": "user", "content": "안녕하세요"}],
    "stream": false
  }' | jq . 2>/dev/null || \
curl -s -X POST "http://112.148.37.41:1886/api/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-cheeseade:latest", 
    "messages": [{"role": "user", "content": "안녕하세요"}],
    "stream": false
  }'

echo ""

# 4. 에러 로그 확인
echo "4️⃣ 에러 로그 확인"
echo "----------------------------------------"
echo "📋 최근 RAG 서버 에러 로그:"
docker logs --tail 20 cheeseade-rag-server 2>/dev/null | grep -i -E "error|exception|header" || echo "관련 에러 로그 없음"

echo ""

# 5. 해결 방법 제시
echo "5️⃣ 해결 방법"
echo "----------------------------------------"
echo "🔧 방법 1: auth.py 파일 수정 (권장)"
echo "   1. server-rag/api/auth.py 파일 열기"
echo "   2. get_current_user_optional 함수에서 except 부분 수정:"
echo "      except (HTTPException, TypeError, AttributeError):"
echo ""
echo "🔧 방법 2: 컨테이너 재시작"
echo "   cd server-rag"
echo "   docker compose restart"
echo ""
echo "🔧 방법 3: 인증 완전 비활성화"
echo "   server-rag/.env 파일에 추가:"
echo "   WEBUI_AUTH=false"
echo "   ENABLE_API_KEY=false"
echo ""
echo "🔧 방법 4: 전체 재배포 (수정 파일 적용)"
echo "   ./stop.sh"
echo "   # auth.py 파일 수정 후"
echo "   ./deploy.sh"

echo ""

# 6. 수정 후 확인 방법
echo "6️⃣ 수정 후 확인"
echo "----------------------------------------"
echo "# 채팅 API 테스트"
echo "curl -X POST http://112.148.37.41:1886/api/chat \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"message\": \"안녕하세요\", \"model\": \"rag-cheeseade:latest\"}'"

echo ""
echo "========================================"
echo "✅ 해결 방법 제시 완료!"
