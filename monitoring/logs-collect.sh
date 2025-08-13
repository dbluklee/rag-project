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

echo "📋 CHEESEADE RAG 시스템 로그 수집"
echo "========================================"
echo "📅 수집 시간: $(date)"
echo ""

# 로그 저장 디렉토리 생성
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="./logs_collected_${TIMESTAMP}"
mkdir -p "$LOG_DIR"

echo "📁 로그 저장 위치: $LOG_DIR"
echo ""

# Docker 명령어 확인
if ! command -v docker > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker가 설치되지 않았습니다${NC}"
    exit 1
fi

# 컨테이너 목록
containers=(
    "webui:server-webui:Open WebUI"
    "rag-server:server-rag:RAG Server" 
    "rag-init:server-rag:RAG Init"
    "milvus-standalone:server-milvus:Milvus DB"
    "milvus-etcd:server-milvus:Milvus etcd"
    "milvus-minio:server-milvus:Milvus MinIO"
    "llm-server:server-llm:LLM Server"
    "ollama-init:server-llm:Ollama Init"
)

# 1. Docker 컨테이너 로그 수집
echo "🐳 Docker 컨테이너 로그 수집 중..."
echo "----------------------------------------"

for container_info in "${containers[@]}"; do
    container_name="${container_info%%:*}"
    service_dir=$(echo "$container_info" | cut -d':' -f2)
    description=$(echo "$container_info" | cut -d':' -f3)
    
    echo -n "📦 $container_name ($description): "
    
    if docker ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
        # 최근 1000줄 로그 수집
        docker logs --tail 1000 "$container_name" > "$LOG_DIR/${container_name}.log" 2>&1
        
        # 로그 파일 크기 확인
        log_size=$(wc -l < "$LOG_DIR/${container_name}.log" 2>/dev/null || echo "0")
        
        if [ "$log_size" -gt 0 ]; then
            echo -e "${GREEN}✅ 수집됨${NC} (${log_size} lines)"
        else
            echo -e "${YELLOW}⚠️ 빈 로그${NC}"
        fi
    else
        echo -e "${RED}❌ 컨테이너 없음${NC}"
        echo "Container not found" > "$LOG_DIR/${container_name}.log"
    fi
done

echo ""

# 2. Docker 컨테이너 상태 정보 수집
echo "📊 Docker 상태 정보 수집 중..."
echo "----------------------------------------"

echo "🔍 컨테이너 목록 및 상태..."
{
    echo "=== Docker 컨테이너 상태 ==="
    echo "수집 시간: $(date)"
    echo ""
    
    echo "=== 실행 중인 컨테이너 ==="
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"
    echo ""
    
    echo "=== 모든 컨테이너 (중지 포함) ==="
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Created}}\t{{.Image}}"
    echo ""
    
    echo "=== 이미지 목록 ==="
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
    echo ""
    
    echo "=== 볼륨 사용량 ==="
    docker system df
    echo ""
    
    echo "=== 네트워크 목록 ==="
    docker network ls
    echo ""
    
} > "$LOG_DIR/docker-status.log" 2>&1

echo -e "${GREEN}✅ Docker 상태 정보 저장됨${NC}"

# 3. 시스템 리소스 정보 수집
echo ""
echo "💻 시스템 리소스 정보 수집 중..."
echo "----------------------------------------"

echo "🔍 시스템 리소스 상태..."
{
    echo "=== 시스템 리소스 상태 ==="
    echo "수집 시간: $(date)"
    echo ""
    
    echo "=== 메모리 사용량 ==="
    free -h
    echo ""
    
    echo "=== 디스크 사용량 ==="
    df -h
    echo ""
    
    echo "=== CPU 정보 및 로드 ==="
    uptime
    if command -v nproc > /dev/null 2>&1; then
        echo "CPU 코어 수: $(nproc)"
    fi
    echo ""
    
    echo "=== 실행 중인 프로세스 (상위 20개) ==="
    if command -v ps > /dev/null 2>&1; then
        ps aux --sort=-%cpu | head -21
    fi
    echo ""
    
    echo "=== 네트워크 연결 상태 ==="
    if command -v netstat > /dev/null 2>&1; then
        netstat -tuln | grep -E ":3000|:8000|:11434|:19530|:9091"
    elif command -v ss > /dev/null 2>&1; then
        ss -tuln | grep -E ":3000|:8000|:11434|:19530|:9091"
    fi
    echo ""
    
    echo "=== GPU 상태 (있는 경우) ==="
    if command -v nvidia-smi > /dev/null 2>&1; then
        nvidia-smi
    else
        echo "NVIDIA GPU 없음 또는 nvidia-smi 설치되지 않음"
    fi
    echo ""
    
} > "$LOG_DIR/system-resources.log" 2>&1

echo -e "${GREEN}✅ 시스템 리소스 정보 저장됨${NC}"

# 4. 서비스별 설정 파일 수집
echo ""
echo "⚙️ 설정 파일 수집 중..."
echo "----------------------------------------"

echo "🔍 Docker Compose 설정..."
mkdir -p "$LOG_DIR/configs"

# Docker Compose 파일들 복사
services=("server-webui" "server-rag" "server-milvus" "server-llm")
for service in "${services[@]}"; do
    if [ -d "$service" ]; then
        echo -n "📄 $service: "
        
        # docker-compose.yml 복사
        if [ -f "$service/docker-compose.yml" ]; then
            cp "$service/docker-compose.yml" "$LOG_DIR/configs/${service}-docker-compose.yml"
            echo -n "compose "
        fi
        
        # .env 복사
        if [ -f "$service/.env" ]; then
            cp "$service/.env" "$LOG_DIR/configs/${service}.env"
            echo -n "env "
        fi
        
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "📄 $service: ${YELLOW}⚠️ 디렉토리 없음${NC}"
    fi
done

# 전역 설정 복사
if [ -f ".env.global" ]; then
    cp ".env.global" "$LOG_DIR/configs/global.env"
fi

echo -e "${GREEN}✅ 설정 파일 수집 완료${NC}"

# 5. API 상태 테스트 결과 수집
echo ""
echo "🧪 API 상태 테스트 중..."
echo "----------------------------------------"

{
    echo "=== API 상태 테스트 ==="
    echo "테스트 시간: $(date)"
    echo ""
    
    # Open WebUI 테스트
    echo "=== Open WebUI 테스트 ==="
    echo -n "URL: http://${WEBUI_SERVER_IP}:${WEBUI_PORT} - "
    curl_result=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://${WEBUI_SERVER_IP}:${WEBUI_PORT}" 2>/dev/null)
    echo "HTTP Status: $curl_result"
    echo ""
    
    # RAG Server 테스트
    echo "=== RAG Server 테스트 ==="
    echo -n "Health Check: http://${RAG_SERVER_IP}:${RAG_PORT}/health - "
    curl_result=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://${RAG_SERVER_IP}:${RAG_PORT}/health" 2>/dev/null)
    echo "HTTP Status: $curl_result"
    
    echo -n "Model List: http://${RAG_SERVER_IP}:${RAG_PORT}/api/tags - "
    curl_result=$(curl -s --connect-timeout 5 "http://${RAG_SERVER_IP}:${RAG_PORT}/api/tags" 2>/dev/null)
    if echo "$curl_result" | grep -q "models"; then
        echo "✅ 정상 응답"
        echo "Models: $(echo "$curl_result" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')"
    else
        echo "❌ 응답 없음"
    fi
    echo ""
    
    # LLM Server 테스트
    echo "=== LLM Server 테스트 ==="
    echo -n "Model List: http://${LLM_SERVER_IP}:${LLM_PORT}/api/tags - "
    curl_result=$(curl -s --connect-timeout 5 "http://${LLM_SERVER_IP}:${LLM_PORT}/api/tags" 2>/dev/null)
    if echo "$curl_result" | grep -q "models"; then
        echo "✅ 정상 응답"
        echo "Models: $(echo "$curl_result" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')"
    else
        echo "❌ 응답 없음"
    fi
    echo ""
    
    # Milvus 테스트
    echo "=== Milvus 테스트 ==="
    echo -n "Health Check: http://${MILVUS_SERVER_IP}:${MILVUS_MONITOR_PORT}/healthz - "
    curl_result=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://${MILVUS_SERVER_IP}:${MILVUS_MONITOR_PORT}/healthz" 2>/dev/null)
    echo "HTTP Status: $curl_result"
    echo ""
    
} > "$LOG_DIR/api-tests.log" 2>&1

echo -e "${GREEN}✅ API 테스트 결과 저장됨${NC}"

# 6. 에러 로그 필터링
echo ""
echo "🚨 에러 로그 분석 중..."
echo "----------------------------------------"

{
    echo "=== 에러 로그 요약 ==="
    echo "분석 시간: $(date)"
    echo ""
    
    echo "=== 컨테이너별 에러 ==="
    for container_info in "${containers[@]}"; do
        container_name="${container_info%%:*}"
        description=$(echo "$container_info" | cut -d':' -f3)
        
        if [ -f "$LOG_DIR/${container_name}.log" ]; then
            error_count=$(grep -i -E "(error|failed|fatal|exception|panic)" "$LOG_DIR/${container_name}.log" | wc -l)
            if [ "$error_count" -gt 0 ]; then
                echo ""
                echo "--- $container_name ($description) ---"
                echo "에러 개수: $error_count"
                echo "최근 에러 5개:"
                grep -i -E "(error|failed|fatal|exception|panic)" "$LOG_DIR/${container_name}.log" | tail -5
            fi
        fi
    done
    
    echo ""
    echo "=== 경고 로그 요약 ==="
    for container_info in "${containers[@]}"; do
        container_name="${container_info%%:*}"
        description=$(echo "$container_info" | cut -d':' -f3)
        
        if [ -f "$LOG_DIR/${container_name}.log" ]; then
            warning_count=$(grep -i -E "(warning|warn)" "$LOG_DIR/${container_name}.log" | wc -l)
            if [ "$warning_count" -gt 0 ]; then
                echo ""
                echo "--- $container_name ($description) ---"
                echo "경고 개수: $warning_count"
                echo "최근 경고 3개:"
                grep -i -E "(warning|warn)" "$LOG_DIR/${container_name}.log" | tail -3
            fi
        fi
    done
    
} > "$LOG_DIR/error-summary.log" 2>&1

echo -e "${GREEN}✅ 에러 로그 분석 완료${NC}"

# 7. 로그 압축 및 요약
echo ""
echo "📦 로그 압축 및 요약 생성 중..."
echo "----------------------------------------"

# 요약 파일 생성
{
    echo "===== CHEESEADE RAG 시스템 로그 수집 요약 ====="
    echo "수집 시간: $(date)"
    echo "서버 IP: $RAG_SERVER_IP"
    echo "로그 디렉토리: $LOG_DIR"
    echo ""
    
    echo "=== 수집된 파일 목록 ==="
    find "$LOG_DIR" -type f -exec ls -lh {} \; | awk '{print $9 " (" $5 ")"}'
    echo ""
    
    echo "=== 컨테이너 상태 요약 ==="
    for container_info in "${containers[@]}"; do
        container_name="${container_info%%:*}"
        description=$(echo "$container_info" | cut -d':' -f3)
        
        if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
            status="🟢 실행 중"
        elif docker ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
            status="🔴 중지됨"
        else
            status="⚪ 없음"
        fi
        
        echo "$status $container_name ($description)"
    done
    echo ""
    
    echo "=== 주요 에러 개수 ==="
    total_errors=0
    for container_info in "${containers[@]}"; do
        container_name="${container_info%%:*}"
        if [ -f "$LOG_DIR/${container_name}.log" ]; then
            error_count=$(grep -i -E "(error|failed|fatal|exception|panic)" "$LOG_DIR/${container_name}.log" | wc -l)
            if [ "$error_count" -gt 0 ]; then
                echo "$container_name: $error_count 개"
                total_errors=$((total_errors + error_count))
            fi
        fi
    done
    echo "총 에러 개수: $total_errors"
    echo ""
    
    echo "=== 디스크 사용량 ==="
    log_dir_size=$(du -sh "$LOG_DIR" | cut -f1)
    echo "로그 디렉토리 크기: $log_dir_size"
    echo ""
    
    echo "=== 권장 조치 ==="
    if [ "$total_errors" -gt 10 ]; then
        echo "⚠️ 에러가 많이 발생했습니다. error-summary.log를 확인하세요."
    fi
    
    disk_usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    if [ "$disk_usage" -gt 90 ]; then
        echo "⚠️ 디스크 사용률이 높습니다 (${disk_usage}%). 로그 정리가 필요합니다."
    fi
    
    echo "✅ 모든 로그가 수집되었습니다."
    echo ""
    
} > "$LOG_DIR/README.txt"

# 압축 파일 생성 (선택사항)
echo "🗜️ 로그 압축 중..."
if command -v tar > /dev/null 2>&1; then
    tar -czf "${LOG_DIR}.tar.gz" "$LOG_DIR" 2>/dev/null
    if [ $? -eq 0 ]; then
        archive_size=$(du -sh "${LOG_DIR}.tar.gz" | cut -f1)
        echo -e "${GREEN}✅ 압축 완료${NC}: ${LOG_DIR}.tar.gz ($archive_size)"
    else
        echo -e "${YELLOW}⚠️ 압축 실패${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ tar 명령어가 없어 압축을 건너뜁니다${NC}"
fi

# 최종 요약
echo ""
echo "📋 로그 수집 완료 요약:"
echo "========================================"
echo "📁 로그 디렉토리: $LOG_DIR"
echo "📄 요약 파일: $LOG_DIR/README.txt"
echo "🚨 에러 분석: $LOG_DIR/error-summary.log"
echo "🐳 Docker 상태: $LOG_DIR/docker-status.log"
echo "💻 시스템 리소스: $LOG_DIR/system-resources.log"
echo "🧪 API 테스트: $LOG_DIR/api-tests.log"
echo ""

# 파일 크기 표시
log_dir_size=$(du -sh "$LOG_DIR" | cut -f1)
echo "💾 총 로그 크기: $log_dir_size"

if [ -f "${LOG_DIR}.tar.gz" ]; then
    archive_size=$(du -sh "${LOG_DIR}.tar.gz" | cut -f1)
    echo "📦 압축 파일: ${LOG_DIR}.tar.gz ($archive_size)"
fi

echo ""
echo "🔍 다음 단계:"
echo "   1. README.txt 파일을 먼저 확인하세요"
echo "   2. error-summary.log에서 주요 문제점을 파악하세요"
echo "   3. 문제가 있는 컨테이너의 개별 로그를 확인하세요"
echo ""

echo -e "${GREEN}✅ 로그 수집이 완료되었습니다!${NC}"