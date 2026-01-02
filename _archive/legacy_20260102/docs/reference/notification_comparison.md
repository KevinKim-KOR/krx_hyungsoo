# 알림 시스템 비교 분석

## 📊 친구 시스템 vs 현재 시스템

### 친구 시스템 (jasonisdoing/momentum-etf)

**기술 스택**:
- 스케줄러: APScheduler (Python 기반)
- 알림: Slack
- 웹앱: Streamlit
- 실행: `python aps.py` (백그라운드)

**주요 기능**:
1. **자동 추천 생성** - 장 마감 후 자동 실행
2. **Slack 알림** - 추천 결과 자동 전송
3. **웹 대시보드** - Streamlit 기반
   - 계정별 추천 페이지 (`/<account_id>`)
   - 관리자 거래 관리 (`/admin`)
   - 시장 레짐 상태 표시
4. **DB 저장** - 추천 결과 DB 저장
5. **로그 관리** - 계정별 폴더 구조

---

### 현재 시스템 (krx_alertor_modular)

**기술 스택**:
- 스케줄러: Synology Cron (시스템 기반)
- 알림: Telegram
- 웹앱: 없음 (CLI 기반)
- 실행: Bash 스크립트 + Python

**현재 구현된 기능**:
1. ✅ **실시간 신호 생성** - MAPS 전략
2. ✅ **텔레그램 알림** - 매매 신호
3. ✅ **DB 저장** - 신호/성과 이력
4. ✅ **일일/주간 리포트**
5. ✅ **시장 레짐 감지**
6. ✅ **로그 관리**
7. ✅ **DB 백업**

---

## 🔍 차이점 분석

### 1. 스케줄러

| 항목 | 친구 | 현재 |
|------|------|------|
| 방식 | APScheduler (Python) | Cron (시스템) |
| 설정 | `schedule_config.json` | Synology 작업 스케줄러 |
| 유연성 | 높음 (코드로 제어) | 중간 (GUI 설정) |
| 안정성 | Python 프로세스 의존 | 시스템 레벨 |

**장단점**:
- **APScheduler**: 동적 스케줄 변경 가능, Python 프로세스 관리 필요
- **Cron**: 시스템 레벨 안정성, 설정 변경 시 GUI 필요

---

### 2. 알림 채널

| 항목 | 친구 (Slack) | 현재 (Telegram) |
|------|-------------|----------------|
| 설정 | Webhook URL | Bot Token + Chat ID |
| 포맷 | Slack Block Kit | Markdown |
| 기능 | 버튼, 스레드 | 간단한 포맷 |
| 접근성 | 팀 협업 | 개인 사용 |

**선택 기준**:
- **Slack**: 팀 협업, 복잡한 UI
- **Telegram**: 개인 사용, 간단한 설정

---

### 3. 웹 대시보드

| 항목 | 친구 | 현재 |
|------|------|------|
| 웹앱 | ✅ Streamlit | ❌ 없음 |
| 추천 조회 | 웹 UI | CLI |
| 거래 관리 | 웹 UI (로그인) | 없음 |
| 시각화 | 차트, 테이블 | 텍스트 리포트 |

**부족한 부분**: 웹 대시보드 (선택사항)

---

## 📋 부족한 기능 및 추가 제안

### 1. ⚠️ 레짐 변경 알림 (추가 완료)

**친구**: `logic/recommend/market.py` - 시장 레짐 상태 조회  
**현재**: 레짐 감지는 있지만 알림 없음

**추가됨**: `scripts/nas/regime_change_alert.py`
- 레짐 변경 감지
- 텔레그램 알림
- 이전 레짐 저장/비교

---

### 2. 📱 추가 알림 종류

#### 현재 구현됨 (등록 필요)

| 알림 | 시간 | 스크립트 | 상태 |
|------|------|---------|------|
| 장 시작 알림 | 09:00 | `market_open_alert.py` | ⭐ 신규 |
| 장중 급등락 | 11:00, 14:00 | `intraday_alert.py` | ⭐ 신규 |
| 레짐 변경 | 16:00 | `regime_change_alert.py` | ⭐ 신규 |
| 주간 리포트 | 일요일 09:00 | `weekly_report.py` | ⭐ 추가 필요 |

#### 친구가 가진 것으로 추정

| 알림 | 설명 | 우리 시스템 |
|------|------|-----------|
| 장 마감 추천 | 매매 신호 | ✅ 있음 (EoD) |
| 웹 대시보드 | 실시간 조회 | ❌ 없음 |
| 시장 레짐 | 레짐 상태 | ✅ 있음 (감지만) |
| 거래 관리 | 포지션 관리 | ❌ 없음 |

---

### 3. 🌐 웹 대시보드 (선택)

**친구 시스템**:
```python
# Streamlit 기반
python run.py
# → http://localhost:8501
```

**페이지**:
- `/` - 대시보드
- `/<account_id>` - 계정별 추천
- `/admin` - 거래 관리 (로그인)

**우리 시스템에 추가하려면**:
- Flask 또는 Streamlit 사용
- DB 데이터 시각화
- 실시간 포트폴리오 현황
- 신호 히스토리 차트

**필요성**: **선택** (CLI로도 충분하지만 시각화는 편리)

---

## ✅ 권장 추가 사항

### 최소 추가 (필수)

1. **주간 리포트** - 일요일 09:00
2. **레짐 변경 알림** - 평일 16:00

### 추천 추가 (편의성)

3. **장 시작 알림** - 평일 09:00
4. **장중 급등락** - 평일 11:00, 14:00 (선택)

### 선택 추가 (고급)

5. **웹 대시보드** - Streamlit 또는 Flask
6. **Slack 통합** - 팀 협업용 (선택)

---

## 📊 최종 스케줄러 구성 (권장)

### 필수 (5개)

```bash
# 1. 장 시작 알림 (09:00)
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/market_open_alert.py

# 2. EoD 신호 (15:40) - 이미 등록됨
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/daily_realtime_signals.sh

# 3. 레짐 변경 감지 (16:00)
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/regime_change_alert.py

# 4. 주간 리포트 (일요일 09:00)
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/weekly_report.py

# 5. DB 백업 (03:00) - 이미 등록됨
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/backup_db.sh
```

### 선택 (2개)

```bash
# 6. 장중 급등락 (11:00, 14:00)
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py

# 7. 로그 정리 (02:00) - 이미 등록됨
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/cleanup_logs.sh
```

---

## 🎯 결론

### 친구 시스템의 강점
- ✅ 웹 대시보드 (시각화)
- ✅ Slack 통합 (팀 협업)
- ✅ APScheduler (동적 스케줄)

### 우리 시스템의 강점
- ✅ 시스템 레벨 안정성 (Cron)
- ✅ 더 풍부한 모니터링 (DB 추적)
- ✅ 레짐 감지 및 리스크 관리
- ✅ 텔레그램 (간단한 설정)

### 추가하면 좋은 것
1. **레짐 변경 알림** ⭐ (추가 완료)
2. **주간 리포트** ⭐ (추가 필요)
3. **장 시작 알림** (권장)
4. **웹 대시보드** (선택)

---

## 📝 다음 액션

1. **즉시**: 레짐 변경 알림 스케줄러 등록
2. **즉시**: 주간 리포트 스케줄러 등록
3. **선택**: 장 시작 알림 등록
4. **나중에**: 웹 대시보드 개발 (Phase 4)
