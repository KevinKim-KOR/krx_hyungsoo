# 백테스트 실행 가이드

## 개요
백테스트는 PC에서 실행하고, 웹 UI에서 결과를 조회합니다.

---

## 실행 방법

### Windows
```bash
# 프로젝트 루트에서
scripts\run_backtest.bat
```

### Linux/Mac
```bash
# 프로젝트 루트에서
chmod +x scripts/run_backtest.sh
./scripts/run_backtest.sh
```

### Python 직접 실행
```bash
python scripts/phase2/run_backtest_hybrid.py
```

---

## 소요 시간
- **약 5~10분** (데이터 로딩 + 계산 + 최적화)
- 기간: 2022-01-01 ~ 현재

---

## 결과 확인

### 1. 파일로 확인
```
data/output/backtest/hybrid_backtest_results.json
```

### 2. 웹 UI에서 확인
```
http://localhost:3000/backtest
```

**기능**:
- 백테스트 결과 조회
- CAGR, Sharpe Ratio, MDD 확인
- AI에게 질문하기 (ChatGPT/Gemini)

---

## 백테스트 전략

### 하이브리드 레짐 전략
- **상승장**: Jason 모멘텀 (공격적)
- **하락장**: 방어 모드 (손절)
- **중립장**: 하이브리드

### 성과 (2022-2025)
- CAGR: 27.05%
- Sharpe Ratio: 1.51
- Max Drawdown: -19.92%
- 총 수익률: 96.80%
- 거래 횟수: 1,406회

---

## 파라미터 조정

### 레짐 감지
- MA 기간: 50/200일
- 임계값: ±2%

### 포지션 비율
- 상승장: 100~120%
- 중립장: 80%
- 하락장: 40~60%

### 방어 모드
- 신뢰도: 85% 이상

---

## 문제 해결

### Python 버전 오류
```bash
# Python 3.8 이상 필요
python --version
```

### 모듈 없음 오류
```bash
# 의존성 설치
pip install -r requirements.txt
```

### 데이터 없음 오류
```bash
# 데이터 수집 먼저 실행
python scripts/ingest/ingest_all.py
```

---

## 다음 단계

### 1. 결과 분석
- 웹 UI에서 결과 확인
- AI에게 질문하기로 분석

### 2. 파라미터 조정
- 레짐 파라미터 변경
- 포지션 비율 조정

### 3. 재실행
- 스크립트 다시 실행
- 결과 비교

---

## 참고 문서
- `docs/WEEK3_HYBRID_STRATEGY.md` - 전략 상세
- `docs/PHASE2_COMPLETE_SUMMARY.md` - 성과 요약
