### 설정 파일 (`evaluation/config.yaml`)

```yaml
# 서버 정보
servers:
  rag_server_url: "http://112.148.37.41:1886"
  llm_server_url: "http://112.148.37.41:1884"

# 모델 설정 (RAGAS 평가용 LLM만 설정)
models:
  rag_model_name: "rag-cheeseade:latest"
  llm_model_name: "gemma3:27b-it-q4_K_M"
  evaluator_model: "gemma3:27b-it-q4_K_M"  # RAGAS 평가용 (내부 LLM 서버)
  # 임베딩은 RAG 서버 내부 것을 자동으로 사용 (설정 불필요)

# 평가 메트릭
ragas_metrics:
  - "faithfulness"      # 사실 기반성
  - "answer_relevancy"   # 답변 관련성
  - "context_precision"  # 컨텍스트 정확도
  - "context_recall"     # 컨텍스트 재현율
  # ... 기타 메트릭

# 성능 임계값
thresholds:
  faithfulness: 0.8
  answer_relevancy: 0.75
  overall_score: 0.75
```

### RAG 서버 구성요소 변경 워크플로우

1. **RAG 서버 구성 변경**
   ```bash
   # 예: 청킹 전략 변경
   vi server-rag/chunking/chunking_md.py
   
   # 예: 임베딩 모델 변경
   vi server-rag/embedding/bge_m3.py
   
   # 예: 리트리버 설정 변경
   vi server-rag/retriever/retriever.py
   ```

2. **RAG 서버 재시작**
   ```bash
   ./deploy.sh
   ```

3. **RAGAS 재평가 (코드 수정 불필요)**
   ```bash
   ./run_evaluation.sh
   ```

### 성능 최적화 실험 예시

```bash
# 실험 1: 청킹 크기 변경
# → server-rag/chunking/ 수정 → ./deploy.sh → ./run_evaluation.sh

# 실험 2: 임베딩 모델 변경  
# → server-rag/embedding/ 수정 → ./deploy.sh → ./run_evaluation.sh

# 실험 3: 검색 파라미터 튜닝
# → server-rag/retriever/ 수정 → ./deploy.sh → ./run_evaluation.sh

# 결과 비교: evaluation/results/ 폴더의 HTML 보고서들 비교
```# CHEESEADE RAG 시스템 RAGAS 평가

RAGAS 프레임워크를 사용하여 CHEESEADE RAG 시스템의 성능을 종합적으로 평가하는 도구입니다.

## 📋 목차

- [개요](#개요)
- [설치 및 설정](#설치-및-설정)
- [빠른 시작](#빠른-시작)
- [상세 사용법](#상세-사용법)
- [평가 메트릭](#평가-메트릭)
- [결과 해석](#결과-해석)
- [문제 해결](#문제-해결)

## 🎯 개요

### 주요 기능

- **종합 성능 평가**: RAGAS의 7가지 핵심 메트릭으로 RAG 시스템 평가
- **대규모 테스트**: 1000개 질문으로 체계적인 성능 검증
- **RAG 서버 연동**: RAG 서버의 모든 구성요소 변경사항 자동 반영
- **시각화 대시보드**: 직관적인 차트와 인터랙티브 대시보드
- **개선 권장사항**: AI 기반 성능 개선 제안

### 평가 아키텍처

```
질문 데이터 → RAG 서버 → RAGAS 평가 → 결과 분석 → 보고서 생성
     ↓           ↓             ↓           ↓           ↓
   1000개    답변+컨텍스트   7개 메트릭   카테고리 분석  HTML/Excel
   질문집    (청킹/임베딩/리트리버)                     대시보드
```

**핵심 장점**: RAG 서버의 청킹, 임베딩, 리트리버를 변경해도 RAGAS 코드 수정 불필요!

### RAG 서버 구성요소 자동 반영

- ✅ **청킹 전략 변경** → 자동 반영 (코드 수정 불필요)
- ✅ **임베딩 모델 변경** → 자동 반영 (코드 수정 불필요)  
- ✅ **리트리버 설정 변경** → 자동 반영 (코드 수정 불필요)
- ✅ **검색 파라미터 튜닝** → 자동 반영 (코드 수정 불필요)

## 🛠 설치 및 설정

### 1. 필수 요구사항

- Python 3.8 이상
- CHEESEADE RAG 서버 실행 중
- 충분한 디스크 공간 (최소 1GB)

### 2. 패키지 설치

```bash
# 평가용 패키지 설치
pip install -r requirements_evaluation.txt

# 또는 개별 설치
pip install ragas datasets pandas requests matplotlib seaborn plotly jinja2
```

### 3. 환경 설정

```bash
# 환경변수 설정 (선택적)
export OPENAI_API_KEY="your-openai-api-key"  # RAGAS 평가용
```

### 4. 디렉토리 구조 생성

```
evaluation/
├── config.yaml              # 설정 파일
├── data/
│   └── questions_1000.xlsx  # 평가 질문
├── results/
│   ├── charts/              # 생성된 차트
│   └── reports/             # HTML/Excel 보고서
└── logs/                    # 실행 로그
```

## 🚀 빠른 시작

### 방법 1: 자동 실행 스크립트 (권장)

```bash
# 실행 권한 부여
chmod +x run_evaluation.sh

# 자동 질문 로드 + 전체 평가 (엑셀 파일 자동 검색)
./run_evaluation.sh

# 특정 엑셀 파일에서 질문 로드
./run_evaluation.sh --excel-file your_questions.xlsx

# 빠른 테스트 (50개 질문)
./run_evaluation.sh --quick

# 샘플 평가 (100개 질문)
./run_evaluation.sh --sample-size 100
```

### 방법 2: Python 직접 실행

```bash
# 1. 기존 엑셀에서 질문 로드
python3 evaluation/create_sample_questions.py --excel-file your_questions.xlsx

# 또는 샘플 질문 생성 (엑셀 파일이 없는 경우)
python3 evaluation/create_sample_questions.py

# 2. 평가 실행
python3 evaluation/run_evaluation.py

# 3. 샘플 평가
python3 evaluation/run_evaluation.py --sample-size 100
```

### 질문 데이터 준비 방법

#### 1. 기존 엑셀 파일 사용 (권장)
기존에 준비된 1000개 질문이 담긴 엑셀 파일을 사용할 수 있습니다:

```bash
# 특정 엑셀 파일 사용
python3 evaluation/create_sample_questions.py --excel-file questions.xlsx

# 또는 실행 스크립트에서 직접 지정
./run_evaluation.sh --excel-file questions.xlsx
```

**엑셀 파일 형식 요구사항:**
| 컬럼명 (가능한 이름들) | 설명 | 예시 |
|----------------------|------|------|
| question, questions, 질문, query | 평가할 질문 | "카메라 화소는 얼마인가요?" |
| answer, expected_answer, 답변, 정답 | 예상 답변 | "108MP 메인 카메라입니다" |
| category, 카테고리, type, class | 질문 카테고리 | "카메라 기능" |

#### 2. 자동 엑셀 파일 검색
현재 디렉토리에 `.xlsx` 파일이 있으면 자동으로 감지하고 사용 여부를 묻습니다:

```bash
# 자동 검색 실행
./run_evaluation.sh
# → 엑셀 파일 발견시 사용 여부 선택 가능
```

#### 3. 샘플 데이터 자동 생성
엑셀 파일이 없거나 지정하지 않으면 자동으로 1000개 샘플 질문을 생성합니다.

## 📊 상세 사용법

### 설정 파일 (`evaluation/config.yaml`)

```yaml
# 서버 정보
servers:
  rag_server_url: "http://112.148.37.41:1886"
  llm_server_url: "http://112.148.37.41:1884"

# 평가 메트릭
ragas_metrics:
  - "faithfulness"      # 사실 기반성
  - "answer_relevancy"   # 답변 관련성
  - "context_precision"  # 컨텍스트 정확도
  - "context_recall"     # 컨텍스트 재현율
  # ... 기타 메트릭

# 성능 임계값
thresholds:
  faithfulness: 0.8
  answer_relevancy: 0.75
  overall_score: 0.75
```

### 명령행 옵션

```bash
# 기본 실행
python3 evaluation/run_evaluation.py

# 옵션 사용
python3 evaluation/run_evaluation.py \
  --sample-size 500 \           # 500개 질문만 평가
  --skip-charts \               # 차트 생성 건너뛰기
  --output-dir custom_results \ # 사용자 정의 출력 디렉토리
  --verbose                     # 상세 로그
```

### 질문 데이터 형식

Excel/CSV 파일에 다음 컬럼이 필요합니다:

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| question | 평가할 질문 | "카메라 화소는 얼마인가요?" |
| expected_answer | 예상 답변 | "108MP 메인 카메라입니다" |
| category | 질문 카테고리 | "카메라 기능" |

## 📈 평가 메트릭

### RAGAS 핵심 메트릭

| 메트릭 | 설명 | 임계값 |
|--------|------|--------|
| **Faithfulness** | 답변이 제공된 컨텍스트에 근거하는 정도 | 0.8 |
| **Answer Relevancy** | 답변이 질문과 얼마나 관련있는지 | 0.75 |
| **Context Precision** | 검색된 컨텍스트의 정확도 | 0.7 |
| **Context Recall** | 필요한 모든 컨텍스트를 검색했는지 | 0.7 |
| **Context Relevancy** | 검색된 컨텍스트의 관련성 | 0.65 |
| **Answer Similarity** | 답변과 정답의 유사도 | 0.7 |
| **Answer Correctness** | 답변의 전반적인 정확성 | 0.75 |

### 성능 등급

- 🟢 **우수** (0.8 이상): 프로덕션 사용 가능
- 🟡 **양호** (0.6-0.8): 튜닝 후 사용 권장  
- 🔴 **개선필요** (0.6 미만): 시스템 개선 필요

## 📊 결과 해석

### 생성되는 파일들

```
evaluation/results/
├── evaluation_results_20241201_143022.json     # 상세 결과 (JSON)
├── evaluation_results_20241201_143022.xlsx     # 상세 결과 (Excel)
├── reports/
│   ├── evaluation_report_20241201_143022.html  # HTML 보고서
│   └── evaluation_summary_20241201_143022.txt  # 텍스트 요약
└── charts/
    ├── metrics_overview.png                    # 메트릭 개요
    ├── category_analysis.png                   # 카테고리 분석
    ├── summary_report.png                      # 요약 보고서
    └── interactive_dashboard.html              # 인터랙티브 대시보드
```

### HTML 보고서 활용

1. **전체 성능 점수**: 시스템의 종합적인 성능 확인
2. **메트릭별 성능**: 각 메트릭의 상세 분석
3. **카테고리별 성능**: 질문 유형별 강약점 파악
4. **개선 권장사항**: 우선순위별 구체적인 개선 방안

### 대시보드 사용법

인터랙티브 대시보드(`interactive_dashboard.html`)에서는:

- 📊 실시간 메트릭 비교
- 🏷️ 카테고리별 드릴다운
- 📈 성능 트렌드 분석
- 🔍 개별 질문 상세 검토

## 🔧 문제 해결

### 일반적인 문제들

#### 1. 서버 연결 실패
```bash
❌ RAG 서버 연결 실패
```
**해결방법:**
- CHEESEADE RAG 서버가 실행 중인지 확인
- `./deploy.sh`로 서버 시작
- `./health-check.sh`로 상태 확인

#### 2. 패키지 설치 오류
```bash
❌ 패키지 설치 실패
```
**해결방법:**
```bash
# 가상환경 생성 권장
python3 -m venv eval_env
source eval_env/bin/activate
pip install --upgrade pip
pip install -r requirements_evaluation.txt
```

#### 3. RAGAS 평가 실패
```bash
❌ RAGAS 평가 실패
```
**해결방법:**
- OpenAI API 키 설정 확인: `export OPENAI_API_KEY="your-key"`
- 네트워크 연결 확인
- 평가 모델을 로컬 모델로 변경

#### 4. 메모리 부족
```bash
❌ 메모리 부족 오류
```
**해결방법:**
```bash
# 배치 크기 줄이기
python3 evaluation/run_evaluation.py --sample-size 100

# config.yaml에서 설정 조정
evaluation:
  batch_size: 5        # 기본값: 10
  max_workers: 2       # 기본값: 4
```

### 로그 확인

```bash
# 최신 로그 확인
tail -f evaluation/logs/evaluation_*.log

# 에러 로그만 필터링
grep -i error evaluation/logs/evaluation_*.log
```

### 성능 최적화

#### 빠른 평가를 위한 설정

```yaml
# config.yaml
evaluation:
  batch_size: 20           # 배치 크기 증가
  max_workers: 8           # 워커 수 증가
  sample_size: 500         # 샘플 크기 제한

output:
  generate_charts: false   # 차트 생성 건너뛰기
```

#### GPU 사용 설정

```bash
# CUDA 사용 확인
nvidia-smi

# GPU 메모리 최적화
export CUDA_VISIBLE_DEVICES=0
```

## 📞 지원 및 문의

### 개발팀 연락처
- **기술 지원**: CHEESEADE 개발팀
- **이슈 리포트**: GitHub Issues
- **문서 개선**: Pull Request 환영

### 추가 리소스
- [RAGAS 공식 문서](https://docs.ragas.io/)
- [CHEESEADE RAG 시스템 문서](../docs/)
- [성능 튜닝 가이드](../docs/performance-tuning.md)

---

**🎯 성공적인 평가를 위한 체크리스트**

- [ ] CHEESEADE RAG 서버 실행 확인
- [ ] 질문 데이터 준비 (1000개)
- [ ] 평가 환경 설정 완료
- [ ] 충분한 시스템 리소스 확보
- [ ] 네트워크 연결 안정성 확인

**✨ 평가 완료 후 할 일**

- [ ] HTML 보고서 검토
- [ ] 개선 권장사항 우선순위 검토
- [ ] 시스템 튜닝 계획 수립
- [ ] 정기 평가 일정 설정