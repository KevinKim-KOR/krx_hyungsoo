# POC3-02D-OPS-04 인계 — 남은 운영 정정 6건 (2026-10-07)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(`POC5-01B` 운영 원장 마무리 · 검증 대응 · 배포)
- **입력**
  - 설계서 `docs/ai_design/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_DESIGN_V1.md` — PLAN 판정 · 2026-10-06 판정 · 사용자 결정 · RESULT 판정 원문(끝)
  - PLAN `docs/ai_plan/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_PLAN_V1.md`
  - 결과서 `docs/ai_result/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_RESULT.md` — 첫 거래일 실측 §10-5 · 한계 §5 · 발송 변화 §7-8
  - 지금 실제 동작 정본 `docs/PROGRAM_TRUTH.md`(프로세스 C-1 보유 가격 기준 · C-4 배치) · 상태 `docs/STATE_LATEST.md`

```text
POC3-02D-OPS-04  IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-07)
                 설계자 PLAN PASS(2026-10-04) · RESULT PASS_TO_DEPLOY(2026-10-06 · 코드 수정 없음 · 한계 2건 수용)
                 검증자 r2 VERIFIED(2026-10-06) ← r1 REJECTED(수동 --krx-only 보강 · RemoteProtocolError · 줄 수)
배포             커밋 a308353c push 2026-10-06 · OCI pull 2026-10-06 21:40(사용자 · fast-forward) · cron · .env 변경 없음
운영 확인         2026-10-07 첫 거래일 통과(아래 §2) · 종료 = 사용자 결정 '지금 종료'(2026-10-07)
다음             POC5-01B 운영 원장(설계자 PLAN 판정으로 로컬 구현 허용 · 로컬 구현 · 개발자 자체 검증 완료 · 문서 반영 뒤 검증자 제출 · OCI 배포 = 설계자 RESULT 뒤)
```

---

## 1. OPS-04 가 바꾼 것

| 항목 | 내용 |
|---|---|
| 1 개별주 공식 종가 | 보유 코스피 개별주 3종(000660 · 005930 · 006400)의 20거래일 하락 · 고점 대비를 KRX `sto/stk_bydd_trd` 공식 종가(새 표 `krx_stock_daily_price_unadjusted`)로 계산한다. 08:10 KRX 단계의 곁 작업(`krx_stock_sync.HoldingsStockTask` · ETF 와 독립 · 시각표 08:10 · 15 · 20 · 24 · 마감 08:27 · 09:20 1칸). 별도 ledger `state/market/krx_stock_backfill_ledger.json` |
| 2 FDR 실패 고지 | 08:30 배치 실패 고지에서 FDR 단계 실패를 뺐다 |
| 3 대표 ETF 행 | 「OCI 운영·적용」 ① `장중 대표 ETF` 행 |
| 4 단절 가드 | 운영 코드 변경 없음(기존 가드 확인 · 개별주 경로 테스트) |
| 5 09:20 보강 | 첫 호출이 일시 오류(timeout · 연결 오류 · `RemoteProtocolError` · 429 · 5xx)였던 창 날짜만 09:20 회차에 1회 더 |
| 6 PARAM 의미 | ② 카드 '전달' 문구 · ① `운영 기준 활성` 행 |

## 2. 첫 거래일 실측 (2026-10-07 · 목표일 10-06 · OCI 읽기 전용 · 09:27 ~ 09:35 KST 수집 + 09:30 `risk_price_basis` · 로그 목록 추가 확인)

| 시각 | 실행 | 결과 |
|---|---|---|
| 08:10 | 시장 데이터 배치 | `success` · ETF 목표일 08:10:23 1,171행 · 개별주 곁 작업 `krx_holdings_stocks` `ok`(목표일 08:10:23 첫 칸 942행 · 보유 3행 · 창 30일 호출 · 31일 채움 · 실패 0 · 08:11:34 끝) |
| — | 개별주 표 | 93행 = 3종 × 31거래일(2026-08-20 ~ 10-06) |
| 08:30 | 시장 브리핑 | sent(전망 UP · 기초지수 ok · S&P500 10-06 fresh) |
| 09:15 | 보유 브리핑 OPEN | **`skipped/no_selection`** — 개별주 3종 KRX 파생값 ok(가드 ±0.003%) · 선정 0(아래 §3) |
| 09:20 | KRX 보강 | `ok` · `already_loaded` · KRX 호출 0(개별주 포함) |
| 09:30 | 장중 위험 | sent · `risk_price_basis` 개별주 3종 KRX ok |

- 로그(오늘 바뀐 3개 · 09:35 까지): Traceback · ERROR 0. 12:30 · 15:40 보유 브리핑과 10:30 이후 장중 틱은 확인 범위 밖이다(같은 개별주 경로가 09:15 · 09:30 에 정상).
- 재시도 칸(08:15 이후) · 09:20 목표일 재시도 · 일시 오류 보강은 오늘 발동하지 않았다 — 운영에서는 아직 한 번도 돌지 않은 경로다(결과서 §5-1).
- 배치 로그 줄이 두 번 찍히는 것은 로거 stderr 와 cron 리다이렉트가 같은 파일로 가기 때문이다(7월부터 · OPS-04 무관 · 줄 수로 셀 때 주의).

## 3. 사용자에게 보이는 변화 — 보유 브리핑 미발송 날이 생긴다

- 10-02 · 10-06 의 보유 브리핑 '선정 3'(세 슬롯 모두 · 실측) 은 하락 종목이 아니라 개별주 3종이 FDR 가격 기준 불일치(`price_basis_mismatch`)로 늘 `데이터 확인 필요` 에 들어간 것이었다(09-28 ~ 10-01 은 선정 1 ~ 2).
- OPS-04 뒤에는 개별주가 정상 평가되므로, 20거래일 수익률(소수 1자리 반올림)이 -5.0% 이하인 종목과 데이터 문제 종목이 모두 0 인 날은 `skipped/no_selection` 이다(PROGRAM_TRUTH C-1 '선정 0건' 행 · 계약대로). 2026-10-07 09:15 가 OPS-04 배포 뒤 첫 사례다(09-28 이후 실행 기록 기준). 종가 기준 최저는 0107F0 -4.56%(10-06 대 09-04)였다.
- 사용자에게 2026-10-07 보고했다. PLAN §7-4 는 '선정이 늘 수 있다' 만 적었으므로, **다음 설계자 차례에 사용자에게 보이는 변화로 전달**한다(라운드 중간 설계자 질문 금지 원칙 · 지금은 기록만).

## 4. OCI 읽기 전용 확인 방법

```bash
# 08:10 개별주 곁 작업 · 09:20 보강
ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo && python3 -c "import json;d=json.load(open(\"state/market/oci_market_data_batch_state.json\"));print(json.dumps(d.get(\"krx_holdings_stocks\"),ensure_ascii=False))"'
ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo && cat state/market/oci_krx_reinforcement_state.json'
# 개별주 표(읽기 전용)
ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo && venv/bin/python -c "import sqlite3;c=sqlite3.connect(\"file:state/market/market_data.sqlite?mode=ro\",uri=True);print(c.execute(\"SELECT date,COUNT(*) FROM krx_stock_daily_price_unadjusted GROUP BY date ORDER BY date DESC LIMIT 5\").fetchall())"'
```

실행 기록은 `state/three_push/oci_runtime_history.jsonl`(보유 `holdings_price_basis` · 장중 `risk_price_basis`)이다. 본문 · 키 값 · 개인값은 출력하지 않는다. 쓰기 · 발송 · 재시작 · pull · cron 변경은 사용자 몫이다.

## 5. 다음 단계 진입 정보

1. **`POC5-01B` 운영 원장** — 설계자 PLAN 판정 `PASS_WITH_MANDATORY_AMENDMENTS`(2026-10-06 · 필수 보정 5). 로컬 구현 · 개발자 자체 검증 완료(전체 회귀 2894 passed 2026-10-07 00:12 ~ 00:19 · 그 뒤 원장 테스트 2파일 보강 → 원장 3파일 62 passed 재확인). 결과서 초안 `docs/ai_result/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_RESULT.md`(01B 파일은 이 인계 문서의 커밋에 들어가지 않는다 · 01B 커밋에서 함께 올린다).
   - 남은 일: 01B 의 PROGRAM_TRUTH(§4 진입점 · DB 경로 · 새 CLI · §7.1 · §9 · 부록 A) · STATE_LATEST 반영 → 01B 파일만 stage → git 상태 실측 → **검증자** → 설계자 RESULT 판정 → 커밋 · push(승인) → OCI pull + `.env` 에 `DECISION_LEDGER_ENABLED=true`(사용자 · 거래일 15:45 이후나 비거래일).
   - PROGRAM_TRUTH 에 남은 `POC5-01A` 배포 전 표현 3곳(§4 'OCI PUSH 정식 runner' 행 "저장소 코드 · OCI 는 pull 뒤" · 보유 브리핑 근거 줄 · 부록 A `_finish` 행 "저장소 코드부터")은 01A 배포(2026-10-04) 뒤 지난 표현이다 — 01B 가 같은 행을 고칠 때 함께 정리한다.
2. **다음 설계자 차례에 전달할 것**: §3 발송 변화 · 결과서 §5-2(08:10 ETF 실패 날 09:20 전 수동 `--krx-only` 가 그날 09:20 보강을 막음 · 설계자 수용 한계) · 재시도 경로 운영 미관측.
3. 휴일 다음 영업일(예: 10-12 월 · 10-09 한글날 뒤)에 개별주 목표일이 08:10 에 공개돼 있는지는 아직 관측하지 않았다(10-05 휴일엔 ETF 만 공개됐다).

## 6. 교훈

- **'선정 수가 줄었다' 는 장애가 아닐 수 있다** — 데이터 문제 그룹이 늘 차 있던 기간과 비교하면 정상 동작도 '미발송' 으로 보인다. 같은 기록의 가격 기준 evidence(`holdings_price_basis.tickers[*].reason`)로 전후를 대조한다.
- **계획 시각표와 실제 시도를 섞지 않는다** — `krx_holdings_stocks.slots` 는 계획이고, 실제 시도는 `target_attempts[].at_kst` 와 로그 `slot=` 이다. 09:20 의 `attempted` 는 ETF 시도만 센다.
- **첫날 확인 범위를 결과서에 적는다** — 오전 확인으로 종료할 때는 확인 시각 범위와 아직 돌지 않은 경로를 함께 남긴다.
