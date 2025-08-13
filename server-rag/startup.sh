#!/bin/bash

# RAG Server 시작 스크립트
# CHEESEADE RAG 시스템의 핵심 서버 초기화 및 실행

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_header() {
    echo -e "${PURPLE}[HEADER]${NC} $1"
}

# 시작 헤더
log_header "🚀 CHEESEADE RAG Server 시작"
log_header "========================================"
log_info "시작 시간: $(date)"
log_info "호스트명: $(hostname)"
log_info "사용자: $(whoami)"
log_info "작업 디렉토리: $(pwd)"
echo ""

# 환경변수 설정 및 검증
setup_environment() {
    log_header "⚙️ 환경변수 설정 및 검증"
    
    # 기본 환경변수 설정
    export PYTHONUNBUFFERED=1
    export PYTHONPATH=/app
    
    # 필수 환경변수 확인
    local required_vars=(
        "LLM_SERVER_URL"
        "MILVUS_SERVER_IP"
        "MILVUS_PORT"
    )
    

    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        else
            log_info "$var = ${!var}"
        fi
    done

    # 기본값 설정
    export LLM_SERVER_URL=${LLM_SERVER_URL}
    export MILVUS_SERVER_IP=${MILVUS_SERVER_IP}
    export MILVUS_PORT=${MILVUS_PORT}
    export RAG_MODEL_NAME=${RAG_MODEL_NAME}
    export LLM_MODEL_NAME=${LLM_MODEL_NAME}
    export COLLECTION_NAME=${COLLECTION_NAME}
    export RETRIEVAL_TOP_K=${RETRIEVAL_TOP_K}
    export EMBEDDING_BATCH_SIZE=${EMBEDDING_BATCH_SIZE}
    export API_TIMEOUT=${API_TIMEOUT:-"120"}
    export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
    
    # GPU 설정
    if [ "${FORCE_CPU:-false}" = "true" ]; then
        export CUDA_VISIBLE_DEVICES=""
        log_warning "GPU 비활성화됨 (FORCE_CPU=true)"
    else
        # GPU 사용 가능성 확인
        if command -v nvidia-smi > /dev/null 2>&1; then
            if nvidia-smi > /dev/null 2>&1; then
                log_success "GPU 감지됨: $(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -1)"
            else
                log_warning "nvidia-smi 실행 실패, CPU 모드로 전환"
                export CUDA_VISIBLE_DEVICES=""
            fi
        else
            log_info "NVIDIA GPU 없음, CPU 모드 사용"
            export CUDA_VISIBLE_DEVICES=""
        fi
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_warning "일부 환경변수가 설정되지 않았습니다. 기본값을 사용합니다:"
        for var in "${missing_vars[@]}"; do
            log_warning "  $var (기본값: ${!var})"
        done
    fi
    
    log_success "환경변수 설정 완료"
    echo ""
}

# 디렉토리 및 권한 설정
setup_directories() {
    log_header "📁 디렉토리 및 권한 설정"
    
    # 필요한 디렉토리 생성
    local directories=(
        "/app/docs"
        "/app/logs"
        "/app/chunking"
        "/app/embedding" 
        "/app/vector_db"
        "/app/retriever"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            log_info "디렉토리 생성: $dir"
            mkdir -p "$dir"
        fi
        
        # 권한 확인
        if [ -w "$dir" ]; then
            log_success "쓰기 권한 확인: $dir"
        else
            log_error "쓰기 권한 없음: $dir"
            return 1
        fi
    done
    
    log_success "디렉토리 설정 완료"
    echo ""
}

# 외부 서비스 연결 확인
check_external_services() {
    log_header "🔗 외부 서비스 연결 확인"
    
    local services_ok=true
    
    # LLM 서버 확인
    log_info "LLM 서버 연결 확인: $LLM_SERVER_URL"
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --connect-timeout 5 --max-time 10 "$LLM_SERVER_URL/api/tags" > /dev/null 2>&1; then
            log_success "LLM 서버 연결 성공 (시도: $attempt/$max_attempts)"
            
            # 사용 가능한 모델 확인
            local models=$(curl -s --connect-timeout 5 "$LLM_SERVER_URL/api/tags" 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | head -3 | tr '\n' ', ' | sed 's/,$//')
            if [ -n "$models" ]; then
                log_info "사용 가능한 모델: $models"
            fi
            break
        else
            if [ $attempt -eq $max_attempts ]; then
                log_error "LLM 서버 연결 실패!"
                log_error "확인 사항:"
                log_error "  - LLM 서버가 실행 중인지 확인: $LLM_SERVER_URL"
                log_error "  - 네트워크 연결 및 방화벽 확인"
                log_error "  - 환경변수 LLM_SERVER_URL 확인"
                services_ok=false
                break
            fi
            log_info "LLM 서버 연결 대기... ($attempt/$max_attempts)"
            sleep 10
            attempt=$((attempt + 1))
        fi
    done
    
    # Milvus 서버 확인
    log_info "Milvus 서버 연결 확인: $MILVUS_SERVER_URL"
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --connect-timeout 5 --max-time 10 "http://$MILVUS_SERVER_IP:$MILVUS_MONITOR_PORT/healthz" > /dev/null 2>&1; then
            log_success "Milvus 서버 연결 성공 (시도: $attempt/$max_attempts)"
            break
        else
            if [ $attempt -eq $max_attempts ]; then
                log_error "Milvus 서버 연결 실패!"
                log_error "확인 사항:"
                log_error "  - Milvus 서버가 실행 중인지 확인: $MILVUS_SERVER_URL"
                log_error "  - etcd, minio 서비스 상태 확인"
                log_error "  - 환경변수 MILVUS_SERVER_IP, MILVUS_PORT 확인"
                services_ok=false
                break
            fi
            log_info "Milvus 서버 연결 대기... ($attempt/$max_attempts)"
            sleep 10
            attempt=$((attempt + 1))
        fi
    done
    
    if [ "$services_ok" = false ]; then
        log_error "외부 서비스 연결 실패. 서버를 시작할 수 없습니다."
        return 1
    fi
    
    log_success "모든 외부 서비스 연결 확인됨"
    echo ""
}

# 문서 검증
validate_documents() {
    log_header "📚 문서 확인"
    
    # .md 파일 존재 확인
    local md_files=$(find /app/docs -type f 2>/dev/null | wc -l)
    if [ "$md_files" -eq 0 ]; then
        log_error "docs 디렉토리에 문서 파일이 없습니다!"
        log_error "해결 방법:"
        log_error "  1. docs/ 폴더에 문서 파일을 추가하세요"
        log_error "  2. 파일은 UTF-8 인코딩이어야 합니다"
        log_error "현재 docs/ 내용:"
        ls -la /app/docs/ 2>/dev/null || log_error "   (비어있음)"
        return 1
    fi

    log_success "$md_files 개의 문서 파일 발견"
}

# Python 의존성 확인
check_python_dependencies() {
    log_header "🐍 Python 의존성 확인"
    
    # 핵심 패키지 확인
    local required_packages=(
        "fastapi"
        "uvicorn"
        "langchain"
        "langchain_community"
        "langchain_huggingface"
        "langchain_milvus" 
        "langchain_ollama"
        "pymilvus"
        "torch"
        "sentence_transformers"
        "requests"
    )
    
    local missing_packages=()
    
    for package in "${required_packages[@]}"; do
        if python -c "import $package" 2>/dev/null; then
            local version=$(python -c "import $package; print(getattr($package, '__version__', 'unknown'))" 2>/dev/null)
            log_success "$package ($version)"
        else
            missing_packages+=("$package")
            log_error "$package (없음)"
        fi
    done
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        log_error "필수 패키지가 누락되었습니다:"
        for package in "${missing_packages[@]}"; do
            log_error "  - $package"
        done
        log_error "pip install -r requirements.txt 를 실행하세요"
        return 1
    fi
    
    # Python 버전 확인
    local python_version=$(python --version 2>&1)
    log_info "Python 버전: $python_version"
    
    log_success "Python 의존성 확인 완료"
    echo ""
}

# 모델 준비상태 확인
check_model_readiness() {
    log_header "🤖 모델 준비상태 확인"
    
    # 임베딩 모델 로드 테스트
    log_info "임베딩 모델 로드 테스트 중..."
    
    cat > /tmp/test_embedding.py << 'EOF'
import sys
import os
sys.path.append('/app')

try:
    from embedding.bge_m3 import get_bge_m3_model
    
    print("임베딩 모델 로드 중...")
    model = get_bge_m3_model()
    
    # 간단한 테스트
    test_text = "테스트 문서입니다."
    embedding = model.embed_query(test_text)
    
    print(f"임베딩 차원: {len(embedding)}")
    print("임베딩 모델 테스트 성공")
    
except Exception as e:
    print(f"임베딩 모델 오류: {e}")
    sys.exit(1)
EOF
    
    if python /tmp/test_embedding.py; then
        log_success "임베딩 모델 준비 완료"
    else
        log_error "임베딩 모델 로드 실패"
        return 1
    fi
    
    rm -f /tmp/test_embedding.py
    
    # LLM 연결 테스트
    log_info "LLM 연결 테스트 중..."
    local test_response=$(curl -s -X POST "$LLM_SERVER_URL/api/generate" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"$LLM_MODEL_NAME\", \"prompt\": \"Hello\", \"stream\": false}" \
        --connect-timeout 15 2>/dev/null)
    
    if echo "$test_response" | grep -q "response"; then
        log_success "LLM 연결 테스트 성공"
    else
        log_warning "LLM 연결 테스트 실패 (서버는 계속 진행)"
    fi
    
    log_success "모델 준비상태 확인 완료"
    echo ""
}

# 로그 설정
setup_logging() {
    log_header "📝 로그 설정"
    
    # 로그 디렉토리 생성
    mkdir -p /app/logs
    
    # 로그 파일 설정
    export LOG_FILE_PATH=${LOG_FILE_PATH:-"/app/logs/rag-server.log"}
    
    # 기존 로그 백업 (크기가 큰 경우)
    if [ -f "$LOG_FILE_PATH" ]; then
        local log_size=$(stat -c%s "$LOG_FILE_PATH" 2>/dev/null || echo "0")
        if [ "$log_size" -gt 104857600 ]; then  # 100MB
            local backup_name="/app/logs/rag-server_$(date +%Y%m%d_%H%M%S).log"
            log_info "기존 로그 백업: $backup_name"
            mv "$LOG_FILE_PATH" "$backup_name"
        fi
    fi
    
    # 로그 파일 생성
    touch "$LOG_FILE_PATH"
    
    log_info "로그 파일: $LOG_FILE_PATH"
    log_info "로그 레벨: $LOG_LEVEL"
    
    log_success "로그 설정 완료"
    echo ""
}

# 시스템 정보 출력
print_system_info() {
    log_header "💻 시스템 정보"
    
    # 시스템 리소스
    if command -v free > /dev/null 2>&1; then
        local memory_info=$(free -h | grep "Mem:")
        local total_mem=$(echo $memory_info | awk '{print $2}')
        local available_mem=$(echo $memory_info | awk '{print $7}')
        log_info "메모리: $available_mem / $total_mem 사용 가능"
    fi
    
    if command -v df > /dev/null 2>&1; then
        local disk_info=$(df -h /app | tail -1)
        local disk_available=$(echo $disk_info | awk '{print $4}')
        local disk_usage=$(echo $disk_info | awk '{print $5}')
        log_info "디스크: $disk_available 사용 가능 (사용률: $disk_usage)"
    fi
    
    # CPU 정보
    if [ -f /proc/cpuinfo ]; then
        local cpu_count=$(grep -c ^processor /proc/cpuinfo)
        log_info "CPU 코어: $cpu_count 개"
    fi
    
    # GPU 정보
    if [ -n "$CUDA_VISIBLE_DEVICES" ] && [ "$CUDA_VISIBLE_DEVICES" != "" ]; then
        if command -v nvidia-smi > /dev/null 2>&1; then
            local gpu_info=$(nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits 2>/dev/null | head -1)
            if [ -n "$gpu_info" ]; then
                log_info "GPU: $gpu_info"
            fi
        fi
    else
        log_info "GPU: CPU 모드 사용"
    fi
    
    log_success "시스템 정보 출력 완료"
    echo ""
}

# 메인 서버 시작
start_server() {
    log_header "🚀 RAG 서버 시작"
    
    # 최종 설정 요약
    log_info "서버 설정 요약:"
    log_info "  포트: 8000"
    log_info "  LLM 서버: $LLM_SERVER_URL"
    log_info "  Milvus: $MILVUS_SERVER_URL"
    log_info "  RAG 모델: $RAG_MODEL_NAME"
    log_info "  백엔드 모델: $LLM_MODEL_NAME"
    log_info "  컬렉션: $COLLECTION_NAME"
    log_info "  검색 개수: $RETRIEVAL_TOP_K"
    log_info "  로그 레벨: $LOG_LEVEL"
    echo ""
    
    log_success "모든 준비 완료! FastAPI 서버를 시작합니다..."
    log_info "접속 URL: http://0.0.0.0:8000"
    log_info "헬스체크: http://0.0.0.0:8000/health"
    log_info "API 문서: http://0.0.0.0:8000/docs"
    echo ""
    
    # uvicorn 설정
    local uvicorn_args=(
        "server:app"
        "--host" "0.0.0.0"
        "--port" "8000"
        "--log-level" "${LOG_LEVEL,,}"
        "--access-log"
        "--loop" "uvloop"
    )
    
    # 개발 모드 확인
    if [ "${DEBUG_MODE:-false}" = "true" ]; then
        uvicorn_args+=("--reload")
        log_info "개발 모드: 파일 변경 감지 활성화"
    fi
    
    # 워커 설정 (프로덕션)
    if [ "${UVICORN_WORKERS:-1}" -gt 1 ]; then
        uvicorn_args+=("--workers" "${UVICORN_WORKERS}")
        log_info "워커 프로세스: ${UVICORN_WORKERS}개"
    fi
    
    # 서버 시작
    exec uvicorn "${uvicorn_args[@]}"
}

# 에러 핸들러
handle_error() {
    local exit_code=$?
    local line_number=$1
    
    log_error "스크립트 실행 중 오류 발생!"
    log_error "  종료 코드: $exit_code"
    log_error "  라인 번호: $line_number"
    log_error "  명령어: ${BASH_COMMAND}"
    
    # 정리 작업
    cleanup
    
    exit $exit_code
}

# 종료 핸들러
cleanup() {
    log_info "정리 작업 수행 중..."
    
    # 임시 파일 정리
    rm -f /tmp/test_*.py
    
    # PID 파일 정리
    if [ -f "/tmp/rag-server.pid" ]; then
        rm -f "/tmp/rag-server.pid"
    fi
    
    log_info "정리 작업 완료"
}

# 신호 핸들러 설정
trap 'handle_error $LINENO' ERR
trap 'cleanup; exit 0' SIGTERM SIGINT

# PID 파일 생성
echo $$ > /tmp/rag-server.pid

# 메인 실행 함수
main() {
    # 모든 검증 단계 실행
    setup_environment || exit 1
    setup_directories || exit 1
    setup_logging || exit 1
    print_system_info
    check_python_dependencies || exit 1
    check_external_services || exit 1
    validate_documents || exit 1
    check_model_readiness || exit 1
    
    # 서버 시작
    start_server
}

# 스크립트 실행
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi