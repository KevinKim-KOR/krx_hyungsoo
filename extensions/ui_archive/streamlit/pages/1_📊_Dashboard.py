#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
대시보드 - 실시간 포트폴리오 현황 및 성과 모니터링
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from pathlib import Path
import sys
import json

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

st.title("📊 대시보드")
st.markdown("---")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📈 성과 요약", "💼 포트폴리오", "📊 레짐 분석"])

with tab1:
    st.subheader("📈 백테스트 성과 요약")
    
    # 성과 지표
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="CAGR",
            value="27.05%",
            delta="-2.95% (목표 30%)",
            delta_color="inverse"
        )
    
    with col2:
        st.metric(
            label="Sharpe Ratio",
            value="1.51",
            delta="+0.01 (목표 1.5)",
            delta_color="normal"
        )
    
    with col3:
        st.metric(
            label="Max Drawdown",
            value="-19.92%",
            delta="-7.92% (목표 -12%)",
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            label="총 수익률",
            value="96.80%",
            delta="1,406회 거래"
        )
    
    st.markdown("---")
    
    # 수익 곡선 (더미 데이터)
    st.subheader("💰 수익 곡선")
    
    dates = pd.date_range(start='2022-01-01', end='2025-11-08', freq='D')
    equity = [10000]
    for i in range(1, len(dates)):
        # 더미 데이터: 랜덤 수익률
        import random
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
        name='포트폴리오 가치',
        line=dict(color='#1f77b4', width=2)
    ))
    
    fig.update_layout(
        title='포트폴리오 가치 추이',
        xaxis_title='날짜',
        yaxis_title='가치 (원)',
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 월별 수익률
    st.subheader("📅 월별 수익률")
    
    monthly_returns = pd.DataFrame({
        '월': ['2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', 
               '2025-07', '2025-08', '2025-09', '2025-10', '2025-11'],
        '수익률': [3.2, -1.5, 4.8, 2.1, -0.8, 5.3, 1.9, -2.3, 3.7, 4.2, 2.5]
    })
    
    fig = go.Figure(data=[
        go.Bar(
            x=monthly_returns['월'],
            y=monthly_returns['수익률'],
            marker_color=['green' if x > 0 else 'red' for x in monthly_returns['수익률']]
        )
    ])
    
    fig.update_layout(
        title='월별 수익률 (%)',
        xaxis_title='월',
        yaxis_title='수익률 (%)',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("💼 현재 포트폴리오")
    
    # 포트폴리오 요약
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("총 평가액", "11,500,000원")
    with col2:
        st.metric("총 수익", "+1,500,000원 (+15.00%)")
    with col3:
        st.metric("보유 종목", "3개")
    
    st.markdown("---")
    
    # 보유 종목 (더미 데이터)
    holdings = pd.DataFrame({
        '종목명': ['KODEX 200', 'TIGER 미국S&P500', 'KODEX 레버리지'],
        '코드': ['069500', '143850', '122630'],
        '수량': [100, 50, 80],
        '매수가': [35000, 42000, 28000],
        '현재가': [36500, 44000, 29500],
        '평가액': [3650000, 2200000, 2360000],
        '수익률': [4.29, 4.76, 5.36]
    })
    
    # 수익률에 따라 색상 적용
    def color_profit(val):
        color = 'green' if val > 0 else 'red'
        return f'color: {color}'
    
    styled_holdings = holdings.style.applymap(
        color_profit,
        subset=['수익률']
    ).format({
        '매수가': '{:,.0f}원',
        '현재가': '{:,.0f}원',
        '평가액': '{:,.0f}원',
        '수익률': '{:+.2f}%'
    })
    
    st.dataframe(styled_holdings, use_container_width=True)
    
    # 포트폴리오 구성 (파이 차트)
    st.subheader("📊 포트폴리오 구성")
    
    fig = go.Figure(data=[go.Pie(
        labels=holdings['종목명'],
        values=holdings['평가액'],
        hole=0.3
    )])
    
    fig.update_layout(
        title='종목별 비중',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("📊 레짐 분석")
    
    # 현재 레짐
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("현재 레짐", "상승장 📈")
    with col2:
        st.metric("신뢰도", "95.0%")
    with col3:
        st.metric("권장 포지션", "120%")
    
    st.markdown("---")
    
    # 레짐 히스토리
    st.subheader("📅 레짐 변경 히스토리")
    
    regime_history = pd.DataFrame({
        '날짜': ['2025-11-01', '2025-10-15', '2025-09-20', '2025-08-10', '2025-07-05'],
        '이전 레짐': ['중립장', '상승장', '중립장', '하락장', '중립장'],
        '현재 레짐': ['상승장', '중립장', '상승장', '중립장', '하락장'],
        '신뢰도': [95.0, 88.5, 92.3, 85.0, 90.5],
        '포지션 변경': ['80% → 120%', '120% → 80%', '80% → 120%', '50% → 80%', '80% → 50%']
    })
    
    st.dataframe(regime_history, use_container_width=True)
    
    # 레짐 분포
    st.subheader("📊 레짐 분포 (최근 6개월)")
    
    regime_dist = pd.DataFrame({
        '레짐': ['상승장', '중립장', '하락장'],
        '일수': [90, 60, 30],
        '비율': [50.0, 33.3, 16.7]
    })
    
    fig = go.Figure(data=[go.Bar(
        x=regime_dist['레짐'],
        y=regime_dist['일수'],
        text=regime_dist['비율'].apply(lambda x: f'{x:.1f}%'),
        textposition='auto',
        marker_color=['green', 'gray', 'red']
    )])
    
    fig.update_layout(
        title='레짐별 일수',
        xaxis_title='레짐',
        yaxis_title='일수',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)

# 푸터
st.markdown("---")
st.caption("📊 Dashboard | 실시간 업데이트")
