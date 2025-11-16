# KRX Alertor 대시보드 (Phase 4.5)

## 🌐 개요

Streamlit 기반 포트폴리오 모니터링 & 손절 전략 분석 대시보드

**Phase 4.5 업데이트:**
- 🎯 손절 전략 성과 비교
- 📊 백테스트 결과 뷰어
- 🔔 알림 히스토리
- 💼 포트폴리오 현황

---

## 📦 설치

```bash
# 의존성 설치
pip install -r requirements_dashboard.txt
```

---

## 🚀 실행

### PC에서 실행

```bash
# 프로젝트 루트에서
streamlit run dashboard/app.py
```

브라우저에서 자동으로 열림: `http://localhost:8501`

### NAS에서 실행 (선택)

```bash
# NAS SSH 접속 후
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 실행
streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
```

NAS IP로 접속: `http://nas-ip:8501`

---

## 📊 페이지 구성

### 1. 🏠 홈
- 주요 지표 요약
- 최근 7일 신호 통계
- 빠른 링크 (Phase 4.5 업데이트)

### 2. 💼 포트폴리오
- 현재 포트폴리오 현황
- 총 자산, 현금, 포지션
- 최근 30일 성과 차트

### 3. 🎯 손절 전략 (Phase 4.5 신규) ⭐
- 4가지 전략 성과 비교
  * 고정 손절 (-7%)
  * 레짐별 손절 (-3% ~ -7%)
  * 동적 손절 (-5% ~ -10%)
  * 하이브리드 손절 (-3% ~ -10%)
- 전략별 개선 효과 차트
- 손절 대상 종목 리스트
- 최적 전략 추천

### 4. 📊 백테스트 (Phase 4.5 신규) ⭐
- Jason 전략 성과 지표
- 하이브리드 전략 성과 지표
- 자산 곡선 (Equity Curve)
- 낙폭 차트 (Drawdown)
- 거래 분석
- 레짐 분석

### 5. 📈 신호 히스토리
- 신호 목록 (기간별)
- 액션 필터 (매수/매도)
- 날짜별 그룹화

### 6. 🔔 알림 히스토리 (Phase 4.5 신규) ⭐
- 알림 통계 (일별, 유형별)
- 알림 타임라인
- 알림 목록 (필터/검색)
- 손절 실행 히스토리
- CSV 다운로드

### 7. 🌡️ 시장 레짐
- 현재 레짐 상태
- 레짐 지표 (변동성, 추세, 모멘텀)
- 레짐별 투자 전략

---

## 🔧 커스터마이징

### 테마 변경

`.streamlit/config.toml` 파일 생성:

```toml
[theme]
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

### 포트 변경

```bash
streamlit run dashboard/app.py --server.port 8080
```

---

## 📝 주의사항

### 데이터 준비
1. **손절 전략 비교** 페이지:
   ```bash
   python scripts/phase4/compare_stop_loss_strategies.py
   ```

2. **백테스트** 페이지:
   ```bash
   python scripts/phase2/run_backtest_jason.py
   ```

3. **알림 히스토리** 페이지:
   - 자동으로 로그 파일에서 추출
   - 손절 실행 시 자동 기록

### 기타
- DB 파일이 없으면 일부 데이터가 표시되지 않습니다
- 실시간 새로고침은 수동으로 해야 합니다 (🔄 버튼)
- NAS에서 실행 시 포트포워딩 또는 VPN 필요

---

## 🐛 트러블슈팅

### 포트 충돌

```bash
# 다른 포트 사용
streamlit run dashboard/app.py --server.port 8502
```

### 모듈 import 오류

```bash
# PYTHONPATH 설정
export PYTHONPATH="${PYTHONPATH}:/path/to/krx_alertor_modular"
streamlit run dashboard/app.py
```

### 데이터 없음

```bash
# 먼저 신호 생성
python nas/app_realtime.py
```
