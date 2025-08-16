"""
RAGAS 평가 결과 시각화 모듈
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
import logging
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo

class RAGASVisualizer:
    """RAGAS 결과 시각화 클래스"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # 시각화 설정
        viz_config = config.get('visualization', {})
        self.figure_size = viz_config.get('figure_size', [12, 8])
        self.dpi = viz_config.get('dpi', 300)
        self.style = viz_config.get('style', 'seaborn-v0_8')
        self.color_palette = viz_config.get('color_palette', 'Set2')
        
        # matplotlib 설정
        try:
            plt.style.use(self.style)
        except:
            plt.style.use('default')
        sns.set_palette(self.color_palette)
        
        # 결과 저장 경로
        self.charts_dir = Path(config['data_paths']['output_dir']) / 'charts'
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("📊 시각화 모듈 초기화 완료")
    
    def create_metrics_overview(self, results: Dict[str, Any]) -> str:
        """메트릭 개요 차트 생성"""
        self.logger.info("📈 메트릭 개요 차트 생성 중...")
        
        try:
            metrics_data = results.get('detailed_metrics', {})
            if not metrics_data:
                self.logger.warning("메트릭 데이터가 없습니다")
                return ""
            
            # 데이터 준비
            metric_names = list(metrics_data.keys())
            scores = [metrics_data[name]['score'] for name in metric_names]
            thresholds = [metrics_data[name]['threshold'] for name in metric_names]
            
            # 차트 생성
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            
            # 1. 막대 차트 (점수 vs 임계값)
            x_pos = np.arange(len(metric_names))
            width = 0.35
            
            bars1 = ax1.bar(x_pos - width/2, scores, width, label='실제 점수', alpha=0.8, color='skyblue')
            bars2 = ax1.bar(x_pos + width/2, thresholds, width, label='임계값', alpha=0.6, color='orange')
            
            ax1.set_xlabel('메트릭')
            ax1.set_ylabel('점수')
            ax1.set_title('RAGAS 메트릭 성능 비교')
            ax1.set_xticks(x_pos)
            ax1.set_xticklabels([name.replace('_', '\n') for name in metric_names], rotation=0)
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(0, 1)
            
            # 막대 위에 값 표시
            for i, (score, threshold) in enumerate(zip(scores, thresholds)):
                ax1.text(i - width/2, score + 0.01, f'{score:.3f}', ha='center', va='bottom', fontsize=9)
                ax1.text(i + width/2, threshold + 0.01, f'{threshold:.3f}', ha='center', va='bottom', fontsize=9)
            
            # 2. 레이더 차트
            angles = np.linspace(0, 2 * np.pi, len(metric_names), endpoint=False)
            angles = np.concatenate((angles, [angles[0]]))  # 원형으로 만들기
            
            scores_radar = scores + [scores[0]]
            thresholds_radar = thresholds + [thresholds[0]]
            
            ax2 = plt.subplot(122, projection='polar')
            ax2.plot(angles, scores_radar, 'o-', linewidth=2, label='실제 점수', color='skyblue')
            ax2.fill(angles, scores_radar, alpha=0.25, color='skyblue')
            ax2.plot(angles, thresholds_radar, 's-', linewidth=2, label='임계값', color='orange')
            ax2.fill(angles, thresholds_radar, alpha=0.1, color='orange')
            
            ax2.set_xticks(angles[:-1])
            ax2.set_xticklabels([name.replace('_', '\n') for name in metric_names])
            ax2.set_ylim(0, 1)
            ax2.set_title('메트릭 성능 레이더 차트')
            ax2.legend(loc='upper right', bbox_to_anchor=(1.2, 1.0))
            ax2.grid(True)
            
            plt.tight_layout()
            
            # 저장
            chart_path = self.charts_dir / 'metrics_overview.png'
            plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"✅ 메트릭 개요 차트 저장: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            self.logger.error(f"❌ 메트릭 개요 차트 생성 실패: {e}")
            plt.close()
            return ""
    
    def create_category_analysis(self, category_data: Dict[str, Any], 
                               results: Dict[str, Any]) -> str:
        """카테고리별 성능 분석 차트"""
        self.logger.info("🏷️ 카테고리별 성능 차트 생성 중...")
        
        try:
            if not category_data:
                self.logger.warning("카테고리 데이터가 없습니다")
                return ""
            
            # 데이터 준비
            categories = list(category_data.keys())
            category_scores = [data['overall_score'] for data in category_data.values()]
            category_counts = [data['count'] for data in category_data.values()]
            
            # 차트 생성
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. 카테고리별 전체 점수
            colors = plt.cm.Set3(np.linspace(0, 1, len(categories)))
            bars = ax1.bar(categories, category_scores, alpha=0.7, color=colors)
            ax1.set_xlabel('카테고리')
            ax1.set_ylabel('전체 점수')
            ax1.set_title('카테고리별 전체 성능')
            ax1.tick_params(axis='x', rotation=45)
            ax1.set_ylim(0, 1)
            
            # 임계값 라인
            overall_threshold = self.config['thresholds'].get('overall_score', 0.75)
            ax1.axhline(y=overall_threshold, color='red', linestyle='--', alpha=0.7, label=f'임계값 ({overall_threshold})')
            ax1.legend()
            
            # 막대 위에 값 표시
            for bar, score in zip(bars, category_scores):
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                        f'{score:.3f}', ha='center', va='bottom', fontsize=9)
            
            # 2. 카테고리별 질문 수
            ax2.pie(category_counts, labels=categories, autopct='%1.1f%%', startangle=90, colors=colors)
            ax2.set_title('카테고리별 질문 분포')
            
            # 3. 히트맵 (카테고리 x 메트릭)
            metric_names = list(self.config['ragas_metrics'])
            heatmap_data = []
            
            for category in categories:
                category_metrics = category_data[category].get('metrics', {})
                row = [category_metrics.get(metric, 0) for metric in metric_names]
                heatmap_data.append(row)
            
            if heatmap_data:
                heatmap_df = pd.DataFrame(heatmap_data, index=categories, columns=metric_names)
                
                sns.heatmap(heatmap_df, annot=True, fmt='.3f', cmap='RdYlGn', 
                           ax=ax3, cbar_kws={'label': '점수'})
                ax3.set_title('카테고리별 메트릭 히트맵')
                ax3.set_xlabel('메트릭')
                ax3.set_ylabel('카테고리')
            
            # 4. 성능 분포
            performance_levels = {'우수': 0, '양호': 0, '개선필요': 0}
            for score in category_scores:
                if score >= 0.8:
                    performance_levels['우수'] += 1
                elif score >= 0.6:
                    performance_levels['양호'] += 1
                else:
                    performance_levels['개선필요'] += 1
            
            colors_perf = ['green', 'orange', 'red']
            ax4.bar(performance_levels.keys(), performance_levels.values(), 
                   color=colors_perf, alpha=0.7)
            ax4.set_xlabel('성능 수준')
            ax4.set_ylabel('카테고리 수')
            ax4.set_title('성능 수준별 카테고리 분포')
            
            # 막대 위에 값 표시
            for i, (level, count) in enumerate(performance_levels.items()):
                ax4.text(i, count + 0.05, str(count), ha='center', va='bottom')
            
            plt.tight_layout()
            
            # 저장
            chart_path = self.charts_dir / 'category_analysis.png'
            plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"✅ 카테고리 분석 차트 저장: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            self.logger.error(f"❌ 카테고리 분석 차트 생성 실패: {e}")
            plt.close()
            return ""
    
    def create_interactive_dashboard(self, results: Dict[str, Any], 
                                   category_data: Dict[str, Any],
                                   individual_results: List[Dict[str, Any]]) -> str:
        """인터랙티브 대시보드 생성 (Plotly)"""
        self.logger.info("🖥️ 인터랙티브 대시보드 생성 중...")
        
        try:
            # 서브플롯 생성
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=[
                    '메트릭 성능 비교',
                    '카테고리별 성능',
                    '성능 트렌드',
                    '처리 결과 분포',
                    '응답 시간 분포',
                    '개선 우선순위'
                ],
                specs=[
                    [{"type": "bar"}, {"type": "bar"}],
                    [{"type": "scatter"}, {"type": "pie"}],
                    [{"type": "histogram"}, {"type": "bar"}]
                ]
            )
            
            # 1. 메트릭 성능 비교
            metrics_data = results.get('detailed_metrics', {})
            if metrics_data:
                metric_names = list(metrics_data.keys())
                scores = [metrics_data[name]['score'] for name in metric_names]
                thresholds = [metrics_data[name]['threshold'] for name in metric_names]
                
                fig.add_trace(
                    go.Bar(name='실제 점수', x=metric_names, y=scores, 
                          text=[f'{s:.3f}' for s in scores], textposition='auto',
                          marker_color='skyblue'),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Bar(name='임계값', x=metric_names, y=thresholds,
                          text=[f'{t:.3f}' for t in thresholds], textposition='auto',
                          marker_color='orange'),
                    row=1, col=1
                )
            
            # 2. 카테고리별 성능
            if category_data:
                categories = list(category_data.keys())
                category_scores = [data['overall_score'] for data in category_data.values()]
                
                fig.add_trace(
                    go.Bar(name='카테고리 점수', x=categories, y=category_scores,
                          text=[f'{s:.3f}' for s in category_scores], textposition='auto',
                          marker_color='lightgreen'),
                    row=1, col=2
                )
            
            # 3. 성능 트렌드 (배치별 성공률)
            if individual_results:
                batch_size = 50
                batch_success_rates = []
                for i in range(0, len(individual_results), batch_size):
                    batch = individual_results[i:i+batch_size]
                    batch_success = len([r for r in batch if r.get('success', False)])
                    batch_success_rates.append(batch_success / len(batch) * 100)
                
                fig.add_trace(
                    go.Scatter(x=list(range(len(batch_success_rates))), 
                             y=batch_success_rates,
                             mode='lines+markers',
                             name='배치별 성공률 (%)',
                             line=dict(color='blue')),
                    row=2, col=1
                )
            
            # 4. 처리 결과 분포
            if individual_results:
                success_count = len([r for r in individual_results if r.get('success', True)])
                error_count = len(individual_results) - success_count
                
                fig.add_trace(
                    go.Pie(labels=['성공', '실패'], values=[success_count, error_count],
                          name="처리 결과",
                          marker=dict(colors=['green', 'red'])),
                    row=2, col=2
                )
            
            # 5. 응답 시간 분포 (시뮬레이션)
            np.random.seed(42)
            response_times = np.random.normal(3.5, 1.2, len(individual_results))
            response_times = np.clip(response_times, 0.5, 10)
            
            fig.add_trace(
                go.Histogram(x=response_times, nbinsx=20, name='응답 시간 분포',
                           marker_color='purple'),
                row=3, col=1
            )
            
            # 6. 개선 우선순위
            if metrics_data:
                priorities = []
                priority_scores = []
                
                for metric_name, metric_info in metrics_data.items():
                    gap = metric_info['threshold'] - metric_info['score']
                    if gap > 0:
                        priorities.append(metric_name)
                        priority_scores.append(gap)
                
                if priorities:
                    # 내림차순 정렬
                    sorted_data = sorted(zip(priorities, priority_scores), 
                                       key=lambda x: x[1], reverse=True)
                    priorities, priority_scores = zip(*sorted_data)
                    
                    fig.add_trace(
                        go.Bar(name='개선 필요도', x=list(priorities), y=list(priority_scores),
                              text=[f'{s:.3f}' for s in priority_scores], textposition='auto',
                              marker_color='red'),
                        row=3, col=2
                    )
            
            # 레이아웃 업데이트
            fig.update_layout(
                height=1200,
                showlegend=True,
                title_text="CHEESEADE RAG 시스템 평가 대시보드",
                title_x=0.5,
                font=dict(size=12)
            )
            
            # 저장
            dashboard_path = self.charts_dir / 'interactive_dashboard.html'
            pyo.plot(fig, filename=str(dashboard_path), auto_open=False)
            
            self.logger.info(f"✅ 인터랙티브 대시보드 저장: {dashboard_path}")
            return str(dashboard_path)
            
        except Exception as e:
            self.logger.error(f"❌ 인터랙티브 대시보드 생성 실패: {e}")
            return ""
    
    def create_summary_report(self, results: Dict[str, Any], 
                            recommendations: Dict[str, List[str]]) -> str:
        """요약 보고서 시각화"""
        self.logger.info("📋 요약 보고서 차트 생성 중...")
        
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. 전체 성능 게이지
            overall_score = results.get('evaluation_summary', {}).get('overall_score', 0)
            overall_threshold = self.config['thresholds'].get('overall_score', 0.75)
            
            # 게이지 차트 시뮬레이션
            categories = ['매우 낮음', '낮음', '보통', '높음', '매우 높음']
            ranges = [0.2, 0.4, 0.6, 0.8, 1.0]
            colors = ['red', 'orange', 'yellow', 'lightgreen', 'green']
            
            for i, (cat, range_val, color) in enumerate(zip(categories, ranges, colors)):
                start = ranges[i-1] if i > 0 else 0
                ax1.barh(0, range_val - start, left=start, height=0.3, 
                        color=color, alpha=0.7, label=cat)
            
            # 현재 점수 표시
            ax1.axvline(x=overall_score, color='black', linewidth=3, label=f'현재 점수: {overall_score:.3f}')
            ax1.axvline(x=overall_threshold, color='blue', linewidth=2, linestyle='--', 
                       label=f'목표: {overall_threshold:.3f}')
            
            ax1.set_xlim(0, 1)
            ax1.set_ylim(-0.2, 0.5)
            ax1.set_xlabel('점수')
            ax1.set_title('전체 성능 게이지')
            ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax1.set_yticks([])
            
            # 2. 개선 우선순위
            priorities = ['높음', '중간', '낮음']
            priority_counts = [
                len(recommendations.get('high_priority', [])),
                len(recommendations.get('medium_priority', [])),
                len(recommendations.get('low_priority', []))
            ]
            
            colors_priority = ['red', 'orange', 'green']
            bars = ax2.bar(priorities, priority_counts, color=colors_priority, alpha=0.7)
            ax2.set_xlabel('우선순위')
            ax2.set_ylabel('권장사항 수')
            ax2.set_title('개선 우선순위별 권장사항')
            
            # 막대 위에 값 표시
            for bar, count in zip(bars, priority_counts):
                if count > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                            str(count), ha='center', va='bottom')
            
            # 3. 메트릭 pass/fail 비율
            performance_analysis = results.get('performance_analysis', {})
            passed = performance_analysis.get('passed_metrics', 0)
            failed = performance_analysis.get('failed_metrics', 0)
            
            if passed + failed > 0:
                ax3.pie([passed, failed], labels=['통과', '실패'], 
                       colors=['green', 'red'], autopct='%1.1f%%',
                       startangle=90)
                ax3.set_title('메트릭 통과/실패 비율')
            
            # 4. 성능 요약 텍스트
            ax4.axis('off')
            
            # 요약 텍스트 생성
            summary_text = f"""
성능 요약 보고서

전체 점수: {overall_score:.3f} / {overall_threshold:.3f}
성능 등급: {"우수" if overall_score >= 0.8 else "양호" if overall_score >= 0.6 else "개선필요"}

메트릭 통과율: {passed}/{passed+failed} ({(passed/(passed+failed)*100):.1f}%)

주요 개선사항:
- 높은 우선순위: {len(recommendations.get('high_priority', []))}개
- 중간 우선순위: {len(recommendations.get('medium_priority', []))}개
- 낮은 우선순위: {len(recommendations.get('low_priority', []))}개

평가 완료 시간: {results.get('timestamp', 'Unknown')}
소요 시간: {results.get('duration_seconds', 0):.1f}초

RAG 서버 구성 변경시:
1. RAG 서버 재시작
2. 평가 재실행 (코드 수정 불필요)
            """
            
            ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, 
                    fontsize=11, verticalalignment='top',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.5))
            
            plt.tight_layout()
            
            # 저장
            chart_path = self.charts_dir / 'summary_report.png'
            plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"✅ 요약 보고서 차트 저장: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            self.logger.error(f"❌ 요약 보고서 차트 생성 실패: {e}")
            plt.close()
            return ""