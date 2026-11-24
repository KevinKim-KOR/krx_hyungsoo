# POC5-01B 인계 — 운영 의사결정 이벤트 원장 · 첫 거래일 확인 (2026-10-08)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(`POC5-02` · `POC5-03` 남은 확인 → 두 단계 종료 → `POC5-04`)
- **입력**
  - 01B: 설계서 `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md` · PLAN `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md` · 결과서 `docs/ai_result/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_RESULT.md`(§10-5 첫 거래일)
  - 02: 결과서 `docs/ai_result/POC5/POC5-02_PRICE_OUTCOME_MATURITY_RESULT.md`(STATUS · 배포 기록)
  - 03: 설계서 `docs/ai_design/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_DESIGN_V1.md`(개정 2 · 끝에 결정 이력 · RESULT 판정 원문) · 결과서 `docs/ai_result/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_RESULT.md`
  - 지금 실제 동작 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md` · 마스터 `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`(Q23 · Q24 일부는 POC5-03 개정 2 로 대체 표시)

```text
POC5-01B   IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-08)
           검증자 r3 VERIFIED · 설계자 RESULT PASS_TO_DEPLOY · 커밋 9cbbd419 · OCI pull 2026-10-07 15:56:59 + 플래그
POC5-02    IMPLEMENTED_VERIFIED_DEPLOYED · 커밋 f0711340 · OCI pull 2026-10-07 22:19:31(사용자 · 01B 확인 전 = 게이트 전 배포)
           첫 실행 10-08 08:10 no_ledger · 09:20 ok 대상 32 · INSERT 0 · 대기 111 → 첫 결과 행 확인 = 10-12 08:10 이후
POC5-03    IMPLEMENTED_VERIFIED_DEPLOYED · 커밋 4e92d0c5 · 검증자 r2 VERIFIED · 설계자 RESULT PASS_TO_USER_CHECK(STEP 미종료)
           사용자 실화면 10-07 · 실데이터 동기화 10-08 10:15 → 가격 결과 표시 확인 = 10-12 08:10 이후
OCI HEAD   4e92d0c5 · cron · .env 변경은 01B 플래그 1줄뿐(2026-10-07)
```

---

## 1. 지금까지 만든 것 (한 줄씩)

- **01B 원장** — OCI 러너 운영 3종(`market_briefing` · `holdings_briefing` · `holdings_risk_alert`)의 send 실행이 OCI `state/decision/decision_evidence.sqlite`(폴더 0700 · 파일 0600 · WAL)에 `evaluation_run` · `signal_item` · `delivery` · `ledger_meta` 를 남긴다. 켜짐 = `.env` `DECISION_LEDGER_ENABLED=true` ∧ send ∧ 운영 3종. 대조 CLI `scripts/run_decision_ledger_reconcile.py`(읽기 전용).
- **02 가격 결과** — 08:10 · 09:20 배치 끝에서 원장의 `PRIMARY_LIVE` · 예정 회차 · 평가 가능 item 에 +1/+5/+20 거래일 원시 결과를 `price_outcome` 에 한 번씩 INSERT(15:30 이전 사건은 사건일 종가가 +1 · 운영 거래일 캘린더 `state/market_meta/krx_trading_days_2026.csv`).
- **03 받은 알림 기록** — PC 「진단·상태 > 받은 알림 기록」. `원장 새로고침` 버튼 때만 OCI 원장을 읽기 전용 export(SSH 1회 · 저장소 `app/ledger_copy/remote_export.py` 를 `python3 -` 표준입력으로) → PC 사본 5표. 평가는 선택(append-only) · 결과는 평가와 무관하게 보인다 · 무평가도 이후 ML 이 쓴다(사용자 결정 · 설계 개정 2 §12).

## 2. 01B 첫 거래일 실측 (2026-10-08 10:13 · OCI 읽기 전용)

| 실행 | 원장 | 전달 | item(전체 · 평가 가능 · 본문 포함) |
|---|---|---|---|
| 08:30 시장 브리핑 | FINALIZED · sent · PRIMARY_LIVE · off 0 · run_id 연결 | sent · 261자 · 보류 0 | 3 · 3 · 3 |
| 09:15 보유 브리핑 | 〃 | sent · 250자 | 29 · 29 · 3 |
| 09:30 장중 급등락 | 〃 | sent · 286자 | 56 · 56 · 4 |

- STARTED 잔류 0 · 대조 CLI `status=OK floor=2026-10-07T23:30:02Z` · `ok=3 missing_in_ledger=0 started_gap=0 ledger_only=0` · exit 0.
- `ledger_meta` 8키(schema_version · primary_start_date=2026-10-08 · first_active_at · deploy_commit · 계약 버전 3 · POC5-02 `schema_version.price_outcome`).
- 폴더 700 · 파일 600(ubuntu) · 러너 로그 `decision ledger` 오류 0.

## 3. 남은 확인 — 2026-10-12(월) 08:10 이후

10-09 는 한글날 휴장이다(운영 캘린더에 없음). 10-08 종가는 KRX 가 다음 영업일 08:00 에 공개하므로, 10-08 사건의 +1 결과는 **10-12 08:10 배치**부터 생긴다(+5 = 10-16 · +20 = 11-06 쯤).

1. **POC5-02** — `logs/oci_market_data_batch.log` 의 `price outcome maturity:` 줄에서 `inserted` > 0 · `by_status` 에 `MATURED`(그리고 결측이면 `PRICE_MISSING` 등)를 본다. 원장 `price_outcome` 상태별 행 수를 읽기 전용으로 센다. 통과면 결과서 STATUS → `…_OPERATION_CONFIRMED`.
2. **POC5-03** — 사용자가 PC 에서 `원장 새로고침` → 10-08 화면 `신호 결과 원장` 의 +1 칸이 `집계 중` 에서 수익률 % 로 바뀌는지 본다(평가 없이도 보여야 한다). PC 사본 `price_outcome` 행 수 = OCI 행 수. 통과면 STEP 종료 기록.
3. 두 단계 종료 뒤: 종료 기록(PROGRAM_TRUTH · STATE · 결과서) · 인계 · 커밋 제안 → 설계자에게 `POC5-04` 설계 요청.

## 4. OCI 읽기 전용 확인 방법

```bash
ssh oci-krx 'bash -s' <<'REMOTE'
cd /home/ubuntu/krx_hyungsoo
stat -c '%a %U %s %n' state/decision state/decision/*
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/home/ubuntu/krx_hyungsoo/state/decision/decision_evidence.sqlite?mode=ro',uri=True)
for t in ('evaluation_run','signal_item','delivery','ledger_meta','price_outcome'):
    print(t, c.execute('select count(*) from '+t).fetchone()[0])
print(c.execute("select run_state, count(*) from evaluation_run group by 1").fetchall())
print(c.execute("select status, horizon, count(*) from price_outcome group by 1,2").fetchall())
PY
venv/bin/python scripts/run_decision_ledger_reconcile.py
grep -n "price outcome maturity" logs/oci_market_data_batch.log | tail -4
REMOTE
```

- 본문(`delivery.body_text`) · 가격 · 키 값은 출력하지 않는다(길이 · 건수만). OCI 에 `sqlite3` 명령이 없다 — `python3` + `mode=ro`.
- 쓰기 · 발송 · 재시작 · pull · cron · `.env` 변경은 사용자 몫이다.
- PC 사본 확인: `sqlite3 -readonly state/decision/decision_evidence.sqlite "select count(*) from price_outcome;"`(테스트 아님 · 읽기만).

## 5. 주의 · 열린 항목

1. **POC5-02 는 배포 게이트 전에 배포됐다** — 설계자 게이트는 '01B 첫 거래일 확인(10-08 09:35 이후) 통과 뒤 pull' 이었으나 사용자가 10-07 22:19 에 pull 했다(POC5-03 커밋과 함께). 영향: 10-08 09:20 성숙 단계가 01B 확인 전에 `price_outcome` 표와 meta 1행을 만들었다(원장 4표 · 러너 쓰기 무관 · 01B 확인 통과). **설계자에게 아직 전달하지 않았다** — 다음 설계자 차례에 함께 올린다.
2. 배치 로그(`oci_market_data_batch.log`)는 줄마다 두 번 찍힌다 — 10-05 이전부터의 기존 동작(배포와 무관 · 미조치).
3. POC5-03 한계(결과서 §5): `CONFLICT` 가 나면 화면 복구 절차 없음 · 원장 열이 바뀌면 PC · OCI 코드가 같아야 동기화 · 전체 export 라 1년 규모에서 60초가 모자랄 수 있음 · 읽기 전용 export 가 OCI 원장 폴더에 `-wal` · `-shm` 을 만들 수 있음(설계자 수용).
4. **보유 이력(매수 · 매도 시점 · 금액)** — 사용자 요청 · 설계자 판단 '별도 소형 설계'(BACKLOG §8) · POC5-03 · 04 를 막지 않는다.
5. **사용자 결정**: 받은 알림 평가는 매일 하지 않는다 · 사후 ML 때 검토 · 무평가도 ML 이 그대로 쓴다(메모리 `project_alert_feedback_retrospective`).
