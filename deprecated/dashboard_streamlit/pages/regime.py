#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/regime.py
시장 레짐 페이지
"""
import streamlit as st
from datetime import date, timedelta
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import RegimeDetector


def show():
    """시장 레짐 페이지 표시"""
    st.title("🌡️ 시장 레짐")
    st.markdown("---")
    
    try:
        regime_detector = RegimeDetector()
        
        # 현재 레짐
        target_date = date.today() - timedelta(days=1)
        regime = regime_detector.detect_regime(target_date)
        
        # 레짐 표시
        regime_emoji = {
            'bull': '🟢',
            'bear': '🔴',
            'sideways': '🟡',
            'volatile': '🟠'
        }
        
        regime_name = {
            'bull': '강세장 (Bull Market)',
            'bear': '약세장 (Bear Market)',
            'sideways': '횡보장 (Sideways)',
            'volatile': '고변동성 (Volatile)'
        }
        
        st.markdown(f"### {regime_emoji.get(regime['state'], '⚪')} 현재 레짐: {regime_name.get(regime['state'], 'Unknown')}")
        
        st.markdown("---")
        
        # 레짐 지표
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "변동성 (20일)",
                f"{regime['volatility']:.2%}",
                help="연율화된 변동성"
            )
        
        with col2:
            st.metric(
                "추세 (60일 MA)",
                f"{regime['trend']:+.2%}",
                help="현재가 대비 60일 이동평균 위치"
            )
        
        with col3:
            st.metric(
                "모멘텀 (20일)",
                f"{regime['momentum']:+.2%}",
                help="20일 수익률"
            )
        
        st.markdown("---")
        
        # 레짐 설명
        st.markdown("### 📖 레짐 설명")
        
        description = regime_detector.get_regime_description(regime)
        st.info(description)
        
        st.markdown("---")
        
        # 레짐별 전략 가이드
        st.markdown("### 💡 레짐별 투자 전략")
        
        if regime['state'] == 'bull':
            st.success("""
            **강세장 전략**
            - ✅ 적극적 매수 포지션 유지
            - ✅ 모멘텀 강한 종목 선호
            - ⚠️ 과열 신호 주의
            """)
        
        elif regime['state'] == 'bear':
            st.error("""
            **약세장 전략**
            - ⚠️ 방어적 포지션 축소
            - ⚠️ 손절매 철저히
            - ✅ 현금 비중 확대
            """)
        
        elif regime['state'] == 'sideways':
            st.warning("""
            **횡보장 전략**
            - ✅ 단기 매매 전략
            - ✅ 레인지 트레이딩
            - ⚠️ 추세 전환 신호 주시
            """)
        
        elif regime['state'] == 'volatile':
            st.warning("""
            **고변동성 전략**
            - ⚠️ 포지션 사이즈 축소
            - ⚠️ 손절매 폭 확대
            - ✅ 리스크 관리 강화
            """)
        
        st.markdown("---")
        
        # 레짐 정의
        with st.expander("📚 레짐 분류 기준"):
            st.markdown("""
            **강세장 (Bull)**:
            - 추세: 상승 (60일 MA 위)
            - 모멘텀: 긍정적 (20일 수익률 > 0)
            - 변동성: 낮음 (< 20%)
            
            **약세장 (Bear)**:
            - 추세: 하락 (60일 MA 아래)
            - 모멘텀: 부정적 (20일 수익률 < 0)
            
            **횡보장 (Sideways)**:
            - 추세: 불분명
            - 모멘텀: 약함
            
            **고변동성 (Volatile)**:
            - 변동성: 높음 (> 20%)
            - 리스크 관리 필요
            """)
    
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
