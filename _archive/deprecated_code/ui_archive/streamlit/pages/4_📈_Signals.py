#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실시간 신호 - 매수/매도 신호 모니터링 및 히스토리
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import json

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Signals", page_icon="📈", layout="wide")

st.title("📈 실시간 신호")
st.markdown("---")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["🔔 오늘의 신호", "📊 신호 히스토리", "📈 신호 분석"])

with tab1:
    st.subheader("🔔 오늘의 신호")
    
    # 현재 시간 및 레짐
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("현재 시간", datetime.now().strftime("%Y-%m-%d %H:%M"))
    with col2:
        st.metric("현재 레짐", "상승장 📈", delta="신뢰도 95%")
    with col3:
        st.metric("권장 포지션", "120%")
    
    st.markdown("---")
    
    # 매수 신호
    st.subheader("🟢 매수 신호")
    
    buy_signals = pd.DataFrame({
        '순위': [1, 2, 3, 4, 5],
        '종목명': ['KODEX 200', 'TIGER 미국S&P500', 'KODEX 레버리지', 'TIGER 차이나전기차', 'KODEX 반도체'],
        '코드': ['069500', '143850', '122630', '371460', '091160'],
        'MAPS 점수': [85.23, 82.15, 78.92, 75.48, 72.31],
        '현재가': [36500, 44000, 29500, 15200, 42800],
        '목표가': [38500, 46000, 31000, 16000, 45000],
        '기대 수익률': [5.48, 4.55, 5.08, 5.26, 5.14]
    })
    
    # MAPS 점수에 따라 색상 적용
    def color_maps(val):
        if val >= 80:
            return 'background-color: #90EE90'  # 연한 초록
        elif val >= 70:
            return 'background-color: #FFFFE0'  # 연한 노랑
        else:
            return ''
    
    styled_buy = buy_signals.style.applymap(
        color_maps,
        subset=['MAPS 점수']
    ).format({
        'MAPS 점수': '{:.2f}',
        '현재가': '{:,.0f}원',
        '목표가': '{:,.0f}원',
        '기대 수익률': '{:+.2f}%'
    })
    
    st.dataframe(styled_buy, use_container_width=True, hide_index=True)
    
    st.info("""
    💡 **매수 신호 해석**
    - MAPS 점수 80 이상: 강력 매수 추천
    - MAPS 점수 70~80: 매수 고려
    - MAPS 점수 70 미만: 관망
    """)
    
    # 매도 신호
    st.markdown("---")
    st.subheader("🔴 매도 신호")
    
    sell_signals = pd.DataFrame({
        '종목명': ['KODEX 인버스', 'TIGER 200선물인버스2X'],
        '코드': ['114800', '252670'],
        '보유 수량': [50, 30],
        '매수가': [5200, 8500],
        '현재가': [4800, 8100],
        '수익률': [-7.69, -4.71],
        '매도 사유': ['손절 라인 도달', '레짐 변경']
    })
    
    def color_loss(val):
        return 'color: red' if val < 0 else 'color: green'
    
    styled_sell = sell_signals.style.applymap(
        color_loss,
        subset=['수익률']
    ).format({
        '매수가': '{:,.0f}원',
        '현재가': '{:,.0f}원',
        '수익률': '{:+.2f}%'
    })
    
    st.dataframe(styled_sell, use_container_width=True, hide_index=True)
    
    if len(sell_signals) > 0:
        st.warning("⚠️ 매도 신호가 발생했습니다. 포지션 정리를 고려하세요.")
    else:
        st.success("✅ 현재 매도 신호가 없습니다.")

with tab2:
    st.subheader("📊 신호 히스토리")
    
    # 날짜 선택
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "시작일",
            value=date.today() - timedelta(days=30)
        )
    
    with col2:
        end_date = st.date_input(
            "종료일",
            value=date.today()
        )
    
    # 신호 로그 디렉토리
    signal_dir = project_root / "data" / "monitoring" / "signals"
    
    if signal_dir.exists():
        signal_files = list(signal_dir.glob("signals_*.json"))
        
        if signal_files:
            st.info(f"💾 기록된 신호: {len(signal_files)}일")
            
            # 신호 히스토리 테이블
            history_data = []
            
            for signal_file in sorted(signal_files, reverse=True)[:30]:  # 최근 30일
                try:
                    with open(signal_file, 'r', encoding='utf-8') as f:
                        signal_data = json.load(f)
                    
                    for signal in signal_data.get('signals', []):
                        history_data.append({
                            '날짜': signal_data['date'],
                            '시간': signal['timestamp'].split('T')[1][:8],
                            '타입': '매수' if signal['type'] == 'buy' else '매도',
                            '신호 수': signal['count'],
                            '레짐': signal.get('regime', {}).get('state', 'N/A'),
                            '신뢰도': f"{signal.get('regime', {}).get('confidence', 0):.1f}%"
                        })
                except Exception as e:
                    continue
            
            if history_data:
                df_history = pd.DataFrame(history_data)
                
                # 타입별 필터
                signal_type_filter = st.multiselect(
                    "신호 타입 필터",
                    options=['매수', '매도'],
                    default=['매수', '매도']
                )
                
                filtered_df = df_history[df_history['타입'].isin(signal_type_filter)]
                
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
                
                # 일별 신호 수 차트
                st.markdown("---")
                st.subheader("📊 일별 신호 수")
                
                daily_counts = df_history.groupby(['날짜', '타입']).size().reset_index(name='count')
                
                fig = go.Figure()
                
                for signal_type in ['매수', '매도']:
                    type_data = daily_counts[daily_counts['타입'] == signal_type]
                    fig.add_trace(go.Bar(
                        x=type_data['날짜'],
                        y=type_data['count'],
                        name=signal_type,
                        marker_color='green' if signal_type == '매수' else 'red'
                    ))
                
                fig.update_layout(
                    title='일별 신호 발생 횟수',
                    xaxis_title='날짜',
                    yaxis_title='신호 수',
                    barmode='group',
                    height=300
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            else:
                st.warning("⚠️ 신호 데이터를 불러올 수 없습니다.")
        
        else:
            st.warning("⚠️ 기록된 신호가 없습니다.")
    
    else:
        st.warning("⚠️ 신호 로그 디렉토리가 없습니다.")

with tab3:
    st.subheader("📈 신호 분석")
    
    # 신호 정확도 분석
    st.markdown("**🎯 신호 정확도**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("전체 정확도", "62.3%", delta="+2.3%")
    with col2:
        st.metric("매수 신호 정확도", "65.8%", delta="+3.1%")
    with col3:
        st.metric("매도 신호 정확도", "58.9%", delta="+1.5%")
    
    st.info("""
    💡 **정확도 계산**
    - 매수 신호: 신호 발생 후 5일 내 수익 발생 비율
    - 매도 신호: 신호 발생 후 추가 하락 방지 비율
    """)
    
    # MAPS 점수 분포
    st.markdown("---")
    st.subheader("📊 MAPS 점수 분포")
    
    maps_scores = [85.23, 82.15, 78.92, 75.48, 72.31, 68.54, 65.23, 62.18, 58.92, 55.47]
    
    fig = go.Figure(data=[go.Histogram(
        x=maps_scores,
        nbinsx=10,
        marker_color='lightblue'
    )])
    
    fig.update_layout(
        title='MAPS 점수 분포',
        xaxis_title='MAPS 점수',
        yaxis_title='빈도',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 레짐별 신호 성과
    st.markdown("---")
    st.subheader("🎯 레짐별 신호 성과")
    
    regime_performance = pd.DataFrame({
        '레짐': ['상승장', '중립장', '하락장'],
        '신호 수': [150, 80, 40],
        '평균 수익률': [3.2, 1.5, -0.8],
        '정확도': [68.5, 58.2, 52.1]
    })
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=regime_performance['레짐'],
        y=regime_performance['평균 수익률'],
        name='평균 수익률',
        marker_color=['green', 'gray', 'red'],
        yaxis='y',
        offsetgroup=1
    ))
    
    fig.add_trace(go.Scatter(
        x=regime_performance['레짐'],
        y=regime_performance['정확도'],
        name='정확도',
        mode='lines+markers',
        marker=dict(size=10),
        yaxis='y2',
        offsetgroup=2
    ))
    
    fig.update_layout(
        title='레짐별 성과',
        xaxis_title='레짐',
        yaxis=dict(title='평균 수익률 (%)'),
        yaxis2=dict(title='정확도 (%)', overlaying='y', side='right'),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 신호 타이밍 분석
    st.markdown("---")
    st.subheader("⏰ 신호 타이밍 분석")
    
    timing_data = pd.DataFrame({
        '보유 기간': ['1일', '3일', '5일', '7일', '10일', '15일'],
        '평균 수익률': [0.8, 1.5, 2.3, 2.8, 3.2, 3.5],
        '최대 수익률': [3.2, 5.1, 7.8, 9.2, 11.5, 13.8],
        '최소 수익률': [-1.5, -2.3, -3.1, -3.8, -4.2, -4.8]
    })
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=timing_data['보유 기간'],
        y=timing_data['평균 수익률'],
        mode='lines+markers',
        name='평균',
        line=dict(color='blue', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=timing_data['보유 기간'],
        y=timing_data['최대 수익률'],
        mode='lines',
        name='최대',
        line=dict(color='green', width=1, dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=timing_data['보유 기간'],
        y=timing_data['최소 수익률'],
        mode='lines',
        name='최소',
        line=dict(color='red', width=1, dash='dash')
    ))
    
    fig.update_layout(
        title='보유 기간별 수익률',
        xaxis_title='보유 기간',
        yaxis_title='수익률 (%)',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)

# 푸터
st.markdown("---")
st.caption("📈 Signals | 실시간 신호 모니터링")
