#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/stop_loss.py
손절 전략 성과 대시보드
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

from extensions.automation.portfolio_loader import PortfolioLoader


def load_strategy_comparison():
    """손절 전략 비교 결과 로드"""
    try:
        json_file = PROJECT_ROOT / "data" / "output" / "backtest" / "stop_loss_strategy_comparison.json"
        if json_file.exists():
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        st.error(f"전략 비교 결과 로드 실패: {e}")
        return None


def show_strategy_overview(comparison):
    """전략 개요"""
    st.header("🎯 손절 전략 개요")
    
    col1, col2, col3, col4 = st.columns(4)
    
    strategies = comparison.get('strategies', {})
    
    with col1:
        st.metric(
            "고정 손절",
            f"{strategies.get('fixed', {}).get('after_stop_loss_return_pct', 0):.2f}%",
            f"{strategies.get('fixed', {}).get('improvement', 0):+.2f}%p"
        )
        st.caption("기준: -7% 고정")
    
    with col2:
        st.metric(
            "레짐별 손절",
            f"{strategies.get('regime', {}).get('after_stop_loss_return_pct', 0):.2f}%",
            f"{strategies.get('regime', {}).get('improvement', 0):+.2f}%p"
        )
        st.caption("기준: -3% ~ -7%")
    
    with col3:
        st.metric(
            "동적 손절",
            f"{strategies.get('dynamic', {}).get('after_stop_loss_return_pct', 0):.2f}%",
            f"{strategies.get('dynamic', {}).get('improvement', 0):+.2f}%p"
        )
        st.caption("기준: -5% ~ -10%")
    
    with col4:
        st.metric(
            "하이브리드 손절",
            f"{strategies.get('hybrid', {}).get('after_stop_loss_return_pct', 0):.2f}%",
            f"{strategies.get('hybrid', {}).get('improvement', 0):+.2f}%p"
        )
        st.caption("기준: -3% ~ -10%")


def show_strategy_comparison_chart(comparison):
    """전략 비교 차트"""
    st.header("📊 전략 성과 비교")
    
    strategies = comparison.get('strategies', {})
    
    # 데이터 준비
    strategy_names = []
    improvements = []
    stop_loss_counts = []
    
    for name, data in strategies.items():
        strategy_info = data.get('strategy_info', {})
        strategy_names.append(strategy_info.get('name', name))
        improvements.append(data.get('improvement', 0))
        stop_loss_counts.append(data.get('stop_loss_count', 0))
    
    # 개선 효과 차트
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(data=[
            go.Bar(
                x=strategy_names,
                y=improvements,
                text=[f"{x:+.2f}%p" for x in improvements],
                textposition='auto',
                marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
            )
        ])
        fig.update_layout(
            title="전략별 개선 효과",
            xaxis_title="전략",
            yaxis_title="개선 (%p)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = go.Figure(data=[
            go.Bar(
                x=strategy_names,
                y=stop_loss_counts,
                text=stop_loss_counts,
                textposition='auto',
                marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
            )
        ])
        fig.update_layout(
            title="전략별 손절 대상 수",
            xaxis_title="전략",
            yaxis_title="손절 대상 (개)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)


def show_strategy_details(comparison):
    """전략 상세 정보"""
    st.header("📋 전략 상세 비교")
    
    strategies = comparison.get('strategies', {})
    
    # 데이터프레임 생성
    data = []
    for name, strategy_data in strategies.items():
        strategy_info = strategy_data.get('strategy_info', {})
        data.append({
            '전략': strategy_info.get('name', name),
            '설명': strategy_info.get('description', '-'),
            '손절 대상': strategy_data.get('stop_loss_count', 0),
            '안전 종목': strategy_data.get('safe_count', 0),
            '현재 수익률': f"{strategy_data.get('total_return_pct', 0):.2f}%",
            '손절 후 수익률': f"{strategy_data.get('after_stop_loss_return_pct', 0):.2f}%",
            '개선': f"{strategy_data.get('improvement', 0):+.2f}%p"
        })
    
    df = pd.DataFrame(data)
    
    # 스타일링
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def show_stop_loss_targets(comparison):
    """손절 대상 종목"""
    st.header("🔴 손절 대상 종목")
    
    # 전략 선택
    strategy_names = {
        'fixed': '고정 손절',
        'regime': '레짐별 손절',
        'dynamic': '동적 손절',
        'hybrid': '하이브리드 손절'
    }
    
    selected_strategy = st.selectbox(
        "전략 선택",
        list(strategy_names.keys()),
        format_func=lambda x: strategy_names[x]
    )
    
    strategies = comparison.get('strategies', {})
    strategy_data = strategies.get(selected_strategy, {})
    targets = strategy_data.get('stop_loss_targets', [])
    
    if targets:
        # 데이터프레임 생성
        df_targets = pd.DataFrame(targets)
        
        # 필요한 컬럼만 선택
        display_cols = ['name', 'code', 'return_pct', 'threshold', 'current_value', 'loss_amount']
        if all(col in df_targets.columns for col in display_cols):
            df_display = df_targets[display_cols].copy()
            df_display.columns = ['종목명', '코드', '손실률(%)', '손절기준(%)', '현재가치(원)', '손실금액(원)']
            
            # 포맷팅
            df_display['손실률(%)'] = df_display['손실률(%)'].apply(lambda x: f"{x:.2f}")
            df_display['손절기준(%)'] = df_display['손절기준(%)'].apply(lambda x: f"{x:.2f}")
            df_display['현재가치(원)'] = df_display['현재가치(원)'].apply(lambda x: f"{x:,.0f}")
            df_display['손실금액(원)'] = df_display['손실금액(원)'].apply(lambda x: f"{x:,.0f}")
            
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
            
            # 총 손실 금액
            total_loss = df_targets['loss_amount'].sum()
            st.metric("총 손실 금액", f"{total_loss:,.0f}원")
        else:
            st.dataframe(df_targets, use_container_width=True)
    else:
        st.success("✅ 손절 대상 없음")


def show_best_strategy(comparison):
    """최적 전략 추천"""
    st.header("⭐ 최적 전략 추천")
    
    best = comparison.get('best_strategy', {})
    best_info = best.get('info', {})
    best_strategy_info = best_info.get('strategy_info', {})
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.success(f"**{best_strategy_info.get('name', '알 수 없음')}**")
        st.write(f"**설명:** {best_strategy_info.get('description', '-')}")
        st.write(f"**손절 후 수익률:** {best_info.get('after_stop_loss_return_pct', 0):.2f}%")
        st.write(f"**개선 효과:** {best_info.get('improvement', 0):+.2f}%p")
        st.write(f"**손절 대상:** {best_info.get('stop_loss_count', 0)}개")
    
    with col2:
        st.info("""
        **적용 방법**
        
        1. NAS SSH 접속
        2. crontab -e
        3. 15:30 손절 스크립트 변경
        4. 저장 및 확인
        """)


def show():
    """메인 함수"""
    st.title("🎯 손절 전략 성과")
    st.markdown("---")
    
    # 데이터 로드
    comparison = load_strategy_comparison()
    
    if comparison is None:
        st.warning("""
        ⚠️ 손절 전략 비교 결과가 없습니다.
        
        다음 명령어를 실행하여 백테스트를 수행하세요:
        ```bash
        python scripts/phase4/compare_stop_loss_strategies.py
        ```
        """)
        return
    
    # 마지막 업데이트 시간
    timestamp = comparison.get('timestamp', 'Unknown')
    st.caption(f"마지막 업데이트: {timestamp}")
    
    # 탭 생성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 개요",
        "📈 비교 차트",
        "📋 상세 정보",
        "🔴 손절 대상",
        "⭐ 최적 전략"
    ])
    
    with tab1:
        show_strategy_overview(comparison)
    
    with tab2:
        show_strategy_comparison_chart(comparison)
    
    with tab3:
        show_strategy_details(comparison)
    
    with tab4:
        show_stop_loss_targets(comparison)
    
    with tab5:
        show_best_strategy(comparison)
    
    # 새로고침 버튼
    st.markdown("---")
    if st.button("🔄 데이터 새로고침"):
        st.rerun()


if __name__ == "__main__":
    show()
