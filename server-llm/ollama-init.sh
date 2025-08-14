#!/bin/sh

echo "🚀 Ollama 모델 초기화 시작"
echo "서버 URL: $LLM_SERVER_URL"
echo "모델명: $LLM_MODEL_NAME"
echo "========================================"

# Ollama 서버 연결 대기
echo "⏳ Ollama 서버 연결 대기 중..."
max_attempts=60
attempt=1

while [ $attempt -le $max_attempts ]; do
    echo "연결 시도 $attempt/$max_attempts..."
    
    if curl -s --connect-timeout 5 --max-time 10 "$LLM_SERVER_URL/api/tags" >/dev/null 2>&1; then
        echo "✅ Ollama 서버 연결 성공!"
        break
    else
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Ollama 서버 연결 실패!"
            exit 1
        fi
        echo "연결 대기 중... (5초 후 재시도)"
        sleep 5
        attempt=$((attempt + 1))
    fi
done

# 현재 설치된 모델 확인
echo "📋 현재 설치된 모델 확인 중..."
models_response=$(curl -s --connect-timeout 10 "$LLM_SERVER_URL/api/tags" 2>/dev/null)

if echo "$models_response" | grep -q "\"name\":\"$LLM_MODEL_NAME\""; then
    echo "✅ 모델 $LLM_MODEL_NAME이 이미 설치되어 있습니다."
    echo "🎉 초기화 완료!"
    exit 0
fi

echo "📥 모델 다운로드 시작: $LLM_MODEL_NAME"
echo "⚠️ 이 작업은 시간이 오래 걸릴 수 있습니다 (15-45분)"

# 모델 다운로드
retry_count=0
while [ $retry_count -lt $MAX_RETRY ]; do
    echo "다운로드 시도 $((retry_count + 1))/$MAX_RETRY..."
    
    # 다운로드 명령 실행 (진행률 표시 포함)
    curl -X POST "$LLM_SERVER_URL/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$LLM_MODEL_NAME\"}" \
        --max-time 3600 | while IFS= read -r line; do
        echo "$line"
        # 완료 메시지 확인
        if echo "$line" | grep -q '"status":"success"'; then
            echo "✅ 모델 다운로드 완료!"
            break
        fi
    done
    
    # 다운로드 완료 확인
    sleep 5
    if curl -s "$LLM_SERVER_URL/api/tags" | grep -q "\"name\":\"$LLM_MODEL_NAME\""; then
        echo "🎉 모델 설치 및 초기화 완료!"
        exit 0
    fi
    
    retry_count=$((retry_count + 1))
    if [ $retry_count -lt $MAX_RETRY ]; then
        echo "❌ 다운로드 실패. $RETRY_DELAY 초 후 재시도..."
        sleep $RETRY_DELAY
    fi
done

echo "❌ 모델 다운로드 실패: 최대 재시도 횟수 초과"
exit 1