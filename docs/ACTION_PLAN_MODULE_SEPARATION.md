# 🎯 모듈 분리 작업 계획서
**작성일**: 2025-10-23 00:50  
**예상 소요 시간**: 2시간  
**목표**: NAS/PC 역할 명확히 분리하여 환경 문제 완전 해결

---

## 📋 작업 개요

### 현재 문제점
1. ❌ NAS에서 불필요한 모듈(ml/, backtest.py) 설치 시도
2. ❌ PyTorch 등 무거운 의존성이 NAS 환경 오염
3. ❌ requirements 파일 5개 혼재 (혼란)
4. ❌ app.py가 모든 기능 통합 (역할 분리 안 됨)

### 해결 방안
✅ **모듈 분리 구조**로 전환
- `core/`: 공통 모듈 (DB, providers, indicators)
- `nas/`: NAS 전용 (경량 CLI + 최소 의존성)
- `pc/`: PC 전용 (백테스트, ML, 분석)

---

## 🗂️ 최종 디렉토리 구조

```
krx_alertor_modular/
├── core/                           # 공통 모듈 (PC + NAS)
│   ├── __init__.py
│   ├── db.py                       # DB 모델
│   ├── fetchers.py                 # 데이터 수집
│   ├── calendar_kr.py              # 거래일 캘린더
│   ├── indicators.py               # 기술 지표
│   ├── notifications.py            # 알림
│   ├── providers/                  # 데이터 소스
│   │   ├── __init__.py
│   │   ├── ohlcv.py
│   │   └── ohlcv_bridge.py
│   └── utils/                      # 유틸리티
│       └── trading_day.py
│
├── nas/                            # NAS 전용
│   ├── __init__.py
│   ├── app_nas.py                  # NAS CLI (경량)
│   ├── scanner_nas.py              # 스캐너 (경량 버전)
│   ├── requirements.txt            # 최소 의존성 (5개)
│   └── README_NAS.md               # NAS 실행 가이드
│
├── pc/                             # PC 전용
│   ├── __init__.py
│   ├── app_pc.py                   # PC CLI (전체)
│   ├── backtest.py                 # 백테스트
│   ├── analyzer.py                 # 성과 분석
│   ├── sector_autotag.py           # 섹터 태깅
│   ├── reporting_eod.py            # 리포트
│   ├── ml/                         # 머신러닝 (PC 전용)
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── train.py
│   │   └── datasets.py
│   └── requirements.txt            # 전체 의존성
│
├── scripts/                        # Shell 스크립트 (NAS)
│   └── linux/
│       ├── batch/
│       │   ├── run_ingest_eod.sh
│       │   ├── run_scanner.sh
│       │   └── run_report_eod.sh
│       └── jobs/
│
├── config/                         # 설정 파일
│   ├── config.nas.yaml             # NAS 설정
│   ├── config.pc.yaml              # PC 설정
│   ├── env.nas.sh
│   └── env.pc.sh
│
├── data/                           # 데이터 저장소
│   ├── cache/
│   ├── db/
│   └── output/
│
├── docs/                           # 문서
│   ├── PROGRESS_2025-10-23.md
│   └── ACTION_PLAN_MODULE_SEPARATION.md
│
└── tests/                          # 테스트
```

---

## 🔧 작업 단계별 체크리스트

### ✅ 1단계: 디렉토리 구조 생성 (5분)

```bash
# 실행 명령어 (PC에서)
cd "E:\AI Study\krx_alertor_modular"

# 디렉토리 생성
mkdir -p core/providers core/utils
mkdir -p nas
mkdir -p pc/ml
```

**체크포인트**:
- [ ] `core/`, `nas/`, `pc/` 폴더 생성 확인
- [ ] 기존 파일 백업 완료

---

### ✅ 2단계: 공통 모듈을 core/로 이동 (15분)

```bash
# 이동할 파일 목록
mv db.py core/
mv fetchers.py core/
mv calendar_kr.py core/
mv indicators.py core/
mv notifications.py core/
mv krx_helpers.py core/
mv cache_store.py core/
mv adaptive.py core/

# providers 폴더 이동
mv providers/* core/providers/

# utils 폴더 이동 (있다면)
mv utils/trading_day.py core/utils/
```

**체크포인트**:
- [ ] 모든 파일이 `core/`로 이동
- [ ] `core/__init__.py` 생성
- [ ] `core/providers/__init__.py` 생성

---

### ✅ 3단계: PC 전용 모듈을 pc/로 이동 (10분)

```bash
# PC 전용 파일 이동
mv backtest.py pc/
mv backtest_cli.py pc/
mv analyzer.py pc/
mv sector_autotag.py pc/
mv reporting_eod.py pc/
mv strategies.py pc/

# ML 폴더 이동
mv ml/* pc/ml/

# 기존 app.py는 pc/app_pc.py로 복사
cp app.py pc/app_pc.py
```

**체크포인트**:
- [ ] 백테스트 관련 파일 `pc/`로 이동
- [ ] ML 폴더 `pc/ml/`로 이동
- [ ] `pc/__init__.py` 생성

---

### ✅ 4단계: NAS 전용 경량 CLI 생성 (30분)

**파일**: `nas/app_nas.py`

```python
# -*- coding: utf-8 -*-
"""
NAS 전용 경량 CLI
- ingest-eod: 데이터 수집
- scanner: 스캐너 실행
- notify: 텔레그램 알림
"""

import argparse
import sys
import os

# core 모듈 import 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.db import init_db
from core.fetchers import ingest_eod
from core.calendar_kr import is_trading_day, load_trading_days
from nas.scanner_nas import run_scanner_nas
from core.notifications import send_notify
import pandas as pd

def cmd_init(args):
    """DB 초기화"""
    init_db()
    print("✅ DB 초기화 완료")

def cmd_ingest_eod(args):
    """EOD 데이터 수집"""
    asof = pd.to_datetime(pd.Timestamp.today().date() if args.date == "auto" else args.date)
    load_trading_days(asof)
    
    if not is_trading_day(asof):
        print(f"[SKIP] 휴장일 {asof.date()} — ingest 생략")
        return
    
    ingest_eod(asof.strftime("%Y-%m-%d"))
    print(f"✅ EOD 데이터 수집 완료: {asof.date()}")

def cmd_scanner(args):
    """스캐너 실행"""
    asof = pd.to_datetime(args.date if args.date else pd.Timestamp.today().date())
    load_trading_days(asof)
    
    if not is_trading_day(asof):
        print(f"[SKIP] 휴장일 {asof.date()} — scanner 생략")
        return
    
    run_scanner_nas(asof)
    print(f"✅ 스캐너 실행 완료: {asof.date()}")

def cmd_notify(args):
    """텔레그램 알림 전송"""
    send_notify(args.message, channel="telegram")
    print("✅ 알림 전송 완료")

def main():
    parser = argparse.ArgumentParser(description="KRX Alertor NAS CLI")
    subparsers = parser.add_subparsers(dest="command", help="명령어")
    
    # init
    parser_init = subparsers.add_parser("init", help="DB 초기화")
    parser_init.set_defaults(func=cmd_init)
    
    # ingest-eod
    parser_ingest = subparsers.add_parser("ingest-eod", help="EOD 데이터 수집")
    parser_ingest.add_argument("--date", default="auto", help="날짜 (YYYY-MM-DD 또는 auto)")
    parser_ingest.set_defaults(func=cmd_ingest_eod)
    
    # scanner
    parser_scanner = subparsers.add_parser("scanner", help="스캐너 실행")
    parser_scanner.add_argument("--date", help="날짜 (YYYY-MM-DD)")
    parser_scanner.set_defaults(func=cmd_scanner)
    
    # notify
    parser_notify = subparsers.add_parser("notify", help="알림 전송")
    parser_notify.add_argument("message", help="메시지 내용")
    parser_notify.set_defaults(func=cmd_notify)
    
    args = parser.parse_args()
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return
    
    args.func(args)

if __name__ == "__main__":
    main()
```

**체크포인트**:
- [ ] `nas/app_nas.py` 생성
- [ ] import 경로 정상 동작 확인
- [ ] 테스트 실행: `python nas/app_nas.py --help`

---

### ✅ 5단계: NAS 전용 스캐너 생성 (20분)

**파일**: `nas/scanner_nas.py`

```python
# -*- coding: utf-8 -*-
"""
NAS 전용 경량 스캐너
- 백테스트/ML 의존성 제거
- 핵심 스캐닝 로직만 포함
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from core.db import SessionLocal, Security, PriceDaily
from core.indicators import sma, adx, mfi, pct_change_n
from core.providers.ohlcv_bridge import get_ohlcv_df
from sqlalchemy import select
import yaml

def load_config():
    """설정 파일 로드"""
    config_path = "config/config.nas.yaml"
    if not os.path.exists(config_path):
        config_path = "config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_universe_codes(session, cfg):
    """유니버스 종목 코드 조회"""
    q = select(Security).where(Security.type == cfg["universe"]["type"])
    secs = session.execute(q).scalars().all()
    
    exclude_keywords = cfg["universe"]["exclude_keywords"]
    codes = []
    for s in secs:
        name = (s.name or "").lower()
        if any(k.lower() in name for k in exclude_keywords):
            continue
        codes.append(s.code)
    
    return sorted(set(codes))

def run_scanner_nas(asof: pd.Timestamp):
    """NAS 전용 스캐너 실행"""
    cfg = load_config()
    
    with SessionLocal() as session:
        # 유니버스 조회
        codes = get_universe_codes(session, cfg)
        print(f"유니버스 크기: {len(codes)} 종목")
        
        # 가격 데이터 로드
        start_date = (asof - pd.Timedelta(days=300)).date()
        q = select(PriceDaily).where(
            PriceDaily.date >= start_date
        ).where(
            PriceDaily.date <= asof.date()
        )
        rows = session.execute(q).scalars().all()
        
        if not rows:
            print("⚠️ 가격 데이터 없음")
            return
        
        df = pd.DataFrame([{
            "code": r.code, "date": r.date,
            "open": r.open, "high": r.high, "low": r.low,
            "close": r.close, "volume": r.volume
        } for r in rows])
        
        df = df[df["code"].isin(codes)]
        df["date"] = pd.to_datetime(df["date"])
        
        # 간단한 필터링 (예시)
        candidates = []
        for code, g in df.groupby("code"):
            g = g.sort_values("date").set_index("date")
            close = g["close"].astype(float)
            
            if len(close) < 60:
                continue
            
            # 간단한 조건: 20일 수익률 > 5%
            ret20 = pct_change_n(close, 20)
            if ret20.iloc[-1] > 0.05:
                candidates.append({
                    "code": code,
                    "ret20": ret20.iloc[-1],
                    "close": close.iloc[-1]
                })
        
        # 결과 출력
        if candidates:
            print(f"\n✅ BUY 후보: {len(candidates)}건")
            for c in sorted(candidates, key=lambda x: x["ret20"], reverse=True)[:5]:
                print(f"  - {c['code']}: 20일 수익률 {c['ret20']*100:.2f}%, 종가 {c['close']:.0f}")
        else:
            print("\n⚠️ BUY 후보 없음")

if __name__ == "__main__":
    run_scanner_nas(pd.Timestamp.today())
```

**체크포인트**:
- [ ] `nas/scanner_nas.py` 생성
- [ ] 테스트 실행: `python nas/scanner_nas.py`

---

### ✅ 6단계: 의존성 파일 정리 (10분)

**파일**: `nas/requirements.txt` (최소 의존성)

```txt
# NAS 전용 최소 의존성 (5개 핵심만)
pykrx==1.0.45
pandas==1.5.3
pytz==2024.1
requests==2.32.3
pyyaml==6.0.2
SQLAlchemy>=2.0,<2.1
```

**파일**: `pc/requirements.txt` (전체 의존성)

```txt
# PC 전용 전체 의존성
pandas>=2.2.2
numpy>=1.26.4
SQLAlchemy>=2.0.29
pyyaml>=6.0.2
requests>=2.32.3
yfinance>=0.2.43
pykrx>=1.0.45
pytz>=2024.1
tabulate>=0.9.0
schedule>=1.2.1

# 백테스트
matplotlib>=3.8.0
seaborn>=0.13.0

# ML (선택)
torch>=2.0.0
scikit-learn>=1.3.0

# 데이터 소스
FinanceDataReader>=0.9.50
pandas-datareader>=0.10.0
```

**체크포인트**:
- [ ] `nas/requirements.txt` 생성 (5개만)
- [ ] `pc/requirements.txt` 생성 (전체)
- [ ] 기존 requirements*.txt 파일 정리

---

### ✅ 7단계: Shell 스크립트 수정 (15분)

**파일**: `scripts/linux/batch/run_scanner.sh` 수정

```bash
#!/bin/bash
# NAS 전용 스캐너 실행

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

# 가상환경 활성화
source venv/bin/activate

# NAS CLI 실행
python nas/app_nas.py scanner --date auto

echo "✅ 스캐너 실행 완료"
```

**수정할 스크립트 목록**:
- [ ] `run_ingest_eod.sh` → `python nas/app_nas.py ingest-eod`
- [ ] `run_scanner.sh` → `python nas/app_nas.py scanner`
- [ ] `run_report_eod.sh` → 필요 시 수정

---

### ✅ 8단계: 설정 파일 분리 (10분)

**파일**: `config/config.nas.yaml` (NAS 전용)

```yaml
# NAS 전용 설정 (경량)
environment: nas

universe:
  type: ETF
  market: KS
  exclude_keywords:
    - 레버리지
    - 인버스
    - 채권
  min_avg_turnover: 1000000000

scanner:
  adx_window: 14
  mfi_window: 14
  vol_z_window: 20
  sector_top_k: 3
  per_sector_cap: 2
  top_n: 5
  
  thresholds:
    daily_jump_pct: 1.0
    adx_min: 15.0
    mfi_min: 40.0
    mfi_max: 80.0
    volz_min: 1.0

regime:
  enabled: true
  spx_ticker: "069500.KS"
  sma_days: 200

notifications:
  channel: telegram
  telegram:
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"

database:
  path: "krx_alertor.sqlite3"
```

**파일**: `config/config.pc.yaml` (PC 전용)

```yaml
# PC 전용 설정 (전체 기능)
environment: pc

# NAS 설정 상속
<<: *nas_config

# 백테스트 추가 설정
backtest:
  start_date: "2018-01-01"
  rebalance_freq: "W"  # W, M, D
  fee_roundtrip: 0.002
  initial_capital: 10000000

# ML 설정
ml:
  enabled: false
  model_type: "lstm"
  lookback_days: 60
```

**체크포인트**:
- [ ] `config/config.nas.yaml` 생성
- [ ] `config/config.pc.yaml` 생성
- [ ] 환경변수 설정 확인

---

### ✅ 9단계: Import 경로 수정 (20분)

**수정 패턴**:

```python
# 기존
from db import SessionLocal
from fetchers import ingest_eod
from scanner import recommend_buy_sell

# 변경 후 (NAS)
from core.db import SessionLocal
from core.fetchers import ingest_eod
from nas.scanner_nas import run_scanner_nas

# 변경 후 (PC)
from core.db import SessionLocal
from core.fetchers import ingest_eod
from pc.backtest import run_backtest
```

**수정할 파일 목록**:
- [ ] `nas/app_nas.py`
- [ ] `nas/scanner_nas.py`
- [ ] `pc/app_pc.py`
- [ ] `pc/backtest.py`
- [ ] `pc/analyzer.py`
- [ ] `scripts/ops/*.py` (필요 시)

---

### ✅ 10단계: 테스트 및 검증 (20분)

**PC 테스트**:
```bash
cd "E:\AI Study\krx_alertor_modular"

# 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# PC CLI 테스트
python pc/app_pc.py --help
python pc/app_pc.py init
```

**NAS 시뮬레이션 (PC에서)**:
```bash
# NAS 의존성만 설치
pip install -r nas/requirements.txt

# NAS CLI 테스트
python nas/app_nas.py --help
python nas/app_nas.py scanner --date auto
```

**체크포인트**:
- [ ] PC CLI 정상 동작
- [ ] NAS CLI 정상 동작
- [ ] Import 오류 없음
- [ ] 데이터 수집 정상
- [ ] 스캐너 실행 정상

---

### ✅ 11단계: 문서 업데이트 (10분)

**파일**: `nas/README_NAS.md`

```markdown
# NAS 실행 가이드

## 설치

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치 (5개만)
pip install -r nas/requirements.txt
```

## 실행

```bash
# DB 초기화 (최초 1회)
python nas/app_nas.py init

# EOD 데이터 수집
python nas/app_nas.py ingest-eod --date auto

# 스캐너 실행
python nas/app_nas.py scanner --date auto

# 알림 전송
python nas/app_nas.py notify "테스트 메시지"
```

## Cron 등록

```bash
# crontab -e
0 9 * * * cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source venv/bin/activate && python nas/app_nas.py ingest-eod --date auto
10 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source venv/bin/activate && python nas/app_nas.py scanner --date auto
```
```

**체크포인트**:
- [ ] `nas/README_NAS.md` 생성
- [ ] `README.md` 업데이트 (구조 변경 반영)
- [ ] `docs/PROGRESS_2025-10-23.md` 업데이트

---

### ✅ 12단계: Git Commit (5분)

```bash
# 변경사항 확인
git status

# 스테이징
git add core/ nas/ pc/ config/ scripts/ docs/

# 커밋
git commit -m "refactor: 모듈 분리 (NAS/PC 역할 명확화)

- core/: 공통 모듈 (DB, providers, indicators)
- nas/: NAS 전용 경량 CLI (5개 의존성)
- pc/: PC 전용 전체 기능 (백테스트, ML)
- 의존성 정리 (nas/requirements.txt, pc/requirements.txt)
- Shell 스크립트 경로 수정
- 설정 파일 분리 (config.nas.yaml, config.pc.yaml)

Resolves: NAS 환경 설정 문제, 의존성 충돌
"

# 푸시
git push origin main
```

**체크포인트**:
- [ ] Git commit 완료
- [ ] Git push 완료
- [ ] GitHub에서 확인

---

## 📊 작업 후 예상 결과

### NAS 환경
```bash
# 의존성 크기
기존: 500MB+ (PyTorch, scikit-learn 등)
변경: 50MB (pykrx, pandas, pytz, requests, pyyaml만)

# 설치 시간
기존: 10분+
변경: 1분

# 메모리 사용량
기존: 500MB+
변경: 100MB
```

### PC 환경
```bash
# 기능
- 백테스트 ✅
- ML 학습 ✅
- 데이터 분석 ✅
- 전략 개발 ✅

# 의존성
- 전체 패키지 사용 가능
- GPU 활용 가능
```

---

## 🚨 주의사항

### 1. 기존 코드 백업
```bash
# 작업 전 백업
cp -r krx_alertor_modular krx_alertor_modular_backup_20251023
```

### 2. Import 경로 변경
- 모든 `from db import` → `from core.db import`
- 모든 `from fetchers import` → `from core.fetchers import`
- 체계적으로 수정 필요

### 3. Shell 스크립트 경로
- `python app.py` → `python nas/app_nas.py`
- 모든 배치 스크립트 확인 필요

### 4. 설정 파일 경로
- `config.yaml` → `config/config.nas.yaml` (NAS)
- `config.yaml` → `config/config.pc.yaml` (PC)

---

## 🎯 다음 세션 시작 방법

### 시작 명령어
```
"모듈 분리 작업을 시작하겠습니다. 
docs/ACTION_PLAN_MODULE_SEPARATION.md를 참고하여 
1단계부터 순차적으로 진행해주세요."
```

### 또는 자동 실행
```
"모듈 분리 작업을 자동으로 진행해주세요. 
각 단계마다 확인 요청하지 말고 
전체를 한 번에 완료해주세요."
```

---

## 📝 체크리스트 요약

- [ ] 1단계: 디렉토리 구조 생성 (5분)
- [ ] 2단계: 공통 모듈 이동 (15분)
- [ ] 3단계: PC 전용 모듈 이동 (10분)
- [ ] 4단계: NAS CLI 생성 (30분)
- [ ] 5단계: NAS 스캐너 생성 (20분)
- [ ] 6단계: 의존성 파일 정리 (10분)
- [ ] 7단계: Shell 스크립트 수정 (15분)
- [ ] 8단계: 설정 파일 분리 (10분)
- [ ] 9단계: Import 경로 수정 (20분)
- [ ] 10단계: 테스트 및 검증 (20분)
- [ ] 11단계: 문서 업데이트 (10분)
- [ ] 12단계: Git Commit (5분)

**총 예상 시간**: 2시간 10분

---

## 🎉 완료 후 기대 효과

1. ✅ **NAS 환경 문제 완전 해결**
   - 의존성 충돌 제거
   - 설치 시간 90% 단축
   - 메모리 사용량 80% 감소

2. ✅ **역할 명확히 분리**
   - NAS: 데이터 수집 + 스캐너 + 알림
   - PC: 백테스트 + ML + 분석

3. ✅ **유지보수 용이**
   - 각 환경별 독립적 개발
   - 의존성 관리 단순화
   - 코드 구조 명확화

4. ✅ **확장성 확보**
   - 새로운 기능 추가 용이
   - 환경별 최적화 가능
   - 프로덕션 레벨 품질

---

**작성자**: Cascade AI  
**문서 버전**: v1.0  
**최종 수정**: 2025-10-23 00:50
