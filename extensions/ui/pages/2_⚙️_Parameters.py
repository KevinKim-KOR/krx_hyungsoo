#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파라미터 조정 - MAPS 임계값, 레짐 감지, 포지션 비율 설정
"""

import streamlit as st
import json
from pathlib import Path
import sys
from datetime import datetime
import pandas as pd

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 프리셋 import
sys.path.insert(0, str(project_root / "extensions" / "ui"))
from components.parameter_presets import get_presets

st.set_page_config(page_title="Parameters", page_icon="⚙️", layout="wide")

st.title("⚙️ 파라미터 조정")
st.markdown("---")

# 프리셋 선택
st.subheader("🎯 프리셋 선택")
st.markdown("미리 정의된 전략을 선택하거나 직접 조정하세요.")

presets = get_presets()
preset_names = list(presets.keys())

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("⚖️ 균형 (기본)", use_container_width=True, type="secondary"):
        preset = presets["균형 (기본)"]
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(preset['params'], f, ensure_ascii=False, indent=2)
        st.success(f"✅ {preset['name']} 프리셋 적용!")
        st.info(f"📊 예상 성과: CAGR {preset['expected']['cagr']}, Sharpe {preset['expected']['sharpe']}")
        st.rerun()

with col2:
    if st.button("🚀 공격적", use_container_width=True, type="secondary"):
        preset = presets["공격적"]
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(preset['params'], f, ensure_ascii=False, indent=2)
        st.success(f"✅ {preset['name']} 프리셋 적용!")
        st.info(f"📊 예상 성과: CAGR {preset['expected']['cagr']}, Sharpe {preset['expected']['sharpe']}")
        st.rerun()

with col3:
    if st.button("🛡️ 보수적", use_container_width=True, type="secondary"):
        preset = presets["보수적"]
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(preset['params'], f, ensure_ascii=False, indent=2)
        st.success(f"✅ {preset['name']} 프리셋 적용!")
        st.info(f"📊 예상 성과: CAGR {preset['expected']['cagr']}, Sharpe {preset['expected']['sharpe']}")
        st.rerun()

with col4:
    if st.button("⭐ Week 3 최적", use_container_width=True, type="secondary"):
        preset = presets["Week 3 최적"]
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(preset['params'], f, ensure_ascii=False, indent=2)
        st.success(f"✅ {preset['name']} 프리셋 적용!")
        st.info(f"📊 검증된 성과: CAGR {preset['expected']['cagr']}, Sharpe {preset['expected']['sharpe']}")
        st.rerun()

# 프리셋 설명
with st.expander("💡 프리셋 상세 설명"):
    for preset_name, preset_data in presets.items():
        st.markdown(f"**{preset_data['name']}**")
        st.markdown(f"- {preset_data['description']}")
        st.markdown(f"- 예상 성과: CAGR {preset_data['expected']['cagr']}, Sharpe {preset_data['expected']['sharpe']}, MDD {preset_data['expected']['mdd']}")
        st.markdown("")

st.markdown("---")

# 설정 파일 경로
config_dir = project_root / "config"
config_dir.mkdir(exist_ok=True)
config_file = config_dir / "strategy_params.json"

# 히스토리 디렉토리
history_dir = project_root / "data" / "parameter_history"
history_dir.mkdir(parents=True, exist_ok=True)

# 기본 파라미터
def get_default_params():
    return {
        'maps_threshold': 5.0,
        'regime_ma_short': 50,
        'regime_ma_long': 200,
        'regime_threshold': 2.0,
        'position_bull': 120,
        'position_sideways': 80,
        'position_bear': 50,
        'defense_confidence': 85,
        'max_position_size': 20,
        'stop_loss': -5.0
    }

# 세션 상태 초기화
if 'params_updated' not in st.session_state:
    st.session_state.params_updated = False

# 현재 파라미터 로드
if config_file.exists():
    with open(config_file, 'r', encoding='utf-8') as f:
        params = json.load(f)
else:
    params = get_default_params()

# 파라미터 히스토리 로드
def load_parameter_history():
    """파라미터 히스토리 로드"""
    history_files = sorted(history_dir.glob("params_*.json"), reverse=True)
    history = []
    
    for file in history_files[:10]:  # 최근 10개
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                history.append(data)
        except:
            continue
    
    return history

def save_parameter_history(params, note=""):
    """파라미터 히스토리 저장"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    history_file = history_dir / f"params_{timestamp}.json"
    
    history_data = {
        'timestamp': timestamp,
        'datetime': datetime.now().isoformat(),
        'note': note,
        'params': params,
        'backtest_result': None  # 나중에 백테스트 결과 연동
    }
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    
    return history_file

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📊 MAPS 설정", "🎯 레짐 감지", "💼 포지션 관리", "🛡️ 리스크 관리"])

with tab1:
    st.subheader("📊 MAPS 설정")
    st.markdown("MAPS 점수 기반 종목 선정 기준을 설정합니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        maps_threshold = st.slider(
            "MAPS 임계값",
            min_value=0.0,
            max_value=20.0,
            value=float(params.get('maps_threshold', 5.0)),
            step=0.5,
            help="이 값보다 높은 MAPS 점수를 가진 종목만 매수 대상"
        )
        
        st.info(f"""
        **현재 설정**: {maps_threshold}
        
        - **낮음 (0~3)**: 많은 종목 선정, 분산 투자
        - **중간 (3~7)**: 균형잡힌 선정 ⭐ 권장
        - **높음 (7~20)**: 소수 우량 종목만 선정
        """)
    
    with col2:
        max_position_size = st.slider(
            "최대 종목 비중 (%)",
            min_value=5,
            max_value=30,
            value=int(params.get('max_position_size', 20)),
            step=5,
            help="단일 종목의 최대 포트폴리오 비중"
        )
        
        st.info(f"""
        **현재 설정**: {max_position_size}%
        
        - **낮음 (5~10%)**: 고분산, 안정적
        - **중간 (10~20%)**: 균형 ⭐ 권장
        - **높음 (20~30%)**: 집중 투자, 고위험
        """)

with tab2:
    st.subheader("🎯 레짐 감지 설정")
    st.markdown("시장 레짐(상승/중립/하락) 감지 파라미터를 설정합니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**이동평균 기간**")
        
        ma_short = st.selectbox(
            "단기 MA",
            options=[20, 50, 100],
            index=[20, 50, 100].index(params.get('regime_ma_short', 50)),
            help="단기 이동평균 기간"
        )
        
        ma_long = st.selectbox(
            "장기 MA",
            options=[50, 100, 200, 300],
            index=[50, 100, 200, 300].index(params.get('regime_ma_long', 200)),
            help="장기 이동평균 기간"
        )
        
        if ma_short >= ma_long:
            st.error("⚠️ 단기 MA는 장기 MA보다 작아야 합니다!")
    
    with col2:
        st.markdown("**레짐 판단 임계값**")
        
        regime_threshold = st.slider(
            "임계값 (%)",
            min_value=0.5,
            max_value=5.0,
            value=float(params.get('regime_threshold', 2.0)),
            step=0.5,
            help="단기MA와 장기MA의 차이 임계값"
        )
        
        st.info(f"""
        **현재 설정**: ±{regime_threshold}%
        
        - 단기MA > 장기MA + {regime_threshold}% → 상승장
        - 단기MA < 장기MA - {regime_threshold}% → 하락장
        - 그 외 → 중립장
        """)
    
    # 레짐 감지 시뮬레이션
    st.markdown("---")
    st.subheader("📊 레짐 감지 시뮬레이션")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sim_ma_short = st.number_input("단기 MA 값", value=2500.0, step=10.0)
    with col2:
        sim_ma_long = st.number_input("장기 MA 값", value=2450.0, step=10.0)
    with col3:
        diff_pct = ((sim_ma_short - sim_ma_long) / sim_ma_long) * 100
        
        if diff_pct > regime_threshold:
            regime = "상승장 📈"
            color = "green"
        elif diff_pct < -regime_threshold:
            regime = "하락장 📉"
            color = "red"
        else:
            regime = "중립장 ➡️"
            color = "gray"
        
        st.metric(
            "예상 레짐",
            regime,
            delta=f"{diff_pct:+.2f}%"
        )

with tab3:
    st.subheader("💼 포지션 비율 설정")
    st.markdown("레짐별 포트폴리오 포지션 비율을 설정합니다.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📈 상승장**")
        position_bull = st.slider(
            "상승장 포지션 (%)",
            min_value=80,
            max_value=150,
            value=int(params.get('position_bull', 120)),
            step=10,
            help="상승장에서의 총 포지션 비율"
        )
        
        st.info(f"""
        **현재**: {position_bull}%
        
        - 100% 초과: 레버리지 활용
        - 100%: 풀 투자
        - 100% 미만: 보수적
        """)
    
    with col2:
        st.markdown("**➡️ 중립장**")
        position_sideways = st.slider(
            "중립장 포지션 (%)",
            min_value=50,
            max_value=100,
            value=int(params.get('position_sideways', 80)),
            step=10,
            help="중립장에서의 총 포지션 비율"
        )
        
        st.info(f"""
        **현재**: {position_sideways}%
        
        - 균형잡힌 투자
        - 리스크 중립
        """)
    
    with col3:
        st.markdown("**📉 하락장**")
        position_bear = st.slider(
            "하락장 포지션 (%)",
            min_value=20,
            max_value=80,
            value=int(params.get('position_bear', 50)),
            step=10,
            help="하락장에서의 총 포지션 비율"
        )
        
        st.info(f"""
        **현재**: {position_bear}%
        
        - 방어적 투자
        - 현금 비중 확대
        """)
    
    # 포지션 비율 시각화
    st.markdown("---")
    st.subheader("📊 레짐별 포지션 비율")
    
    import plotly.graph_objects as go
    
    fig = go.Figure(data=[
        go.Bar(
            x=['상승장', '중립장', '하락장'],
            y=[position_bull, position_sideways, position_bear],
            marker_color=['green', 'gray', 'red'],
            text=[f'{position_bull}%', f'{position_sideways}%', f'{position_bear}%'],
            textposition='auto'
        )
    ])
    
    fig.update_layout(
        title='레짐별 포지션 비율',
        yaxis_title='포지션 비율 (%)',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("🛡️ 리스크 관리")
    st.markdown("손절, 방어 모드 등 리스크 관리 파라미터를 설정합니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**손절 설정**")
        
        stop_loss = st.slider(
            "손절 라인 (%)",
            min_value=-10.0,
            max_value=-2.0,
            value=float(params.get('stop_loss', -5.0)),
            step=0.5,
            help="이 수익률에 도달하면 자동 매도"
        )
        
        st.warning(f"""
        **현재 설정**: {stop_loss}%
        
        종목이 {stop_loss}% 하락하면 자동으로 손절합니다.
        
        ⚠️ 손절 라인을 너무 타이트하게 설정하면 
        정상적인 변동성에도 손절될 수 있습니다.
        """)
    
    with col2:
        st.markdown("**방어 모드**")
        
        defense_confidence = st.slider(
            "방어 모드 신뢰도 (%)",
            min_value=70,
            max_value=95,
            value=int(params.get('defense_confidence', 85)),
            step=5,
            help="이 신뢰도 이상일 때만 방어 모드 진입"
        )
        
        st.info(f"""
        **현재 설정**: {defense_confidence}%
        
        하락장 신뢰도가 {defense_confidence}% 이상일 때만 
        방어 모드에 진입합니다.
        
        - **낮음 (70~80%)**: 민감하게 반응
        - **중간 (80~90%)**: 균형 ⭐ 권장
        - **높음 (90~95%)**: 확실할 때만 반응
        """)

# 저장 버튼
st.markdown("---")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    save_note = st.text_input("메모 (선택)", placeholder="예: 공격적 전략 테스트")

with col2:
    if st.button("💾 파라미터 저장", type="primary", use_container_width=True):
        new_params = {
            'maps_threshold': maps_threshold,
            'regime_ma_short': ma_short,
            'regime_ma_long': ma_long,
            'regime_threshold': regime_threshold,
            'position_bull': position_bull,
            'position_sideways': position_sideways,
            'position_bear': position_bear,
            'defense_confidence': defense_confidence,
            'max_position_size': max_position_size,
            'stop_loss': stop_loss
        }
        
        # 현재 설정 저장
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(new_params, f, ensure_ascii=False, indent=2)
        
        # 히스토리 저장
        history_file = save_parameter_history(new_params, save_note)
        
        st.success(f"✅ 파라미터 저장 완료! (히스토리: {history_file.name})")
        st.balloons()
        st.session_state.params_updated = True

with col3:
    if st.button("🔄 기본값으로 초기화", use_container_width=True):
        default_params = get_default_params()
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_params, f, ensure_ascii=False, indent=2)
        
        st.success("✅ 기본값으로 초기화되었습니다!")
        st.session_state.params_updated = True
        st.rerun()

# 현재 설정 요약
st.markdown("---")
st.subheader("📋 현재 설정 요약")

summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.markdown("""<div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px;'>
    <h4 style='margin-top: 0;'>📊 MAPS 설정</h4>
    <p><b>임계값:</b> {}</p>
    <p><b>최대 종목 비중:</b> {}%</p>
    <hr>
    <h4>🎯 레짐 감지</h4>
    <p><b>단기 MA:</b> {}일</p>
    <p><b>장기 MA:</b> {}일</p>
    <p><b>임계값:</b> ±{}%</p>
    </div>""".format(maps_threshold, max_position_size, ma_short, ma_long, regime_threshold), unsafe_allow_html=True)

with summary_col2:
    st.markdown("""<div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px;'>
    <h4 style='margin-top: 0;'>💼 포지션 비율</h4>
    <p><b>상승장:</b> {}%</p>
    <p><b>중립장:</b> {}%</p>
    <p><b>하락장:</b> {}%</p>
    <hr>
    <h4>🛡️ 리스크 관리</h4>
    <p><b>손절 라인:</b> {}%</p>
    <p><b>방어 모드 신뢰도:</b> {}%</p>
    </div>""".format(position_bull, position_sideways, position_bear, stop_loss, defense_confidence), unsafe_allow_html=True)

# 파라미터 히스토리
st.markdown("---")
st.subheader("📜 파라미터 히스토리")

history = load_parameter_history()

if history:
    # 히스토리 테이블
    history_data = []
    for h in history:
        dt = datetime.fromisoformat(h['datetime'])
        history_data.append({
            '저장 시간': dt.strftime('%Y-%m-%d %H:%M:%S'),
            '메모': h.get('note', '-'),
            'MAPS': h['params'].get('maps_threshold', '-'),
            '단기MA': h['params'].get('regime_ma_short', '-'),
            '장기MA': h['params'].get('regime_ma_long', '-'),
            '상승장': f"{h['params'].get('position_bull', '-')}%",
            '중립장': f"{h['params'].get('position_sideways', '-')}%",
            '하락장': f"{h['params'].get('position_bear', '-')}%",
            '백테스트': '미실행' if h.get('backtest_result') is None else f"{h['backtest_result'].get('cagr', 0):.2f}%"
        })
    
    df_history = pd.DataFrame(history_data)
    st.dataframe(df_history, use_container_width=True, hide_index=True)
    
    # 히스토리 불러오기
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_history = st.selectbox(
            "히스토리 선택",
            options=range(len(history)),
            format_func=lambda x: f"{history[x]['datetime'][:19]} - {history[x].get('note', '메모 없음')}"
        )
    
    with col2:
        if st.button("📥 불러오기", use_container_width=True):
            selected_params = history[selected_history]['params']
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(selected_params, f, ensure_ascii=False, indent=2)
            
            st.success("✅ 파라미터를 불러왔습니다!")
            st.rerun()
else:
    st.info("💡 저장된 파라미터 히스토리가 없습니다. 파라미터를 저장하면 히스토리가 기록됩니다.")

# 푸터
st.markdown("---")
st.caption("⚙️ Parameters | 설정 파일: config/strategy_params.json")
