#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX Alertor 통합 대시보드
Streamlit 기반 파라미터 조정, 백테스트, 신호 모니터링 UI
"""

import streamlit as st
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

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
st.sidebar.info("💡 좌측 메뉴에서 페이지를 선택하세요")

# 메인 페이지
st.title("🏠 Main")
st.markdown("---")

# 환영 메시지
st.markdown("""
## 👋 환영합니다!

이 대시보드는 KRX Alertor 시스템의 통합 관리 도구입니다.

### 📋 주요 기능

1. **📊 대시보드** - 실시간 포트폴리오 현황 및 성과 모니터링
2. **⚙️ 파라미터 조정** - MAPS 임계값, 레짐 감지, 포지션 비율 설정
3. **🔬 백테스트** - 전략 성과 검증 및 최적화
4. **📈 실시간 신호** - 매수/매도 신호 모니터링 및 히스토리

### 🚀 시작하기

왼쪽 사이드바에서 원하는 메뉴를 선택하세요.
""")

# 현재 상태 표시
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📅 Phase",
        value="2.5",
        delta="하이브리드 실행"
    )

with col2:
    st.metric(
        label="🎯 CAGR",
        value="27.05%",
        delta="목표 30%"
    )

with col3:
    st.metric(
        label="📊 Sharpe",
        value="1.51",
        delta="목표 달성 ✅"
    )

with col4:
    st.metric(
        label="📉 MDD",
        value="-19.92%",
        delta="목표 -12%"
    )

st.markdown("---")

# 빠른 링크
st.subheader("🔗 빠른 링크")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **📚 문서**
    - [마스터 플랜](../../docs/MASTER_PLAN_2025.md)
    - [실행 가이드](../../docs/guides/HYBRID_EXECUTION_GUIDE.md)
    - [NAS 배포](../../docs/guides/nas/deployment.md)
    """)

with col2:
    st.markdown("""
    **🛠 도구**
    - 파라미터 최적화
    - 신호 로거
    - 주간 비교 리포트
    """)

with col3:
    st.markdown("""
    **📊 성과**
    - Week 3 하이브리드 전략
    - Phase 2 완료 요약
    - 텔레그램 PUSH 개선
    """)

# 푸터
st.markdown("---")
st.caption("KRX Alertor v2.5 | Phase 2.5 하이브리드 실행 | 2025-11-10")
