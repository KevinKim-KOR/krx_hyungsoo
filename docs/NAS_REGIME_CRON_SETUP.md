# NAS 레짐 감지 Cron 설정 가이드

**작성일**: 2025-11-23  
**목적**: NAS에서 매일 오전 9시 레짐 감지 및 매도 신호 알림

---

## 📋 개요

매일 오전 9시 (장 시작 전) 시장 레짐을 감지하고, 변화 시 텔레그램 알림을 전송합니다.

### 주요 기능
1. **한국 시장 레짐 감지** (KOSPI 50/200일 이동평균)
2. **미국 시장 지표 모니터링** (나스닥, S&P 500, VIX)
3. **보유 종목 매도 신호 생성**
4. **텔레그램 알림 전송**

---

## 🚀 설정 방법

### 1. NAS SSH 접속

```bash
ssh your_username@your_nas_ip
```

### 2. Cron 편집

```bash
crontab -e
```

### 3. Cron 작업 추가

```bash
# 매일 오전 9시 레짐 감지 (평일만)
0 9 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/nas/daily_regime_check.sh >> /volume2/homes/Hyungsoo/krx/logs/regime_check.log 2>&1
```

**설명**:
- `0 9 * * 1-5`: 평일 (월~금) 오전 9시
- `>>`: 로그 파일에 추가
- `2>&1`: 에러도 로그에 기록

### 4. Cron 저장 및 종료

- `ESC` → `:wq` → `Enter` (vi 에디터)
- 또는 `Ctrl+X` → `Y` → `Enter` (nano 에디터)

### 5. Cron 확인

```bash
crontab -l
```

---

## 📁 파일 구조

```
krx_alertor_modular/
├── scripts/nas/
│   ├── daily_regime_check.sh      # Shell 스크립트
│   ├── daily_regime_check.py      # Python 메인 로직
│   └── regime_change_alert.py     # 텔레그램 알림
├── data/state/
│   └── current_regime.json        # 현재 레짐 상태
└── logs/
    └── regime_check.log           # 실행 로그
```

---

## 🔧 텔레그램 봇 설정

### 1. BotFather에서 봇 생성

1. 텔레그램에서 `@BotFather` 검색
2. `/newbot` 명령어 입력
3. 봇 이름 설정
4. **토큰 복사** (예: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Chat ID 확인

1. 봇과 대화 시작 (메시지 1개 전송)
2. 브라우저에서 접속:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. `"chat":{"id":123456789}` 부분에서 **Chat ID 복사**

### 3. .env 파일 설정

```bash
# NAS에서 실행
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
nano .env
```

```bash
# 텔레그램 설정
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## 📊 알림 예시

### 레짐 변화 알림

```
🚨 시장 레짐 변화 감지

📍 한국 시장:
➡️ 이전: 상승장
📉 현재: 중립장
📊 신뢰도: 87.5%

🇺🇸 미국 시장:
📉 레짐: bearish

📌 나스닥 50일선 - AI/반도체 섹터 모멘텀
   현재가: 15,000
   이동평균: 15,800
   괴리율: -5.06%
   신호: bearish

💰 권장 조치:
- 현금 보유율: 40~50% 🔥
- 포지션 크기: 50~60%
- 전략: 중립적 투자

⚠️ 보유 종목 매도 신호 (3건)

📌 삼성전자 (005930)
   수량: 50주
   평균가: 70,000원
   사유: 중립장 전환 (일부 매도 권장)
```

---

## 🧪 테스트

### 수동 실행 (테스트)

```bash
# NAS에서 실행
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
bash scripts/nas/daily_regime_check.sh
```

### 로그 확인

```bash
tail -f /volume2/homes/Hyungsoo/krx/logs/regime_check.log
```

---

## 🔍 문제 해결

### 1. Python 모듈 없음

```bash
pip3 install pyyaml requests beautifulsoup4
```

### 2. 권한 오류

```bash
chmod +x scripts/nas/daily_regime_check.sh
```

### 3. 텔레그램 알림 안 옴

- `.env` 파일 확인
- 토큰과 Chat ID 재확인
- 봇과 대화 시작했는지 확인

### 4. 데이터 없음

```bash
# 데이터 수집 먼저 실행
python3 scripts/ingest/ingest_all.py
```

---

## 📅 실행 시간표

| 시간 | 작업 | 설명 |
|-----|------|------|
| 09:00 | 레짐 감지 | 장 시작 전 레짐 확인 |
| 16:00 | 일일 리포트 | 장 마감 후 성과 확인 |
| 토 10:00 | 주간 리포트 | 주간 성과 요약 |

---

## 🎯 다음 단계

1. ✅ NAS Cron 설정
2. ⏳ WebUI에서 레짐 파라미터 수정
3. ⏳ Oracle Cloud 외부 접속 설정
4. ⏳ 백테스트 UI 개선

---

## 📚 참고 문서

- `docs/REGIME_MONITORING_GUIDE.md` - 상세 가이드
- `config/us_market_indicators.yaml` - 미국 시장 지표 설정
- `scripts/nas/daily_regime_check.py` - 메인 스크립트
