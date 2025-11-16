#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/backtest.py
백테스트 결과 뷰어
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import json
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_backtest_results():
    """백테스트 결과 로드"""
    try:
        # Phase 2 백테스트 결과 찾기
        backtest_dir = PROJECT_ROOT / "data" / "output" / "backtest"
        
        results = {}
        
        # Jason 전략 백테스트 결과
        jason_file = backtest_dir / "jason_backtest_results.json"
        if jason_file.exists():
            with open(jason_file, 'r', encoding='utf-8') as f:
                results['jason'] = json.load(f)
        
        # 하이브리드 전략 백테스트 결과
        hybrid_file = backtest_dir / "hybrid_backtest_results.json"
        if hybrid_file.exists():
            with open(hybrid_file, 'r', encoding='utf-8') as f:
                results['hybrid'] = json.load(f)
        
        return results if results else None
    
    except Exception as e:
        st.error(f"백테스트 결과 로드 실패: {e}")
        return None


def show_performance_metrics(results):
    """성과 지표"""
    st.header("📊 성과 지표")
    
    # Jason 전략 지표
    if 'jason' in results:
        st.subheader("Jason 전략 (Phase 2)")
        jason = results['jason']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cagr = jason.get('cagr', 0) * 100
            st.metric("CAGR", f"{cagr:.2f}%")
        
        with col2:
            sharpe = jason.get('sharpe', 0)
            st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        
        with col3:
            mdd = jason.get('max_drawdown', 0) * 100
            st.metric("Max Drawdown", f"{mdd:.2f}%")
        
        with col4:
            total_return = jason.get('total_return', 0) * 100
            st.metric("총 수익률", f"{total_return:.2f}%")
    
    # 하이브리드 전략 지표
    if 'hybrid' in results:
        st.subheader("하이브리드 전략 (Phase 2)")
        hybrid = results['hybrid']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cagr = hybrid.get('cagr', 0) * 100
            st.metric("CAGR", f"{cagr:.2f}%")
        
        with col2:
            sharpe = hybrid.get('sharpe', 0)
            st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        
        with col3:
            mdd = hybrid.get('max_drawdown', 0) * 100
            st.metric("Max Drawdown", f"{mdd:.2f}%")
        
        with col4:
            total_return = hybrid.get('total_return', 0) * 100
            st.metric("총 수익률", f"{total_return:.2f}%")


def show_equity_curve(results):
    """자산 곡선"""
    st.header("📈 자산 곡선")
    
    # 전략 선택
    strategy_names = {}
    if 'jason' in results:
        strategy_names['jason'] = 'Jason 전략'
    if 'hybrid' in results:
        strategy_names['hybrid'] = '하이브리드 전략'
    
    if not strategy_names:
        st.warning("자산 곡선 데이터가 없습니다.")
        return
    
    selected = st.selectbox(
        "전략 선택",
        list(strategy_names.keys()),
        format_func=lambda x: strategy_names[x]
    )
    
    strategy_data = results[selected]
    
    # 자산 곡선 데이터
    equity_curve = strategy_data.get('equity_curve', [])
    
    if equity_curve:
        df = pd.DataFrame(equity_curve)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['equity'],
            mode='lines',
            name='자산',
            line=dict(color='#4ECDC4', width=2)
        ))
        
        fig.update_layout(
            title=f"{strategy_names[selected]} 자산 곡선",
            xaxis_title="날짜",
            yaxis_title="자산 (원)",
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("자산 곡선 데이터가 없습니다.")


def show_drawdown_chart(results):
    """낙폭 차트"""
    st.header("📉 낙폭 (Drawdown)")
    
    # 전략 선택
    strategy_names = {}
    if 'jason' in results:
        strategy_names['jason'] = 'Jason 전략'
    if 'hybrid' in results:
        strategy_names['hybrid'] = '하이브리드 전략'
    
    if not strategy_names:
        st.warning("낙폭 데이터가 없습니다.")
        return
    
    selected = st.selectbox(
        "전략 선택 (낙폭)",
        list(strategy_names.keys()),
        format_func=lambda x: strategy_names[x],
        key='dd_strategy'
    )
    
    strategy_data = results[selected]
    
    # 낙폭 데이터
    drawdowns = strategy_data.get('drawdowns', [])
    
    if drawdowns:
        df = pd.DataFrame(drawdowns)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['drawdown'] * 100,
            mode='lines',
            name='낙폭',
            fill='tozeroy',
            line=dict(color='#FF6B6B', width=2)
        ))
        
        fig.update_layout(
            title=f"{strategy_names[selected]} 낙폭",
            xaxis_title="날짜",
            yaxis_title="낙폭 (%)",
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("낙폭 데이터가 없습니다.")


def show_trade_analysis(results):
    """거래 분석"""
    st.header("💼 거래 분석")
    
    # 전략 선택
    strategy_names = {}
    if 'jason' in results:
        strategy_names['jason'] = 'Jason 전략'
    if 'hybrid' in results:
        strategy_names['hybrid'] = '하이브리드 전략'
    
    if not strategy_names:
        st.warning("거래 데이터가 없습니다.")
        return
    
    selected = st.selectbox(
        "전략 선택 (거래)",
        list(strategy_names.keys()),
        format_func=lambda x: strategy_names[x],
        key='trade_strategy'
    )
    
    strategy_data = results[selected]
    
    # 거래 통계
    trades = strategy_data.get('trades', [])
    
    if trades:
        df_trades = pd.DataFrame(trades)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_trades = len(df_trades)
            st.metric("총 거래 수", f"{total_trades}회")
        
        with col2:
            if 'profit' in df_trades.columns:
                winning_trades = len(df_trades[df_trades['profit'] > 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                st.metric("승률", f"{win_rate:.2f}%")
        
        with col3:
            if 'profit' in df_trades.columns:
                avg_profit = df_trades['profit'].mean()
                st.metric("평균 수익", f"{avg_profit:.2f}%")
        
        # 거래 내역 테이블
        st.subheader("거래 내역")
        st.dataframe(
            df_trades.head(50),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("거래 데이터가 없습니다.")


def show_regime_analysis(results):
    """레짐 분석"""
    st.header("🌡️ 시장 레짐 분석")
    
    if 'hybrid' not in results:
        st.info("하이브리드 전략 결과가 필요합니다.")
        return
    
    hybrid = results['hybrid']
    regime_stats = hybrid.get('regime_stats', {})
    
    if regime_stats:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bull_days = regime_stats.get('bull_days', 0)
            bull_pct = regime_stats.get('bull_pct', 0) * 100
            st.metric("상승장", f"{bull_days}일", f"{bull_pct:.1f}%")
        
        with col2:
            neutral_days = regime_stats.get('neutral_days', 0)
            neutral_pct = regime_stats.get('neutral_pct', 0) * 100
            st.metric("중립장", f"{neutral_days}일", f"{neutral_pct:.1f}%")
        
        with col3:
            bear_days = regime_stats.get('bear_days', 0)
            bear_pct = regime_stats.get('bear_pct', 0) * 100
            st.metric("하락장", f"{bear_days}일", f"{bear_pct:.1f}%")
        
        # 레짐 분포 차트
        fig = go.Figure(data=[
            go.Pie(
                labels=['상승장', '중립장', '하락장'],
                values=[bull_days, neutral_days, bear_days],
                marker_colors=['#96CEB4', '#FFEAA7', '#FF6B6B']
            )
        ])
        
        fig.update_layout(
            title="시장 레짐 분포",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("레짐 분석 데이터가 없습니다.")


def show():
    """메인 함수"""
    st.title("📊 백테스트 결과")
    st.markdown("---")
    
    # 데이터 로드
    results = load_backtest_results()
    
    if results is None:
        st.warning("""
        ⚠️ 백테스트 결과가 없습니다.
        
        Phase 2 백테스트를 먼저 실행하세요:
        ```bash
        python scripts/phase2/run_backtest_jason.py
        ```
        """)
        return
    
    # 탭 생성
    tabs = st.tabs([
        "📊 성과 지표",
        "📈 자산 곡선",
        "📉 낙폭",
        "💼 거래 분석",
        "🌡️ 레짐 분석"
    ])
    
    with tabs[0]:
        show_performance_metrics(results)
    
    with tabs[1]:
        show_equity_curve(results)
    
    with tabs[2]:
        show_drawdown_chart(results)
    
    with tabs[3]:
        show_trade_analysis(results)
    
    with tabs[4]:
        show_regime_analysis(results)
    
    # 새로고침 버튼
    st.markdown("---")
    if st.button("🔄 데이터 새로고침"):
        st.rerun()


if __name__ == "__main__":
    show()
