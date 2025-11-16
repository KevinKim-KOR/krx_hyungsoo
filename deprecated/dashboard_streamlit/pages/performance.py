#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/performance.py
성과 분석 페이지
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import PerformanceTracker


def show():
    """성과 분석 페이지 표시"""
    st.title("📊 성과 분석")
    st.markdown("---")
    
    try:
        perf_tracker = PerformanceTracker()
        
        # 기간 선택
        period = st.selectbox(
            "조회 기간",
            [30, 60, 90, 180, 365],
            index=2,
            format_func=lambda x: f"최근 {x}일"
        )
        
        end_date = date.today()
        start_date = end_date - timedelta(days=period)
        
        # 성과 데이터
        performance_data = perf_tracker.get_performance_history(start_date, end_date)
        
        if not performance_data or len(performance_data) == 0:
            st.warning("성과 데이터가 없습니다.")
            return
        
        df = pd.DataFrame(performance_data)
        df['date'] = pd.to_datetime(df['date'])
        
        # 주요 지표
        st.markdown("### 📊 주요 성과 지표")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_return = df['cumulative_return'].iloc[-1]
            st.metric("총 수익률", f"{total_return:.2%}")
        
        with col2:
            avg_daily = df['daily_return'].mean()
            st.metric("평균 일일 수익률", f"{avg_daily:.2%}")
        
        with col3:
            max_dd = df['daily_return'].min()
            st.metric("최대 일일 손실", f"{max_dd:.2%}")
        
        with col4:
            win_rate = (df['daily_return'] > 0).sum() / len(df) * 100
            st.metric("승률", f"{win_rate:.1f}%")
        
        st.markdown("---")
        
        # 누적 수익률 차트
        st.markdown("### 📈 누적 수익률 추이")
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['cumulative_return'] * 100,
            mode='lines',
            name='누적 수익률',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.update_layout(
            xaxis_title="날짜",
            yaxis_title="수익률 (%)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 일일 수익률 차트
        st.markdown("### 📊 일일 수익률 분포")
        
        fig2 = go.Figure()
        
        colors = ['green' if x > 0 else 'red' for x in df['daily_return']]
        
        fig2.add_trace(go.Bar(
            x=df['date'],
            y=df['daily_return'] * 100,
            marker_color=colors,
            name='일일 수익률'
        ))
        
        fig2.update_layout(
            xaxis_title="날짜",
            yaxis_title="수익률 (%)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig2, use_container_width=True)
        
        # 통계 테이블
        st.markdown("### 📋 상세 통계")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**수익률 통계**")
            stats_df = pd.DataFrame({
                '지표': ['평균', '중앙값', '표준편차', '최대', '최소'],
                '값': [
                    f"{df['daily_return'].mean():.2%}",
                    f"{df['daily_return'].median():.2%}",
                    f"{df['daily_return'].std():.2%}",
                    f"{df['daily_return'].max():.2%}",
                    f"{df['daily_return'].min():.2%}"
                ]
            })
            st.dataframe(stats_df, hide_index=True, use_container_width=True)
        
        with col2:
            st.markdown("**거래 통계**")
            trade_stats = pd.DataFrame({
                '지표': ['총 거래일', '상승일', '하락일', '승률'],
                '값': [
                    f"{len(df)}일",
                    f"{(df['daily_return'] > 0).sum()}일",
                    f"{(df['daily_return'] < 0).sum()}일",
                    f"{(df['daily_return'] > 0).sum() / len(df) * 100:.1f}%"
                ]
            })
            st.dataframe(trade_stats, hide_index=True, use_container_width=True)
    
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
