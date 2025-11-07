# 웹 대시보드

## 🌐 개요

Streamlit 기반 실시간 모니터링 대시보드

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
- 빠른 링크

### 2. 💼 포트폴리오
- 현재 포트폴리오 현황
- 총 자산, 현금, 포지션
- 최근 30일 성과 차트

### 3. 📈 신호 히스토리
- 신호 목록 (기간별)
- 액션 필터 (매수/매도)
- 날짜별 그룹화

### 4. 📊 성과 분석
- 누적 수익률 차트
- 일일 수익률 분포
- 상세 통계

### 5. 🌡️ 시장 레짐
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

- DB 파일이 없으면 데이터가 표시되지 않습니다
- 먼저 신호를 생성하여 DB에 데이터를 저장해야 합니다
- 실시간 새로고침은 수동으로 해야 합니다 (🔄 버튼)

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
