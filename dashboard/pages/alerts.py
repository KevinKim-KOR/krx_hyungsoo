#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard/pages/alerts.py
알림 히스토리 뷰어
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import json
from datetime import datetime, timedelta
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_alert_history():
    """알림 히스토리 로드"""
    try:
        # 로그 파일에서 알림 히스토리 추출
        log_dir = PROJECT_ROOT / "logs"
        
        alerts = []
        
        # 최근 7일간의 로그 파일 읽기
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            log_file = log_dir / f"krx_alertor_{date.strftime('%Y%m%d')}.log"
            
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        # 알림 관련 로그 추출
                        if '텔레그램 알림' in line or 'Telegram' in line:
                            try:
                                parts = line.split(' - ')
                                if len(parts) >= 3:
                                    timestamp = parts[0]
                                    level = parts[1]
                                    message = ' - '.join(parts[2:])
                                    
                                    alerts.append({
                                        'timestamp': timestamp,
                                        'level': level,
                                        'message': message.strip()
                                    })
                            except:
                                continue
        
        return alerts if alerts else None
    
    except Exception as e:
        st.error(f"알림 히스토리 로드 실패: {e}")
        return None


def load_stop_loss_history():
    """손절 실행 히스토리 로드"""
    try:
        history_file = PROJECT_ROOT / "data" / "output" / "stop_loss_history.json"
        
        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
    
    except Exception as e:
        st.error(f"손절 히스토리 로드 실패: {e}")
        return None


def show_alert_stats(alerts):
    """알림 통계"""
    st.header("📊 알림 통계")
    
    df = pd.DataFrame(alerts)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_alerts = len(df)
        st.metric("총 알림 수", f"{total_alerts}개")
    
    with col2:
        today_alerts = len(df[df['timestamp'].str.contains(datetime.now().strftime('%Y-%m-%d'))])
        st.metric("오늘 알림", f"{today_alerts}개")
    
    with col3:
        # 레벨별 카운트
        if 'level' in df.columns:
            info_count = len(df[df['level'].str.contains('INFO')])
            st.metric("INFO", f"{info_count}개")
    
    with col4:
        if 'level' in df.columns:
            warning_count = len(df[df['level'].str.contains('WARNING')])
            st.metric("WARNING", f"{warning_count}개")


def show_alert_timeline(alerts):
    """알림 타임라인"""
    st.header("📅 알림 타임라인")
    
    df = pd.DataFrame(alerts)
    
    # 날짜별 알림 수
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily_counts = df.groupby('date').size().reset_index(name='count')
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=daily_counts['date'],
        y=daily_counts['count'],
        marker_color='#4ECDC4',
        text=daily_counts['count'],
        textposition='auto'
    ))
    
    fig.update_layout(
        title="일별 알림 수",
        xaxis_title="날짜",
        yaxis_title="알림 수",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def show_alert_list(alerts):
    """알림 목록"""
    st.header("📋 알림 목록")
    
    df = pd.DataFrame(alerts)
    
    # 필터
    col1, col2 = st.columns(2)
    
    with col1:
        # 레벨 필터
        if 'level' in df.columns:
            levels = ['전체'] + df['level'].unique().tolist()
            selected_level = st.selectbox("레벨 필터", levels)
            
            if selected_level != '전체':
                df = df[df['level'] == selected_level]
    
    with col2:
        # 검색
        search = st.text_input("메시지 검색")
        if search:
            df = df[df['message'].str.contains(search, case=False, na=False)]
    
    # 정렬
    df = df.sort_values('timestamp', ascending=False)
    
    # 표시
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=600
    )
    
    # 다운로드
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 CSV 다운로드",
        data=csv,
        file_name=f"alert_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )


def show_stop_loss_history(history):
    """손절 실행 히스토리"""
    st.header("🔴 손절 실행 히스토리")
    
    if not history:
        st.info("손절 실행 기록이 없습니다.")
        return
    
    df = pd.DataFrame(history)
    
    # 통계
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_stop_loss = len(df)
        st.metric("총 손절 수", f"{total_stop_loss}회")
    
    with col2:
        if 'loss_amount' in df.columns:
            total_loss = df['loss_amount'].sum()
            st.metric("총 손실 금액", f"{total_loss:,.0f}원")
    
    with col3:
        if 'loss_pct' in df.columns:
            avg_loss = df['loss_pct'].mean()
            st.metric("평균 손실률", f"{avg_loss:.2f}%")
    
    # 손절 내역
    st.subheader("손절 내역")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def show_alert_types(alerts):
    """알림 유형 분석"""
    st.header("📊 알림 유형 분석")
    
    df = pd.DataFrame(alerts)
    
    # 알림 유형 분류
    alert_types = []
    for msg in df['message']:
        if '손절' in msg:
            alert_types.append('손절')
        elif '장시작' in msg or '장 시작' in msg:
            alert_types.append('장시작')
        elif '장중' in msg:
            alert_types.append('장중')
        elif '주간' in msg:
            alert_types.append('주간리포트')
        elif '일일' in msg:
            alert_types.append('일일리포트')
        else:
            alert_types.append('기타')
    
    df['type'] = alert_types
    
    # 유형별 카운트
    type_counts = df['type'].value_counts()
    
    fig = go.Figure(data=[
        go.Pie(
            labels=type_counts.index,
            values=type_counts.values,
            marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DFE6E9']
        )
    ])
    
    fig.update_layout(
        title="알림 유형 분포",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def show():
    """메인 함수"""
    st.title("🔔 알림 히스토리")
    st.markdown("---")
    
    # 데이터 로드
    alerts = load_alert_history()
    stop_loss_history = load_stop_loss_history()
    
    if alerts is None and stop_loss_history is None:
        st.warning("""
        ⚠️ 알림 히스토리가 없습니다.
        
        시스템이 실행되면 자동으로 기록됩니다.
        """)
        return
    
    # 탭 생성
    if alerts and stop_loss_history:
        tabs = st.tabs([
            "📊 통계",
            "📅 타임라인",
            "📋 알림 목록",
            "📊 유형 분석",
            "🔴 손절 히스토리"
        ])
        
        with tabs[0]:
            if alerts:
                show_alert_stats(alerts)
        
        with tabs[1]:
            if alerts:
                show_alert_timeline(alerts)
        
        with tabs[2]:
            if alerts:
                show_alert_list(alerts)
        
        with tabs[3]:
            if alerts:
                show_alert_types(alerts)
        
        with tabs[4]:
            if stop_loss_history:
                show_stop_loss_history(stop_loss_history)
    
    elif alerts:
        tabs = st.tabs([
            "📊 통계",
            "📅 타임라인",
            "📋 알림 목록",
            "📊 유형 분석"
        ])
        
        with tabs[0]:
            show_alert_stats(alerts)
        
        with tabs[1]:
            show_alert_timeline(alerts)
        
        with tabs[2]:
            show_alert_list(alerts)
        
        with tabs[3]:
            show_alert_types(alerts)
    
    else:
        show_stop_loss_history(stop_loss_history)
    
    # 새로고침 버튼
    st.markdown("---")
    if st.button("🔄 데이터 새로고침"):
        st.rerun()


if __name__ == "__main__":
    show()
