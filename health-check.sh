#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 환경변수 로드
if [ -f ".env.global" ]; then
    source .env.global
else
    echo -e "${YELLOW}⚠️ .env.global 파일이 없습니다. ${NC}"
    exit 1
fi

echo "🏥 CHEESEADE RAG 시스템 상태 확인"
echo "========================================"
echo "📅 체크 시간: $(date)"
echo ""

# 전역 상태 변수
OVERALL_STATUS=0
SERVICES_TOTAL=0
SERVICES_HEALTHY=0

# 상태 체크 함수
check_service() {
    local service_name="$1"
    local url="$2"
    local expected_status="$3"
    local description="$4"
    local timeout="${5:-5}"
    
    SERVICES_TOTAL=$((SERVICES_TOTAL + 1))
    
    echo -n "🔍 ${service_name}: "
    
    # HTTP 상태 체크
    if command -v curl > /dev/null 2>&1; then
        response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $timeout --max-time $timeout "$url" 2>/dev/null)
        
        if [ "$response" = "$expected_status" ]; then
            echo -e "${GREEN}✅ 정상${NC} (${description})"
            SERVICES_HEALTHY=$((SERVICES_HEALTHY + 1))
            
            # 추가 정보 표시
            if [ "$service_name" = "LLM Server" ]; then
                models=$(curl -s --connect-timeout 3 "$url" 2>/dev/null | grep -o '"name":"[^"]*"' | head -3)
                if [ -n "$models" ]; then
                    echo "    📋 사용 가능한 모델: $(echo "$models" | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')"
                fi
            fi
            
        else
            echo -e "${RED}❌ 실패${NC} (응답: $response, 기대: $expected_status)"
            OVERALL_STATUS=1
        fi
    else
        echo -e "${YELLOW}⚠️ curl 없음${NC} (설치 필요)"
        OVERALL_STATUS=1
    fi
}

# Docker 컨테이너 상태 체크
check_docker_containers() {
    echo ""
    echo "🐳 Docker 컨테이너 상태:"
    echo "----------------------------------------"
    
    if ! command -v docker > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker가 설치되지 않았습니다${NC}"
        OVERALL_STATUS=1
        return
    fi
    
    # 각 서비스별 컨테이너 체크
    containers=(
        "webui:server-webui"
        "rag-server:server-rag" 
        "milvus-standalone:server-milvus"
        "milvus-etcd:server-milvus"
        "milvus-minio:server-milvus"
        "llm-server:server-llm"
    )
    
    for container_info in "${containers[@]}"; do
        container_name="${container_info%%:*}"
        service_dir="${container_info##*:}"
        
        if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$container_name"; then
            status=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "$container_name" | awk '{print $2}')
            if [[ "$status" == "Up" ]]; then
                echo -e "✅ ${container_name}: ${GREEN}실행 중${NC} ($service_dir)"
            else
                echo -e "⚠️ ${container_name}: ${YELLOW}$status${NC} ($service_dir)"
                OVERALL_STATUS=1
            fi
        else
            echo -e "❌ ${container_name}: ${RED}실행되지 않음${NC} ($service_dir)"
            OVERALL_STATUS=1
        fi
    done
}

# 포트 체크
check_ports() {
    echo ""
    echo "🔌 포트 상태 확인:"
    echo "----------------------------------------"
    
    ports=("$WEBUI_PORT:Open WebUI" "$RAG_PORT:RAG Server" "$MILVUS_PORT:Milvus" "$LLM_PORT:LLM Server")
    
    for port_info in "${ports[@]}"; do
        port="${port_info%%:*}"
        service="${port_info##*:}"
        
        if command -v netstat > /dev/null 2>&1; then
            if netstat -tuln 2>/dev/null | grep -q ":$port "; then
                echo -e "✅ 포트 $port: ${GREEN}열림${NC} ($service)"
            else
                echo -e "❌ 포트 $port: ${RED}닫힘${NC} ($service)"
                OVERALL_STATUS=1
            fi
        elif command -v ss > /dev/null 2>&1; then
            if ss -tuln 2>/dev/null | grep -q ":$port "; then
                echo -e "✅ 포트 $port: ${GREEN}열림${NC} ($service)"
            else
                echo -e "❌ 포트 $port: ${RED}닫힘${NC} ($service)"
                OVERALL_STATUS=1
            fi
        else
            echo -e "⚠️ 포트 $port: ${YELLOW}확인 불가${NC} (netstat/ss 없음)"
        fi
    done
}

# 시스템 리소스 체크
check_system_resources() {
    echo ""
    echo "💻 시스템 리소스:"
    echo "----------------------------------------"
    
    # 메모리 사용량
    if command -v free > /dev/null 2>&1; then
        memory_info=$(free -h | grep "Mem:")
        total_mem=$(echo $memory_info | awk '{print $2}')
        used_mem=$(echo $memory_info | awk '{print $3}')
        free_mem=$(echo $memory_info | awk '{print $4}')
        echo "🧠 메모리: 사용 $used_mem / 전체 $total_mem (여유: $free_mem)"
    fi
    
    # 디스크 사용량
    if command -v df > /dev/null 2>&1; then
        disk_usage=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')
        disk_info=$(df -h / | tail -1)
        echo "💾 디스크: $(echo $disk_info | awk '{print $3}') / $(echo $disk_info | awk '{print $2}') (사용률: ${disk_usage}%)"
        
        if [ "$disk_usage" -gt 90 ]; then
            echo -e "    ${RED}⚠️ 디스크 사용률이 높습니다 (${disk_usage}%)${NC}"
            OVERALL_STATUS=1
        fi
    fi
    
    # CPU 로드
    if command -v uptime > /dev/null 2>&1; then
        load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
        echo "⚙️ CPU 로드: $load_avg"
    fi
}

# 주요 서비스 상태 체크
echo "🌐 웹 서비스 상태:"
echo "----------------------------------------"
check_service "Open WebUI" "http://${WEBUI_SERVER_IP}:${WEBUI_PORT}" "200" "사용자 인터페이스"
check_service "RAG Server" "http://${RAG_SERVER_IP}:${RAG_PORT}/health" "200" "RAG API 서버"
check_service "RAG Models" "http://${RAG_SERVER_IP}:${RAG_PORT}/api/tags" "200" "모델 목록 API"

echo ""
echo "🤖 AI 서비스 상태:"
echo "----------------------------------------"
check_service "LLM Server" "http://${LLM_SERVER_IP}:${LLM_PORT}/api/tags" "200" "Ollama 언어모델"
check_service "Milvus Health" "http://${MILVUS_SERVER_IP}:9091/healthz" "200" "벡터 데이터베이스"

# Docker 및 포트 체크
check_docker_containers
check_ports
check_system_resources

# 기능 테스트 (선택적)
echo ""
echo "🧪 기능 테스트:"
echo "----------------------------------------"

# RAG 기능 테스트
echo -n "🔍 RAG 검색 테스트: "
rag_test_response=$(curl -s -X POST "http://${RAG_SERVER_IP}:${RAG_PORT}/debug/test-retrieval" \
    -H "Content-Type: application/json" \
    -d '{"question": "테스트"}' \
    --connect-timeout 10 2>/dev/null)

if echo "$rag_test_response" | grep -q "question"; then
    echo -e "${GREEN}✅ 정상${NC}"
    SERVICES_HEALTHY=$((SERVICES_HEALTHY + 1))
else
    echo -e "${RED}❌ 실패${NC}"
    OVERALL_STATUS=1
fi
SERVICES_TOTAL=$((SERVICES_TOTAL + 1))

# LLM 연결 테스트
echo -n "🤖 LLM 연결 테스트: "
llm_test_response=$(curl -s -X POST "http://${LLM_SERVER_IP}:${LLM_PORT}/api/generate" \
    -H "Content-Type: application/json" \
    -d '{"model": "gemma3:27b-it-q4_K_M", "prompt": "Hello", "stream": false}' \
    --connect-timeout 15 2>/dev/null)

if echo "$llm_test_response" | grep -q "response\|model"; then
    echo -e "${GREEN}✅ 정상${NC}"
    SERVICES_HEALTHY=$((SERVICES_HEALTHY + 1))
else
    echo -e "${RED}❌ 실패${NC}"
    OVERALL_STATUS=1
fi
SERVICES_TOTAL=$((SERVICES_TOTAL + 1))

# 최종 결과
echo ""
echo "📊 종합 상태 요약:"
echo "========================================"
echo "✅ 정상 서비스: ${SERVICES_HEALTHY}/${SERVICES_TOTAL}"

if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "🎉 ${GREEN}전체 시스템 상태: 정상${NC}"
    echo ""
    echo "🌐 접속 정보:"
    echo "   • Open WebUI: http://${WEBUI_SERVER_IP}:${WEBUI_PORT}"
    echo "   • RAG API: http://${RAG_SERVER_IP}:${RAG_PORT}"
    echo "   • Milvus Admin: http://${MILVUS_SERVER_IP}:9001"
    echo ""
    echo "📋 사용 가능한 모델:"
    echo "   • rag-cheeseade:latest (CHEESEADE RAG를 활용한 전문 상담)"
    echo "   • gemma3:27b-it-q4_K_M (일반 대화)"
else
    echo -e "⚠️ ${YELLOW}전체 시스템 상태: 일부 문제 있음${NC}"
    echo ""
    echo "🔧 문제 해결 방법:"
    echo "   1. 실패한 서비스의 로그 확인:"
    echo "      docker compose logs -f [service-name]"
    echo "   2. 서비스 재시작:"
    echo "      cd [service-directory] && docker compose restart"
    echo "   3. 전체 재배포:"
    echo "      ./stop.sh && ./deploy.sh"
fi

echo ""
echo "📋 상세 로그 확인:"
echo "   ./monitoring/logs-collect.sh"
echo ""

exit $OVERALL_STATUS

