#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/home.py
홈 페이지 - 대시보드 개요
"""
import streamlit as st
from datetime import date, timedelta
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import SignalTracker, PerformanceTracker, RegimeDetector


def show():
    """홈 페이지 표시"""
    st.title("🏠 대시보드")
    st.markdown("---")
    
    # 날짜 선택
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📅 {date.today():%Y년 %m월 %d일}")
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    # 주요 지표 (4개 카드)
    st.markdown("### 📊 주요 지표")
    
    try:
        # 데이터 로드
        perf_tracker = PerformanceTracker()
        signal_tracker = SignalTracker()
        regime_detector = RegimeDetector()
        
        latest_perf = perf_tracker.get_latest_performance()
        signal_stats = signal_tracker.get_signal_stats(days=7)
        
        target_date = date.today() - timedelta(days=1)
        regime = regime_detector.detect_regime(target_date)
        
        # 4개 컬럼
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="💰 총 자산",
                value=f"{latest_perf['total_value']:,.0f}원" if latest_perf else "N/A",
                delta=f"{latest_perf['daily_return']:.2%}" if latest_perf else None
            )
        
        with col2:
            st.metric(
                label="📈 누적 수익률",
                value=f"{latest_perf['cumulative_return']:.2%}" if latest_perf else "N/A"
            )
        
        with col3:
            st.metric(
                label="📊 포지션 수",
                value=f"{latest_perf['position_count']}개" if latest_perf else "N/A"
            )
        
        with col4:
            regime_emoji = {
                'bull': '🟢',
                'bear': '🔴',
                'sideways': '🟡',
                'volatile': '🟠'
            }
            st.metric(
                label="🌡️ 시장 레짐",
                value=f"{regime_emoji.get(regime['state'], '⚪')} {regime['state'].upper()}"
            )
        
        st.markdown("---")
        
        # 최근 7일 신호 요약
        st.markdown("### 📈 최근 7일 신호 요약")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 신호", f"{signal_stats['total_signals']}개")
        
        with col2:
            st.metric("매수 신호", f"{signal_stats['buy_count']}개")
        
        with col3:
            st.metric("매도 신호", f"{signal_stats['sell_count']}개")
        
        st.markdown("---")
        
        # 빠른 링크
        st.markdown("### 🔗 빠른 링크")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("💼 포트폴리오", use_container_width=True):
                st.switch_page("pages/portfolio.py")
        
        with col2:
            if st.button("🎯 손절 전략", use_container_width=True):
                st.switch_page("pages/stop_loss.py")
        
        with col3:
            if st.button("📊 백테스트", use_container_width=True):
                st.switch_page("pages/backtest.py")
        
        with col4:
            if st.button("🔔 알림 히스토리", use_container_width=True):
                st.switch_page("pages/alerts.py")
    
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        st.info("DB 파일이 없거나 데이터가 없습니다. 먼저 신호를 생성해주세요.")
