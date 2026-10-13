# POC5-09 · POC5-10 인계 — 저장 거래량 확인 근거 · PC 가격 기준일 정정 · 보유 개별주 가격 수집 (2026-10-13)

- **작성**: 개발자(VSCode Claude)
- **독자**: 다음 세션 개발자 — 설계자의 「오늘의 투자 점검」 정보량 판단 → 다음 설계 대응 · 10-23 공식 R0
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-09_STORED_VOLUME_EVIDENCE_DESIGN_V1.md`
    - §9 PLAN 판정 CONDITIONAL_PASS · §10 검증 요청 보충 · POC5-10 판정 · 끝에 전달문 원문
    - POC5-10 은 별도 설계서 없이 이 설계서 §9-6 · §10-4 · §10-5 가 근거다.
  - PLAN
    - `docs/ai_plan/POC5/POC5-09_STORED_VOLUME_EVIDENCE_PLAN_V1.md`(§7 보충 · §8)
    - `docs/ai_plan/POC5/POC5-10_PC_HOLDINGS_EQUITY_PRICE_REFRESH_PLAN_V1.md`(§6 판정 반영 · §7 구현 메모)
  - 결과서
    - `docs/ai_result/POC5/POC5-09_STORED_VOLUME_EVIDENCE_RESULT.md`(§6-3 검증자 r1 정정 · §7 실화면 · §10 종료)
    - `docs/ai_result/POC5/POC5-10_PC_HOLDINGS_EQUITY_PRICE_REFRESH_RESULT.md`(§6-3 검증자 r1 정정 · §7 실제 수집 · §10 종료)
  - 설계자용 메모(미처리) `docs/ai_result/POC5/POC5_TODAY_SCREEN_DENSITY_NOTE_2026-10-13.md`
  - 직전 인계 `docs/handoff/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_HANDOFF_2026-10-12.md` · 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md`

```text
POC5-09  IMPLEMENTED_VERIFIED_CLOSED (2026-10-13)
         검증자 r1 REJECTED(이력 부족 + 기준일 불일치 겹침 → 날짜 사유 누락) → 정정 → r2 VERIFIED(위험 NONE)
         실화면 통과 → 커밋 7f394deb push
POC5-10  IMPLEMENTED_VERIFIED_CLOSED (2026-10-13)
         검증자 r1 REJECTED('마지막 전체 갱신' 보존이 순서 의존) → 정정 → r2 VERIFIED(위험 NONE)
         사용자 갱신 1회(실제 수집 · 3종목 08-12 → 10-13) · 실화면 확인 → 종료 커밋 push(번호 = git log)
         DEF-PRICE-EQUITY-REFRESH 수집 원인 해소
PC 반영  next dev · uvicorn --reload 자동 다시 읽기(재기동 없음) · OCI pull 없음(둘 다 PC 전용)
다음     설계자 — 「오늘의 투자 점검」 정보량 판단(사용자 의견 · 메모 전달은 사용자)
남은 운영 10-23(금) 배치 완료 뒤 공식 R0 1회(POC5-04 인계 §2)
```

---

## 1. 바뀐 것

### 1-1. POC5-09 — PC 가격 흐름 기준일 정정 (`app/pc_price_basis.py`)

- `GET /holdings/market-evidence/latest`(「확인 근거」 · 「오늘의 투자 점검」)는 공유 builder 결과의 **사본**을 정정해 돌려준다. 공유 builder(`build_holdings_market_evidence`) · PUSH · 초안 · 원장 경로는 그대로다.
- PC 비교 기준일 = KODEX200(069500) 최신 저장 가격 날짜(응답 `price_basis.reference_date`).
- 종목 · KODEX200 최근 21행을 한 번 읽어 **날짜와 값을 같은 읽기에서** 만든다(`fetch_recent_price_rows` · 산식은 builder 와 같은 `_window_return_pct`).
- 판정 순서 = **기준일 → 이력 길이 → 비교 기간**(상태표는 `_normalize_item` 설명).
  - 기준일이 다르면 이력이 짧아도 `date_mismatch`(5 · 10 · 20일 변화 · KODEX200 대비 비움 · `unavailable`).
  - 기준일은 같고 비교 기간 시작만 다르면 그 KODEX200 대비만 비우고 status 는 `ok`(최대 3개 후보에 남음).
- 최대 3개 · 자료 확인 필요 건수는 정정된 사본으로 `summarize_holdings` 를 다시 불러 만든다.
- 화면
  - 「확인 근거」: 목록 위 가격 흐름 기준 줄 · 기준일이 다른 행의 세 칸 '—' · 상세 맨 위 날짜 사유 · '가격 흐름 기준' 줄.
  - 「오늘의 투자 점검」: 최대 3개 설명 줄의 'PC 저장 가격 기준일' · (있을 때만) 뺀 보유 줄 · 비중 · 손익은 종목 합산(`holdings_compare/helpers.ts :: aggregateHoldingsByTicker`).

### 1-2. POC5-09 — 저장 거래량 (`app/stored_volume_evidence.py` · `frontend/app/components/StoredVolumeBlock.tsx`)

- D = 최신 저장 가격 행. 평균 = 직전 20개 저장일(D 제외 · 20개 모두 유효할 때만 · 0 은 유효 · 음수 · NaN · inf 는 무효). 단위 주. 출처 = D 행의 source.
- 배수 사유 순서 = 거래량 없음 → 평균 자료 부족 → 평균 0.
- 위치: 「확인 근거」 종목 상세 4칸 · 「오늘의 투자 점검」 KOSPI 카드 'KODEX200 거래량' 2 × 2(`kodex200_stored_volume`).
- 두 안내 카드('코스피 상세 지표' · '개발 중인 판단 기능') 문구를 판정 §9-3 대로 고쳤다(KOSPI 지수 거래량 = 미저장 · KODEX200 거래량 = ETF 한 종목 값).

### 1-3. POC5-10 — PC 갱신에 보유 개별주 가격 단계 (`app/holdings_equity_refresh.py`)

- PC '최신 시장 데이터 갱신'(`app/market_refresh_service.py`)이 ETF 가격 단계 뒤 · KOSPI 단계 앞에서 한 단계를 더 돈다.
- 대상 = 현재 보유 − `etf_master`(지금 삼성전자 · SK하이닉스 · 삼성SDI). 마지막 저장일부터 갱신 끝 날짜까지 증분으로 받는다.
- 수집은 OCI 와 같은 `refresh_approved_prices` 를 쓰되, **종목별 기록 행을 남기지 않는 수집 함수**를 넘긴다. 기록은 요약 행 1개 `holdings-equity-prices-<refresh_id>`(source `FinanceDataReader/holdings-equity-prices`)뿐이다.
- '마지막 전체 갱신' 조회(`market_topn_helpers._latest_refresh_payload`)는 `latest_refresh_log(exclude_source=HOLDINGS_EQUITY_PRICE_LOG_SOURCE)` 로 이 행을 뺀다. 보존은 **순서가 아니라 조회의 행 구분**이다.
- 성공 · 실패는 종목마다 직접 센다(공유 함수의 이중 집계는 다른 종목 성공까지 깎을 수 있어 쓰지 않음 · 공유 함수 본문 변경 0).
- 보유 파일 없음 = 읽기 실패 · 유효한 빈 보유(파일 있음 · 0행) = 대상 없음(정상).
- 실패는 한국어 `error_summary`('보유 개별주 가격 갱신 일부 실패(N종목)' 등)로 기존 사유 뒤에 붙는다. 「요즘 잘 오르는 ETF」 갱신 완료 줄은 사유가 있으면 '갱신 완료. 확인 필요: …'로 보인다(사용자 결정).

## 2. 지금 실데이터 (2026-10-13 · 사용자 갱신 1회 뒤 · 개발자 읽기 전용 확인)

- 3종목 최신 저장일 2026-08-12 → 2026-10-13(각 39행 · KODEX 200 과 같은 날짜 수).
- 요약 행 = 시도 3 · 성공 3 · 실패 0. 종목별 부수 행 0. 가장 최근 행 = KOSPI 단계 행.
- `reference_date` = 2026-10-13 · `date_mismatch` = [] · 32항목 모두 `ok` · 자료 확인 필요 0.
- 그래서 지금 실화면에서는 기준일이 다른 행의 '—' · 뺀 보유 줄을 볼 수 없다. 그 표시는 시험으로만 확인된다.

## 3. 보류 · 후속 (이번 종료 범위 밖)

1. **「오늘의 투자 점검」 정보량 = 설계자 다음 차례.** 사용자 의견(2026-10-13): 대문에 값이 너무 많아졌다 · 글로 된 설계에서는 실제 화면을 놓쳤다. 메모 `docs/ai_result/POC5/POC5_TODAY_SCREEN_DENSITY_NOTE_2026-10-13.md`(현재 구성 · 값 개수 실측 · 절차 제안 = 화면이 바뀌는 설계는 PLAN 판정 전 전체 화면 목업). **결정 전에는 화면을 임의로 줄이거나 옮기지 않는다.**
2. KOSPI 지수 거래량 · 종합 위험 구간 분류 = 미완료(09 는 ETF · KODEX200 저장 거래량 관찰 근거만).
3. **seed 정합** = 사용자 결정 대기(PC seed 3개 ↔ OCI 승인본 20개 · 차이표 = UI-02 PLAN 부록).
4. PC FDR 수동 갱신 보호 = 조건부 후속(멈춤 관측 0). 이번 실제 갱신은 211.6초였다.
5. 갱신 완료 줄의 기존 영문 사유('price_partial_failure: fail=N' 등)는 번역하지 않았다(10 결과서 §4-5 · §5-3).
6. 「요즘 잘 오르는 ETF」 보유 비교(`HoldingsCompareView`)도 같은 응답을 쓰지만 날짜 사유는 보이지 않는다(09 결과서 §5-4 · 판정 범위 = 「확인 근거」).

## 4. 다음 개발자 주의 (이번 단계 교훈)

1. **화면 개발 서버의 낡은 결과물.** 09 화면 변이 확인 뒤 백업 파일 이동으로 복원해 수정 시각이 예전 값으로 돌아갔고, `next dev` 가 다시 컴파일하지 않았다. 사용자 실화면 일부가 변이 상태 위에서 이뤄졌다(10 결과서 §7). 변이 복원은 '원본 내용 쓰기 + `os.utime`'으로 하고, 실화면 전에 `.next/static/chunks/app/page.js` 에 변이 문구가 없는지 확인한다. backend 도 같은 크기 변이는 `.pyc` 가 남는다(`PYTHONDONTWRITEBYTECODE=1`).
2. **판정 순서를 상태 조합 표로 시험한다.** 09 r1 은 '이력 부족'을 먼저 봐서 기준일 불일치 사유가 사라졌다. 사유가 여럿 겹칠 수 있으면 조합 표를 만들어 모두 시험한다(`tests/test_pc_price_basis.py` 상태 조합).
3. **'순서상 맞다'는 보존이 아니다.** 10 r1 은 '마지막 전체 갱신'이 KOSPI 행이 뒤에 쓰인다는 순서에 기대고 있었다. 조회가 행을 구분하게 고쳤고, 재사용 공유 함수가 남기는 부수 기록(종목별 행)도 직접 확인했다.
4. **값과 날짜는 같은 읽기에서.** 앞서 계산된 값에 나중에 읽은 날짜를 붙이면 경쟁 상태에서 옛 값이 새 날짜로 'ok'가 된다(설계 §10-2-1).
5. **화면 값이 늘어나는 설계는 대문 전체 모습을 먼저 보인다.** 09 목업은 거래량 칸(부분)만 보였고, 사용자는 실화면에서야 대문 정보량을 알았다(메모 §3 · 절차 제안은 설계자 판단 대상).
6. `git add -A docs/` 금지 — 사용자 소유 untracked `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`.

## 5. 다음 단계

- **사용자**: 설계자용 메모를 설계자에게 전달.
- **설계자**: 「오늘의 투자 점검」 대문 역할 · 정보량 판단 → 설계서가 오면 PLAN 먼저(`docs/ai_plan/POC5/`) · 화면이 바뀌면 PLAN 단계에서 전체 화면 실제 폭 목업.
- **10-23(금) 배치 완료 뒤**: 공식 R0 1회(POC5-04 인계 §2 · 별도 운영 점검).
- **사용자 결정 대기**: seed 정합(위 §3-3).
