#!/usr/bin/env python3
"""
CHEESEADE RAG 시스템 RAGAS 평가 메인 스크립트
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from evaluator import CheeseadeRAGEvaluator
from ragas_runner import RAGASRunner
from visualization import RAGASVisualizer
from report_generator import ReportGenerator

def main():
    """메인 실행 함수"""
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description='CHEESEADE RAG 시스템 RAGAS 평가')
    parser.add_argument('--config', type=str, default='evaluation/config.yaml',
                       help='설정 파일 경로')
    parser.add_argument('--questions', type=str,
                       help='질문 파일 경로 (설정 파일 오버라이드)')
    parser.add_argument('--sample-size', type=int,
                       help='샘플 크기 (전체 대신 일부만 평가)')
    parser.add_argument('--skip-charts', action='store_true',
                       help='차트 생성 건너뛰기')
    parser.add_argument('--output-dir', type=str,
                       help='출력 디렉토리 (설정 파일 오버라이드)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='상세 로그 출력')
    
    args = parser.parse_args()
    
    print("🚀 CHEESEADE RAG 시스템 RAGAS 평가 시작")
    print("=" * 60)
    
    try:
        # 1. 평가기 초기화
        print("🔧 평가 시스템 초기화 중...")
        evaluator = CheeseadeRAGEvaluator(args.config)
        
        # 명령행 인자로 설정 오버라이드
        if args.questions:
            evaluator.config['data_paths']['questions_file'] = args.questions
        if args.sample_size:
            evaluator.config['evaluation']['sample_size'] = args.sample_size
        if args.output_dir:
            evaluator.config['data_paths']['output_dir'] = args.output_dir
        if args.skip_charts:
            evaluator.config['output']['generate_charts'] = False
        if args.verbose:
            evaluator.config['logging']['level'] = 'DEBUG'
        
        # 2. 서버 상태 확인
        print("\n🔍 서버 상태 확인 중...")
        if not evaluator.check_server_health():
            print("❌ 서버 상태 확인 실패. 평가를 중단합니다.")
            return 1
        
        # 3. 질문 데이터 로드
        print("\n📄 질문 데이터 로드 중...")
        questions_df = evaluator.load_questions()
        if questions_df.empty:
            print("❌ 질문 데이터가 없습니다.")
            return 1
        
        print(f"✅ {len(questions_df)}개 질문 로드 완료")
        
        # 4. 질문 처리 (RAG 시스템에서 답변 생성)
        print("\n🤖 RAG 시스템으로 답변 생성 중...")
        individual_results = evaluator.process_questions_batch(questions_df)
        
        successful_count = len([r for r in individual_results if r.get('success', False)])
        print(f"✅ 답변 생성 완료: {successful_count}/{len(individual_results)}개 성공")
        
        if successful_count == 0:
            print("❌ 성공한 답변이 없습니다. 평가를 중단합니다.")
            return 1
        
        # 5. RAGAS 데이터셋 준비
        print("\n📊 RAGAS 평가 데이터셋 준비 중...")
        dataset = evaluator.prepare_ragas_dataset(individual_results)
        
        if len(dataset) == 0:
            print("❌ RAGAS 데이터셋이 비어있습니다.")
            return 1
        
        # 6. RAGAS 평가 실행
        print(f"\n🎯 RAGAS 평가 실행 중... ({len(dataset)}개 항목)")
        print(f"🔄 RAG 서버의 구성 (청킹/임베딩/리트리버)이 결과에 자동 반영됩니다")
        print(f"📊 RAGAS는 RAG 서버가 제공한 답변과 컨텍스트만 평가합니다")
        ragas_runner = RAGASRunner(evaluator.config, evaluator.logger)
        ragas_results = ragas_runner.run_evaluation(dataset)
        
        # 7. 카테고리별 분석
        print("\n🏷️ 카테고리별 성능 분석 중...")
        category_analysis = ragas_runner.analyze_by_category(
            dataset, ragas_results, individual_results
        )
        
        # 8. 개선 권장사항 생성
        print("\n💡 개선 권장사항 생성 중...")
        recommendations = ragas_runner.generate_recommendations(ragas_results)
        
        # 9. 시각화 생성
        chart_paths = []
        if evaluator.config['output'].get('generate_charts', True):
            print("\n📈 시각화 차트 생성 중...")
            visualizer = RAGASVisualizer(evaluator.config, evaluator.logger)
            
            # 메트릭 개요 차트
            chart_path = visualizer.create_metrics_overview(ragas_results)
            if chart_path:
                chart_paths.append(chart_path)
            
            # 카테고리 분석 차트
            if category_analysis:
                chart_path = visualizer.create_category_analysis(category_analysis, ragas_results)
                if chart_path:
                    chart_paths.append(chart_path)
            
            # 요약 보고서 차트
            chart_path = visualizer.create_summary_report(ragas_results, recommendations)
            if chart_path:
                chart_paths.append(chart_path)
            
            # 인터랙티브 대시보드
            dashboard_path = visualizer.create_interactive_dashboard(
                ragas_results, category_analysis, individual_results
            )
            if dashboard_path:
                chart_paths.append(dashboard_path)
        
        # 10. 결과 저장 및 보고서 생성
        print("\n📝 결과 저장 및 보고서 생성 중...")
        report_generator = ReportGenerator(evaluator.config, evaluator.logger)
        
        # JSON 결과 저장
        json_path = report_generator.save_json_results(
            ragas_results, category_analysis, recommendations, individual_results
        )
        
        # Excel 결과 저장
        if evaluator.config['output'].get('export_to_excel', True):
            excel_path = report_generator.save_excel_results(
                ragas_results, category_analysis, individual_results
            )
        
        # HTML 보고서 생성
        if evaluator.config['output'].get('generate_html_report', True):
            html_path = report_generator.generate_html_report(
                ragas_results, category_analysis, recommendations, chart_paths
            )
        
        # 텍스트 요약 생성
        summary_path = report_generator.generate_summary_text(ragas_results, recommendations)
        
        # 11. 최종 결과 출력
        print("\n" + "=" * 60)
        print("🎉 CHEESEADE RAG 시스템 평가 완료!")
        print("=" * 60)
        
        # 전체 성능 요약
        overall_score = ragas_results.get('evaluation_summary', {}).get('overall_score', 0)
        overall_threshold = evaluator.config['thresholds'].get('overall_score', 0.75)
        performance_status = "✅ 우수" if overall_score >= 0.8 else "🟡 양호" if overall_score >= 0.6 else "❌ 개선필요"
        
        print(f"📊 전체 성능 점수: {overall_score:.4f} / {overall_threshold:.4f}")
        print(f"🎯 성능 등급: {performance_status}")
        
        # 메트릭 요약
        performance_analysis = ragas_results.get('performance_analysis', {})
        passed_metrics = performance_analysis.get('passed_metrics', 0)
        total_metrics = performance_analysis.get('total_metrics', 0)
        print(f"📈 메트릭 통과율: {passed_metrics}/{total_metrics} ({(passed_metrics/total_metrics*100):.1f}%)")
        
        # 권장사항 요약
        high_priority_count = len(recommendations.get('high_priority', []))
        medium_priority_count = len(recommendations.get('medium_priority', []))
        print(f"💡 개선 권장사항: 높음 {high_priority_count}개, 중간 {medium_priority_count}개")
        
        # 생성된 파일들
        print(f"\n📁 생성된 파일들:")
        if json_path:
            print(f"   📄 JSON 결과: {json_path}")
        if 'excel_path' in locals() and excel_path:
            print(f"   📊 Excel 결과: {excel_path}")
        if 'html_path' in locals() and html_path:
            print(f"   🌐 HTML 보고서: {html_path}")
        if summary_path:
            print(f"   📝 텍스트 요약: {summary_path}")
        
        if chart_paths:
            print(f"   📈 차트 파일: {len(chart_paths)}개")
            for chart_path in chart_paths:
                print(f"     - {Path(chart_path).name}")
        
        # 다음 단계 제안
        print(f"\n🔄 다음 단계:")
        if high_priority_count > 0:
            print(f"   1. 높은 우선순위 권장사항 {high_priority_count}개 즉시 검토")
        if overall_score < overall_threshold:
            print(f"   2. 전체 점수 개선을 위한 시스템 튜닝")
        print(f"   3. HTML 보고서 확인: {html_path if 'html_path' in locals() else '생성 안됨'}")
        if chart_paths:
            dashboard = [p for p in chart_paths if 'dashboard' in p]
            if dashboard:
                print(f"   4. 인터랙티브 대시보드 확인: {dashboard[0]}")
        
        # 성공/실패 반환
        if overall_score >= overall_threshold and high_priority_count == 0:
            print(f"\n🎊 축하합니다! RAG 시스템이 모든 기준을 통과했습니다.")
            return 0
        else:
            print(f"\n⚠️ 개선이 필요한 영역이 있습니다. 권장사항을 검토하세요.")
            return 1
        
    except KeyboardInterrupt:
        print(f"\n\n⏸️ 사용자에 의해 평가가 중단되었습니다.")
        return 2
    
    except Exception as e:
        print(f"\n\n❌ 평가 중 오류 발생: {str(e)}")
        print(f"자세한 로그는 evaluation/logs/ 디렉토리를 확인하세요.")
        return 3


def validate_environment():
    """실행 환경 검증"""
    print("🔍 실행 환경 검증 중...")
    
    # 필수 디렉토리 확인
    required_dirs = [
        'evaluation',
        'evaluation/data',
        'evaluation/results',
        'evaluation/logs'
    ]
    
    for directory in required_dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # 필수 파일 확인
    config_file = Path('evaluation/config.yaml')
    if not config_file.exists():
        print(f"❌ 설정 파일이 없습니다: {config_file}")
        print("evaluation/config.yaml 파일을 생성하세요.")
        return False
    
    # Python 패키지 확인
    required_packages = [
        'ragas', 'datasets', 'pandas', 'requests', 
        'matplotlib', 'seaborn', 'plotly', 'jinja2'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 필수 패키지가 설치되지 않았습니다: {', '.join(missing_packages)}")
        print("pip install -r requirements_evaluation.txt 를 실행하세요.")
        return False
    
    print("✅ 실행 환경 검증 완료")
    return True


def show_help():
    """도움말 표시"""
    help_text = """
🤖 CHEESEADE RAG 시스템 RAGAS 평가 도구

사용법:
    python evaluation/run_evaluation.py [옵션]

주요 옵션:
    --config PATH           설정 파일 경로 (기본: evaluation/config.yaml)
    --questions PATH        질문 파일 경로 
    --sample-size N         샘플 크기 (전체 대신 N개만 평가)
    --skip-charts          차트 생성 건너뛰기
    --output-dir PATH       출력 디렉토리
    --verbose, -v          상세 로그 출력

사용 예시:
    # 기본 실행
    python evaluation/run_evaluation.py
    
    # 100개 질문만 샘플링하여 평가
    python evaluation/run_evaluation.py --sample-size 100
    
    # 차트 생성 없이 빠른 평가
    python evaluation/run_evaluation.py --skip-charts
    
    # 사용자 정의 질문 파일로 평가
    python evaluation/run_evaluation.py --questions my_questions.xlsx

필수 준비사항:
    1. evaluation/config.yaml 설정 파일 생성
    2. evaluation/data/questions_1000.xlsx 질문 파일 준비
    3. pip install -r requirements_evaluation.txt
    4. CHEESEADE RAG 서버들이 실행 중이어야 함

출력 파일:
    - JSON 결과: evaluation/results/evaluation_results_YYYYMMDD_HHMMSS.json
    - Excel 결과: evaluation/results/evaluation_results_YYYYMMDD_HHMMSS.xlsx  
    - HTML 보고서: evaluation/results/reports/evaluation_report_YYYYMMDD_HHMMSS.html
    - 차트들: evaluation/results/charts/
    - 로그: evaluation/logs/evaluation_YYYYMMDD_HHMMSS.log

문의사항:
    CHEESEADE 개발팀
    """
    print(help_text)


if __name__ == "__main__":
    # 환경 검증
    if not validate_environment():
        sys.exit(1)
    
    # 도움말 요청 확인
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_help()
        sys.exit(0)
    
    # 메인 실행
    exit_code = main()
    
    # 종료 메시지
    if exit_code == 0:
        print("\n🎉 평가가 성공적으로 완료되었습니다!")
    elif exit_code == 1:
        print("\n⚠️ 평가는 완료되었지만 개선이 필요합니다.")
    elif exit_code == 2:
        print("\n⏸️ 평가가 중단되었습니다.")
    else:
        print("\n❌ 평가 중 오류가 발생했습니다.")
    
    sys.exit(exit_code)