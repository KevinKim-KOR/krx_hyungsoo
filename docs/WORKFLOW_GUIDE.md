# 개발 워크플로우 가이드

## 🔄 전체 순환 구조

```
PC (전략 개발) → PC (백테스트) → NAS (자동 반영) → 
NAS (장중 스캐너) → NAS (EOD 리포트) → PC (분석) → 
PC (전략 수정) → ...
```

---

## 📍 Phase 1: 전략 개발 (PC)

### 위치
```
E:\AI Study\krx_alertor_modular
```

### 작업 내용
1. **전략 파라미터 수정**
   ```yaml
   # config.yaml
   scanner:
     thresholds:
       daily_jump_pct: 1.5  # 조정
       adx_min: 18.0        # 조정
   ```

2. **지표 로직 수정**
   ```python
   # scanner.py 또는 indicators.py
   # 새로운 필터 추가
   ```

3. **테스트 실행**
   ```bash
   # PC에서
   pytest tests/ -v
   ```

---

## 📍 Phase 2: 백테스트 (PC)

### GPU 활용
```bash
# PC (RTX 4070S)
python app.py backtest \
  --start 2024-01-01 \
  --end 2025-10-20 \
  --config config.yaml
```

### 결과 분석
```bash
# backtests/ 폴더 확인
# - equity_curve.csv
# - trades.csv
# - metrics.json
```

### 성과 지표 확인
- 연환산 수익률
- 샤프 비율
- MDD (최대 낙폭)
- 승률
- 벤치마크 대비 초과 수익

---

## 📍 Phase 3: Git 커밋 & Push (PC)

```bash
# PC에서
git add config.yaml scanner.py
git commit -m "strategy: lower jump threshold to 1.5% based on backtest"
git push origin main
```

---

## 📍 Phase 4: 자동 반영 (NAS)

### 자동 동기화 (Cron)
```bash
# NAS cron - 매일 15:50 실행
50 15 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/update_from_git.sh
```

### 수동 동기화
```bash
# NAS에서
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
bash scripts/linux/batch/update_from_git.sh
```

---

## 📍 Phase 5: 장중 스캐너 (NAS)

### 스케줄
- **09:30**: 장 시작 전 스캔
- **15:40**: 장 마감 전 스캔

### 실행
```bash
# NAS cron
40 15 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_scanner.sh
```

### Telegram 알림 내용
```
📊 [KRX Scanner] 2025-10-22 15:40

🟢 BUY 추천 (3종목)
1. 삼성전자 (005930) - 급등 2.3%, ADX 25
2. SK하이닉스 (000660) - 급등 1.8%, MFI 65
3. NAVER (035420) - 급등 1.5%, 섹터 강세

🔴 SELL 추천 (1종목)
1. 카카오 (035720) - SMA200 이탈

📈 현재 레짐: ON (투자 가능)
```

---

## 📍 Phase 6: EOD 리포트 (NAS)

### 스케줄
- **16:30**: 장 마감 후 리포트 생성

### 실행
```bash
# NAS cron
30 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_report_eod.sh
```

### Telegram 알림 내용
```
📊 [EOD Report] 2025-10-22

💰 오늘 수익률: +1.2%
📈 누적 수익률: +15.3%
🎯 벤치마크 대비: +3.2%

📋 보유 종목 (5개)
1. 삼성전자: +2.1% (비중 25%)
2. SK하이닉스: +1.5% (비중 20%)
...

⚠️ 주의 종목
- 카카오: SMA50 이탈 (청산 검토)

🔔 내일 액션
- BUY: NAVER (신호 발생)
- SELL: 카카오 (약세 전환)
```

---

## 📍 Phase 7: 분석 & 개선 (PC)

### 로그 다운로드 (옵션)
```bash
# PC에서 - NAS 로그 다운로드
scp Hyungsoo@nas:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/*.log ./logs/
```

### 성과 분석
1. Telegram 리포트 확인
2. 승률/손익비 계산
3. 문제점 파악

### 전략 수정
- 필터 조건 조정
- 신호 임계값 변경
- 새로운 지표 추가

→ **Phase 1로 돌아감**

---

## 🛠️ 도구별 역할

| 도구 | 역할 | 위치 |
|------|------|------|
| **PC** | 개발, 백테스트, 테스트 | Windows |
| **NAS** | 실행, 알림, 로그 | DS220j |
| **GitHub** | 코드 저장소 | 클라우드 |
| **Telegram** | 알림 수신 | 모바일 |

---

## 📅 일일 스케줄 (NAS Cron)

```bash
# /etc/crontab 또는 crontab -e

# 09:30 - 장 시작 전 스캔
30 9 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_scanner.sh

# 15:40 - 장 마감 전 스캔
40 15 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_scanner.sh

# 15:50 - Git 동기화 (PC 전략 변경사항 반영)
50 15 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/update_from_git.sh

# 16:30 - EOD 리포트 & 데이터 수집
30 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_daily_cycle.sh
```

---

## 🎯 핵심 원칙

1. **PC = 두뇌** (전략 개발, 백테스트)
2. **NAS = 손발** (자동 실행, 알림)
3. **GitHub = 동기화** (코드 전달)
4. **Telegram = 피드백** (결과 확인)

---

## 🚀 빠른 시작 체크리스트

### PC 설정
- [ ] Python 환경 구축
- [ ] pytest 설치
- [ ] Git 설정
- [ ] config.yaml 작성

### NAS 설정
- [ ] Docker 또는 Miniconda 설치
- [ ] 의존성 패키지 설치
- [ ] Cron 등록
- [ ] Telegram 봇 설정

### 첫 실행
- [ ] PC에서 백테스트
- [ ] Git Push
- [ ] NAS에서 Git Pull
- [ ] NAS에서 수동 스캐너 실행
- [ ] Telegram 알림 확인

---

## 💡 최적화 팁

### PC (백테스트 속도 향상)
```python
# GPU 활용 (cuDF, Rapids)
import cudf  # NVIDIA GPU 가속

# 병렬 처리
from joblib import Parallel, delayed
```

### NAS (리소스 절약)
```bash
# 메모리 사용량 모니터링
free -h

# 불필요한 로그 정리
find logs/ -mtime +30 -delete
```

---

## 📊 성과 추적

### 주간 리뷰 (PC)
```bash
# 1주일 성과 분석
python app.py report --start 2025-10-15 --end 2025-10-22

# 벤치마크 비교
python app.py report --benchmark 069500
```

### 월간 리뷰 (PC)
- 전략별 성과 비교
- 섹터별 수익률
- 리스크 지표 점검
- 전략 파라미터 재조정

---

**작성자**: Hyungsoo Kim  
**일시**: 2025-10-22  
**버전**: 1.0
