# -*- coding: utf-8 -*-
"""
extensions/ui/dashboard.py
하이브리드 전략 대시보드

실행 방법:
    streamlit run extensions/ui/dashboard.py

기능:
- 파라미터 조정
- 백테스트 실행
- 히스토리 조회
- 성과 비교
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
import json

from extensions.ui.backtest_database import BacktestDatabase
from core.engine.krx_maps_adapter import KRXMAPSAdapter
from infra.data.loader import load_price_data

# 페이지 설정
st.set_page_config(
    page_title="하이브리드 전략 대시보드",
    page_icon="📊",
    layout="wide"
)

# 데이터베이스 초기화
@st.cache_resource
def get_database():
    return BacktestDatabase()

db = get_database()


def main():
    """메인 함수"""
    st.title("📊 하이브리드 전략 대시보드")
    st.markdown("---")
    
    # 사이드바: 메뉴
    menu = st.sidebar.selectbox(
        "메뉴",
        ["파라미터 조정", "백테스트 히스토리", "성과 비교", "레짐 타임라인"]
    )
    
    if menu == "파라미터 조정":
        show_parameter_panel()
    elif menu == "백테스트 히스토리":
        show_backtest_history()
    elif menu == "성과 비교":
        show_performance_comparison()
    elif menu == "레짐 타임라인":
        show_regime_timeline()


def show_parameter_panel():
    """파라미터 조정 패널"""
    st.header("⚙️ 파라미터 조정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("레짐 감지 파라미터")
        
        regime_short_ma = st.slider(
            "단기 MA 기간",
            min_value=10,
            max_value=100,
            value=50,
            step=10
        )
        
        regime_long_ma = st.slider(
            "장기 MA 기간",
            min_value=100,
            max_value=300,
            value=200,
            step=20
        )
        
        regime_bull_threshold = st.slider(
            "상승장 임계값 (%)",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.5
        )
        
        regime_bear_threshold = st.slider(
            "하락장 임계값 (%)",
            min_value=-5.0,
            max_value=-0.5,
            value=-2.0,
            step=0.5
        )
    
    with col2:
        st.subheader("포지션 비율")
        
        bull_min = st.slider(
            "상승장 최소 비율 (%)",
            min_value=80,
            max_value=120,
            value=100,
            step=10
        )
        
        bull_max = st.slider(
            "상승장 최대 비율 (%)",
            min_value=100,
            max_value=150,
            value=120,
            step=10
        )
        
        neutral_ratio = st.slider(
            "중립장 비율 (%)",
            min_value=50,
            max_value=100,
            value=80,
            step=10
        )
        
        bear_min = st.slider(
            "하락장 최소 비율 (%)",
            min_value=0,
            max_value=60,
            value=40,
            step=10
        )
        
        bear_max = st.slider(
            "하락장 최대 비율 (%)",
            min_value=40,
            max_value=80,
            value=60,
            step=10
        )
    
    st.markdown("---")
    
    # 백테스트 기간 설정
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input(
            "시작일",
            value=date(2022, 1, 1)
        )
    
    with col2:
        end_date = st.date_input(
            "종료일",
            value=date.today()
        )
    
    with col3:
        max_positions = st.number_input(
            "최대 보유 종목",
            min_value=5,
            max_value=20,
            value=10
        )
    
    # 메모
    notes = st.text_area("메모 (선택)", "")
    
    # 백테스트 실행
    if st.button("🚀 백테스트 실행", type="primary"):
        run_backtest(
            regime_short_ma=regime_short_ma,
            regime_long_ma=regime_long_ma,
            regime_bull_threshold=regime_bull_threshold / 100,
            regime_bear_threshold=regime_bear_threshold / 100,
            start_date=start_date,
            end_date=end_date,
            max_positions=max_positions,
            notes=notes
        )


def run_backtest(
    regime_short_ma: int,
    regime_long_ma: int,
    regime_bull_threshold: float,
    regime_bear_threshold: float,
    start_date: date,
    end_date: date,
    max_positions: int,
    notes: str
):
    """백테스트 실행"""
    
    with st.spinner("백테스트 실행 중..."):
        try:
            # 유니버스 로드
            universe_df = pd.read_csv("data/universe/etf_universe.csv")
            code_col = 'code' if 'code' in universe_df.columns else 'ticker'
            tickers = universe_df[code_col].astype(str).str.zfill(6).tolist()
            
            # KOSPI 추가
            if '069500' not in tickers:
                tickers.append('069500')
            
            # 가격 데이터 로드
            st.info(f"데이터 로딩 중... ({len(tickers)}개 종목)")
            price_data = load_price_data(
                universe=tickers,
                start_date=start_date,
                end_date=end_date
            )
            
            if price_data.empty:
                st.error("가격 데이터가 없습니다.")
                return
            
            # 백테스트 설정
            backtest_config = {
                'initial_capital': 10000000,
                'commission_rate': 0.00015,
                'slippage_rate': 0.001,
                'max_positions': max_positions,
                'country_code': 'kor'
            }
            
            # 어댑터 초기화
            adapter = KRXMAPSAdapter(
                **backtest_config,
                enable_defense=True,
                fixed_stop_loss_pct=-100.0,
                trailing_stop_pct=-100.0,
                portfolio_stop_loss_pct=-100.0,
                cooldown_days=0,
                regime_short_ma=regime_short_ma,
                regime_long_ma=regime_long_ma,
                regime_bull_threshold=regime_bull_threshold,
                regime_bear_threshold=regime_bear_threshold
            )
            
            # 백테스트 실행
            st.info("백테스트 실행 중...")
            results = adapter.run(
                price_data=price_data,
                start_date=start_date,
                end_date=end_date
            )
            
            # 결과 저장
            params = {
                'regime_short_ma': regime_short_ma,
                'regime_long_ma': regime_long_ma,
                'regime_bull_threshold': regime_bull_threshold,
                'regime_bear_threshold': regime_bear_threshold,
                'max_positions': max_positions,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            
            record_id = db.save_result(params, results, notes)
            
            # 결과 표시
            st.success(f"✅ 백테스트 완료! (ID: {record_id})")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("CAGR", f"{results['cagr']:.2f}%")
            
            with col2:
                st.metric("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
            
            with col3:
                st.metric("Max Drawdown", f"{results['max_drawdown']:.2f}%")
            
            with col4:
                st.metric("거래 수", f"{results['num_trades']}회")
            
            # 레짐 통계
            if 'regime_stats' in results:
                st.subheader("📊 레짐 통계")
                regime_stats = results['regime_stats']
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "상승장",
                        f"{regime_stats.get('bull_days', 0)}일",
                        f"{regime_stats.get('bull_pct', 0):.1f}%"
                    )
                
                with col2:
                    st.metric(
                        "하락장",
                        f"{regime_stats.get('bear_days', 0)}일",
                        f"{regime_stats.get('bear_pct', 0):.1f}%"
                    )
                
                with col3:
                    st.metric(
                        "중립장",
                        f"{regime_stats.get('neutral_days', 0)}일",
                        f"{regime_stats.get('neutral_pct', 0):.1f}%"
                    )
                
                st.info(f"레짐 변경: {regime_stats.get('regime_changes', 0)}회")
            
        except Exception as e:
            st.error(f"백테스트 실패: {e}")
            import traceback
            st.code(traceback.format_exc())


def show_backtest_history():
    """백테스트 히스토리"""
    st.header("📜 백테스트 히스토리")
    
    # 히스토리 로드
    history_df = db.get_history(limit=50)
    
    if history_df.empty:
        st.info("백테스트 히스토리가 없습니다.")
        return
    
    # 테이블 표시
    display_df = history_df[[
        'id', 'created_at', 'cagr', 'sharpe_ratio',
        'max_drawdown', 'num_trades', 'notes'
    ]].copy()
    
    display_df.columns = [
        'ID', '날짜', 'CAGR (%)', 'Sharpe', 'MDD (%)', '거래 수', '메모'
    ]
    
    st.dataframe(display_df, use_container_width=True)
    
    # 최고 성과
    st.subheader("🏆 최고 성과")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        best_cagr = db.get_best_result('cagr')
        if best_cagr:
            st.metric(
                "최고 CAGR",
                f"{best_cagr['cagr']:.2f}%",
                f"ID: {best_cagr['id']}"
            )
    
    with col2:
        best_sharpe = db.get_best_result('sharpe_ratio')
        if best_sharpe:
            st.metric(
                "최고 Sharpe",
                f"{best_sharpe['sharpe_ratio']:.2f}",
                f"ID: {best_sharpe['id']}"
            )
    
    with col3:
        best_mdd = db.get_best_result('max_drawdown')
        if best_mdd:
            st.metric(
                "최소 MDD",
                f"{best_mdd['max_drawdown']:.2f}%",
                f"ID: {best_mdd['id']}"
            )


def show_performance_comparison():
    """성과 비교"""
    st.header("📊 성과 비교")
    
    # 히스토리 로드
    history_df = db.get_history(limit=20)
    
    if history_df.empty:
        st.info("백테스트 히스토리가 없습니다.")
        return
    
    # ID 선택
    selected_ids = st.multiselect(
        "비교할 백테스트 선택 (최대 5개)",
        options=history_df['id'].tolist(),
        max_selections=5
    )
    
    if not selected_ids:
        st.info("비교할 백테스트를 선택하세요.")
        return
    
    # 비교 데이터 로드
    compare_df = db.compare_results(selected_ids)
    
    # 성과 지표 차트
    col1, col2 = st.columns(2)
    
    with col1:
        # CAGR 비교
        fig_cagr = go.Figure()
        fig_cagr.add_trace(go.Bar(
            x=[f"ID {row['id']}" for _, row in compare_df.iterrows()],
            y=compare_df['cagr'],
            name='CAGR',
            marker_color='lightblue'
        ))
        fig_cagr.update_layout(
            title="CAGR 비교",
            yaxis_title="CAGR (%)",
            height=400
        )
        st.plotly_chart(fig_cagr, use_container_width=True)
    
    with col2:
        # Sharpe 비교
        fig_sharpe = go.Figure()
        fig_sharpe.add_trace(go.Bar(
            x=[f"ID {row['id']}" for _, row in compare_df.iterrows()],
            y=compare_df['sharpe_ratio'],
            name='Sharpe',
            marker_color='lightgreen'
        ))
        fig_sharpe.update_layout(
            title="Sharpe Ratio 비교",
            yaxis_title="Sharpe Ratio",
            height=400
        )
        st.plotly_chart(fig_sharpe, use_container_width=True)
    
    # MDD 비교
    fig_mdd = go.Figure()
    fig_mdd.add_trace(go.Bar(
        x=[f"ID {row['id']}" for _, row in compare_df.iterrows()],
        y=compare_df['max_drawdown'],
        name='MDD',
        marker_color='lightcoral'
    ))
    fig_mdd.update_layout(
        title="Max Drawdown 비교",
        yaxis_title="MDD (%)",
        height=400
    )
    st.plotly_chart(fig_mdd, use_container_width=True)
    
    # 파라미터 비교 테이블
    st.subheader("파라미터 비교")
    
    params_data = []
    for _, row in compare_df.iterrows():
        params = row['params']
        params_data.append({
            'ID': row['id'],
            '단기 MA': params.get('regime_short_ma'),
            '장기 MA': params.get('regime_long_ma'),
            '상승 임계값': f"{params.get('regime_bull_threshold', 0)*100:.1f}%",
            '하락 임계값': f"{params.get('regime_bear_threshold', 0)*100:.1f}%",
        })
    
    st.table(pd.DataFrame(params_data))


def show_regime_timeline():
    """레짐 타임라인"""
    st.header("🎯 레짐 타임라인")
    
    # 레짐 히스토리 로드
    from extensions.automation.regime_monitor import RegimeMonitor
    monitor = RegimeMonitor()
    
    history = monitor.load_history(days=90)
    
    if not history:
        st.info("레짐 히스토리가 없습니다.")
        return
    
    # DataFrame 변환
    df = pd.DataFrame(history)
    df['date'] = pd.to_datetime(df['date'])
    
    # 레짐별 색상
    color_map = {
        'bull': 'green',
        'bear': 'red',
        'neutral': 'gray'
    }
    
    df['color'] = df['regime'].map(color_map)
    
    # 타임라인 차트
    fig = go.Figure()
    
    for regime in ['bull', 'bear', 'neutral']:
        regime_df = df[df['regime'] == regime]
        if not regime_df.empty:
            fig.add_trace(go.Scatter(
                x=regime_df['date'],
                y=regime_df['confidence'],
                mode='markers',
                name=regime,
                marker=dict(
                    size=10,
                    color=color_map[regime]
                )
            ))
    
    fig.update_layout(
        title="레짐 변화 타임라인",
        xaxis_title="날짜",
        yaxis_title="신뢰도",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 레짐 통계
    st.subheader("📊 레짐 통계")
    
    regime_counts = df['regime'].value_counts()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("상승장", f"{regime_counts.get('bull', 0)}일")
    
    with col2:
        st.metric("하락장", f"{regime_counts.get('bear', 0)}일")
    
    with col3:
        st.metric("중립장", f"{regime_counts.get('neutral', 0)}일")


if __name__ == "__main__":
    main()
