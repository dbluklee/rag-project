#!/bin/bash

echo "🔍 로깅 서버 디버깅 시작"
echo "========================================"

# 1. 컨테이너 상태 확인
echo "📦 컨테이너 상태:"
docker ps -a --filter "name=cheeseade-logging" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 2. 로그 확인 (최근 50줄)
echo "📋 로깅 서버 로그 (최근 50줄):"
echo "----------------------------------------"
docker logs --tail 50 cheeseade-logging-api 2>&1
echo ""

# 3. 포트 바인딩 확인
echo "🔌 포트 바인딩 상태:"
docker port cheeseade-logging-api 2>/dev/null || echo "포트 정보 없음"
echo ""

# 4. 컨테이너 내부 프로세스 확인
echo "⚙️ 컨테이너 내부 프로세스:"
docker exec cheeseade-logging-api ps aux 2>/dev/null || echo "프로세스 확인 실패"
echo ""

# 5. 컨테이너 내부에서 헬스체크 테스트
echo "🧪 컨테이너 내부 헬스체크:"
docker exec cheeseade-logging-api curl -f http://localhost:7000/health 2>/dev/null || echo "내부 헬스체크 실패"
echo ""

# 6. 디스크 공간 확인
echo "💾 디스크 공간:"
df -h | grep -E "(Use%|/app|tmpfs)"
echo ""

# 7. 메모리 사용량 확인
echo "🧠 메모리 사용량:"
free -h
echo ""

# 8. Docker 컨테이너 리소스 사용량
echo "📊 컨테이너 리소스:"
docker stats --no-stream cheeseade-logging-api 2>/dev/null || echo "리소스 정보 없음"
echo ""

# 9. 네트워크 연결 확인
echo "🌐 네트워크 연결:"
docker exec cheeseade-logging-api netstat -tuln 2>/dev/null | grep 7000 || echo "포트 7000 바인딩 없음"
echo ""

# 10. Python 프로세스 상세 확인
echo "🐍 Python 프로세스:"
docker exec cheeseade-logging-api pgrep -af python 2>/dev/null || echo "Python 프로세스 없음"
echo ""

echo "🔍 추가 확인 명령어:"
echo "1. 컨테이너 재시작: docker restart cheeseade-logging-api"
echo "2. 컨테이너 쉘 접속: docker exec -it cheeseade-logging-api /bin/bash"
echo "3. 컨테이너 재빌드: cd server-logging && docker compose up --build -d"
echo "4. 전체 로그 확인: docker logs cheeseade-logging-api"
