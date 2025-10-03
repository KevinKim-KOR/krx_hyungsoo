# OPERATIONS.md

## 0) TL;DR (필수 요약)
- **Repo:** `git@github.com:KevinKim-KOR/krx_hyungsoo.git` (단일 `main`)
- **로컬(Windows):** `E:\AI Study\krx_alertor_modular` (항상 PC에서 먼저 작업)
- **NAS(DS220j / DSM):** `/volume2/homes/Hyungsoo/krx/krx_alertor_modular`
- **운영 방식:** Docker 없이 **venv + DSM 스케줄러** (웹/리포트/시그널 자동화)
- **시세 캐시:** `data/cache/kr/*.pkl` (증분 병합, 휴장일은 과거 거래일 캐시 사용)
- **거래일/레짐:** 069500(KODEX200) 일봉 존재일을 거래일로 사용, 200SMA로 레짐 참고
- **비밀 설정:** `secret/config.yaml` (Git 미추적) + `KRX_CONFIG`/`KRX_WATCHLIST` 환경변수로 참조
- **알림:** Telegram(봇 토큰/챗ID는 `secret/config.yaml`에만)

---

## 1) 개발 룰 (DEVELOPMENT_RULES 요약)
1. **병렬 금지**: 모든 계산은 순차 수행(멀티스레드/프로세스 사용 금지)
2. **휴장일 처리**:  
   - 휴장일엔 **데이터 생성 금지**  
   - 휴장일 평가금액/가격은 **마지막 거래일 캐시** 사용  
   - 휴장일 이후 신호는 **다음 거래일** 기준
3. **가격 소스**:  
   - 개장 전: 전 거래일 가격  
   - 개장~자정: 당일 가격(한국은 네이버 실시간 허용)  
   - 캐시는 `data/cache/kr/*.pkl`
4. **평가금액 보정**: 기록된 값이 0이거나 보유 종목 합보다 작은 경우, **보유 종목 가치로 자동 보정** (사용자 입력 값은 절대 임의 축소 금지)
5. **제외 종목 처리**: `etf.json`에서 `is_active: false`는 제외
6. **데이터 부족/비정상**: 기간 부족·음수·결측 등은 제외하고 로그에 남기며, 심각 시 ERROR + 알림
7. **코드 원칙**: 1파일 1기능, 중복 최소화, 미사용 import 제거

---

## 2) 디렉터리/파일 (핵심)
krx_alertor_modular/
├─ app.py # 기존 CLI(ingest, report 등)
├─ reporting_eod.py # EOD 요약/텔레그램 (내장 fallback 포함)
├─ report_eod_cli.py # EOD 전용 CLI
├─ run_report_eod.sh # EOD 자동화(재시도/락/알림)
├─ web/
│ ├─ main.py # FastAPI 엔트리
│ ├─ signals.py # 시그널 라우트
│ ├─ watchlist.py # 워치리스트 편집 UI(/watchlist)
│ └─ templates/
│ ├─ index.html
│ └─ signals.html # 행 색상/배지/마지막 보기 기억(localStorage)
├─ signals/
│ ├─ service.py # 신호 계산/정렬/텔레그램 전송
│ └─ queries.py # DB/캐시 쿼리 계층
├─ run_web.sh # 웹 기동(락/로그/ENV 설정)
├─ stop_web.sh # 웹 종료
├─ signals_cli.py # 시그널 전송 CLI
├─ run_signals.sh # 시그널 자동 전송(스케줄용)
├─ secret/
│ ├─ config.yaml # 🔐 비밀 설정(텔레그램 등)
│ └─ watchlist.yaml # 🔐 워치리스트(웹에서 편집)
├─ data/cache/kr/.pkl # 시세 캐시
├─ logs/.log # 실행 로그(일자별)
├─ requirements-web.txt # 웹 의존성(uvicorn/fastapi/pyyaml/... + python-multipart)
├─ requirements-nas.txt # NAS 공용 의존성
└─ OPERATIONS.md # 본 문서

yaml
코드 복사

> **ENV 표준**(run\_web.sh 등에서 export):  
> `KRX_CONFIG="$PWD/secret/config.yaml"`  
> `KRX_WATCHLIST="$PWD/secret/watchlist.yaml"`

---

## 3) Git 플로우 (항상 PC → NAS)
1. **PC에서 수정/테스트**  
   ```powershell
   cd "E:\AI Study\krx_alertor_modular"
   git add -A
   git commit -m "feat/fix: <요약>"
   git push origin main
NAS 반영/재기동/검증

bash
코드 복사
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
./update_from_git.sh
# 캐시 줄바꿈 정리 필요 시: sed -i 's/\r$//' *.sh web/*.py web/templates/*.html
bash stop_web.sh
: > logs/web_$(date +%F).log
bash run_web.sh
tail -n 120 logs/web_$(date +%F).log
4) 리포트(EOD) 운영
수동

bash
코드 복사
./venv/bin/python report_eod_cli.py --date auto
자동(스케줄): run_report_eod.sh

재시도: 기본 2회(환경변수 RETRY_MAX/RETRY_SLEEP)

실패 시 텔레그램 경보 전송

잠금 디렉토리: .locks/report_eod.lock

로그: logs/report_YYYY-MM-DD.log

포맷 특징: 상승/하락 TopN, 임계치 필터, 시장/커버리지 표시

5) 웹(시그널/워치리스트) 운영
기동/중지

bash
코드 복사
bash run_web.sh     # 0.0.0.0:8899
bash stop_web.sh
주요 기능

/signals: 정렬/모드(score_abs|rank)·watchlist 토글, 마지막 보기 기억

텔레그램 버튼: 현재 화면 요약을 전송

/watchlist: 한 줄 1코드 편집, 저장 시 secret/watchlist.yaml + 자동 백업

의존성 주의: python-multipart (Form 사용)

6) 시그널 자동 전송
CLI: signals_cli.py

스케줄: run_signals.sh (락/로그/대체모드/실패시 경보)

DSM 예시: 평일 09:10

bash
코드 복사
bash /volume2/homes/Hyungsoo/krx/krx_alertor_modular/run_signals.sh
7) 데이터/거래일/캐시 규칙
거래일: 069500 일봉 존재일 + 평일은 거래일 간주(장중 신호 유지)

휴장일: 새 데이터 생성 금지. 캐시/직전 거래일 사용

캐시: data/cache/kr/<TICKER>.pkl 증분 저장, 히트시 재활용

DB: SQLite(예: krx_alertor.sqlite3), prices_daily/securities 등

8) 비밀 설정/경로
secret/config.yaml (Git 미추적)

yaml
코드 복사
notifications:
  telegram:
    token: "****:****"
    chat_id: 123456789
환경변수 고정(run_*.sh):
export KRX_CONFIG="$PWD/secret/config.yaml"
export KRX_WATCHLIST="$PWD/secret/watchlist.yaml"

9) 장애 대응 런북
ImportError(옛 바이트코드) → stop → find . -name "__pycache__" -type d -exec rm -rf {} → run

CRLF 깨짐 → sed -i 's/\r$//' *.sh

텔레그램 미발송 → KRX_CONFIG 경로/키 확인, requests/pyyaml 설치

웹 405/404 → 라우트/메소드 확인, 템플릿 파일명/경로 점검

시그널 공백 → 템플릿 변수명(rows/signals/payload.signals) 호환, 엔진 필터 임계치 확인

10) 백테스트(개요)
CLI 예시

bash
코드 복사
./venv/bin/python backtest_cli.py --start 2024-01-02 --end 2025-09-20 --mode score_abs --wl 1
출력: reports/backtests/<timestamp>.csv|json

규칙: 병렬 금지(순차 루프), 휴장일/캐시 규칙 동일 적용

11) 체크리스트
PC: git status 깨끗 → git push

NAS: ./update_from_git.sh → stop_web.sh → run_web.sh → 로그 OK

텔레그램: 테스트 메시지 수신 확인

스케줄: DSM에서 run_* 잡 활성화