# Low-Frequency Telegram Push Operation v1 — Conclusion (DONE)

작성일: 2026-07-26
상태: **DONE** · Market / Holdings / Spike = **ACTIVE** (OCI 운영 중)
next_step_gate: `FIRST_REAL_DECISION_CYCLE_V1`

---

## 0. 최종 상태 앵커

```text
low_frequency_telegram_push_operation = DONE
market_briefing = ACTIVE (평일 08:00 KST)
holdings_briefing = ACTIVE (평일 OPEN 09:15 / MIDDAY 12:30 / CLOSE 15:40 KST)
spike_or_falling_alert = ACTIVE (평일 09:30~15:20 7 tick · 조건 발생형)
oci_market_data_batch = ACTIVE (평일 07:20 KST · 증분 갱신 + artifact + freshness)
next_step_gate = FIRST_REAL_DECISION_CYCLE_V1
```

---

## 1. 이 STEP 이 완성한 것

PC 없이 OCI 가 **Market · Holdings · Spike 3-PUSH 를 자율 운영**한다.

- **Market briefing**: 평일 08:00 KST 1회 정기 발송.
- **Holdings briefing**: 평일 3 슬롯 (OPEN/MIDDAY/CLOSE) · Runtime 현재가 오버레이 (holdings_latest.json 미수정) · 슬롯별 registry 중복 차단.
- **Spike/Falling alert**: 평일 7 tick 조건 평가 · 신규 falling signal 만 발송 · fingerprint 중복 차단.
- **OCI 자율 시장 데이터**: 승인 대상(seed ∪ Holdings) 일별 시세 증분 갱신 → SQLite Universe artifact 생성 → freshness 검증. Spike 는 그 결과만 소비 (외부 거래일 조회 없음).

---

## 2. 구현 계약 (핵심)

### 2.1 Runtime 가격 오버레이 (Holdings/Spike)
- 기존 승인 시세 출처 `market_naver.fetch_many` 로 실행 시점 현재가 조회.
- Holdings: 현재가/평가수익률/as-of 별도 fact 라인. `price_asof` 필수 (없으면 라인 생략).
- Spike: universe artifact Published Evidence (`spike_trigger_type`/`direction`/`falling_threshold_pct`/`base_close`/`evidence_as_of`) + Runtime 현재가로 falling 재평가.

### 2.2 registry key 확장 (DB PRIMARY KEY 무변경)
- Holdings: `runtime_date_kst#slot_id`.
- Spike: `runtime_date_kst#ticker#trigger#direction` (fingerprint 는 date 제외 · Runner 가 date 1회 접두).

### 2.3 OCI 자율 시장 데이터 (OCI Operational Market Data Refresh v1)
- **증분 갱신**: 기존 FDR `refresh_price_history` 재사용 (신규 source 없음). `lookback = end_date - 마지막저장일` → 마지막 저장일 이후만 수집.
- **전체 최솟값**: 승인 대상 **전체** 가 유효 종가(close>0) 확보해야 `price_data_as_of` 확정. 하나라도 누락 = fail·None (성공 위장 금지).
- **SQLite fetcher**: `fetch_price_history` 기반 · pykrx `fetch_one_month_basis` 와 동일 계약. builder 에 DI 주입. **기존 pykrx 경로는 PC/진단용 보존**.
- **저장 순서**: 생성(저장 전) → refresh_status ok → validate_artifact → freshness → **통과 시에만** save_latest_artifact (실패 artifact 로 latest 덮어쓰기 방지).

### 2.4 Freshness 계약 (설계자 C 확정)
DB 를 거래일 캘린더로 쓰는 방식은 순환 결함(stale DB → lag 0)이라 **폐기**. freshness 는 07:20 배치가 한 번 확정하고 Spike 는 결과만 검증한다 (외부 거래일 조회 없음).

**Spike 실행 조건 (모두 충족)**:
1. 당일 데이터 갱신 배치 `status = success`
2. artifact `evidence_as_of` == 배치 `price_data_as_of`
3. `artifact_generated_at` 이 현재 36시간 이내
4. `현재일 - price_data_as_of <= 7 달력일` (장기 stale 최종 안전 상한)
5. 공용 `validate_artifact` 통과

하나라도 실패 → `failed` · Telegram 미발송 · sent registry 미기록.

> **AC 정정 (§11)**: 지시문 §4.3 원문의 "최근 완료된 KRX 거래일 기준 최대 1거래일 지연" 은 정확한 KRX 거래일 캘린더가 없어 순환 결함을 유발했다. 대체 계약 = "당일 배치 성공 + artifact.price_data_as_of == 배치 결과 + 7달력일 상한 + 36시간 + validate". 7일은 정상 freshness 증명 기준이 아니라 주말·설/추석 연휴를 흡수하는 **장기 stale 차단 최종 안전 상한**이다.

---

## 3. OCI 실측 (2026-07-26)

| 단계 | 결과 |
|---|---|
| 일별 배치 | `status=success` · attempted=41 success=41 fail=0 · price_data_as_of=2026-07-24 · freshness_ok=true |
| SQLite | 069500 유효종가 최신일 2026-07-24 (2026-07-03 중단분 → 오늘까지 증분 채움) |
| 배치 state ↔ artifact | price_data_as_of == evidence_as_of == 2026-07-24 일치 · data_source=sqlite_etf_daily_price · scored=20 |
| Spike 수동 send | **status=sent · freshness=fresh · Telegram 실 수신 확인** |

builder 가 pykrx 아닌 SQLite 로 계산 (외부 호출 0) · Spike 최초 정상 발송 확인.

---

## 4. crontab (KST · OCI 등록 완료)

```crontab
# Market / Holdings (기존)
0 8 * * 1-5   market_briefing --mode send
15 9 * * 1-5  holdings_briefing --mode send --slot-id OPEN
30 12 * * 1-5 holdings_briefing --mode send --slot-id MIDDAY
40 15 * * 1-5 holdings_briefing --mode send --slot-id CLOSE
# OCI Operational Market Data Refresh v1 (신규)
20 7 * * 1-5  run_oci_market_data_batch.py            # 데이터 배치 (Market 이전)
30 9,10,11,12,13,14 * * 1-5 + 20 15  spike_or_falling_alert --mode send  # 7 tick
```

---

## 5. 검증 이력 (참고)

이 STEP 은 다수 REJECTED 라운드를 거쳐 완성됐다:
- Runtime 오버레이/Spike 재평가 A+ 재작업 (6 라운드): partial 발송 계약, 혼합 신호 재발송, fallback 재도입, 공용 validator 미재사용 등 정정.
- OCI Operational Market Data Refresh (4 라운드): SQLite 갱신↔artifact 기준일 연결, freshness 순환 결함(DB 거래일 캘린더), 전체 최솟값·증분 엄격화·success/fail 카운터 정합.

최종: focused 26 passed · 전체 회귀 1066 passed/4 skipped/0 failed · black·flake8 clean · Runner 626줄.

---

## 6. 다음 STEP

`FIRST_REAL_DECISION_CYCLE_V1` — 실제 판단 1주기 (Holdings→evidence→PENDING 초안→사용자 매수/매도 판단). 설계자 지시 대기.

관련 conclusion:
- 이 STEP 의 OCI 경계 정의: `POC2_OCI_AUTONOMOUS_MARKET_DATA_BOUNDARY_AMENDMENT_CONCLUSION.md`
- crontab 초안: `OCI_LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1_CRONTAB.md`
