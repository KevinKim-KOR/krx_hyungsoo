# POC3-02D-OPS-02 인계 — 장중 전달 상태 · 운영 UI 정합성 보완 (검증 · OCI 반영 · 배포 확인)

> **인계 시점 (2026-09-29 · 설계자 RESULT `PASS` · 검증자 `VERIFIED` r2 · 배포 확인 `CONFIRMED`).** 구현 · 검증 · 커밋 ·
> push · OCI pull 까지 끝났다. 남은 것은 새 코드의 **첫 장중 자연 발송 실측** 하나다(설계자: 기다리느라 다음 작업을 멈추지 않는다).
> 정본 증거는 결과서와 설계서 끝의 설계자 판정 원문이다. 이 문서는 다음 사람이 바로 이어받는 데 필요한 것만 추린다.

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(첫 자연 발송 실측 · `POC3-02D-OPS-03` 진행)
- **입력**
  - 설계서 `docs/ai_design/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_DESIGN_V1.md` — 지시 원문 · Q1~Q6 판정 · 3-4 문구 확정 · RESULT 판정(`PASS_WITH_MANDATORY_AMENDMENT`) 원문
  - PLAN `docs/ai_plan/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_PLAN_V1.md`
  - 결과서 `docs/ai_result/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_RESULT.md`
  - 설계자 통합 판정(2026-09-29 · OPS-02 `PASS` · 배포 확인 지시 · OPS-03 개시) 원문 — `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md`

```text
POC3-02D-OPS-02            IMPLEMENTED_VERIFIED_DEPLOYED — 3-1 · 3-2 · 3-3 · 3-4
                           설계자 RESULT PASS (2026-09-29 · 앞서 PASS_WITH_MANDATORY_AMENDMENT M1 · M2 반영)
                           검증자 VERIFIED r2 (2026-09-29 · r1 REJECTED = 결과서 화면 확인 표기 모순)
커밋                       b5b15509 (3-1 · 「OCI 운영·적용」 합침과 함께) · eff609a0 (3-2 · 3-3 · 3-4 · 35파일) — origin/main push
OCI                        pull 2026-09-29 밤(사용자) · 재기동 불필요 · POC3-02D-OPS-02_DEPLOYMENT = CONFIRMED
RUNTIME_FIELD_OBSERVED     = OBSERVED (2026-09-30 09:30 틱 · OCI 읽기 전용 09:32 · HEAD eff609a0) — 장중 통합 본문 `sent` · `partial_delivery` false · `sent_today` 1 · 관측 4종 모두 `last_delivered_state` = 전달 상태 · `last_sent_at` 09:30 · `continuous` true · 첫 틱 새 파일(date_reset) · 잘림 · 전송 실패 틱 0 — 판정 기준 1~4 충족
사용자 구현 화면 확인       PASSED (2026-09-28)
운영 상태                  OPERATING_DEGRADED (설계자 2026-09-29) — 국내 추세 T-2 · KOSPI 정지 → POC3-02D-OPS-03
러너 646줄 변경 0 · 신규 의존성 · 신규 API · DB 스키마 · cron · flag 변경 0
```

---

## 1. 이 단계가 바꾼 것 (계약 정본은 `docs/PROGRAM_TRUTH.md`)

| 항목 | 바뀐 것 | 정본 위치 |
|---|---|---|
| 3-1 | 「오늘의 투자 점검」 OCI 한 줄 링크 → 「OCI 운영·적용」(`approval`) · 문구 'OCI 운영·적용에서 상세 보기 →' | PROGRAM_TRUTH §5.2 |
| 3-2 | 장중 억제 비교 = 마지막 **성공 전달** 상태 `last_delivered_state`(관측 `state` 아님). 잘림 · 전송 실패 · 부분 전송 · 조립 뒤 예외로 전달 못 한 변화는 다음 틱 후보. 구파일은 다음 정상 저장 때 추정값을 필드로 옮김 · 회복 기록은 미전달 관측이 지우지 않음 | PROGRAM_TRUTH 「장중 급등락」 절 · §7.2 |
| 3-3 | 낡은 fingerprint 역검증 ⑦ → ⑦-a · ⑦-b · 목업 ⑦ 제목 · 현재형 옛 문구 · 과거 기록 적용 기간 | 결과서 §1-6 |
| 3-4 | KOSPI 최신성 상태 — `GET /market/topn/latest` 선택 필드 3개 · 두 화면 공용 생성기 `KospiStatusNote` · 설계자 확정 문구 · 영문 KOSPI 경고 화면에서만 숨김 · C7 lag 계산을 `trading_day_lag.benchmark_lag_trading_days` 로 이동(동작 불변) | PROGRAM_TRUTH §13-4 · §6.1 · §8 |

---

## 2. 배포 확인 (설계자 STEP 1 · 2026-09-29 20:4x · OCI 읽기 전용)

| # | 항목 | 결과 |
|---|---|---|
| 1 | OCI HEAD | `eff609a0` |
| 2 | 추적 파일 변경 | 0 |
| 3 | 배포본 계약 | `sector_signal_state.py` 에 `DELIVERED_STATE_KEY` · `_pin_legacy_delivered` · `_apply_observation` · `holdings_risk_flow.py` 대입 위치 · except 되돌림 · 러너 646줄 |
| 4 | cron · flag | cron 12줄(08:00 시장 · 보유 3 · 07:20 배치 · 장중 7) · `PUSH_AUTOSEND_*` = 전체 · 시장 · 보유 · 장중 true · 폐지된 spike false — `docs/STATE_LATEST.md` 배포 · 운영 상태 표(2026-09-21~22 실측 · 러너 11건 + 배치 1건 · spike false)와 같음 |
| 5 | KOSPI 상태 계약 | OCI 는 API 서버를 돌리지 않는다(`pydantic` 없음) — 07:20 배치 저장 코드가 공용 lag 함수를 쓰는 것 확인(09-29 기준 lag 5). PC `GET /market/topn/latest` = `stale` · `2026-09-17` · 5거래일 지연 · 오늘 거래일 |

2026-09-29 장중 4건 발송은 pull **전** 옛 코드였다 — 상태 파일에 `last_delivered_state` 0건(정상). 다음 날 첫 틱은
`date_reset` 으로 새로 시작한다.

---

## 3. 남은 관측 — 첫 자연 발송 (설계자 STEP 3)

**수동 발송 금지.** 조건형 신호가 없어 발송이 없으면 실패가 아니다 — 첫 자연 성공 발송 때까지 관측만 미결로 남기고 OPS-03 을 막지 않는다.

장중 틱(09:30~15:20) 뒤 OCI 를 읽기 전용으로 본다. 가격 · 등락률은 출력하지 않는다.

```bash
ssh oci-krx 'bash -s' <<'EOF'
cd /home/ubuntu/krx_hyungsoo
python3 - <<"PY"
import json
b=json.load(open("state/three_push/sector_signal_state_latest.json",encoding="utf-8"))
e=b.get("entries") or {}
print("date",b.get("date_kst"),"sent_today",b.get("sent_today"),"entries",len(e))
for t,v in sorted(e.items()):
    print(t,"state",v.get("state"),"cont",v.get("continuous"),"delivered",v.get("last_delivered_state"),"sent_at",(v.get("last_sent_at") or "")[11:16])
PY
python3 - <<"PY"
import json
for ln in open("state/three_push/oci_runtime_history.jsonl",encoding="utf-8"):
    r=json.loads(ln)
    if r.get("push_kind")=="holdings_risk_alert" and (r.get("runtime_kst") or "")[:10]=="<오늘 YYYY-MM-DD>":
        print(r.get("runtime_kst")[:16],r.get("status"),r.get("reason"),r.get("partial_delivery"),r.get("intraday_skip_reason"),r.get("intraday_error"))
PY
EOF
```

판정 기준(설계자 STEP 3):

1. `last_delivered_state` 는 **실제로 전달된 신호에만** 있다(`last_sent_at` 시각 = 전체 전송 성공 틱).
2. 잘림 · 전송 실패 · 부분 전송 틱의 신호는 `last_delivered_state` · `last_sent_at` 이 전진하지 않았다(관측 `state` 만 바뀜).
3. `sent_today` = 그날 `status=sent` 이고 `partial_delivery` 가 아닌 장중 통합 본문 틱 수.
4. 옛 형식 파일과 호환 — 첫 틱은 `date_reset` 으로 새 파일이라 구파일 전환은 장중 배포 때만 생긴다(이번 pull 은 장 마감 뒤).

결과는 이 문서의 `RUNTIME_FIELD_OBSERVED` 와 `docs/STATE_LATEST.md` 에 적는다(`OBSERVED` · 날짜 · 틱).

---

## 4. 다음 단계 `POC3-02D-OPS-03` (URGENT · 설계자 2026-09-29)

설계서 `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md` ·
PLAN `docs/ai_plan/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_PLAN_V1.md`(사실조사 포함 · 설계자 판정 `PASS_WITH_MANDATORY_AMENDMENTS` 2026-09-29 · KRX KOSPI 조회 사용자 승인 · 구현 착수).
사용자 결정(2026-09-29): 시장 흐름 브리핑 08:00 → 08:30 · KRX 수집 08:10~ — KRX 는 전일 자료를 익영업일 08:00 에 공개한다(공식 FAQ).
`POC5-01A = BLOCKED_BY_OPS-03`(OPS-03 `IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED` 뒤).

확정 계약 요지(정본 = PLAN 맨 위 '확정 계약' 표): 07:20 배치 폐지 → 전체 배치 08:10(단계별 실패 격리 · FDR timeout) · KRX 재시도
08:15 · 08:20 · 08:24 · 마감 08:27 · 시장 흐름 브리핑 08:30 · 09:20 KRX 전용 보강 1회 · 국내 정상 = `actual_basis_date ==
expected_previous_trading_day`(없으면 구역 생략 · 한 줄 고지 · 재발송 없음) · 신규 진입은 `추세 기준 YYYY-MM-DD 종가` 줄 · 5일 · 20일은
거래일 날짜 기준 · KOSPI 는 KRX 공식 종가 · C7 `lag ≤ 1` 폐기 · 09-17 정정 절차 · 모든 KOSPI 화면(차트 포함) 같은 판정 · S&P500 =
가장 최근 완료 미국 세션(NYSE 공식 휴장 CSV) · 캘린더 readiness · 실패 고지 하루 최대 1회.

2026-09-29 까지의 실측(읽기 전용 · PLAN 에 옮긴다):

- OCI 07:20 배치 47회(거래일 44 · 휴장일 3): FDR `etf_daily_price` 는 거래일 44회 모두 **T-1**, KRX `etf_bydd_trd` 는 수집 시작(09-14) 뒤 **거래일 10회 모두 T-2** — KRX 공식 FAQ '모든 API 데이터는 익일 영업일 오전 8시에 업데이트 · 8시 전 호출은 조회되지 않음' 때문이다(07:20 은 늘 8시 전).
- KRX 조회 7회(2026-09-29 20:46 · PC 키): 당일(09-29) ETF 0행 · 전일(09-28) 1,171행 · `idx/kospi_dd_trd` 로 공식 KOSPI 수신(09-28 종가 6,889.74) · 당일 지수 0행.
- KOSPI 같은 날짜 대조: 09-15 · 09-16 은 저장값 = KRX 공식 종가, **09-17 저장값 6,724.34 ≠ 공식 6,715.41**(캐시가 장중에 멈춘 값으로 보임).
- T-1 최초 가용 시각: KRX 공식 FAQ '익영업일 08:00' 로 확인 — 맥북 예약 조회는 중지했다(호출 0). 08:00~08:30 사이 실제 완료 시각은 OPS-03 배포 뒤 시도별 기록으로 쌓는다.

---

## 5. 운영하면서 알아야 할 것

- **장중 알림이 조금 늘 수 있다** — 전달 못 한 상태 변화가 다음 틱에 다시 나가 일일 상한(4)에 더 일찍 닿을 수 있다(상한 불변).
- **회복 → 미전달 Y → cooldown 이내 X 재진입은 보내지 않는다** — 마지막 전달 X 와 같기 때문(설계자 승인). cooldown 뒤에는 보낸다.
- **KOSPI 표시**: 「오늘의 투자 점검」 · 「요즘 잘 오르는 ETF」 에 `기준일 지연` · N거래일 지연(거래일이 지날 때마다 1씩 는다). 코스피 **차트**에는 아직 지연 표시가 없다 — OPS-03 에서 모든 KOSPI 화면에 같은 판정을 붙인다.
- **08:00 국내 기준일은 매일 T-2** 로 나간다(날짜는 '국내 YYYY-MM-DD 종가'로 표시) — OPS-03 전까지 그대로다.

---

## 6. 이 단계에서 배운 것 (반복하지 말 것)

- **상태 표기는 같은 뜻의 문장을 전부 찾아 한 번에 바꾼다** — r1 REJECTED 는 머리 한 줄만 `PASSED` 로 바꾸고 본문 4곳의 '확인 대상 · 확인되면' 을 남긴 자기모순이었다. 바꾸기 전에 '대기 · 대상 · 확인되면 · PENDING · HOLD' 를 전수 검색한다.
- **데이터가 멈추거나 늦으면 '알려진 한계' 로 넘기지 않는다** — KOSPI 정지를 09-26 에 알고도 한계로만 적어, 사용자가 화면에서 먼저 발견했다. 값별 나이(T-n)를 실측해 바로 올린다.
- **적대 리뷰는 설계 빈칸을 찾는다** — 구파일 전환 · 회복 뒤 재진입 두 결함은 구현 뒤 리뷰가 run() 실측으로 잡았다. 계약 문장마다 반대 경우를 만들어 본다.

---

## 7. 문서

| 문서 | 상태 |
|---|---|
| 설계서 · PLAN · 결과서(OPS-02) | 커밋 `eff609a0` · 이 인계와 함께 상태 갱신 |
| `docs/STATE_LATEST.md` | OPS-02 `IMPLEMENTED_VERIFIED_DEPLOYED` · 운영 상태 `OPERATING_DEGRADED` · 다음 = OPS-03 |
| `docs/PROGRAM_TRUTH.md` | OPS-02 OCI 반영 · KOSPI 09-17 값 불일치 · `SOURCE_SWITCH` 해제(OPS-03) |
| OPS-03 설계서 · PLAN | 설계자 원문 · PLAN 판정(`PASS_WITH_MANDATORY_AMENDMENTS` 2026-09-29) 기록 · PLAN `CONFIRMED` · 구현 착수 |

---

## 8. 사용자 확인

- **(선택 · OPS-01 C3)** 「장중 급등락」 Telegram '기준' 다음 줄이 `현재가 YYYY-MM-DD HH:MM` 인지 — 미회신. 검증 · 다음 단계를 막지 않는다.
