#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/app.py
실시간 모니터링 대시보드 (Streamlit)
"""
import streamlit as st
import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 페이지 설정
st.set_page_config(
    page_title="KRX Alertor Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바
st.sidebar.title("📊 KRX Alertor")
st.sidebar.markdown("---")

# 페이지 선택
page = st.sidebar.radio(
    "페이지 선택",
    [
        "🏠 홈", 
        "💼 포트폴리오", 
        "🎯 손절 전략", 
        "📊 백테스트", 
        "📈 신호 히스토리", 
        "🔔 알림 히스토리",
        "🌡️ 시장 레짐"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("실시간 매매 신호 모니터링 시스템")

# 메인 페이지
if page == "🏠 홈":
    from pages import home
    home.show()

elif page == "💼 포트폴리오":
    from pages import portfolio
    portfolio.show()

elif page == "🎯 손절 전략":
    from pages import stop_loss
    stop_loss.show()

elif page == "📊 백테스트":
    from pages import backtest
    backtest.show()

elif page == "📈 신호 히스토리":
    from pages import signals
    signals.show()

elif page == "🔔 알림 히스토리":
    from pages import alerts
    alerts.show()

elif page == "🌡️ 시장 레짐":
    from pages import regime
    regime.show()
