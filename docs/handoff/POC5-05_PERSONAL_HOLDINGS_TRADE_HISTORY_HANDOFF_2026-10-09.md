# POC5-05 인계 — 보유 · 매매 이력 통합 (2026-10-09)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(10-12 POC5-02 · 03 확인 → 10-23 공식 R0 → POC5-06 설계 대응)
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_DESIGN_V1.md` — 개정 2 · §11 PLAN 판정 · §12 RESULT 판정 · 전달문 원문
  - PLAN `docs/ai_plan/POC5/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_PLAN_V1.md`
  - 결과서 `docs/ai_result/POC5/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_RESULT.md` — §6-3 ~ §6-7 검증자 r1 ~ r4 정정 · §10 배포 · 종료 기록
  - 직전 인계 `docs/handoff/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_HANDOFF_2026-10-08.md`(10-23 공식 R0 절차) · 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md` · `docs/backlog/BACKLOG.md` §8

```text
POC5-05   IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED (2026-10-09)
          검증자 r1 ~ r4 REJECTED → r5 VERIFIED(위험 NONE) · 설계자 RESULT PASS_TO_DEPLOY(지시문 외 변경 17 · 한계 12 수용)
          구현 커밋 33b002e4 · OCI pull 10-09 07:32 · 첫 정상 OCI 적용 07:34 · 개발자 읽기 전용 확인 통과
          PC 보유 파일 = 아직 기존 형식(v1 · 32줄) — 첫 저장(매매 · 입력 정정) 때 v2 로 바뀜
남은 운영  10-12(월) 08:10 이후  POC5-02 첫 결과 행 · POC5-03 화면 가격 결과(POC5-01B 인계 §3)
          10-23(금) 배치 완료 뒤  공식 R0 1회(POC5-04 인계 §2)
다음 설계  POC5-06 수동 '재진입 검토' / ML 사후평가(설계자 · 무평가 알림도 사용 · 05 화면에 ML 버튼 없음)
```

---

## 1. 만든 것

- **정본 한 파일**: `state/holdings/holdings_latest.json` v2 = `schema_version 2` · `revision` · `holdings`(계산 결과 + `position_id` · `cycle_id`) · `personal_trade_history`(`positions` · `records`). records 가 정본이고 holdings 는 저장 때마다 다시 계산해 일치를 판정한다(어긋나면 손상 · 빈 보유로 바꾸지 않음).
- **기록 종류**: BASELINE(기존 줄 · 첫 변경 때 · 매수일 미상) · REGISTER(잔고 등록) · BUY · SELL · ADJUSTMENT(입력 정정 · 수량 0 = '입력 정정으로 종료' · 이름만 = 표시값) · VOID. 거래 정정 = 같은 종류 + `supersedes_id`.
- **모듈**: `app/holdings_store.py`(저장 경계 `commit` — Lock · 재시도 우선 · revision · 쓰기 직전 판정 · 원자 교체) · `app/holdings_book.py`(이동평균 · 날짜 · seq 순 · 무결성 `check_document`) · `app/holdings_history.py`(매매 명령 · 입력 검증 · `_check_new_quantity`) · `app/holdings_edit.py`(입력 정정 `PUT /holdings`) · `app/holdings_history_view.py`(History) · `app/holdings_market_flow.py`(시장 흐름 · PC 시세 DB `mode=ro`) · `app/api_holdings.py` · `app/api_holdings_history.py` · `app/holdings.py :: holdings_from_document`(공용 판정 · `load()`) · `app/holdings_oci_apply.py`(허용 5필드 payload · hash · `pending_apply`).
- **OCI 에서 도는 변경 5파일**: `app/holdings.py` · `app/three_push_runtime/target_tickers.py` · `app/runtime_evidence/holdings_selection_flow.py` · `app/runtime_evidence/holdings_risk_flow.py` · `scripts/run_holdings_publication.py` — 정상 빈 보유(보유 브리핑 `skipped/no_holdings` · 위험 알림 = 사업군 대표만).
- **화면 「종목 관리」**: 보유 표(수익률 열) · 줄 클릭 매매 창 · History(보유 기간별 · 정정 · 취소 · 시장 흐름 보기) · 접힌 과거 보유(재매수) · 새 보유(최초 매수 / 잔고 등록) · 입력 정정 모드 · OCI 카드(미적용 주황 · 확인 안 됨 회색 · 적용된 보유와 같음 초록).

## 2. 운영 · 사용 메모

1. 조회 · 기동 · History 열기는 파일에 쓰지 않는다. 첫 저장 때 기존 32줄이 줄마다 BASELINE 으로 확정된다.
2. **백업 = 배포 전 보유 복원용**: `state/holdings/backup/holdings_latest_pre_POC5-05_20261009.json`(읽기 전용 · git 추적 제외 · sha256 `62712039…`). v2 에 실제 기록이 생긴 뒤 이 백업만 덮어쓰면 새 기록이 사라진다 — 되돌릴 일이 생기면 현재 문서를 먼저 보존하고 변경분을 확인한다(설계자 §12-4 · 자동 롤백 없음).
3. 매매 저장은 OCI 를 건드리지 않는다. PC 보유가 바뀌면 OCI 카드가 '아직 OCI 미적용'(주황) → 사용자가 적용 버튼. 같은 종목 · 계좌 두 줄의 평단이 우연히 같아지면 OCI 적용은 `APPLY_FAILED`(전송 0 · 결과서 §5).
4. **라이브 보유에 시험 매매를 넣지 않는다**(설계 §11-3). 화면 확인은 창을 열어 보기만 한다. 시험은 tmp 파일 + `tests/_live_guard.py`.
5. 입력 한도(수량 소수 6 · 단가 소수 2 · 정수부 15자리 미만)는 **새로 입력한 매매 값에만**. 잔량을 0 으로 만드는 매도 · 정정에서 원래 수량(= 이번 `supersedes_id` 대상 유효 기록의 수량 · 설계자 §12-2) · 기준잔고 · 잔고 등록 · 입력 정정은 기존 보유 입력 규칙(형식 · 유한 · 양수 · float 범위).
6. 시장 흐름은 PC 시세 DB 마지막 저장일까지의 참고 자료다(개별주 = 자료 없음 · 거래일 캘린더는 2026 만).
7. OCI 적용 확인(읽기 전용) — 결과서 §10 과 같은 방법: OCI 파일의 최상위 키 · 행 키 · 줄 수 · sha256 을 보고, PC 에서 `holdings_oci_apply._build_payload(<보유 파일 bytes>)` 의 sha256 · `state/holdings/holdings_apply_status_latest.json` 의 `last_applied_sha256` 과 대조한다. 값은 출력하지 않는다.

## 3. 다음 개발자 주의 (이번 단계 교훈)

1. **'기존 값에 새 규칙 소급 금지' 계약은 값이 다시 들어오는 모든 경로를 표로 열거한다** — 정정 · 정정의 정정 · 재매수 · 같은 기록 종류를 만드는 다른 경로 · 화면 왕복(채우기 → 그대로 저장) · 정규화(대소문자 · 공백 · 지수 표기) · 길이 단위(UTF-16 vs 코드 포인트). 명령별로만 고쳐 r3 · r4 가 반려됐다.
2. 시험 파일: `tests/test_poc5_05_holdings_history.py` 940 · `tests/test_poc5_05_history_integrity.py` 787(KS-10 분리 · 공용 도우미는 앞 파일에서 import). 새 시험은 두 파일 중 책임이 맞는 곳에 넣고 1,450줄 근접선을 본다.
3. 변이 시험은 저장소 **사본**(scratchpad)에서 돌린다 — 작업 폴더를 잠깐이라도 고치면 같은 때 도는 전체 회귀 · 점검 에이전트 결과가 오염된다.
4. 라이브 해시 비교는 회차마다 같은 범위로 한다(이번에 `state/ml/research/` 포함 여부가 회차마다 달라 결과서에 따로 적었다).
5. `git add -A docs/` 금지 — 사용자 소유 untracked `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 가 같이 올라간다. 경로를 하나씩 지정한다.
6. 후속 UI 후보(설계자 §12-3 · 배포 게이트 아님): 아주 작은 양수 잔량이 소수 6자리 표시로 '0' 처럼 보이는 문제.

## 4. 다음 단계

- **10-12(월) 08:10 이후**: POC5-02 첫 결과 행(OCI 읽기 전용) · POC5-03 화면 가격 결과 표시 확인 → 02 · 03 종료(POC5-01B 인계 §3).
- **10-23(금) 배치 완료 뒤**: 공식 R0 1회(POC5-04 인계 §2).
- **설계자**: POC5-06 수동 재진입 검토 / ML 사후평가 설계 — 설계서가 오면 바로 코딩하지 말고 PLAN 먼저(`docs/ai_plan/POC5/`).
