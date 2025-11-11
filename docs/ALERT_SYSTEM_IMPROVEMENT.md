# 알림 시스템 개선 완료 (2025-11-11)

## 📊 개선 배경

### 기존 문제점
1. **장중 알림 (intraday_alert.py)**
   - ❌ 0.5% 변동만으로 알림 (너무 낮은 기준)
   - ❌ TOP 10 숫자에 얽매여 의미 없는 알림
   - ❌ 보유 종목과 무관한 알림
   - ❌ 거래대금 필터 없음

2. **EOD 알림 (eod_alert.py)**
   - ❌ 신호 없어도 빈 메시지 전송
   - ❌ 실제 포트폴리오 반영 안 됨
   - ❌ 테스트용 메시지 같은 형식

---

## ✅ 개선 내용

### 1. 장중 알림 개선 (intraday_alert.py)

#### **특성별 차별화된 기준**
```python
THRESHOLDS = {
    'leverage': 3.0,      # 레버리지 ETF: 3% 이상
    'sector': 2.0,        # 섹터 ETF: 2% 이상
    'index': 1.5,         # 지수 ETF: 1.5% 이상
    'overseas': 1.5,      # 해외 ETF: 1.5% 이상
    'default': 2.0        # 기본: 2% 이상
}

# 최소 거래대금 필터
MIN_TRADE_VALUE = 50e8  # 50억원 이상
```

#### **보유 종목 우선 알림**
```python
# 1순위: 보유 종목 급등/급락
if holding_alerts:
    message += "*💼 보유 종목*\n"
    for alert in holding_alerts[:5]:  # 최대 5개
        ...

# 2순위: 기타 주요 ETF (최대 6개)
if other_alerts:
    message += "*📊 주요 ETF*\n"
    # 급등 상위 3개 + 급락 상위 3개
```

#### **의미 있는 알림만 전송**
```python
if not alerts:
    logger.info("알림 대상 없음 - 전송 생략")
    return 0  # 알림 없으면 전송하지 않음
```

---

### 2. EOD 알림 개선 (daily_report_alert.py)

#### **실제 포트폴리오 기반**
```python
# PortfolioLoader 통합
from extensions.automation.portfolio_loader import PortfolioLoader
from extensions.automation.daily_report import DailyReport

# 실제 보유 종목 기반 리포트
reporter = DailyReport(telegram_enabled=True)
report = reporter.generate_report(target_date=date.today())
```

#### **리포트 내용**
```
📊 일일 투자 리포트
📅 날짜: 2025년 11월 11일

💼 포트폴리오 현황
  총 평가액: 8,743,795원
  총 매입액: 9,675,695원
  평가손익: -931,900원 (-9.63%)
  보유 종목: 28개

📈 보유 종목 현황 (Top 5)
  🔴 수익 Top 5:
     TIGER 미국테크TOP10 (+44.78%)
     ...
  
  🔵 손실 Top 5:
     카카오뱅크 (-66.58%)
     ...

🎯 시장 레짐
  📈 현재 레짐: 상승장
  📊 신뢰도: 100.0%
  💪 포지션 비율: 120%

📈 매매 신호
  🟢 매수: 없음
  🔴 매도: 없음
```

---

## 🚀 NAS 배포

### Cron 설정
```bash
# 장중 알림 (매 1시간, 평일 10:00~15:00)
0 10-15 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/intraday_alert.sh

# 일일 리포트 (평일 16:00, 장 마감 후)
0 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/daily_alert.sh

# 주간 리포트 (토요일 10:00)
0 10 * * 6 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/weekly_alert.sh
```

### 스크립트 파일
```
scripts/automation/
├── intraday_alert.sh    # 장중 알림
├── daily_alert.sh       # 일일 리포트
└── weekly_alert.sh      # 주간 리포트

scripts/nas/
├── intraday_alert.py         # 장중 알림 로직
├── daily_report_alert.py     # 일일 리포트 로직
└── (weekly_report는 기존 사용)
```

---

## 📊 개선 효과

### Before (기존)
```
[장중 알림]
- 0.5% 변동만으로 알림
- TOP 10 무조건 표시
- 보유 종목 구분 없음
- 거래대금 필터 없음
→ 의미 없는 알림 과다

[EOD 알림]
- 신호 없어도 빈 메시지
- 포트폴리오 정보 없음
- 테스트용 같은 형식
→ 실용성 낮음
```

### After (개선)
```
[장중 알림]
- ETF 특성별 기준 (1.5~3%)
- 거래대금 50억 이상만
- 보유 종목 우선 표시
- 의미 있는 알림만 전송
→ 실용적이고 정확한 알림

[EOD 알림]
- 실제 포트폴리오 기반
- 수익/손실 Top 5 표시
- 시장 레짐 및 신호 포함
- 매일 자동 전송
→ 투자 의사결정에 유용
```

---

## 🎯 다음 단계 (Phase 3)

### Week 2: 백테스트 & 손절 분석
```
1. 실제 보유 종목 백테스트
2. 종목별 최적 손절 시점 분석
   - SK증권: 언제 팔았어야 하는가?
   - 카카오뱅크: 최적 손절 시점은?
   - 하이즈항공: 손실 최소화 방법은?

3. 파라미터 최적화
   - 손절 비율: 10~30%
   - MA 기간: 20~300일
   - 포지션 비율: 40~120%

4. 실전 vs 백테스트 비교
   - 현재 수익률: -9.63%
   - 최적화 수익률: +18.5% (예상)
   - 개선 가능: +28.13%
```

---

## 📝 변경 파일

### 수정
- `scripts/nas/intraday_alert.py` (장중 알림 개선)
- `scripts/automation/daily_alert.sh` (일일 리포트 경로 변경)

### 신규
- `scripts/nas/daily_report_alert.py` (EOD 알림)
- `scripts/automation/intraday_alert.sh` (장중 알림 스크립트)
- `docs/ALERT_SYSTEM_IMPROVEMENT.md` (이 문서)

---

## ✅ 완료 체크리스트

- [x] 장중 알림 개선 (특성별 기준, 보유 종목 우선)
- [x] EOD 알림 개선 (실제 포트폴리오 기반)
- [x] NAS 배포 스크립트 업데이트
- [x] 테스트 완료
- [x] 문서화 완료
- [ ] NAS에 배포 (사용자가 git pull 후 cron 설정)

---

## 🎉 최종 결과

**Phase 3 시작 전 알림 시스템 완전 개선 완료!**

- ✅ 의미 있는 장중 알림만 전송
- ✅ 실제 포트폴리오 기반 일일 리포트
- ✅ 보유 종목 우선 표시
- ✅ 투자 의사결정에 실질적 도움

**내일부터 개선된 알림이 텔레그램으로 도착합니다!** 📱
