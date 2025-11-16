#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/portfolio.py
포트폴리오 현황 페이지
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import PerformanceTracker


def show():
    """포트폴리오 페이지 표시"""
    st.title("💼 포트폴리오 현황")
    st.markdown("---")
    
    try:
        perf_tracker = PerformanceTracker()
        
        # 최근 성과
        latest = perf_tracker.get_latest_performance()
        
        if not latest:
            st.warning("포트폴리오 데이터가 없습니다.")
            return
        
        # 주요 지표
        st.markdown("### 📊 현재 포트폴리오")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "총 자산",
                f"{latest['total_value']:,.0f}원",
                delta=f"{latest['daily_return']:.2%}"
            )
        
        with col2:
            st.metric(
                "현금",
                f"{latest['cash']:,.0f}원"
            )
        
        with col3:
            st.metric(
                "포지션 가치",
                f"{latest['positions_value']:,.0f}원"
            )
        
        st.markdown("---")
        
        # 수익률 정보
        st.markdown("### 📈 수익률")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "일일 수익률",
                f"{latest['daily_return']:.2%}"
            )
        
        with col2:
            st.metric(
                "누적 수익률",
                f"{latest['cumulative_return']:.2%}"
            )
        
        with col3:
            st.metric(
                "포지션 수",
                f"{latest['position_count']}개"
            )
        
        st.markdown("---")
        
        # 최근 30일 성과 차트
        st.markdown("### 📊 최근 30일 성과")
        
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        performance_data = perf_tracker.get_performance_history(start_date, end_date)
        
        if performance_data and len(performance_data) > 0:
            df = pd.DataFrame(performance_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # 누적 수익률 차트
            st.line_chart(
                df.set_index('date')['cumulative_return'],
                use_container_width=True
            )
            
            # 데이터 테이블
            st.markdown("### 📋 상세 데이터")
            
            display_df = df[['date', 'total_value', 'daily_return', 'cumulative_return', 'position_count']].copy()
            display_df.columns = ['날짜', '총 자산', '일일 수익률', '누적 수익률', '포지션 수']
            display_df['총 자산'] = display_df['총 자산'].apply(lambda x: f"{x:,.0f}원")
            display_df['일일 수익률'] = display_df['일일 수익률'].apply(lambda x: f"{x:.2%}")
            display_df['누적 수익률'] = display_df['누적 수익률'].apply(lambda x: f"{x:.2%}")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("성과 데이터가 없습니다.")
    
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
