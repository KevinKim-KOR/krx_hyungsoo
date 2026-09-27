# POC3-02D-OPS-01 인계 — PRIMARY 전 운영 정정 C1~C7 (검증 완료 · OCI 적용 대기)

> **인계 시점 (2026-09-27 · 설계자 RESULT `PASS_TO_VERIFIER` · 검증자 `VERIFIED`).** 구현과 검증은 끝났다. **OCI 적용(STEP 7)과
> 연휴 뒤 첫 거래일 확인은 남아 있다.** 정본 증거는 결과서와 설계서 끝의 설계자 판정 원문이다. 이 문서는 다음 사람이 바로
> 이어받는 데 필요한 것만 추린다.

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(STEP 7 · `POC3-02D-OPS-02` 진입)
- **입력**
  - 설계서 `docs/ai_design/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md` — PLAN 판정 · 최종 R2 · RESULT 판정 원문
  - PLAN `docs/ai_plan/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md`
  - 결과서 `docs/ai_result/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md`
  - 검증자 `VERIFIED`(2026-09-27 · 읽기 전용 정적 검증 · C1~C7 한정 · OCI 적용 · PRIMARY 승인 아님)

```text
POC3-02D-OPS-01  VERIFIED — C1~C7 구현 · 검증 완료 · OCI 미반영
                 설계자 RESULT PASS_TO_VERIFIER · 검증자 VERIFIED (2026-09-27)
커밋             4dd7e526 (기능 · 37개 파일) + 이 인계 문서 커밋 — 둘 다 origin/main push (2026-09-27)
남은 것          OCI pull 완료(2026-09-27 17:13) · 캘린더 정정 재 pull(09-28 07:15 전) → 2026-09-28 07:20 · 08:00 확인 → STATE_LATEST 2차 갱신
다음 단계         POC3-02D-OPS-02 (설계자 결정 · PRIMARY 전) → POC5-01A
PRIMARY          NOT_STARTED — 이 단계 pull + OPS-02 완료 + POC5-01 코드 pull 뒤 첫 KRX 거래일
러너 · 스키마 · 신규 의존성 · 외부 API 변경 = 0 · SOURCE_SWITCH(KOSPI) = PROHIBITED
```

---

## 1. 이 단계가 바꾼 것 (계약 정본은 `docs/PROGRAM_TRUTH.md`)

| 정정 | 사실 성격 | 바뀐 것 | 정본 위치 |
|---|---|---|---|
| C1 | 실제 발생 | 08:00 기초지수 구역: 공식 CSV 공용 resolver(07:20 · 08:00 공유 · 최신 유효 `krx_etf_basic_YYYYMMDD.csv`) · d20 종가 없는 신규 ETF 는 차단 대신 pending · `refresh_due` · 판정 창 검사(`META_GATE_STALE`) · 08:00 갱신 안내 1줄 · 새 CSV `20260927` | PROGRAM_TRUTH 프로세스 **C-3** |
| C2 | 발생 추정 | 「OCI 운영 상태」 필수 판정 = `market_briefing` · `holdings_briefing` · `holdings_risk_alert` | PROGRAM_TRUTH §5.2 · §9-D |
| C3 | 실제 발생 | 「장중 급등락」 '기준' 다음 줄 `현재가 YYYY-MM-DD HH:MM`(러너 실행 시각) | PROGRAM_TRUTH 「장중 급등락」 절 |
| C4 | 잠재 | 구역 상한에 잘린 보유 급락을 발송 완료로 저장하지 않음(본문 기준 재계산) | 같은 절 |
| C5 | 잠재 | 전송 실패 · 조립 뒤 실패 회차 = `send_failed` · 15:40 줄 `· 발송 실패 N회` | 같은 절 |
| C6 | 실제 발생 | `holdings_risk_alert` 의 `message_text_length` = 조립 본문 길이 | 같은 절 |
| C7 | 실제 발생 | KOSPI 적재 stale → `failed` + `source_stale:as_of=…,ref=…,lag=N` · 공용 `app/trading_day_lag.py` | PROGRAM_TRUTH §8 |

새 파일: `app/market_briefing/official_csv.py` · `app/trading_day_lag.py` · `scripts/check_krx_etf_basic_csv.py`(PC 전용) ·
`state/market_meta/krx_etf_basic_20260927.csv` · `tests/test_poc3_02d_ops01_holdings_risk_flow.py`.

---

## 2. STEP 7 — OCI 적용 절차 (바로 할 일)

OCI 는 **읽기 전용**으로만 접속한다(`ssh oci-krx "<읽기 명령>"` · 명령별 승인). 쓰기 · 발송 · 재시작은 하지 않는다. pull 은 사용자가 한다.

1. **pull 직전 대조(개발자)** — OCI 정합성 JSON 의 API 전용 목록이 새 CSV 에 모두 있는지 본다.

   ```bash
   ssh oci-krx "cd ~/krx_hyungsoo && python3 -c \"import json;d=json.load(open('state/three_push/market_briefing_meta_consistency_latest.json'));print(d.get('status'),d.get('api_basis_date'),d.get('api_only_count'));print(sorted(d.get('api_only') or []))\""
   ```

   PC 에서 `app.market_briefing.official_csv.resolve_official_csv(Path('state/market_meta'))` 로 고른 파일의 단축코드와 대조한다.
   d20 종가가 있는데 새 CSV 에 없는 ticker 가 있으면 **pull 하지 않고 멈춰 보고**한다(CSV 재수령은 설계자 · 사용자 판정).
   2026-09-27 읽기: `CSV_REFRESH_REQUIRED` · 기준일 `20260922` · 8종 → 새 CSV 에 모두 있음(누락 0).
2. **pull 시간(사용자)** — **거래일 15:40 뒤 ~ 다음 거래일 07:15 전에만**, 그 사이에도 07:15~08:05 는 피한다(PLAN STEP 7 · C4 ·
   Q4). 다음 거래일은 **2026-09-28(월)**이다(설계자 정정 2026-09-27). 저장소 캘린더가 09-28 을 '추석 대체공휴일'로
   잘못 빼고 있었다 — 설 · 추석 대체공휴일은 일요일과 겹칠 때만 생긴다(2026 은 토요일 9/26). 캘린더 정정은 별도 커밋이므로
   09-28 07:15 전에 한 번 더 pull 해야 그날 08:00 시장 브리핑이 휴장일로 건너뛰지 않는다.
3. **pull 확인(개발자)** — `git log --oneline -1` 이 `origin/main` 과 같은지, `sha256sum state/market_meta/krx_etf_basic_20260927.csv`
   가 `0f0c0742…22314` 인지.
4. **PC 백엔드 재기동(사용자)** — C2 는 PC 가 기동할 때 OCI crontab 을 읽으므로 재기동해야 「OCI 운영 상태」가 OPERATING 이 된다.
   PC 수동 갱신(`POST /market/refresh`)의 KOSPI 기록(C7)도 재기동 뒤부터 바뀐다.

---

## 3. 2026-09-28(첫 거래일) 운영 확인

**개발자 OCI 읽기** — 값 · 날짜 · 건수 · ticker 식별자만 본다. 본문 전문 · 가격 · 과거 수익률은 출력하지 않는다.

| 시각 | 볼 것 | 기대(추정 · 확인 대상) |
|---|---|---|
| 07:20 | `logs/oci_market_data_batch.log` 의 `공식 CSV 갱신 판정: refresh_due=… csv=…` · `benchmark 갱신: kospi=…` 줄 | `csv=krx_etf_basic_20260927.csv` · `refresh_due=False` · KOSPI 는 upstream 이 멈춰 있으면 `kospi=failed(as_of=2026-09-17)` |
| 07:20 | 정합성 JSON: `status` · `csv_name` · `csv_sha256` · `api_only_count` · `api_only_pending` · `name_mismatch_count` · `evaluated_api_basis_date` · `evaluated_window_d20_date` · `evaluated_at_kst` · `refresh_due` | `status=ok` · 판정 창 3필드가 채워짐 · 09-22 뒤 상장분이 있으면 pending 으로만 남음 |
| 08:00 | `state/three_push/oci_runtime_history.jsonl` 의 `market_briefing` 행: `status` · `index_status` · `index_candidates` · `message_text_length` | `index_status` 가 `CSV_REFRESH_REQUIRED` 가 아님(`ok` · `no_candidate_normal` · 최신성 `stale` 중 하나) |
| 09:30~ | 같은 파일의 `holdings_risk_alert` 행: `status` · `message_text_length` · `intraday_tally_outcome` | 발송 행의 길이가 0 이 아님 · 전송 실패가 있으면 `send_failed` |

**사용자 실화면** — 08:00 브리핑에 '오늘 볼 기초지수' 가 돌아왔는지(후보가 있을 때) · 「장중 급등락」 '기준' 다음 줄에 시각이
찍히는지(`현재가 2026-09-28 HH:MM · 직전 종가 …`) · PC 「OCI 운영 상태」가 OPERATING 인지.

확인이 끝나면 `docs/STATE_LATEST.md` 를 2차 갱신하고(PLAN §9) 이 단계를 닫는다. 예상과 다르면 원인을 먼저 보고한다.

---

## 4. 다음 단계 `POC3-02D-OPS-02` (설계자 결정 2026-09-27 · PRIMARY 전)

설계자 RESULT 판정이 이 단계에 섞지 않고 다음 번호 단계로 분리했다. 흐름은 그대로 설계서 → 개발 PLAN(모호점 질문) → 설계자
확정 → 구현 → 결과서 → 검증이다.

1. **첫 화면 OCI 링크** — 「오늘의 투자 점검」 OCI 한 줄의 '진단·상태에서 상세 보기 →' 가 「개발·실험용」(`diagnostics`)으로
   간다(`frontend/app/components/today/OciStatusOneLine.tsx:58`). 상세는 「OCI 운영 상태」(`oci_status`)에 있다.
2. **사업군 · 급등 상태 저장 결함 2건**(결과서 §8 · tmp 재현만 함) — 운영 정확성 결함이라 PRIMARY 전에 끝낸다.
   - 이미 발송된 사업군 · 보유 급등 신호가 다른 상태로 바뀌었는데 구역 상한 · 전송 실패 · 부분 전송으로 전달되지 못하면 그 뒤로
     억제된다.
   - 장중 조립 중간(`out.intraday` 대입 뒤) 예외로 구 본문만 나가도 사업군 · 급등 신호가 발송 완료로 기록된다.
   - 재현 스크립트는 세션 임시 폴더에 있었고 저장소에 없다. 결과서 §8 의 틱 표(경우 · 주입 위치 · 기대 결과)로 다시 만든다.
     C4 의 방식(본문에 실린 것만 발송으로 기록 · 재계산은 `out.intraday` 대입 전)이 참고가 된다.
3. **낡은 역검증 ⑦ · 목업 ⑦ 제목** — `scripts/ops02b2/reverse_verify_guards.py` ⑦ 'fingerprint 반복 억제'는 2026-09-18 부터
   실패한다(내용이 같아도 발송으로 계약이 바뀜 · 기준 코드에서도 같은 출력). `scripts/build_market_briefing_mockups.py` ⑦ 제목
   '동일 fingerprint (미발송)' 도 결과('발송 = 예')와 어긋난다. 현 계약 검증으로 쓰지 않도록 정리한다.
4. **후보**: KOSPI stale 화면 문구(Q19 · 2026-09-26 PLAN 판정) — 「오늘의 투자 점검」은 stale 을 구분하지 않고, 「요즘 잘 오르는
   ETF」는 'N/A — KOSPI 시계열이 수집되지 않았습니다.' 와 영문 stale 경고를 함께 보인다. 포함 여부는 OPS-02 PLAN 때 판정.

---

## 5. 운영하면서 알아야 할 것

- **CSV 갱신 안내가 오면**: 08:00 본문 끝 `※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요.` → 사용자가 KRX Data
  Marketplace `증권상품 > ETF > 전종목 기본정보` 에서 CSV 를 받아 전달(Excel 재저장 금지) → 개발자가 byte 그대로
  `state/market_meta/krx_etf_basic_YYYYMMDD.csv`(다운로드 · 스냅샷 날짜 — 거래 기준일 아님)로 추가 →
  `python scripts/check_krx_etf_basic_csv.py --meta-dir state/market_meta` exit 0 확인 → 커밋 · push · pull(각각 승인). 코드 변경은 없다.
  이 CSV 는 가격 파일이 아니라 공식 메타정보 검증 스냅샷이다(가격은 07:20 API 가 자동 수집).
- **KOSPI**: upstream `FinanceData/fdr_krx_data_cache` KS11 `2026.csv` 가 09-17 에서 멈췄다. source 교체 금지. 재개되면 180일
  lookback 으로 자동 채움. 계속 멈추면 source 교체를 별도 설계로 판단한다.
- **알려진 한계**(결과서 §5 · 비차단): 2027 캘린더 파일이 없으면 2027 년 평일 휴장 다음 배치마다 KOSPI 가 lag 2 로 `failed`
  (첫 사례 2027-01-04) · 07:20 ~ 08:00 사이 CSV 가 바뀌면 코드 가드 없음(pull 금지 시간으로만 막음) · C2 주석 줄 필터 없음 ·
  C7 upsert 가 NaN 으로 유효 종가를 덮어쓸 수 있음(기존).
- **테스트 환경**: 전체 pytest 약 6분(`run_in_background` · `caffeinate -i` · 덮개 열기). 새 테스트는 라이브 DB 를 열 수 없다
  (`tests/_live_guard.py`). 07:20 · 08:00 관련 테스트는 `state/market_meta` 를 tmp 로 격리한다(`tests/conftest.py`).

---

## 6. 이 단계에서 배운 것 (반복하지 말 것)

1. **렌더 단위 테스트만으로는 배선 결함을 못 잡는다** — C3 `현재가 —` 는 렌더에 값을 직접 넘기는 테스트만 있어, 장중 정책 활성
   (2026-09-21) 뒤 통합 본문 8건 모두에 나갔다. 본문 줄을 바꾸면 `run()` 관통 테스트로 확인한다.
2. **결과서 · PROGRAM_TRUTH 는 쓰고 나서 코드와 한 번 더 대조한다** — 독립 교차 확인이 라운드마다 9~14건(과장 · 조건 누락 ·
   줄 번호 · 문서 간 불일치)을 잡았다. 특히 "모든 정정은 pull 뒤" 처럼 넓게 쓰면 PC 쪽 경로(C2 · C7 PC 갱신)가 빠진다.
3. **코드를 한 줄이라도 고치면 그 파일의 줄 번호 인용을 다시 잰다** — 주석 1줄 추가로 `render.py` 인용 2곳이 밀렸다.
4. **순서 · 시간 계약은 모든 문서에서 같이 바꾼다** — STATE_LATEST 갱신 시점 · pull 허용 시간이 PLAN · 결과서 · STATE 에서 따로
   놀았다. pull 시간은 "07:15~08:05 만 피한다" 가 아니라 "거래일 15:40 뒤 ~ 다음 거래일 07:15 전" 이다.
5. **사용자 원문이 1차 근거다** — CSV 출처 · 다운로드일은 파일명 추정이 아니라 사용자 확인으로 확정했다. 파일명에서 읽은 값은
   끝까지 '확인 대상'으로 남긴다.
6. **RED 는 기준 커밋 사본으로 만든다** — `git archive <기준>` 사본에 새 테스트만 넣어 돌리면 저장소 · git 메타데이터를 건드리지
   않고 결함 재현(47건 실패)을 같은 실행에서 인용할 수 있다.

---

## 7. 문서

```text
설계서 · 설계자 판정   docs/ai_design/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md (§3 PLAN 판정 · # 설계자 최종 판정 R2 · # 설계자 RESULT 판정)
PLAN                 docs/ai_plan/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md
결과서                docs/ai_result/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md (§8 Q8 재현 · §5 한계)
상위 설계            docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md (보완 판정 · C1~C7 분류)
현행 동작             docs/PROGRAM_TRUTH.md (C-3 · 「장중 급등락」 절 · §5.2 · §8 · §9-D)
현재 상태             docs/STATE_LATEST.md (POC3 절 '다음')
직전 챕터             docs/handoff/POC4-03_RF_VS_MOMENTUM_KILL_GATE_HANDOFF_2026-09-26.md
```

## 8. 사용자 확인

- **OCI `git pull`** — 사용자가 한다(§2 시간 규칙). pull 전에 개발자가 대조 결과를 먼저 알린다.
- **PC 백엔드 재기동** — 「OCI 운영 상태」 반영용.
- **2026-09-28 실화면** — §3 의 세 가지.
- **`POC3-02D-OPS-02` 착수** — 설계자 설계서가 오면 시작한다.
