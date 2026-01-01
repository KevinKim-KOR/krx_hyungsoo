#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파라미터 비교 - 여러 설정을 나란히 비교
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys
import json
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Compare", page_icon="🔍", layout="wide")

st.title("🔍 파라미터 비교")
st.markdown("---")

# 히스토리 디렉토리
history_dir = project_root / "data" / "parameter_history"

if not history_dir.exists() or not list(history_dir.glob("params_*.json")):
    st.warning("⚠️ 저장된 파라미터 히스토리가 없습니다.")
    st.info("💡 Parameters 페이지에서 파라미터를 저장하면 비교할 수 있습니다.")
    st.stop()

# 히스토리 로드
history_files = sorted(history_dir.glob("params_*.json"), reverse=True)
history_data = []

for file in history_files[:20]:  # 최근 20개
    try:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            history_data.append({
                'file': file,
                'data': data
            })
    except:
        continue

if not history_data:
    st.error("❌ 히스토리 데이터를 불러올 수 없습니다.")
    st.stop()

# 비교할 설정 선택
st.subheader("📋 비교할 설정 선택")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**설정 A**")
    selected_a = st.selectbox(
        "첫 번째 설정",
        options=range(len(history_data)),
        format_func=lambda x: f"{history_data[x]['data']['datetime'][:19]} - {history_data[x]['data'].get('note', '메모 없음')}",
        key="select_a"
    )

with col2:
    st.markdown("**설정 B**")
    selected_b = st.selectbox(
        "두 번째 설정",
        options=range(len(history_data)),
        format_func=lambda x: f"{history_data[x]['data']['datetime'][:19]} - {history_data[x]['data'].get('note', '메모 없음')}",
        index=min(1, len(history_data)-1),
        key="select_b"
    )

if selected_a == selected_b:
    st.warning("⚠️ 같은 설정을 선택했습니다. 다른 설정을 선택하세요.")
    st.stop()

# 선택된 설정
config_a = history_data[selected_a]['data']
config_b = history_data[selected_b]['data']

# 비교 테이블
st.markdown("---")
st.subheader("📊 파라미터 비교")

# 비교 데이터 생성
comparison_data = {
    '항목': [
        '저장 시간',
        '메모',
        'MAPS 임계값',
        '단기 MA',
        '장기 MA',
        '레짐 임계값',
        '상승장 포지션',
        '중립장 포지션',
        '하락장 포지션',
        '손절 라인',
        '방어 모드 신뢰도',
        '최대 종목 비중',
        '백테스트 CAGR',
        '백테스트 Sharpe',
        '백테스트 MDD'
    ],
    '설정 A': [
        config_a['datetime'][:19],
        config_a.get('note', '-'),
        config_a['params'].get('maps_threshold', '-'),
        f"{config_a['params'].get('regime_ma_short', '-')}일",
        f"{config_a['params'].get('regime_ma_long', '-')}일",
        f"±{config_a['params'].get('regime_threshold', '-')}%",
        f"{config_a['params'].get('position_bull', '-')}%",
        f"{config_a['params'].get('position_sideways', '-')}%",
        f"{config_a['params'].get('position_bear', '-')}%",
        f"{config_a['params'].get('stop_loss', '-')}%",
        f"{config_a['params'].get('defense_confidence', '-')}%",
        f"{config_a['params'].get('max_position_size', '-')}%",
        f"{config_a.get('backtest_result', {}).get('cagr', '미실행')}" if isinstance(config_a.get('backtest_result'), dict) else '미실행',
        f"{config_a.get('backtest_result', {}).get('sharpe', '미실행')}" if isinstance(config_a.get('backtest_result'), dict) else '미실행',
        f"{config_a.get('backtest_result', {}).get('mdd', '미실행')}" if isinstance(config_a.get('backtest_result'), dict) else '미실행'
    ],
    '설정 B': [
        config_b['datetime'][:19],
        config_b.get('note', '-'),
        config_b['params'].get('maps_threshold', '-'),
        f"{config_b['params'].get('regime_ma_short', '-')}일",
        f"{config_b['params'].get('regime_ma_long', '-')}일",
        f"±{config_b['params'].get('regime_threshold', '-')}%",
        f"{config_b['params'].get('position_bull', '-')}%",
        f"{config_b['params'].get('position_sideways', '-')}%",
        f"{config_b['params'].get('position_bear', '-')}%",
        f"{config_b['params'].get('stop_loss', '-')}%",
        f"{config_b['params'].get('defense_confidence', '-')}%",
        f"{config_b['params'].get('max_position_size', '-')}%",
        f"{config_b.get('backtest_result', {}).get('cagr', '미실행')}" if isinstance(config_b.get('backtest_result'), dict) else '미실행',
        f"{config_b.get('backtest_result', {}).get('sharpe', '미실행')}" if isinstance(config_b.get('backtest_result'), dict) else '미실행',
        f"{config_b.get('backtest_result', {}).get('mdd', '미실행')}" if isinstance(config_b.get('backtest_result'), dict) else '미실행'
    ]
}

df_comparison = pd.DataFrame(comparison_data)

# 차이 강조
def highlight_diff(row):
    if row['설정 A'] != row['설정 B'] and row['항목'] not in ['저장 시간', '메모']:
        return ['background-color: #fff3cd'] * len(row)
    return [''] * len(row)

styled_df = df_comparison.style.apply(highlight_diff, axis=1)

st.dataframe(styled_df, use_container_width=True, hide_index=True)

# 성과 비교 차트
if (isinstance(config_a.get('backtest_result'), dict) and 
    isinstance(config_b.get('backtest_result'), dict)):
    
    st.markdown("---")
    st.subheader("📈 백테스트 성과 비교")
    
    metrics = ['CAGR', 'Sharpe', 'MDD']
    values_a = [
        config_a['backtest_result'].get('cagr', 0),
        config_a['backtest_result'].get('sharpe', 0),
        abs(config_a['backtest_result'].get('mdd', 0))  # MDD는 절대값
    ]
    values_b = [
        config_b['backtest_result'].get('cagr', 0),
        config_b['backtest_result'].get('sharpe', 0),
        abs(config_b['backtest_result'].get('mdd', 0))
    ]
    
    fig = go.Figure(data=[
        go.Bar(name='설정 A', x=metrics, y=values_a, marker_color='lightblue'),
        go.Bar(name='설정 B', x=metrics, y=values_b, marker_color='lightcoral')
    ])
    
    fig.update_layout(
        title='성과 지표 비교',
        barmode='group',
        height=400,
        yaxis_title='값'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 승자 표시
    st.markdown("---")
    st.subheader("🏆 종합 평가")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        winner_cagr = "설정 A" if values_a[0] > values_b[0] else "설정 B"
        st.metric(
            "CAGR 우수",
            winner_cagr,
            delta=f"{abs(values_a[0] - values_b[0]):.2f}% 차이"
        )
    
    with col2:
        winner_sharpe = "설정 A" if values_a[1] > values_b[1] else "설정 B"
        st.metric(
            "Sharpe 우수",
            winner_sharpe,
            delta=f"{abs(values_a[1] - values_b[1]):.2f} 차이"
        )
    
    with col3:
        winner_mdd = "설정 A" if values_a[2] < values_b[2] else "설정 B"
        st.metric(
            "MDD 우수 (낮을수록 좋음)",
            winner_mdd,
            delta=f"{abs(values_a[2] - values_b[2]):.2f}% 차이"
        )

else:
    st.info("💡 백테스트 결과가 있는 설정을 선택하면 성과 비교 차트가 표시됩니다.")

# 파라미터 차이 요약
st.markdown("---")
st.subheader("🔍 주요 차이점")

differences = []

param_names = {
    'maps_threshold': 'MAPS 임계값',
    'regime_ma_short': '단기 MA',
    'regime_ma_long': '장기 MA',
    'regime_threshold': '레짐 임계값',
    'position_bull': '상승장 포지션',
    'position_sideways': '중립장 포지션',
    'position_bear': '하락장 포지션',
    'stop_loss': '손절 라인',
    'defense_confidence': '방어 모드 신뢰도',
    'max_position_size': '최대 종목 비중'
}

for key, name in param_names.items():
    val_a = config_a['params'].get(key)
    val_b = config_b['params'].get(key)
    
    if val_a != val_b:
        differences.append({
            '파라미터': name,
            '설정 A': val_a,
            '설정 B': val_b,
            '차이': val_b - val_a if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)) else 'N/A'
        })

if differences:
    df_diff = pd.DataFrame(differences)
    st.dataframe(df_diff, use_container_width=True, hide_index=True)
else:
    st.success("✅ 두 설정이 동일합니다.")

# 설정 적용
st.markdown("---")
st.subheader("💾 설정 적용")

col1, col2 = st.columns(2)

with col1:
    if st.button("📥 설정 A 적용", use_container_width=True, type="primary"):
        config_file = project_root / "config" / "strategy_params.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_a['params'], f, ensure_ascii=False, indent=2)
        st.success("✅ 설정 A를 현재 설정으로 적용했습니다!")

with col2:
    if st.button("📥 설정 B 적용", use_container_width=True, type="primary"):
        config_file = project_root / "config" / "strategy_params.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_b['params'], f, ensure_ascii=False, indent=2)
        st.success("✅ 설정 B를 현재 설정으로 적용했습니다!")

# 푸터
st.markdown("---")
st.caption("🔍 Compare | 파라미터 비교 분석")
