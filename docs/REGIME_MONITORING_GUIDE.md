# 실시간 레짐 모니터링 가이드

## 개요
매일 오전 9시 (장 시작 전) 시장 레짐을 감지하고, 변화 시 텔레그램 알림을 전송합니다.

---

## 주요 기능

### 1. 한국 시장 레짐 감지
- KOSPI 50일/200일 이동평균 기반
- 상승장/중립장/하락장 판단
- 신뢰도 계산

### 2. 미국 시장 지표 모니터링
- **나스닥 50일선** (AI/반도체 섹터)
- **S&P 500 200일선** (장기 추세)
- **VIX** (변동성 지수)

### 3. 보유 종목 매도 신호
- 하락장 전환 시 전량 매도 권장
- 중립장 전환 시 일부 매도 권장

### 4. 텔레그램 알림
- 레짐 변화 시 즉시 알림
- 미국 시장 지표 포함
- 권장 조치 안내

---

## 실행 방법

### Windows (테스트)
```bash
scripts\nas\daily_regime_check.bat
```

### Linux/Mac (NAS)
```bash
chmod +x scripts/nas/daily_regime_check.sh
./scripts/nas/daily_regime_check.sh
```

### Python 직접 실행
```bash
python scripts/nas/daily_regime_check.py
```

---

## NAS Cron 설정

### 매일 오전 9시 실행
```bash
# crontab -e
0 9 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/nas/daily_regime_check.sh >> /volume2/homes/Hyungsoo/krx/logs/regime_check.log 2>&1
```

**설명**:
- `0 9 * * 1-5`: 평일 오전 9시
- `>>`: 로그 파일에 추가
- `2>&1`: 에러도 로그에 기록

---

## 미국 시장 지표 설정

### 설정 파일
```
config/us_market_indicators.yaml
```

### 지표 활성화/비활성화
```yaml
enabled_indicators:
  - nasdaq_50ma      # 활성화
  - sp500_200ma      # 활성화
  - vix              # 활성화
  # - nasdaq_100ma   # 비활성화
  # - dxy            # 비활성화
```

### 가중치 조정
```yaml
nasdaq_50ma:
  weight: 0.4        # 40% 가중치

sp500_200ma:
  weight: 0.3        # 30% 가중치

vix:
  weight: 0.3        # 30% 가중치
```

### 임계값 조정
```yaml
nasdaq_50ma:
  threshold: 0.02    # 2% 괴리율

vix:
  threshold_high: 20   # 공포 수준
  threshold_low: 12    # 안정 수준
```

---

## ChatGPT와 대화로 조정

### 1. 현재 지표 확인
```bash
python scripts/nas/daily_regime_check.py
```

출력 예시:
```
📊 미국 시장 지표 분석

📈 미국 시장 레짐: 상승

📌 나스닥 50일선 - AI/반도체 섹터 모멘텀
   현재가: 16,000
   이동평균: 15,800
   괴리율: +1.27%
   신호: bullish
   해석: 50일선 상향 돌파 → 상승 모멘텀
```

### 2. ChatGPT 프롬프트 생성
스크립트 실행 시 자동으로 생성됩니다:

```
현재 미국 시장 지표:
- 나스닥 50일선: +1.27%
- S&P 500 200일선: +2.15%
- VIX: 14.5

한국 시장 상황:
- KOSPI: 상승장
- 주요 섹터: AI/반도체

질문:
1. 현재 미국 시장 지표를 어떻게 해석해야 하나요?
2. 한국 시장에 미치는 영향은?
3. 어떤 지표를 추가로 봐야 하나요?
4. 레짐 판단 규칙을 조정해야 하나요?
```

### 3. ChatGPT 응답 예시
```
현재 미국 시장은 강한 상승 모멘텀을 보이고 있습니다.

1. 지표 해석:
   - 나스닥 50일선 상향 → AI/반도체 강세
   - S&P 500 200일선 상향 → 장기 상승 추세
   - VIX 낮음 → 시장 안정

2. 한국 시장 영향:
   - AI/반도체 섹터 긍정적
   - 삼성전자, SK하이닉스 수혜
   - 수출주 강세 예상

3. 추가 지표:
   - 달러 인덱스 (환율 영향)
   - 반도체 지수 (SOX)
   - 금리 (10년물 국채)

4. 조정 제안:
   - 나스닥 가중치 50%로 증가
   - SOX 지수 추가 (30%)
   - VIX 가중치 20%로 감소
```

### 4. 설정 파일 수정
ChatGPT 제안을 반영하여 `config/us_market_indicators.yaml` 수정:

```yaml
enabled_indicators:
  - nasdaq_50ma
  - sp500_200ma
  - vix
  - sox_index      # 추가

nasdaq_50ma:
  weight: 0.5      # 40% → 50%

sox_index:         # 신규 추가
  enabled: true
  symbol: "^SOX"
  period: 50
  threshold: 0.02
  weight: 0.3
  description: "반도체 지수"
```

---

## 알림 예시

### 레짐 변화 알림
```
🚨 시장 레짐 변화 감지

📍 한국 시장:
➡️ 이전: 상승장
📉 현재: 중립장
📊 신뢰도: 87.5%

🇺🇸 미국 시장:
📉 레짐: bearish

📊 미국 시장 지표 분석

📉 미국 시장 레짐: 하락

📌 나스닥 50일선 - AI/반도체 섹터 모멘텀
   현재가: 15,000
   이동평균: 15,800
   괴리율: -5.06%
   신호: bearish
   해석: 50일선 하향 이탈 → 하락 모멘텀

⚠️ 긴급 알림:
   🚨 나스닥 50일선 - AI/반도체 섹터 모멘텀: -5.06% (기준: -5.00%)

💰 권장 조치:
- 현금 보유율: 40~50% 🔥
- 포지션 크기: 50~60%
- 전략: 중립적 투자
- 종목: 방어적 종목으로 전환

⚠️ 주의:
- 방향성 불확실
- 변동성 증가 가능
- 보유 종목 점검 필요

📅 감지 시간: 2025-11-21 09:00:00
```

### 보유 종목 매도 신호
```
⚠️ 보유 종목 매도 신호 (3건)

📌 삼성전자 (005930)
   수량: 50주
   평균가: 70,000원
   사유: 중립장 전환 (일부 매도 권장)

📌 SK하이닉스 (000660)
   수량: 30주
   평균가: 130,000원
   사유: 중립장 전환 (일부 매도 권장)

📌 KODEX 레버리지 (122630)
   수량: 100주
   평균가: 10,000원
   사유: 중립장 전환 (일부 매도 권장)
```

---

## 문제 해결

### Python 모듈 없음
```bash
pip install pyyaml
```

### 데이터 없음
```bash
# 데이터 수집 먼저 실행
python scripts/ingest/ingest_all.py
```

### 텔레그램 알림 안 옴
```bash
# .env 파일 확인
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 다음 단계

### 1. Holdings 페이지 구현
- 보유 종목 조회
- 매도 신호 표시
- 레짐 리스크 표시

### 2. 파라미터 조정 UI
- 미국 시장 지표 설정
- 가중치 조정
- 임계값 조정

### 3. 백테스트 히스토리
- 레짐별 성과 분석
- 최적 파라미터 찾기

---

## 참고 문서
- `config/us_market_indicators.yaml` - 미국 시장 지표 설정
- `core/strategy/us_market_monitor.py` - 미국 시장 모니터
- `scripts/nas/daily_regime_check.py` - 레짐 감지 스크립트
