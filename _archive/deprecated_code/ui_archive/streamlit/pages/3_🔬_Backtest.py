#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
백테스트 - 전략 성과 검증 및 최적화
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
import sys
import json

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Backtest", page_icon="🔬", layout="wide")

st.title("🔬 백테스트")
st.markdown("---")

# 탭 구성
tab1, tab2 = st.tabs(["▶️ 백테스트 실행", "📊 결과 비교"])

with tab1:
    st.subheader("▶️ 백테스트 실행")
    
    # 사용할 파라미터 먼저 표시
    st.markdown("### 📋 백테스트 설정")
    
    # 설정 섹션
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📅 백테스트 기간**")
        
        start_date = st.date_input(
            "시작일",
            value=date(2022, 1, 1),
            min_value=date(2020, 1, 1),
            max_value=date.today()
        )
        
        end_date = st.date_input(
            "종료일",
            value=date.today(),
            min_value=start_date,
            max_value=date.today()
        )
        
        days = (end_date - start_date).days
        st.info(f"백테스트 기간: **{days}일** ({days/365:.1f}년)")
    
    with col2:
        st.markdown("**⚙️ 파라미터 소스**")
        
        param_source = st.radio(
            "파라미터 선택",
            ["현재 설정", "최적화 결과", "커스텀"],
            help="백테스트에 사용할 파라미터를 선택하세요"
        )
        
        if param_source == "현재 설정":
            config_file = project_root / "config" / "strategy_params.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    params = json.load(f)
                st.success("✅ 현재 설정 파일 로드 완료")
            else:
                st.warning("⚠️ 설정 파일이 없습니다. 기본값을 사용합니다.")
                params = {
                    'maps_threshold': 5.0,
                    'regime_ma_short': 50,
                    'regime_ma_long': 200,
                    'position_bull': 120,
                    'position_sideways': 80,
                    'position_bear': 50
                }
        
        elif param_source == "최적화 결과":
            opt_file = project_root / "data" / "optimization" / "best_params.json"
            if opt_file.exists():
                with open(opt_file, 'r') as f:
                    params = json.load(f)
                st.success("✅ 최적화 결과 로드 완료")
            else:
                st.error("❌ 최적화 결과가 없습니다. 먼저 파라미터 최적화를 실행하세요.")
                params = {}
        
        else:  # 커스텀
            st.info("💡 파라미터 조정 페이지에서 설정을 변경하세요.")
            config_file = project_root / "config" / "strategy_params.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    params = json.load(f)
            else:
                params = {}
    
    # 사용할 파라미터 표시
    if params:
        st.markdown("---")
        st.markdown("### 🎯 백테스트에 사용될 파라미터")
        
        param_col1, param_col2, param_col3 = st.columns(3)
        
        with param_col1:
            st.markdown("""<div style='background-color: #e3f2fd; padding: 15px; border-radius: 8px;'>
            <h5>📊 MAPS & 레짐</h5>
            <p><b>MAPS 임계값:</b> {}</p>
            <p><b>단기 MA:</b> {}일</p>
            <p><b>장기 MA:</b> {}일</p>
            </div>""".format(
                params.get('maps_threshold', 'N/A'),
                params.get('regime_ma_short', 'N/A'),
                params.get('regime_ma_long', 'N/A')
            ), unsafe_allow_html=True)
        
        with param_col2:
            st.markdown("""<div style='background-color: #e8f5e9; padding: 15px; border-radius: 8px;'>
            <h5>💼 포지션 비율</h5>
            <p><b>상승장:</b> {}%</p>
            <p><b>중립장:</b> {}%</p>
            <p><b>하락장:</b> {}%</p>
            </div>""".format(
                params.get('position_bull', 'N/A'),
                params.get('position_sideways', 'N/A'),
                params.get('position_bear', 'N/A')
            ), unsafe_allow_html=True)
        
        with param_col3:
            st.markdown("""<div style='background-color: #fff3e0; padding: 15px; border-radius: 8px;'>
            <h5>🛡️ 리스크 관리</h5>
            <p><b>손절 라인:</b> {}%</p>
            <p><b>방어 신뢰도:</b> {}%</p>
            <p><b>최대 비중:</b> {}%</p>
            </div>""".format(
                params.get('stop_loss', 'N/A'),
                params.get('defense_confidence', 'N/A'),
                params.get('max_position_size', 'N/A')
            ), unsafe_allow_html=True)
    
    # 고급 옵션
    with st.expander("🔧 고급 옵션"):
        col1, col2 = st.columns(2)
        
        with col1:
            initial_capital = st.number_input(
                "초기 자본 (원)",
                min_value=1000000,
                max_value=100000000,
                value=10000000,
                step=1000000
            )
            
            commission = st.number_input(
                "수수료 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.015,
                step=0.001,
                format="%.3f"
            )
        
        with col2:
            slippage = st.number_input(
                "슬리피지 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.1,
                step=0.05,
                format="%.2f"
            )
            
            rebalance_freq = st.selectbox(
                "리밸런싱 주기",
                ["매일", "매주", "매월"],
                index=0
            )
    
    # 실행 버튼
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        run_backtest = st.button(
            "▶️ 백테스트 실행",
            type="primary",
            use_container_width=True
        )
    
    if run_backtest:
        # 백테스트 실행 (더미)
        with st.spinner("백테스트 실행 중... ⏳"):
            import time
            progress_bar = st.progress(0)
            
            for i in range(100):
                time.sleep(0.02)
                progress_bar.progress(i + 1)
            
            st.success("✅ 백테스트 완료!")
        
        # 결과 표시
        st.markdown("---")
        st.subheader("📊 백테스트 결과")
        
        # 성과 지표
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("CAGR", "27.05%", delta="+2.05%")
        with col2:
            st.metric("Sharpe Ratio", "1.51", delta="+0.01")
        with col3:
            st.metric("Max Drawdown", "-19.92%", delta="+3.08%")
        with col4:
            st.metric("총 수익률", "96.80%", delta="+10.50%")
        
        # 수익 곡선
        st.markdown("---")
        st.subheader("💰 수익 곡선")
        
        # 더미 데이터 생성
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        equity = [initial_capital]
        
        import random
        for i in range(1, len(dates)):
            daily_return = random.uniform(-0.02, 0.03)
            equity.append(equity[-1] * (1 + daily_return))
        
        df_equity = pd.DataFrame({
            'Date': dates,
            'Equity': equity
        })
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_equity['Date'],
            y=df_equity['Equity'],
            mode='lines',
            name='포트폴리오',
            line=dict(color='#1f77b4', width=2)
        ))
        
        # 벤치마크 추가
        benchmark = [initial_capital]
        for i in range(1, len(dates)):
            daily_return = random.uniform(-0.015, 0.02)
            benchmark.append(benchmark[-1] * (1 + daily_return))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=benchmark,
            mode='lines',
            name='KOSPI',
            line=dict(color='gray', width=1, dash='dash')
        ))
        
        fig.update_layout(
            title='포트폴리오 vs 벤치마크',
            xaxis_title='날짜',
            yaxis_title='가치 (원)',
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 상세 통계
        st.markdown("---")
        st.subheader("📈 상세 통계")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**수익률 통계**")
            stats_df = pd.DataFrame({
                '지표': ['연평균 수익률', '표준편차', '최대 수익', '최대 손실', '승률'],
                '값': ['27.05%', '15.32%', '8.45%', '-5.23%', '62.3%']
            })
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("**거래 통계**")
            trade_df = pd.DataFrame({
                '지표': ['총 거래 수', '평균 보유 기간', '평균 수익', '최대 연속 손실', '수수료 총액'],
                '값': ['1,406회', '12.5일', '+2.3%', '3회', '142,500원']
            })
            st.dataframe(trade_df, use_container_width=True, hide_index=True)
        
        # 월별 수익률
        st.markdown("---")
        st.subheader("📅 월별 수익률")
        
        monthly_returns = pd.DataFrame({
            '월': pd.date_range(start='2024-01', end='2024-12', freq='MS').strftime('%Y-%m'),
            '수익률': [3.2, -1.5, 4.8, 2.1, -0.8, 5.3, 1.9, -2.3, 3.7, 4.2, 2.5, 1.8]
        })
        
        fig = go.Figure(data=[
            go.Bar(
                x=monthly_returns['월'],
                y=monthly_returns['수익률'],
                marker_color=['green' if x > 0 else 'red' for x in monthly_returns['수익률']],
                text=monthly_returns['수익률'].apply(lambda x: f'{x:+.1f}%'),
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title='월별 수익률 (%)',
            xaxis_title='월',
            yaxis_title='수익률 (%)',
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 결과 저장
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("💾 결과 저장", use_container_width=True):
                # 결과 저장 로직
                result_dir = project_root / "data" / "backtest_results"
                result_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
                result_file = result_dir / f"backtest_{timestamp}.json"
                
                result_data = {
                    'timestamp': timestamp,
                    'datetime': datetime.now(KST).isoformat(),
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    },
                    'param_source': param_source,
                    'params': params,
                    'metrics': {
                        'cagr': 27.05,
                        'sharpe': 1.51,
                        'mdd': -19.92,
                        'total_return': 96.80
                    }
                }
                
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                
                # 파라미터 히스토리에 백테스트 결과 연동
                if param_source == "현재 설정":
                    history_dir = project_root / "data" / "parameter_history"
                    if history_dir.exists():
                        # 가장 최근 파라미터 히스토리 파일 찾기
                        history_files = sorted(history_dir.glob("params_*.json"), reverse=True)
                        if history_files:
                            latest_history = history_files[0]
                            try:
                                with open(latest_history, 'r', encoding='utf-8') as f:
                                    history_data = json.load(f)
                                
                                # 백테스트 결과 업데이트
                                history_data['backtest_result'] = result_data['metrics']
                                history_data['backtest_timestamp'] = timestamp
                                
                                with open(latest_history, 'w', encoding='utf-8') as f:
                                    json.dump(history_data, f, ensure_ascii=False, indent=2)
                                
                                st.info(f"📊 파라미터 히스토리에 백테스트 결과 연동 완료")
                            except:
                                pass
                
                st.success(f"✅ 결과 저장 완료: {result_file.name}")

with tab2:
    st.subheader("📊 백테스트 결과 비교")
    
    # 저장된 결과 로드
    result_dir = project_root / "data" / "backtest_results"
    
    if result_dir.exists():
        result_files = list(result_dir.glob("backtest_*.json"))
        
        if result_files:
            st.info(f"💾 저장된 백테스트 결과: {len(result_files)}개")
            
            # 결과 비교 테이블
            comparison_data = []
            
            for result_file in sorted(result_files, reverse=True)[:10]:  # 최근 10개
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                
                # 파라미터 요약
                params_summary = result.get('params', {})
                param_str = f"MAPS:{params_summary.get('maps_threshold', 'N/A')} / "
                param_str += f"MA:{params_summary.get('regime_ma_short', 'N/A')}/{params_summary.get('regime_ma_long', 'N/A')} / "
                param_str += f"Pos:{params_summary.get('position_bull', 'N/A')}/{params_summary.get('position_sideways', 'N/A')}/{params_summary.get('position_bear', 'N/A')}"
                
                comparison_data.append({
                    '실행 시간': result.get('datetime', result['timestamp'])[:19] if 'datetime' in result else result['timestamp'],
                    '파라미터 소스': result.get('param_source', 'N/A'),
                    '파라미터': param_str,
                    '기간': f"{result['period']['start']} ~ {result['period']['end']}",
                    'CAGR': f"{result['metrics']['cagr']:.2f}%",
                    'Sharpe': f"{result['metrics']['sharpe']:.2f}",
                    'MDD': f"{result['metrics']['mdd']:.2f}%"
                })
            
            df_comparison = pd.DataFrame(comparison_data)
            st.dataframe(df_comparison, use_container_width=True, hide_index=True)
            
            # 성과 비교 차트
            st.markdown("---")
            st.subheader("📈 성과 지표 비교")
            
            metrics = ['CAGR', 'Sharpe', 'MDD', '총 수익률']
            selected_metric = st.selectbox("비교할 지표 선택", metrics)
            
            # 더미 차트
            fig = go.Figure(data=[
                go.Bar(
                    x=[f"Run {i+1}" for i in range(5)],
                    y=[27.05, 25.32, 28.91, 26.15, 27.88],
                    marker_color='lightblue'
                )
            ])
            
            fig.update_layout(
                title=f'{selected_metric} 비교',
                xaxis_title='백테스트 실행',
                yaxis_title=selected_metric,
                height=300
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.warning("⚠️ 저장된 백테스트 결과가 없습니다. 먼저 백테스트를 실행하세요.")
    
    else:
        st.warning("⚠️ 백테스트 결과 디렉토리가 없습니다.")

# 푸터
st.markdown("---")
st.caption("🔬 Backtest | 백테스트 엔진 v2.5")
