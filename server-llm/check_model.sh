#!/bin/sh

# 모델이 설치되었는지 확인하는 간단한 헬스체크 스크립트
# 종료 코드 0: 정상 (모델 설치 완료)
# 종료 코드 1: 실패 (모델 미설치)

# Ollama 서버에서 모델 목록 가져오기
models=$(curl -s --connect-timeout 5 "$LLM_SERVER_URL/api/tags" 2>/dev/null)

# 모델이 존재하는지 확인
if echo "$models" | grep -q "\"name\":\"$LLM_MODEL_NAME\""; then
    echo "✅ 모델 $LLM_MODEL_NAME 설치 완료"
    exit 0
else
    echo "⏳ 모델 $LLM_MODEL_NAME 다운로드 중..."
    exit 1
fi