#!/bin/bash

echo "📥 RAG 대화 이력 CSV 내보내기 (SQLite3 직접 사용)"
echo "========================================"

# UTF-8 환경 설정
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# 환경변수 로드
if [ -f ".env.global" ]; then
    source .env.global
else
    echo "❌ .env.global 파일이 없습니다."
    exit 1
fi

# CSV 파일명 생성
CSV_FILE="rag_conversations_$(date +%Y%m%d_%H%M%S).csv"
DB_PATH="server-logging/data/rag_logging.db"

echo "📊 데이터베이스 확인..."

if [ ! -f "$DB_PATH" ]; then
    echo "❌ 데이터베이스 파일을 찾을 수 없습니다: $DB_PATH"
    exit 1
fi

echo "✅ 데이터베이스 파일 확인: $DB_PATH"

# 데이터 개수 확인
TOTAL_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM rag_conversations;")
echo "📋 총 대화 수: $TOTAL_COUNT 개"

if [ "$TOTAL_COUNT" -eq 0 ]; then
    echo "⚠️ 저장된 대화가 없습니다."
    exit 0
fi

echo "📝 CSV 파일 생성 중: $CSV_FILE"

# BOM 추가로 Excel 한글 호환성 향상
printf '\xEF\xBB\xBF' > "$CSV_FILE"

# CSV 헤더 작성
echo "질문시간,질문,RAG답변,RAG찾은Context들,시스템프롬프트" >> "$CSV_FILE"

# Python 스크립트로 안전한 CSV 생성
python3 << 'EOF' >> "$CSV_FILE"
# -*- coding: utf-8 -*-
import sqlite3
import json
import csv
import sys
from datetime import datetime
import os

# UTF-8 출력 보장
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def clean_text(text):
    """CSV 안전한 텍스트 정리"""
    if not text:
        return ''
    # 한글 보존하면서 CSV 문제 문자만 처리
    result = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    # 쌍따옴표 이스케이프
    result = result.replace('"', '""')
    return result

def extract_contexts(contexts_json):
    """Context JSON에서 요약 추출"""
    if not contexts_json or contexts_json == 'null':
        return '컨텍스트 정보 없음'
    
    try:
        contexts = json.loads(contexts_json)
        if isinstance(contexts, list):
            content_list = []
            for ctx in contexts[:3]:  # 최대 3개
                if isinstance(ctx, dict) and 'content' in ctx:
                    content = clean_text(ctx['content'][:100])
                    if content:
                        content_list.append(content)
            
            if content_list:
                result = ' | '.join(content_list)
                return result[:200] + '...' if len(result) > 200 else result
            else:
                return '컨텍스트 내용 없음'
        else:
            return '컨텍스트 형식 오류'
    except Exception as e:
        return f'컨텍스트 파싱 오류'

def format_datetime(created_at):
    """날짜 시간 형식 변환"""
    try:
        if 'T' in created_at:
            # ISO 8601 형식 처리
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return created_at[:19]
    except:
        return str(created_at)[:19].replace('T', ' ')

# 데이터베이스 연결
db_path = 'server-logging/data/rag_logging.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 데이터 조회
cursor.execute('''
    SELECT 
        created_at,
        user_question,
        rag_response,
        contexts
    FROM rag_conversations 
    WHERE user_question IS NOT NULL 
    AND rag_response IS NOT NULL
    ORDER BY created_at DESC
''')

rows = cursor.fetchall()

# CSV 라이터 설정 (UTF-8 with BOM)
import io
output = io.StringIO()
writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\n')

# 각 행 처리
for row in rows:
    created_at, user_question, rag_response, contexts = row
    
    # 데이터 정리
    formatted_time = format_datetime(created_at)
    clean_question = clean_text(user_question)
    clean_response = clean_text(rag_response)
    context_summary = extract_contexts(contexts)
    system_prompt = 'Samsung 매장 상담원으로서 전문적이고 친근하게 고객에게 제품 정보를 제공합니다.'
    
    # CSV 행 작성
    writer.writerow([
        formatted_time,
        clean_question,
        clean_response, 
        context_summary,
        system_prompt
    ])

# 결과 출력
csv_content = output.getvalue()
print(csv_content, end='')

conn.close()
output.close()
EOF

# 결과 확인 및 요약
if [ -f "$CSV_FILE" ]; then
    CSV_SIZE=$(du -h "$CSV_FILE" | cut -f1)
    CSV_LINES=$(wc -l < "$CSV_FILE")
    DATA_LINES=$((CSV_LINES - 1))  # 헤더 제외
    
    echo ""
    echo "✅ CSV 파일 생성 완료!"
    echo "📁 파일명: $CSV_FILE"
    echo "📏 파일 크기: $CSV_SIZE"
    echo "📊 데이터 행 수: $DATA_LINES 개"
    echo ""
    
    if [ "$DATA_LINES" -gt 0 ]; then
        echo "🔧 파일 정보:"
        file "$CSV_FILE" | grep -o "UTF-8.*" || echo "인코딩: UTF-8 with BOM"
        echo ""
        
        echo "📋 첫 번째 대화 미리보기:"
        echo "----------------------------------------"
        # 헤더와 첫 번째 데이터 행만 표시 (한글 확인용)
        head -2 "$CSV_FILE" | tail -1 | cut -d',' -f1-2 | sed 's/"//g'
        echo "----------------------------------------"
        echo ""

        echo "💡 Excel에서 한글 깨짐 방지:"
        echo "  1️⃣ 파일을 바로 더블클릭해서 열기 (BOM으로 자동 인식)"
        echo "  2️⃣ 또는 Excel → 데이터 → 텍스트에서 → UTF-8 선택"
        echo ""
        echo "📊 Google Sheets: 가져오기 → 파일 업로드 → UTF-8 선택"
        echo ""
        echo "🔍 파일 위치: $(pwd)/$CSV_FILE"
    else
        echo "⚠️ CSV 파일이 생성되었지만 데이터가 없습니다."
    fi
else
    echo "❌ CSV 파일 생성 실패"
    exit 1
fi