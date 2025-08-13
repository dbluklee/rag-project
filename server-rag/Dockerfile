# CHEESEADE RAG Server Dockerfile - GPU Support
# NVIDIA CUDA 지원 버전

FROM nvidia/cuda:12.1-devel-ubuntu22.04 as base

# 환경변수
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_VISIBLE_DEVICES=0

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3.11-venv \
    # CUDA 관련
    nvidia-cuda-toolkit \
    # 빌드 도구
    build-essential \
    cmake \
    # 기타 도구
    curl \
    wget \
    git \
    && ln -s /usr/bin/python3.11 /usr/bin/python \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# PyTorch와 CUDA 지원 패키지
FROM base as pytorch

WORKDIR /app
COPY requirements.txt .

# PyTorch CUDA 버전 설치
RUN pip install --upgrade pip \
    && pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 \
    && pip install --no-cache-dir -r requirements.txt

# 애플리케이션 스테이지
FROM pytorch as app

# 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 애플리케이션 복사
COPY --chown=appuser:appuser . .

# 권한 설정
RUN mkdir -p docs logs \
    && chown -R appuser:appuser /app \
    && chmod +x startup.sh

# GPU 메모리 최적화를 위한 환경변수
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128 \
    CUDA_LAUNCH_BLOCKING=0

USER appuser
EXPOSE 8000
VOLUME ["/app/docs", "/app/logs"]

# GPU 상태 확인 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["./startup.sh"]