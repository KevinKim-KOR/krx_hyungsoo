# KRX Alertor Modular — STATE_LATEST (Handoff)

> 목적: 새 세션/새 담당자/새 AI가 “추측 없이” 동일한 방식으로 운영을 이어가기 위한 1장 요약.
> 원칙: Fail-Closed / Resolver-only / PC→OCI Pull / 운영 스크립트 파싱 단순 유지 / Daily Summary Enum화(UNKNOWN 금지).

---

## 0) 오늘 결론 (한 줄)
- ✅ 현재 운영 상태: [OK] (P67: Spike/Holding Watch 완전 정상화)
- 🧩 핵심 이슈: 없음. (Spike receipt artifact 경로 불일치 및 미생성 문제 해결됨)

---

## 1) 아키텍처 요약 (PC → OCI Pull)
- PC(주도): UI에서 **백테스트/결과확인/포트폴리오/설정/워치리스트** 입력 및 저장
- OCI(운영): 매일 **git pull → ops summary → live cycle → order plan → daily status push**
- 실시간(장중): **spike_watch / holding_watch**가 크론으로 돌며 텔레그램 알림

---

## 2) Git / 브랜치
- Repo: `krx_hyungsoo`
- Branch(운영 기준): `archive-rebuild`
- PC 기준 커밋: `f04d81f` (OCI Synced)
- OCI 기준 커밋: `P67-FIX-FINAL` (Assumed Synced)
- 마지막 변경 요약(짧게): Fix Spike Watch Artifacts & API Path Match

---

## 3) OCI 서비스(backend) 상태
- 서비스명: `krx-backend.service`
- 포트: `:8000`
- 상태 확인:
  - `sudo systemctl status krx-backend.service --no-pager -l | head -60`
  - `sudo ss -lntp | grep ':8000'`
- Health API:
  - `curl -s http://localhost:8000/api/ops/health | python3 -m json.tool | head -80`

---

## 4) 텔레그램 발송 설정(OCI)
- Sender enable 스위치:
  - 파일: `state/real_sender_enable.json`
  - 예시:
    ```json
    {"enabled": true, "provider": "telegram"}
    ```
- Telegram secrets:
  - 파일: `state/secrets/telegram.env` (chmod 600)
  - 키:
    - `TELEGRAM_BOT_TOKEN=...`
    - `TELEGRAM_CHAT_ID=...`
- systemd env 주입:
  - `/etc/systemd/system/krx-backend.service` 내 `[Service]`에
    - `EnvironmentFile=/home/ubuntu/krx_hyungsoo/state/secrets/telegram.env`
  - 적용:
    - `sudo systemctl daemon-reload`
    - `sudo systemctl restart krx-backend.service`

---

## 5) 운영 스케줄 (OCI crontab)
- crontab:
  - `crontab -l`
- 현재 등록(붙여넣기):
  ```cron
  # 1. 일요일 로그 정리
  0 1 * * 0 cd /home/ubuntu/krx_hyungsoo && test -f logs/daily_ops.log && tail -n 5000 logs/daily_ops.log > logs/daily_ops.log.tmp && mv -f logs/daily_ops.log.tmp logs/daily_ops.log || true
  
  # 2. Daily Ops (매일 09:05)
  5 9 * * * cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
  
  # 3. Spike Watch (장중 매 5분)
  */05 09-15 * * 1-5 cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/spike_watch.sh >> logs/spike_watch.log 2>&1
  
  # 4. Holding Watch (장중 매 10분, 보유종목 감시)
  */10 9-15 * * 1-5 cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/holding_watch.sh >> logs/holding_watch.log 2>&1
  ```

---

## 6) 주요 “운영 버튼” (CLI 한 줄)
### A) 로그 요약 (P69 Standard)
- 최근 1회 실행 "Reason" 확정:
  - Spike: `tail -n 80 logs/spike_watch.log | grep "Reason=" | tail -1`
  - Holding: `tail -n 80 logs/holding_watch.log | grep "Reason=" | tail -1`

### B) 운영자 1커맨드 상태판 (P71, Dashboard)
아래 블록을 통째로 복사해서 실행하면, **백엔드/Spike/Holding**의 상태와 **WHY(미발송 사유)**를 즉시 확인 가능합니다.

bash deploy/oci/ops_dashboard.sh
```
> **판정 규칙 (WHY/DELIVERY)**
> - Backend: **ONLINE**(정상), **DOWN**(점검필요)
> - Watchers: **Active**(정상), **SUCCESS**(정상), **FAIL**(장애)
> - Contract 5: **Ready**(정상)
> - Daily Status: **Generated**(정상), **TELEGRAM**(전송됨)


### C) 데일리 운영 (P72 Summary)
- **표준 확인 커맨드 (Daily Standard)**:
  1. **최신 요약 (1초 확인)**: `cat logs/daily_summary.latest`
  2. **흐름 확인 (히스토리)**: `tail -n 20 logs/daily_summary.log`
  3. **데이터 오염 검사**: `egrep "reco=UNKNOWN|reco=GENERATED" logs/daily_summary.log && echo "❌ BAD" || echo "✅ CLEAN"`

- **Reason별 조치 (Actionable Troubleshooting)**:
  - `ORDER_PLAN_PORTFOLIO_MISSING` / `PORTFOLIO_MISSING`: 포트폴리오 파일(`state/portfolio/latest`) 누락.
  - `ORDER_PLAN_PORTFOLIO_READ_ERROR` / `PORTFOLIO_READ_ERROR`: JSON 파싱 실패 / 파일 깨짐.
  - `ORDER_PLAN_PORTFOLIO_SCHEMA_INVALID` / `PORTFOLIO_SCHEMA_INVALID`: 필수 키(`asof`, `cash`, `holdings`) 누락 또는 타입 오류.
  - `NO_ACTION_PORTFOLIO_EMPTY`: (정상) 자산/현금 모두 0. 주문 없음.
  - `NO_ACTION_PORTFOLIO_CASH_ONLY`: (정상) 현금만 존재. 주문 없음.
  - `ORDER_PLAN_BUNDLE_STALE` / `BUNDLE_STALE`: 전략 번들 24시간 경과. PC에서 전략 재생성 후 Push.
  - `ORDER_PLAN_EMPTY_RECO` / `EMPTY_RECO`: 추천 종목 없음. (정상 or 번들 데이터 부족).

- 실행:
  `bash deploy/oci/daily_ops.sh`
- Exit code:
  - 0 = OK/WARN/NO_ACTION 정상 완료
  - 2 = BLOCKED(정상 차단: stale/missing/schema 등)
  - 3 = 운영 장애(스크립트/백엔드/예외)

### B) 스파이크 감시(OCI)
- 실행(수동):
  `bash deploy/oci/spike_watch.sh`

### C) 보유 감시(OCI)
- 실행(수동):
  `bash deploy/oci/holding_watch.sh`

---

## 7) idempotency 규칙(핵심만)
- **Daily Status Push**: `daily_status_YYYYMMDD` (하루 1회)
- **Incident Push**: `incident_<KIND>_YYYYMMDD` (동일 타입 하루 1회)
- **Spike/Holding**: 쿨다운 + “추가 변동(realert_delta)”일 때만 재알림

---

## 8) 운영 확인(증거/리포트)
### A) Daily Status 최신
```bash
curl -s http://localhost:8000/api/push/daily_status/latest | python3 -m json.tool | head -120
```

### B) Holding Watch 최신 (Evidence-based)
- Evidence Ref: `guard_holding_latest` (Alias)
- 검증 (Resolver):
```bash
curl "http://localhost:8000/api/evidence/resolve?ref=guard_holding_latest"
```

### C) Spike Watch 최신 (Evidence-based, P67 Completed)
- Evidence Ref: `guard_spike_latest` (Alias)
- 검증 (Resolver):
```bash
curl "http://localhost:8000/api/evidence/resolve?ref=guard_spike_latest"
```

### D) Contract 5 Reports (P73 Freeze)
- **Human Report** (`guard_report_human_latest`):
  ```bash
  curl "http://localhost:8000/api/evidence/resolve?ref=guard_report_human_latest"
  ```
- **AI Report** (`guard_report_ai_latest`):
  ```bash
  curl "http://localhost:8000/api/evidence/resolve?ref=guard_report_ai_latest"
  ```

### E) P80/P81 최종 검증 표준 (Consistency & Validity)
- **1. 안정성 검사 (No Flapping)**:
  ```bash
  for i in 1 2 3; do bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1; done
  tail -3 logs/daily_summary.log
  ```
  *(기대: Reco/Reason 유지, reco=UNKNOWN/GENERATED 없음)*

- **2. Order Plan / Dashboard 검사 (P81)**:
  ```bash
  python3 -m app.utils.ops_dashboard
  ```
  *(기대: Order Plan 라인이 명시적으로 보이며, `BLOCKED`(Schema/Missing) 또는 `NO_ACTION`(Empty/Cash) 상태가 정확히 표시)*

- **3. 리스크 동기화 검사**:
  Reason이 `ORDER_PLAN_*` (Blocked) 일 때만 `risks`에 `ORDER_PLAN_BLOCKED` + 구체 사유가 포함됨. `NO_ACTION`일 땐 리스크 없음.

- **4. 데이터 오염 검사 (P81 Log Hygiene - 최근 200줄만 검사)**:
  ```bash
  tail -n 200 logs/daily_summary.log | egrep "reco=UNKNOWN|reco=GENERATED|Reason=[A-Z0-9_]+:|INVALID_PORTFOLIO|Bundleisstale|created" && echo "❌ BAD" || echo "✅ CLEAN"
  ```
  *(기대: ✅ CLEAN 출력)*

- **5. 1회성 과거 로그 정리 (최초 P81 적용 시 필요)**:
  ```bash
  mkdir -p logs/archive
  ts=$(date +%Y%m%d_%H%M%S)
  test -f logs/daily_summary.log && mv logs/daily_summary.log logs/archive/daily_summary.log.preP81FIX_${ts} || true
  : > logs/daily_summary.log
  : > logs/daily_summary.latest
  ```

### F) P82 API Reason Enum-only 검증 표준
- **1. Order Plan API reason 콜론 금지**:
  ```bash
  curl -s http://localhost:8000/api/order_plan/latest | python3 -c 'import json,sys; d=json.load(sys.stdin); r=(d.get("rows") or [{}])[0]; print(r.get("reason",""))' | egrep "^[A-Z0-9_]+$" && echo "✅ REASON_ENUM" || echo "❌ REASON_DIRTY"
  ```
  *(기대: ✅ REASON_ENUM)*

- **2. Reco API reason 콜론 금지**:
  ```bash
  curl -s http://localhost:8000/api/reco/latest | python3 -m json.tool | egrep -n '"reason"|"reason_detail"' | head -20
  ```
  *(기대: reason이 ENUM-only, reason_detail에 상세 메시지 분리)*

- **3. Risk Code 오염 금지**:
  ```bash
  curl -s http://localhost:8000/api/ops/summary/latest | python3 -m json.tool | egrep -n '"code"' | head -50
  ```
  *(기대: code에 콜론/문장/공백 없음, ENUM-only)*

---

## 9) PC에서 입력되는 것 → OCI로 넘어오는 경로
- **Portfolio**: PC UI에서 저장 → git push → OCI git pull → `state/portfolio/latest/...`
- **Settings(Spike/Holding 통합)**: PC UI 저장 → git push → OCI git pull → `state/settings/latest/...`
- **Watchlist**: PC UI 저장 → git push → OCI git pull → `state/watchlist/latest/...`
- **Strategy bundle**: PC 생성 → `state/strategy_bundle/latest/...` 갱신 → git push → OCI git pull

---

## 10) 오늘 장애/이슈 기록 (필수)
- 날짜: 2026-01-27
- 증상:
  1. Holding Watch 알림 미수신 (Env 미로드) -> 해결
  2. Spike Watch Artifact(JSON) 미생성 (Early Return 문제) -> 해결
  3. API Path Mismatch (구형 spike 경로 참조) -> 해결
- 조치:
  - holding_watch.sh: `set -a` 추가.
  - run_spike_push.py: `try-finally` 블록으로 Artifact 생성 보장, Indentation Fix.
  - backend/main.py: API 경로를 `spike_watch`로 변경.
- 검증:
  - 모든 Watcher가 실행 후 JSON Artifact를 남기며, API(`api/push/spike/latest`, `api/evidence/resolve`)가 정상 응답함.
  - `logs/spike_watch.log` 최근 구간 에러 없음(RECENT_OK).

---

## 11) 다음 단계(Phase)
- 현재 완료: D-P.67 (Spike/Holding Artifact Consistency & Evidence System)
- 다음 후보:
  - P68: Spike Receipt Quality (execution_reason enum화 등, 잔여 개선)
- 보류(나중에): 보유임계치 백테스트/평단 실시간 정교화/괴리율 고도화 등

---

## 12) P83: Bundle Stale 자동복구 + Reason 우선순위

### Reason 우선순위 (P83 정책)
1. `GIT_PULL_FAILED` / `BUNDLE_REFRESH_FAILED` (운영 장애급)
2. `BUNDLE_STALE_WARN` (PC 작업 필요)
3. `ORDER_PLAN_*` (portfolio/schema 등 구체 사유)
4. `EMPTY_RECO` (번들이 fresh인데도 비었으면)
5. `OK`

### Reason별 조치
| Reason | 조치 |
|--------|------|
| `BUNDLE_STALE_WARN` | PC에서 번들 생성/갱신 후 git push → OCI 다음 실행 시 자동 복구 |
| `GIT_PULL_FAILED` | 네트워크/권한/디스크, OCI repo 상태 확인 |
| `ORDER_PLAN_PORTFOLIO_*` | PC에서 포트폴리오 확인 후 git push |

### 표준 확인 커맨드
```bash
# 현재 상태 확인
cat logs/daily_summary.latest
tail -n 20 logs/daily_summary.log

# GIT_PULL 결과 확인
grep "Repository" logs/daily_ops.log | tail -5
```

### git pull 결과 Enum
- `GIT_PULL_UPDATED`: 변경 적용됨
- `GIT_PULL_NO_CHANGES`: 이미 최신
- `GIT_PULL_FAILED`: 실패 (exit 3 + incident)
