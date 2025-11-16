#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/signals.py
신호 히스토리 페이지
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import SignalTracker


def show():
    """신호 히스토리 페이지 표시"""
    st.title("📈 신호 히스토리")
    st.markdown("---")
    
    try:
        signal_tracker = SignalTracker()
        
        # 기간 선택
        col1, col2 = st.columns(2)
        
        with col1:
            days = st.selectbox(
                "조회 기간",
                [7, 14, 30, 60, 90],
                index=2,
                format_func=lambda x: f"최근 {x}일"
            )
        
        with col2:
            action_filter = st.selectbox(
                "액션 필터",
                ["전체", "매수", "매도"],
                index=0
            )
        
        # 통계
        stats = signal_tracker.get_signal_stats(days=days)
        
        st.markdown(f"### 📊 최근 {days}일 통계")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 신호", f"{stats['total_signals']}개")
        
        with col2:
            st.metric("매수", f"{stats['buy_count']}개")
        
        with col3:
            st.metric("매도", f"{stats['sell_count']}개")
        
        with col4:
            st.metric("평균 신뢰도", f"{stats['avg_confidence']:.2f}")
        
        st.markdown("---")
        
        # 신호 목록
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        signals = signal_tracker.get_signals(start_date=start_date, end_date=end_date)
        
        if len(signals) > 0:
            df = pd.DataFrame(signals)
            
            # 액션 필터링
            if action_filter == "매수":
                df = df[df['action'] == 'buy']
            elif action_filter == "매도":
                df = df[df['action'] == 'sell']
            
            st.markdown(f"### 📋 신호 목록 ({len(df)}개)")
            
            # 날짜별 그룹화
            df['signal_date'] = pd.to_datetime(df['signal_date'])
            df_sorted = df.sort_values('signal_date', ascending=False)
            
            # 날짜별로 표시
            for signal_date in df_sorted['signal_date'].dt.date.unique():
                with st.expander(f"📅 {signal_date}", expanded=False):
                    day_signals = df_sorted[df_sorted['signal_date'].dt.date == signal_date]
                    
                    for _, signal in day_signals.iterrows():
                        action_emoji = "🟢" if signal['action'] == 'buy' else "🔴"
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.markdown(f"{action_emoji} **{signal['name']}** (`{signal['code']}`)")
                        
                        with col2:
                            st.markdown(f"신뢰도: **{signal['confidence']:.1%}**")
                        
                        with col3:
                            st.markdown(f"MAPS: **{signal['maps_score']:.2f}**")
                        
                        if signal['reason']:
                            st.caption(f"사유: {signal['reason']}")
                        
                        st.markdown("---")
        else:
            st.info("신호 데이터가 없습니다.")
    
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
