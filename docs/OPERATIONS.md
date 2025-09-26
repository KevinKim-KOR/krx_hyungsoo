## 0) 요약 (TL;DR)
- **Repo:** `git@github.com:KevinKim-KOR/krx_hyungsoo.git` (`main` 단일 브랜치 운용)
- **로컬(Windows):** `E:\AI Study\krx_alertor_modular`
- **NAS(DS220j / DSM):** `/volume2/homes/Hyungsoo/krx/krx_alertor_modular`
- **운영 방식:** Docker 없음 → **venv + DSM 작업 스케줄러**
- **파이썬:** NAS Python **3.8.12** (타입힌트 호환 주의)
- **알림:** Telegram (Slack 미사용)
- **시세 소스:** KRX(pykrx, 네이버) + **파일 캐시**(yfinance 의존 최소화)
- **레짐 판단:** `069500.KS`의 200SMA
- **거래일 판정:** ETF 일봉 존재일 + “**오늘 평일은 거래일 간주**” 예외

---

## 1) 디렉터리 구조 (핵심)
**NAS:** `/volume2/homes/Hyungsoo/krx/krx_alertor_modular`
app.py # CLI 엔트리
scanner.py # 스캐너(신호/알림)
fetchers.py # 시세 적재/보조
db.py # DB 스키마/세션(SQLite 가정)
backtest.py # 백테스트
notifications.py # Telegram 전송
calendar_kr.py # 거래일/휴장일 판정
krx_helpers.py # KRX 안전 수집 + 캐시
cache_store.py # 파일 캐시(data/cache/kr/*.pkl)
adaptive.py # (shim) experimental/adaptive 우회 로더
experimental/
init.py
adaptive.py # (선택) 장세별 임계값 오버레이 구현
config.yaml # 🔐 로컬 전용(민감정보) — Git에 올리지 않음
requirements-nas.txt # NAS 의존성 고정
run_scanner.sh # 스캐너 실행(스케줄러에서 호출)
update_from_git.sh # 최신 코드 반영(hard reset + deps)
logs/
scanner_YYYY-MM-DD.log
data/
cache/
kr/
069500.KS.pkl # 캐시
backups/
venv/ # NAS 가상환경 — Git에 추적 금지
docs/
OPERATIONS.md # 이 파일

markdown
코드 복사

**로컬(Windows):** `E:\AI Study\krx_alertor_modular`  
구조는 동일. 로컬은 `.venv/` 사용 가능. **.sh 파일은 LF 유지** 필요.

---

## 2) Git 규칙
- **브랜치:** `main`만 사용(실수 방지)  
- **원격:** `origin = git@github.com:KevinKim-KOR/krx_hyungsoo.git`  
- **.gitignore (필수)**
venv/
.venv/
pycache/
logs/
data/
config.yaml

markdown
코드 복사
- **.gitattributes (권장)** — Windows에서 LF 유지
*.sh text eol=lf

bash
코드 복사

**일상 플로우**
1) 로컬에서 작업 → `git add/commit/push`
2) NAS 반영:
 ```bash
 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/update_from_git.sh
검증:

bash
코드 복사
/volume2/homes/Hyungsoo/krx/krx_alertor_modular/run_scanner.sh
tail -n 80 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/scanner_$(date +%F).log
싱크 확인 (커밋 해시)

로컬: git rev-parse --short HEAD

NAS : cd /volume2/.../krx_alertor_modular && git rev-parse --short HEAD

3) NAS venv & 의존성
bash
코드 복사
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
python3 -m venv venv
./venv/bin/python -m pip install -U pip
./venv/bin/python -m pip install -r requirements-nas.txt -q
# (백테스트 필요 시)
./venv/bin/pip install -q tabulate==0.9.0
Python 3.8 호환 지침 (이미 반영)

파일 맨 위: from __future__ import annotations

pd.DataFrame | None → Optional[pd.DataFrame]

list[str] → List[str]

4) 스크립트 원본
update_from_git.sh

bash
코드 복사
#!/bin/bash
set -e
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git fetch --all
git reset --hard origin/main
find . -name "*.sh" -type f -exec sed -i 's/\r$//' {} \;
./venv/bin/python -m pip install -U pip
./venv/bin/python -m pip install --upgrade -r requirements-nas.txt -q || true
echo "[OK] pulled & deps checked"
run_scanner.sh

bash
코드 복사
#!/bin/bash
set -e
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
. ./venv/bin/activate
python app.py scanner-slack --date "$(date +%F)" >> "logs/scanner_$(date +%F).log" 2>&1
CRLF로 깨지면: sed -i 's/\r$//' run_scanner.sh

5) 설정(config.yaml) — 로컬 전용(예시)
yaml
코드 복사
universe:
  type: ETF
  market: KS
  exclude_keywords: ["레버리지","채권","커버드콜","인버스","선물","ETN"]
  min_avg_turnover: 500000000

regime:
  spx_ticker: "069500.KS"
  sma_days: 200

scanner:
  thresholds:
    daily_jump_pct: 0.5
    adx_min: 20
    mfi_min: 45
    mfi_max: 80
    volz_min: 1.0
  trend_sma_short: 50
  trend_sma_long: 200
  trend_sma20_slope_days: 20
  sector_top_k: 5
  per_sector_cap: 2
  top_n: 10
  weight_scheme: "equal"
  rebalance: "W"

sell_rules:
  hard_exit_under_sma200: true
  soft_exit_under_sma50: true
  mdd_trailing_pct: 0.10
  weak_momentum_days: 20
  adx_soft_threshold: 15
  mfi_soft_threshold: 40
  vol_z_soft_threshold: -1.0

backtest:
  slippage_bps: 8
  fee_bps: 5
  trade_frequency: "W"
  benchmark_code: "379800"

notifications:
  channel: "telegram"
  telegram:
    bot_token: "****:****"   # 🔐 Git 금지
    chat_id: 1234567890       # 🔐 Git 금지

adaptive:
  enabled: true
  regime_source: "069500.KS"
  regime_lookback_days: 200
  vol_downgrade_atr_pct: 0.03
  profiles:
    bull:
      scanner:
        daily_jump_threshold: 0.3
        min_adx: 15
        mfi_low: 45
        mfi_high: 85
        min_volz: 0.5
      universe: { min_avg_turnover: 0, top_n: 10 }
    neutral:
      scanner:
        daily_jump_threshold: 0.5
        min_adx: 20
        mfi_low: 45
        mfi_high: 80
        min_volz: 1.0
      universe: { min_avg_turnover: 0, top_n: 8 }
    bear:
      scanner:
        daily_jump_threshold: 0.8
        min_adx: 25
        mfi_low: 40
        mfi_high: 70
        min_volz: 1.5
      universe: { min_avg_turnover: 0, top_n: 5 }
6) 거래일/휴장일
calendar_kr.py: 069500.KS 일봉 존재일을 거래일로 사용

“오늘”은 평일이면 거래일 간주(장중 알림 유지)

7) 캐시 동작
경로: data/cache/kr/<TICKER>.pkl

모듈: krx_helpers.py, cache_store.py

증분 병합 후 저장 → 다음 호출 시 hit 로그

pgsql
코드 복사
[CACHE] 069500.KS: hit 400 rows, +before 0, +after 0 → use 400
8) 실행/스케줄
수동

bash
코드 복사
./run_scanner.sh
# 또는 특정일
./venv/bin/python app.py scanner --date 2025-09-24
./venv/bin/python app.py scanner-slack --date 2025-09-24
DSM 작업 스케줄러

“사용자 지정 스크립트” → /volume2/.../run_scanner.sh

평일 09:10, 10~15시 매시 정각, 실패 재시도 ON

9) 텔레그램
notifications.py가 config.yaml의 토큰/채팅ID로 전송

토큰/ID는 Git 업로드 금지

10) 백테스트
bash
코드 복사
./venv/bin/python app.py backtest --start 2024-01-02 --end 2025-09-20 --config config.yaml
필요 패키지: tabulate==0.9.0

11) 문제 해결(런북)
CRLF로 스크립트 깨짐
sed -i 's/\r$//' *.sh

venv가 Git에 올라가 충돌

bash
코드 복사
echo "venv/" >> .gitignore
git rm -r --cached venv
git commit -m "stop tracking venv"
git push
Py3.8 타입힌트 에러 (| None, list[str])

from __future__ import annotations

Optional[...], List[...]로 변경

adaptive import 실패

루트 adaptive.py(shim):

python
코드 복사
try:
    from experimental.adaptive import get_effective_cfg
except Exception:
    def get_effective_cfg(cfg, asof): return cfg
experimental/__init__.py 빈 파일 유지

yfinance 레이트리밋

이미 KRX/캐시 우선 구조. 벤치마크도 069500.KS 활용.

12) 상태 체크리스트
git status (로컬 변경 커밋/푸시)

NAS:

bash
코드 복사
/volume2/.../update_from_git.sh
/volume2/.../run_scanner.sh
tail -n 80 /volume2/.../logs/scanner_$(date +%F).log
로그에 에러 없고, *[KRX Scanner]* ... 있으면 OK