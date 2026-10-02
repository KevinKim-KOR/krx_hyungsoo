# POC3-02D-OPS-03 인계 — 운영 데이터 최신성 · 자료원 복구 (2026-10-02)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(`POC5-01A` 시작 · OPS-03 후속 결정 처리)
- **입력**
  - 설계서 `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md` — 설계자 지시 · PLAN 판정 · RESULT 판정 · 한국 거래일 계약 정정(2026-10-02) · 사용자 종료 결정 원문(문서 끝)
  - PLAN `docs/ai_plan/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_PLAN_V1.md` — 맨 위 '확정 계약' 15항
  - 결과서 `docs/ai_result/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_RESULT.md` — 계약 · 시나리오 · 실측 · 종료 커밋(§11)
  - 지금 실제 동작 정본 `docs/PROGRAM_TRUTH.md`(프로세스 C-1 · C-4 · §8 · §13-4) · 상태 `docs/STATE_LATEST.md`

```text
POC3-02D-OPS-03   IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-02)
                  설계자 PLAN · RESULT PASS_WITH_MANDATORY_AMENDMENTS (2026-09-29 · 09-30)
                  검증자 VERIFIED r3 (2026-10-01 · r1 KRX 기존 날짜 read-back · untracked 표기 / r2 옛 함수 호출처 기록 → 정정)
배포              커밋 7feddf2c push 2026-10-01 · OCI pull + cron 3줄(사용자) · read-back 16:32(13줄)
운영 확인          2026-10-02 첫 거래일 실측 통과 · 사용자 결정으로 10-06 재실측 생략(1인 운영)
운영 상태          OPERATING (OPERATING_DEGRADED 해제 — 국내 T-2 · KOSPI 정지 해소)
다음              POC5-01A 개방(설계자 RESULT STEP 8) — 설계서 대기
종료 커밋          한국 거래일 계약 정정(설계자 2026-10-02) — OCI 미반영 · 다음 pull 때 적용(급하지 않음)
```

---

## 1. OPS-03 이 바꾼 것 (계약 정본은 `docs/PROGRAM_TRUTH.md`)

| 영역 | 바뀐 것 |
|---|---|
| 시간 계약 | 배치 07:20 → **08:10** · KRX 목표일(T-1) 시도 08:10 · 08:15 · 08:20 · 08:24 · 마감 08:27 · 시장 흐름 브리핑 08:00 → **08:30** · 09:20 KRX 전용 보강 1회(`--krx-only`). 원인: KRX OPEN API 는 전일 자료를 익영업일 08:00 에 공개(공식 FAQ) |
| 국내 최신성 | 정상 = 기준일 == 기대 직전 거래일(T-1) — lag 숫자로 보지 않는다 · 5일 · 20일 = 거래일 날짜 · T-1 없으면 08:30 기초지수 구역 생략 + 한 줄 · 장중 「신규 진입 검토」만 생략 · `추세 기준 YYYY-MM-DD 종가` |
| KRX 적재 | 성공 = ① 기준일 ③ 행 수 ≥ 직전 정상 95% ④ 관계식 · 중복 · 0행 ⑤ read-back(종목 · 종가 · 건수 · 다르면 한 트랜잭션 교체 · 어긋나면 날짜 비움) · 성공한 T-1 은 덮지 않음 · 창 빈 날 채우기(같은 날짜 하루 1회 ledger) |
| 대표 ETF | 적재 성공 조건이 아니다 — 장중 「신규 진입 검토」만 활성 대표 27종 T-1 100% 관문 · 상태는 배치 JSON `krx_representatives` |
| 배치 | 단계 격리 · FDR 요청 20초 · 단계 180초 · 배치 실패 고지 하루 1회(08:30 브리핑 안) |
| KOSPI | KRX `idx/kospi_dd_trd` 공식 종가 · 정상 = T-1 정확 일치(C7 `lag ≤ 1` 폐기) · 08:15 · 08:20 · 08:24 재시도(ETF 와 독립) · 09-17 정정 증거 · 화면 제목 `KOSPI (보조)` · `출처: 한국거래소(KRX)` · 카드 기준일 = KOSPI 기준일 · 정비 큐 · 판정 · 문구 `frontend/lib/kospiStatus.ts` |
| S&P500 | 가장 최근 완료 NYSE 세션(NYSE 공식 휴장 CSV 2026 · 2027) · 다음 해 준비 상태는 미국만 |
| 보유 가격 기준 | `ETF_KRX_UNADJUSTED__STOCK_FDR` — ETF 20거래일 전 · 구간 종가 = KRX 무조정 표 · 개별주 3종 파생값은 늘 닫힘(`20거래일 데이터 확인 불가`) · 20거래일 기준일 = 캘린더 |

## 2. 배포 · 첫 거래일 실측 (2026-10-02 · OCI 읽기 전용)

| 시각 | 결과 |
|---|---|
| 08:10 | KRX T-1(10-01) 08:10:31 첫 시도 성공 · 1,171행 · read-back 일치 · 09-30 빈 날 1회 채움 · 대표 27/27 · KOSPI 10-01 · 09-17 정정(6,724.34 → 6,715.41 · 증거 JSON) · 배치 `success` |
| 08:30 | 시장 브리핑 1회 · 기초지수 기준일 10-01 · d5 09-22 · d20 09-01 · S&P500 세션 10-01 정상 · 배치 실패 고지 없음 |
| 09:15 | 보유 브리핑 · ETF 26종 KRX 창 전부 ok · 개별주 3종 닫힘 |
| 09:20 | 보강 `already_loaded` · 목표일 조회 0 |
| 09:30 | 장중 · 추세 기준일 10-01 · 대표 27/27 · 「신규 진입 검토」 정상 |
| — | 오류 · 중복 0 |

발송 본문은 OCI 기록에 길이만 남는다(`message_text_length`) — 본문 줄은 사용자 텔레그램으로 확인한다.

## 3. 종료 커밋 — 한국 거래일 계약 정정 (설계자 2026-10-02 · OCI 다음 pull)

계약(2026-09-11 사용자 확정 · **다시 사용자 결정 항목으로 올리지 않는다**): 주말 · 확인된 공휴일 · 명절 · 5월 1일 · 12월 31일 미운영 · 그 밖의 평일 운영 · 연도 파일은 보조자료 · 없으면 평일 기본 · 연 2~3회 오판 허용 · 한국 다음 연도 캘린더는 필수가 아니다.

- `app/market_briefing/calendar.py :: is_fallback_trading_day` — 연도 파일 없는 해의 평일 기본에서 5월 1일 · 12월 31일 제외.
- `app/trading_day_lag.py` — 창 함수에 `stored` · 연도 파일 없는 해에 저장 자료 없는 T-1 이전 평일은 건너뜀(`unconfirmed_days` 창 닫기 삭제).
- `app/runtime_evidence/holdings_price_basis.py` — KRX 종가를 축 20 + 앞쪽 10거래일 읽는다(건너뛰어 늘어난 기준일 종가).
- `app/us_trading_calendar.py` · `app/oci_startup_status.py` · `OciStatusView.tsx` — 달력 준비 경고는 미국만 · 「OCI 운영·적용」 `거래일 기준`(한국 · 고정 문구 · 늘 정상) · `미국 휴장일 달력` 행.
- **적용**: PC 화면 행은 PC 백엔드에 바로. OCI 쪽(배치 JSON `calendar_readiness` · 평일 기본 규칙)은 **다음 OCI pull** — 거래일 15:40 뒤 사용자에게 `git pull` 을 부탁한다(cron 변경 없음 · 연도 파일 없는 해(2027~)에만 동작 차이).

## 4. 남은 설계자 결정 (배포와 무관 · 결과서 §7-3)

1. 개별주 3종 파생값 복구 — KRX 주식 일별(`sto/stk_bydd_trd` · 기존 키로 조회 가능 확인)을 정식 원천으로 승인 + 저장 방식.
2. 08:30 배치 실패 고지 발동 입력의 FDR 단계 — 가격 기준 개정 뒤 보유 영향이 사실상 없어 과잉 고지 가능.
3. 대표 ETF 커버리지 상태를 「OCI 운영·적용」 화면 행으로 올릴지(지금은 OCI 배치 JSON · 로그에만).
4. ETF 가격 단절(분할 등) 가드.
5. 08:10 일시 오류로 실패한 누락일의 당일 재호출(지금은 '같은 날짜 하루 1회' 그대로).

기술부채: `docs/backlog/BACKLOG.md` §16 — `scripts/ops02c/reverse_verify_guards.py` ④ 미성립(이중 가드 · 이번 배포 무관).

## 5. OCI 읽기 전용 확인 방법

```bash
ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo; python3 - <<"PY"
import json
b=json.load(open("state/market/oci_market_data_batch_state.json",encoding="utf-8"))
for k in ("refresh_date_kst","status","krx_basis_date","krx_target_date","kospi_as_of","stage_status","krx_representatives","krx_backfill","calendar_readiness","kospi_retry"):
    print(k, json.dumps(b.get(k), ensure_ascii=False)[:300])
for a in b.get("krx_attempts") or []: print("krx", a)
s=json.load(open("state/market/oci_krx_reinforcement_state.json",encoding="utf-8"))
print("0920", {k:s.get(k) for k in ("date_kst","status","attempted","krx_stage_mode")})
PY'
```

실행 기록(`state/three_push/oci_runtime_history.jsonl`)에서 볼 필드: 시장 브리핑 `index_status` · `index_diagnostics` · `sp500_*` · `batch_failure_notice` / 보유 브리핑 `holdings_price_basis` / 장중 `intraday_trend_basis` · `intraday_entry_omitted` · `intraday_representatives` · `risk_price_basis`. 가격 · 키 값은 출력하지 않는다.

## 6. 교훈

- **검증은 줄인 방식으로**(사용자 2026-09-30): 파괴 시험은 검토 1회 · 전체 회귀는 마지막 1회 · 검토 관점 중복 금지 — 시간 단축이 최우선.
- **한국 거래일 계약을 다시 묻지 않는다**(설계자 2026-10-02).
- **결과서 주장 = 코드 · 실측**: 호출처 · 상태 표기(untracked/staged)는 전수 grep · 그 자리 실측으로만 적는다(검증자 r1 · r2 반려 원인).
- **기존 저장분이 있다는 이유로 성공 처리하지 않는다**: read-back 은 이번 snapshot 과 내용까지 같아야 한다(검증자 r1).
- 서브에이전트가 멈추면(stall) 재시작 대신 남은 범위를 직접 마무리하는 편이 빨랐다.
