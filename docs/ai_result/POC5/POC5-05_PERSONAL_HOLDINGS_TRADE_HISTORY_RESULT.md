# POC5-05 개발 결과서 — PERSONAL_HOLDINGS_TRADE_HISTORY (보유 · 매매 이력 통합 · 설계 개정 2)

작성 2026-10-08 · 갱신 2026-10-09(검증자 r1 ~ r4 REJECTED 정정 · r5 VERIFIED · 보유 파일 백업 · 설계자 RESULT PASS_TO_DEPLOY) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED_LOCAL — 검증자 r5 VERIFIED(2026-10-09 · 위험 NONE) · 설계자 RESULT PASS_TO_DEPLOY(2026-10-09) · 보유 파일 백업 완료(§7-2) · 미커밋 · 미배포 · 다음 = 커밋 · push(사용자 승인) → OCI pull → PC 실화면 · 첫 정상 적용 읽기 전용 확인 → 종료 기록(§7-3)
DESIGNER_RESULT        = PASS_TO_DEPLOY(2026-10-09 · OUTSIDE_CHANGES ACCEPTED 17 · KNOWN_LIMITATIONS ACCEPTED_CURRENT_SCOPE 12 · REWORK NOT_REQUIRED · RESULT_RESUBMIT NOT_REQUIRED · 정정의 원래 수량 = 이번 supersedes_id 가 가리키는 유효 기록의 수량) — 원문 = 설계서 §12 · 끝에 전달문 원문
VERIFIER               = r5 VERIFIED(2026-10-09 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 위험 NONE · 범위 폭주 NONE · 검증자 임시 사본에서 백엔드 239 · 화면 371 통과 · 결과서 §8-1 '새 5파일' → '새 6파일' 은 검증자가 직접 정정 · stage) · r4 REJECTED(2026-10-08 · A-1 · A-3 · 위험 LOW — 기존 정밀도 · 크기로 저장된 전량매도 기록의 단가만 정정해도 새 입력 한도로 422) → 정정 + 같은 부류 전수 점검(§6-7) · r3 REJECTED(2026-10-08 · A-1 · A-3 · 위험 MEDIUM — 새 검사가 기준잔고에도 10^15 상한을 적용해 기존 형식 경계값 파일이 load() 정상 · 화면 API 손상으로 갈림) → 정정(§6-6) · r2 REJECTED(2026-10-08 · A-1 · A-3 · B-1 · 위험 HIGH — 등록되지 않은 position 을 가리키는 기록을 계산에서 조용히 빼 손상 문서가 정상 빈 보유 · 새 매매 · 빈 OCI 적용으로 통과) → 정정 + 반박 검토 3관점(§6-4) · r1 REJECTED(① 이력과 불일치한 holdings 를 정상 빈 보유로 ② 매매대금 28자리 반올림) → 정정(§6-3)
STEP_ID                = POC5-05 보유 · 매매 이력 통합(설계 개정 2)
DESIGN                 = docs/ai_design/POC5/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_DESIGN_V1.md (개정 2 · §11 PLAN 판정 PASS_TO_IMPLEMENT · §12 RESULT 판정 PASS_TO_DEPLOY · 끝에 전달문 원문)
PLAN                   = docs/ai_plan/POC5/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_PLAN_V1.md (개정 2 기준 · 판정 반영 = 본문 정정 + §9)
PREDECESSOR            = POC5-04
BASE_COMMIT(코드 기준)  = eb5d1ead
MOCKUP                 = 사용자 확인 완료(2026-10-08 · 설계자 §11-3 수용 · 재확인 요구 없음)
API                    = 신규 로컬 3 경로(GET · PUT /holdings/trade-history · GET /holdings/trade-history/market-flow) · 기존 변경 2(GET/PUT /holdings → app/api_holdings.py 이전 + 응답 · 요청 필드 추가 · GET /holdings/apply/status + pending_apply · last_applied_at)
OCI_CODE               = 변경 있음(OCI 에서 도는 파일: app/holdings.py · app/three_push_runtime/target_tickers.py · app/runtime_evidence/holdings_selection_flow.py · app/runtime_evidence/holdings_risk_flow.py · scripts/run_holdings_publication.py) → OCI pull 필요
TESTS                  = 새 테스트 6파일(백엔드 · r4 에서 KS-10 분리 1파일 포함) · 기존 4파일 수정 · vitest 새 5파일 + 기존 1파일 수정 — §8
REVIEW                 = 독립 검토 1회(읽기 전용 · tmp 재현) — MEDIUM 4 · LOW 8 → 모두 반영(§6-2) · r4 같은 부류 전수 점검(개발자 + 독립 점검 1회) — 추가 결함 7건 재현 → 모두 정정(§6-7)
KS-10                  = 트리거 0 — 백엔드 최대 app/holdings_market_flow.py 591(app/holdings_book.py 513) · 테스트 최대 940(tests/test_poc5_05_holdings_history.py — r4 시험 추가로 1,560줄이 되어 손상 판정 · 기존 값 시험을 tests/test_poc5_05_history_integrity.py 787 로 분리 · §4-17) · 프론트 최대 HoldingsManageView.tsx 761(797 → 761) · app/api.py 644 → 582
BACKEND_FULL_REGRESSION= 3258 passed / 0 failed · exit 0 · 547.86s(2026-10-08 22:46:01 ~ 22:55:11 · 검증자 r4 정정 뒤 최종 코드) · PC state/logs 1,153파일 해시 동일(§8-5) · 회귀 시작 뒤 코드 변경 0(문서만)
```

## 0. 요약

「종목 관리」에서 보유 줄의 매매를 한 번 입력하면 현재 수량 · 이동평균 평단과 매매 이력이 함께 바뀐다.

- **저장**: PC `state/holdings/holdings_latest.json` 한 문서가 정본이다(`schema_version 2` · `revision` · `holdings` = 계산 결과 · `personal_trade_history` = positions · records). 모든 PC 보유 쓰기는 `app/holdings_store.py :: commit` 하나를 지난다(threading.Lock → 최신 문서 → 재시도 확인 → revision 확인 → 재계산 · 검증 → 같은 디렉터리 임시 파일 · fsync → `os.replace`).
- **계산**: `app/holdings_book.py`(순수 함수) — 설계 §3 이동평균 · §11-2 날짜 순서 · §11-1 Q-E 입력 정정. 계산값은 저장하지 않고 매번 records 로 다시 계산한다.
- **화면**: 보유 표(읽기 표시 · 수익률 열) → 줄 클릭 = 매매 입력 창(두 줄 같은 폭 칸) · History 창(보유 기간별 · 실현손익 · 정정 · 취소 · 시장 흐름 보기) · 접힌 '과거 보유'(재매수) · 기존 편집 표 = '입력 정정' 모드 · OCI 카드 '미적용' 표시.
- **OCI 경계**: 적용은 허용 5필드 payload 를 만들어 보내고 hash 도 payload 로 계산한다(개인 이력 · ID 는 구조상 0). 정상 빈 보유를 PC · OCI 모두 처리한다(보유 브리핑 `skipped/no_holdings` · 위험 알림 = 사업군 대표만).

## 1. 처리한 요구사항

| 항목 | 상태 | 근거 |
|---|---|---|
| AC1 매매 한 번 = 보유 · 이력 같이 변경 | DONE | 최초 매수 · 추가매수 · 분할매도 · 전량매도 각각 PUT 1회 = 파일 교체 1회(`test_each_trade_is_one_file_replace_and_section3_example`) |
| AC2 §3 계산 예 · 손실 · 잔량 초과 · 소수 · 평단 유지 · 원가 0 · 재매수 원가 분리 | DONE | `tests/test_poc5_05_holdings_book.py` · §11-2 순서 예(SELL 원가 40,000 · 이익 20,000) 포함 |
| AC3 기존 32줄 기준잔고 · 매수일 미상 · 계좌 · 복수 줄 원가 분리 | DONE | V1 은 가상 기준잔고로 읽고(쓰기 0) 첫 변경 때 줄마다 BASELINE 저장 · 다른 계좌 같은 종목 분리 |
| AC4 실패 · 응답 유실 재시도 · 오래된 화면 · 정정/취소 · 반복 요청 | DONE | 교체 전 실패 = 바이트 불변 · 같은 ID 재시도 = 같은 결과(revision 확인보다 먼저) · 다른 내용 409 · 동시 2요청 = 200 + 409 |
| AC5 전량매도 → 과거 보유 · 전 종목 매도 = 정상 빈 보유(PC · OCI) | DONE(로컬) | PC `EMPTY` 상태 · OCI 소비 경로 회귀(`tests/test_poc5_05_empty_holdings_oci.py`) · OCI 배포는 §7 |
| AC6 입력 정정 · 삭제 ≠ 매매 · 종료 기간 정정이 새 기간 평단 불변 | DONE | 수량 0 정정 = SELL 집계 제외 · 손익 null · 종목명만 = 원가 불변 · 계산 경로에서 제외(§6-2 M1) |
| AC7 OCI payload 허용 필드만 · hash · 미적용 판정 · 원장 불변 | DONE | `tests/test_poc5_05_apply_payload.py` · `tests/test_holdings_oci_apply.py` · 원장 · 피드백 · price_outcome 코드 변경 0 |
| AC8 목업 정렬 · 행 매매 · History · 과거 보유 · 재매수 · History 기본 조회 외부 호출 0 | PARTIAL | 목업 확인 완료 · 구현 · vitest 완료 · **사용자 실화면 확인 전**(§7) |
| AC9 회귀 · 정적 검사 · KS-10 | DONE | §8 |
| §11-1 Q-A ~ Q-E | DONE | 본문 §0 · PLAN §2 대로 |
| §11-2 계산 순서 정정 | DONE | BASELINE · REGISTER 기간만 기준잔고 먼저 · BUY 기간은 Q = C = 0 에서 날짜 · seq 순 |
| §11-3 재매수 = 선택 position · pending null 의미 · CLI 행 필드 거절 · 격리 시험 | DONE | 라이브 보유에 시험 매매 0 |
| §11-4 배포 · 결과서 기록 | PARTIAL | 결과서 = 이 문서 · 배포는 RESULT 판정 · 커밋 뒤(§7) |

## 2. 변경된 파일 목록

줄 수 = `wc -l` 실측(2026-10-08) · 수정 파일은 `HEAD → 지금`.

| 파일 | 구분 | 줄 수 |
|---|---|---|
| `app/holdings_store.py` | 신규 · 저장 경계 · V1 읽기 · 가상 기준잔고 · 이력 일관성 판정 · 쓰기 직전 판정 | 180 |
| `app/holdings_book.py` | 신규 · 이동평균 · 보유 기간 계산(순수) · 정확한 곱 · 반올림 없는 십진 문자열 · **문서 무결성 check_document** | 513 |
| `app/holdings_history.py` | 신규(개정 1 파일 재작성) · 매매 명령 · 입력 검증 · 새 입력 한도 판정(`_check_new_quantity`) · 공용 도우미 | 476 |
| `app/holdings_edit.py` | 신규 · 입력 정정 모드 저장(바꾸지 않은 칸 = 이력의 정확한 값 · 종목코드 정규화 비교) · 현재 보유 조회 | 248 |
| `app/holdings_history_view.py` | 신규 · History 조회 · 시장 흐름 입력 | 141 |
| `app/holdings_market_flow.py` | 신규 · 시장 흐름(읽기 전용) | 591 |
| `app/api_holdings.py` | 신규 · GET/PUT /holdings(api.py 에서 이전) | 73 |
| `app/api_holdings_history.py` | 신규(개정 1 파일 재작성) · trade-history · market-flow | 71 |
| `app/api.py` | 수정 · GET/PUT /holdings 블록 제거 · router 등록 2 | 644 → 582 |
| `app/holdings.py` | 수정 · 빈 보유 허용 인자 · serialize_payload · is_history_document · **holdings_from_document(이력 일관성 판정 · load · 저장 경계 · OCI payload 공용)** · save() 이력/손상 문서 거절 · load() 정상 빈 보유 · 기존 형식 판정 엄격화 · NaN · Infinity 거절 | 254 → 389 |
| `app/holdings_oci_apply.py` | 수정 · 허용 5필드 payload(holdings_from_document) · payload hash · 임시 파일 전송 · 원격 len>0 제거 · 마지막 성공 hash/시각 · pending_apply | 350 → 510 |
| `app/api_holdings_oci_apply.py` | 수정 · status 응답 + pending_apply · last_applied_at | 79 → 90 |
| `app/three_push_package_exporter.py` | 수정 · Holding(**h) → holdings.load() | 326 → 325 |
| `scripts/run_holdings_publication.py` | 수정 · 이력 · 행 추가 필드 문서 거절 · active 가 이력 문서이거나 읽을 수 없으면 교체 거절 | 420 → 476 |
| `app/ledger_copy/views.py` | 수정 · 받은 알림 이름표가 이력 문서면 공용 판정을 거침 | 299 → 307 |
| `scripts/build_holdings_selection_preview.py` | 수정 · 보유 브리핑 미리보기가 이력 문서면 공용 판정을 거침 | 188 → 193 |
| `app/three_push_runtime/target_tickers.py` | 수정(OCI) · 정상 빈 보유 = [] / 대표만 | 142 → 146 |
| `app/runtime_evidence/holdings_selection_flow.py` | 수정(OCI) · 정상 빈 보유 = skipped/no_holdings(가드 앞) | 465 → 511 |
| `app/runtime_evidence/holdings_risk_flow.py` | 수정(OCI) · 보유 0 · 대표 0 = skipped/no_holdings | 548 → 569 |
| `frontend/lib/api/holdingsHistory.ts` | 신규 · 타입 · 조회 · 명령 · 시장 흐름 | 193 |
| `frontend/lib/api/holdings.ts` · `holdingsApply.ts` · `index.ts` | 수정 · 줄 ID · revision · status · pending_apply · last_applied_at · barrel | 276 → 292 · 49 → 53 · 29 → 30 |
| `frontend/app/components/HoldingsManageView.tsx` | 수정 · 기본 = 보유 표 섹션 · 편집 표 = 입력 정정 모드 · 빈 보유 허용 · OCI 카드 분리 · 지수 표기 값을 십진 표기로 채움 | 797 → 761 |
| `frontend/app/components/holdings_manage/` | 신규 · `HoldingsBookSection` 327 · `TradeDialog` 361 · `NewHoldingDialog` 400 · `HistoryDialog` 185 · `HistoryCycle` 143 · `HistoryEventRows` 189 · `MarketFlowPanel` 165 · `ClosedHoldings` 92 · `OciApplyCard` 110 · `Dialog` 58 · `format.ts` 126 · `historyText.ts` 108 · `historyFixtures.ts`(테스트 자료) 343 | — |
| `frontend/app/globals.css` | 수정 · 끝에 `hmx-*` 블록 | 3233 → 3291 |
| 테스트(백엔드 신규) | `tests/test_poc5_05_holdings_book.py` 313 · `test_poc5_05_holdings_history.py`(개정 1 파일 재작성) 940 · `test_poc5_05_history_integrity.py`(r4 · KS-10 분리 · 손상 판정 · 기존 값 · 새 입력 한도) 787 · `test_poc5_05_apply_payload.py` 545 · `test_poc5_05_market_flow.py` 539 · `test_poc5_05_empty_holdings_oci.py` 357 | — |
| 테스트(백엔드 수정) | `tests/test_holdings_oci_apply.py` 296 → 411 · `test_holdings_apply_status.py` 98 → 109 · `test_run_holdings_publication.py` 582 → 821 · `test_holdings_draft_flow.py` 244 → 245 | — |
| 테스트(프론트) | 신규 `holdings_manage/{TradeDialog,NewHoldingDialog,HistoryDialog,MarketFlowPanel,ClosedHoldings}.test.tsx` 414 · 446 · 308 · 130 · 69 · 수정 `HoldingsManageView.behavior.test.tsx` 171 → 311 | — |
| `docs/PROGRAM_TRUTH.md` | 수정 · 최종 반영 · §5.1 · §6.1 표 · §7.2 · 프로세스 A · OCI 소스 · 코드 색인 | 991 → 996 |
| `docs/STATE_LATEST.md` · 설계서 · PLAN · 이 결과서 | 갱신 · 신규 | — |

- `tests/conftest.py` 는 HEAD 와 같다(개정 1 의 SQLite 격리 줄을 되돌림 · 626 → 626).

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경

1. `app/holdings.py :: save()` 는 PLAN 의 '저장 경계로 위임' 대신 **이력 문서 · 손상 파일이면 거절**한다. 앱 호출자 0(테스트만) · 구판 writer 가 이력을 버리는 경로를 막는 목적은 같다.
2. 입력 정정 모드에서 기존 줄의 종목코드 · 계좌를 바꾸면 422(그 줄을 지우고 새로 등록). 줄 ID 의 이력이 다른 종목으로 옮겨 붙는 것을 막는다.
3. 입력 정정 모드의 ID 없는 새 줄(잔고 등록)은 Step 2C(같은 종목 · 계좌 평단별 여러 줄)를 유지한다 — 같은 (종목, 계좌)의 과거 줄이 딱 하나이고 보유 중인 같은 줄이 없을 때만 그 줄의 새 기간으로 잇는다.
4. 적용 전 검사 `_payload_readable_by_consumer`: 줄별 계산으로 평단이 우연히 같아진 두 줄(같은 종목 · 계좌)은 OCI `load()` 가 삼중조합 중복으로 거절하므로 적용을 APPLY_FAILED(전송 0)로 막는다.
5. `pending_apply` 는 마지막 시도가 OUT_OF_SYNC · UNKNOWN 이면 null(OCI 내용 미확인). 상태 응답에 `last_applied_at`(마지막 성공 시각) 추가.
6. 매매 수량 한도(소수 6자리 · 정수부 15자리 미만)는 새로 입력한 수량에만 — 잔량을 0 으로 만드는 매도(전량매도 포함) · 정정에서 원래와 같은 수량은 면제(설계 §3 소급 금지 · §6-7).
7. History 응답에 줄 단위 `voided`(기간의 매매가 모두 취소돼 기간이 빠져도 취소 기록이 보이게) · 409 문구에 관련 기록(날짜 · 종류 · 수량).
8. `scripts/run_holdings_publication.py` 거절 문구의 긴 대시(—)를 '-' 로(cp949 콘솔 인코딩 오류 방지) · activate 는 active 가 이력 문서면 교체 거절.
9. `three_push_package_exporter` 가 `load()` 를 쓰게 되어 최상위 list 형식 파일을 이제 거절한다(값 검증도 함께).
10. 화면: History 의 BUY/SELL 줄마다 [정정] · [취소](확인 줄) — PLAN §5 의 정정 · 취소 흐름(목업에는 '정정 전 입력' · '취소한 기록' 펼침만 있었다). 새 보유 창의 종목명은 ETF 목록에 없을 때만 같은 칸에서 직접 입력(선택). 계좌는 목록에서만 고른다(POC3-08 (D) 유지 · 목록 = 추천값 + 현재 · 과거 보유 계좌).
11. 이력 문서 손상 판정을 `app/holdings.py :: holdings_from_document` 한 곳에 두고 저장 경계 · `load()` · OCI 적용 payload 가 함께 쓴다(검증자 r1 ①). 이 때문에 OCI 에서도 `app/holdings_book.py` 를 import 할 수 있다(이력 문서일 때만 · OCI 파일은 5필드라 실제로는 타지 않음 · 같은 pull 로 배포).
12. 이력 문서 판정을 보조 경로에도 — 받은 알림 이름표(`ledger_copy/views.name_map`) · 보유 브리핑 미리보기 CLI(이력 문서일 때만 · 기존 형식 파일은 기존 동작). 공용 `_coerce_holding` 의 NaN · Infinity 거절(OCI `load()` 도 같은 판정 · 실측 OCI 파일 5필드 · 비유한 값 0).
13. 매수 기록이 없는 기간(최초 BUY 취소)은 입력 정정이 남아도 계산에서 빠진다(설계 §11-2 '현재 보유에서 빠짐'). 매도만 남은 기간은 손상.
14. 전량매도 화면이 서버의 정확한 잔량(History 현재 기간 수량 · 십진 문자열)을 보낸다(float 오차로 409 반복 방지).
15. 「종목 관리」 부제 · 카드 제목 문구 변경(보유 표 · 입력 정정 모드) · 마지막 줄 삭제 허용 · 0건일 때 빈 입력 행 대신 상태 문구.
16. r4 같은 부류 전수 점검으로 함께 고친 것(§6-7): 재매수(줄 지정)는 그 줄의 종목 · 계좌를 쓴다(서버 · 화면 · 보낸 종목코드 재검사 없음) · 잔고 등록 명령 = 입력 정정 모드 새 줄과 같은 기존 보유 입력 규칙 · 한도를 미루는 수량도 float 범위 밖이면 422 · 입력 정정 모드의 바꾸지 않은 칸 = 이력의 정확한 값 · 종목코드 공백 · 대소문자 무시 비교 · 화면이 지수 표기 값을 십진 표기로 채움 · 새 보유 창 계좌 글자 수 = 코드 포인트.
17. `tests/test_poc5_05_holdings_history.py` 가 r4 시험 추가로 1,560줄(KS-10 시험 파일 1,500줄 초과) → 손상 판정 · 기존 값 · 새 입력 한도 시험을 `tests/test_poc5_05_history_integrity.py` 로 분리(시험 내용 그대로 · 분리 직후 두 파일 합계 90개 = 분리 전 90개 · 공용 도우미는 원래 파일에서 import — 저장소의 기존 방식).

## 5. 알려진 한계 / 미완성

- **사용자 실화면 · OCI 배포 전**(§7). OCI pull 전에 정상 빈 보유를 적용하면 OCI 구판 `load()` 가 빈 목록을 거절한다 → 배포 순서 §7.
- 첫 실제 저장 때 라이브 v1 파일이 v2 문서로 바뀐다(되돌리려면 이전 파일이 필요) → §7 백업.
- 같은 날 '앞' 은 그날 기존 기록 모두의 앞이다(두 기록 사이에 끼우기 없음).
- 수량 입력 정정 뒤 그보다 앞 날짜로 그 기간을 전량매도하면 409(기간 중간에 0 이 된 뒤 정정 = 다시 열림 · 기간 모델상 거절). 정정 · 취소로 풀어야 한다.
- 시장 흐름: 개별주 = 자료 없음(PC 수집 ETF 만) · 거래일 연도 파일은 2026 만(다른 해는 평일 기본) · 값은 PC 시세 DB 마지막 저장일까지(실측 10-02).
- 화면 표시: 아주 작은 소수 잔량은 소수 6자리 표시라 '0' 으로 보일 수 있다(계산 · 전량매도는 정확값).
- 입력 정정 모드는 종목명이 빈 줄에 자동 채움을 유지하므로, 저장하면 종목명 정정(표시값) 기록이 생길 수 있다(계산 영향 없음).
- 모든 매매가 취소된 줄(보유 기간 0)은 '과거 보유' 목록에 넣지 않는다(기록은 파일에 남음).
- 보유 파일 mtime 을 '보유 기준 시각' 으로 표시하는 PC 경로(근거 화면)는 이력만 바뀌어도 시각이 바뀐다(표시 전용 · 판단 미사용).
- PC 의 scp 원본이 시스템 임시 폴더 절대 경로다(맥북 확인 · Windows PC 는 미확인).
- 입력 정정 모드는 float 호환값을 다룬다 — 바꾸지 않은 칸은 이력의 정확한 값을 유지하지만, 바꾸는 칸은 float 정밀도(유효 숫자 약 17자리)까지만 입력된다.
- 줄별 계산으로 서로 다른 두 줄(같은 종목 · 계좌)의 평단이 우연히 같아지면, PC 에는 저장되지만 OCI 적용은 막힌다(OCI `load()` 삼중조합 중복 규칙 → 전송 0 · APPLY_FAILED · 일부 줄만 보내거나 합치지 않음 · §4-4). 현재 보유는 (종목, 계좌) 중복 0 이라 해당 없음(설계자 §12-1 요청 · 위 한계 12건과 별도 기록).
- 소문자 · 공백이 든 기존 종목코드 줄은 입력 정정 저장 뒤에도 줄의 종목코드가 기존 값 그대로다(대문자로 바꾸지 않음 · 바꾸려면 정정 종료 뒤 새로 등록). 극단 기존 값(1e300 등)은 입력 정정 칸에 전체 자릿수로 표시된다(값은 그대로).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. 판단이 어려웠던 부분

- 재시도 비교 내용: 서버는 정규화한 명령(base_revision 제외)의 hash 로 같은 내용을 판정한다. 프론트도 base_revision 을 빼고 비교한다(응답 유실 뒤 revision 을 새로 받아도 같은 매매를 두 번 저장하지 않게).
- 정상 빈 보유 skip 은 비거래일 판정 · 완전성 가드 앞이다(대상 0 이면 판정 불가). 보유 브리핑 skip 은 기존 `no_selection` 과 같게 빈 상태를 저장한다.
- 시장 흐름 이벤트의 KOSPI 두 날짜 = (기준일, 그 종목의 마지막 저장일). 보유 기간 항목은 첫 BUY → 마지막 SELL(입력 정정으로 끝난 기간도 SELL 기준 · 화면 문구 '마지막 매도일').
- V1 파일의 줄 ID = 파일 내용 sha + 줄 순번의 uuid5(조회가 아무것도 쓰지 않아도 화면이 줄 ID 로 매매를 보낼 수 있게 · 그사이 파일이 바뀌면 409).

### 6-2. 독립 검토(2026-10-08 · 읽기 전용 · tmp 재현) 반영

| 지적 | 반영 |
|---|---|
| M1 종목명만 정정이 앞 날짜 전량매도를 막음 | 종목명만 정정은 계산 경로 · 종료 판정 · 기간 시작일에서 제외 · 종료일 = 닫은 기록 날짜 · 테스트(변이 시 실패 확인) |
| M2 매매 · 취소 뒤 다른 화면 보유 캐시 미무효화 | 저장 · 취소 성공 때 `HOLDINGS_INVALIDATION_KEYS` 무효화 |
| M3 V1 · ID 없는 구형 PUT 이 같은 줄에 두 입력을 맞춰 줄 손실 | 같은 줄 두 번 매칭 = 409 · 테스트 |
| M4 409 에 관련 기록 목록 없음 | 문구에 '관련 기록: 날짜 종류 수량' · 테스트 |
| L1-a 소수 7자리 잔량 전량매도 불가 | 전량매도 정확값 면제(§4-6) · 테스트 |
| L1 vitest 종료 코드 1(처리 안 된 오류) | 종목명 조회 기본 mock · exit 0 실측 |
| L2 save() 손상 파일 덮어씀 · CLI activate 가 이력 문서 교체 | 둘 다 거절 · 테스트 |
| L3 OCI 카드 문구 모순 | 마지막 성공 시각 응답 · 표시 |
| L4 새 보유 창 개별주 종목명 입력 불가 | 목록에 없을 때 같은 칸 입력 · 테스트 |
| L5 지난 기간 정정의 같은 날 판단에 다른 기간 날짜 | 정정 대상 기간 날짜 사용 |
| L6 '전량매도한 종목' · '전량매도일' 문구 | '보유가 끝난 종목' + '입력 정정으로 종료' 태그 · '마지막 매도일' |
| L7 PROGRAM_TRUTH 옛 서술 | 입력 정정 모드로 정정 |

### 6-3. 검증자 r1 REJECTED(2026-10-08) 정정

| 지적 | 원인 | 정정 · 확인 |
|---|---|---|
| ① 이력에 잔량이 남은 v2 문서에서 `holdings` 만 빈 배열 → `GET /holdings` 200/EMPTY · OCI `{"holdings":[]}` payload 생성 | 이력 문서를 형식만 보고, `holdings` 가 이력(정본)으로 다시 계산한 결과인지 확인하지 않았다 | `holdings_from_document` 가 저장된 `holdings` 를 이력으로 다시 계산한 결과(종목 · 수량 · 평단 · 이름 · 계좌 · 줄 ID · 기간 ID · 순서)와 비교 — 다르거나 계산 불가면 손상. 같은 판정을 **저장 경계 `read_document`(조회 · 매매 · 입력 정정 쓰기 모두 500 · 손상 파일 위에 쓰기 0) · 공용 `load()`(PC 근거 화면 · 평가 · exporter) · OCI 적용 `_build_payload`(APPLY_FAILED · 전송 0 · pending null)** 세 층이 함께 쓴다. 테스트: 빈 배열 · 수량만 바꾼 문서 · 기록 손상(예외가 새지 않고 500) |
| ② 단가 `123456789012345.67` × 수량 `123456789012345.123456` 이 `…381600` 으로 저장 | 곱셈이 기본 Decimal 문맥(28자리)에서 실행됐고, 십진 문자열 변환 `fmt()` 의 `normalize()` 도 28자리로 다시 반올림했다(두 층) | `holdings_book.exact_product`(정밀도 40 · Inexact 예외 — 조용한 반올림 금지) · `fmt()` 는 값 자릿수 이상 문맥에서 `normalize` · History 의 기간 수익률 · 평단도 같은 정밀도 문맥. 입력 한도(정수부 15 · 소수 2/6)의 곱은 최대 38자리라 늘 정확. 테스트: 검증자 값 `15241578753238767078092381604.29703552`(응답 · 저장 · History 모두) · 최대 한도 값(정밀도 60 독립 계산과 일치) · 정밀도 초과는 예외 |

### 6-4. 검증자 r2 REJECTED(2026-10-08) 정정 · 반박 검토

**원인**: 계산이 등록된 position 에 연결된 기록만 처리해, 연결이 끊긴 기록을 오류 없이 뺐다. r1 정정은 'holdings = 이력으로 다시 계산한 결과' 만 봤고, 계산 입력(이력 문서 자체)의 무결성은 보지 않았다.

**정정 — 문서 무결성 한 함수(`app/holdings_book.py :: check_document` · `compute` 가 먼저 부름)**: 계약에서 뽑은 규칙 전부를 한 번에 본다.
- 허용 키(문서 · 이력 · 줄 · 기록 · 기록 종류별 내용) · 줄 ID · 기록 ID 유일
- **모든 기록이 있는 줄을 가리킴**(r2) · 한 기간은 한 줄에만 · 기록 없는 줄 없음
- 종류별 내용: 날짜 · 시각 형식 · 양수 십진수(입력 정정 수량만 0 허용) · **매매대금 = 단가 × 수량 정확한 곱** · 정수 seq · 메모 · 종목명 형식
- 정정 · 취소 연결: 앞선 기록만(순환 불가) · 대상은 매매 기록 · 같은 줄 · 같은 기간 · 한 기록은 한 번만 대체 · 취소 · 정정은 같은 종류 · VOID 는 대상 필수
- 저장된 기록에 임시 표시(`virtual`) 없음 · 보유 행은 허용 키만

이 함수는 계산 때마다 돌므로 저장 경계(조회 · 매매 · 입력 정정 쓰기) · 공용 `load()` · OCI 적용 payload 가 모두 같은 판정을 거친다. 저장 경계는 **쓰기 직전 새 문서에도 같은 판정**을 한 번 더 돌린다.

**반박 검토(독립 3관점 · 읽기 전용 · tmp 재현)**와 반영:

| 관점 · 지적 | 반영 |
|---|---|
| 우회 경로 [HIGH] 표지 키(`schema_version` · `personal_trade_history`) 두 개를 지우면 이력 문서가 기존 형식(V1)으로 통과(판정 건너뜀 · 기록 누락 · 쓰기 · 빈 OCI 적용) | 기존 형식 = **최상위가 `holdings` 하나이고 행이 허용 5필드 이하**일 때만. 나머지 dict 는 모두 이력 문서로 보고 전체 판정(`is_history_document`) — OCI payload 는 늘 기존 형식이라 OCI 영향 없음 |
| 우회 경로 [LOW] 받은 알림 이름표(`ledger_copy/views.name_map`) · 보유 브리핑 미리보기 CLI 가 원문 holdings 를 판정 없이 사용 | 이력 문서면 공용 판정을 거친다(기존 형식 파일은 기존 동작 유지) |
| 우회 경로 [LOW] publication CLI activate 가 읽을 수 없는 active 를 5필드 파일로 교체 | 있는데 읽을 수 없는 active 는 교체 거절(`active_unreadable` · 적용 버튼 안내) |
| 통과하는 손상 [MEDIUM] NaN · Infinity 수량 · 평단이 `load()` · payload 를 통과(OCI 적용 OCI_APPLIED) | 공용 `_coerce_holding` 에서 `math.isfinite` · 저장 십진 문자열은 형식(`^\d+(\.\d+)?$`) · 한도(10^15 미만) · `compute` 의 float 변환 유한성 |
| 통과하는 손상 [MEDIUM] 이름 정정만 남은 기간(매수 취소)이 기간 경계 확인을 끊어 API 만으로 겹치는 기간 저장 | 시작 기록(기준잔고 · 잔고 등록 · 유효 매수)이 없는 기간은 계산에서 뺀다(매도만 남으면 손상) · 경계는 **앞선 모든 기간의 가장 늦은 종료일**과 비교 |
| 통과하는 손상 [LOW] 같은 기간 · 같은 날 seq 중복(계산 순서가 저장 순서에 기댐) | 유효 기록의 (기간, 날짜, seq) 유일 |
| 통과하는 손상 [LOW] holdings 가 목록이 아니면 TypeError(500 · 상태 조회 깨짐) | 목록 여부를 먼저 확인 → 손상 판정 |
| 통과하는 손상 [LOW] revision 음수 · schema_version 실수 통과 뒤 매매가 영구 422 | 정수 형식 번호 2 · 정수 revision ≥ 0 |
| 통과하는 손상 [LOW] 닫힌 줄의 계좌 31자 · 공백 종목코드가 읽기 통과 뒤 첫 저장 500 | 줄 단위 계좌(공백 없음 · 30자 이하) · 종목코드(공백만 금지) |
| 통과하는 손상 [LOW] 저장 값의 입력 계약(지수 표기 · 자릿수 · 날짜 상한 · 메모) | 저장 형식 · 단가 소수 2자리 · 거래일 · 정정일 ≤ 저장일 · 메모 200자 |
| 통과하는 손상 [LOW] 저장 값의 입력 계약 | → r3 에서 범위 정정(§6-6): 상한 · 자릿수는 새 매매 입력에만 |
| 거절되는 정상 [LOW] 전량매도가 화면 float 잔량을 보내 float 오차가 있으면 409 반복 | 화면이 서버의 정확한 잔량(십진 문자열)을 보낸다 |
| 거절되는 정상 — 정상 쓰기 흐름 손상 판정 | **재현 0** — V1 7흐름 · 명령 9흐름 · 입력 정정 6흐름 · 무작위 정상 명령(약 6,000 저장 · 시드 140)에서 '200 저장 뒤 손상' · '정상 쓰기 500' 0건 |

남은 판단(결함 아님): PC 의 `{"holdings": []}`(기존 형식 · 이력 없음)는 정상 빈 보유로 읽는다 — 이력이 없어 맞지 않을 대상이 없고 OCI payload 와 같은 모양이다(PC 앱은 이 모양을 쓰지 않음). 기록 ID 의 UUID 형식은 강제하지 않는다(비어 있지 않은 유일 문자열). 라이브 PC · OCI 보유 파일은 실측상 기존 형식(최상위 `holdings` · 행 5필드 · 32줄 · 비유한 값 0 · OCI 는 읽기 전용 ssh 로 키 이름만 확인)이라 엄격한 기존 형식 판정으로 잠기지 않는다.

테스트: 검증자 재현(줄 ID 변경 → History · 보유 · 새 매매 500 · 쓰기 0 · load 예외 · payload 없음 · 변형: 잔량 BUY + 줄 없음 + 빈 holdings) · 손상 21종 행렬(각각 저장 경계 · load · payload · 두 조회 API 모두 손상 · 파일 바이트 불변) · 보조 경로 · CLI.

### 6-6. 검증자 r3 REJECTED(2026-10-08) 정정

| 지적 | 원인 | 정정 · 확인 |
|---|---|---|
| 기존 형식 파일의 수량 또는 평단 `1000000000000000` → 공용 `load()` 정상 · 보유 조회 · History 500(손상) | r2 정정 때 반박 검토 제안('저장 값에도 입력 한도')을 기록 종류 전체에 넣었다 — PLAN §2-1 '기준잔고 = 읽은 값 그대로 · 자릿수 제한 없음'과 대조하지 않음 | 상한(10^15) · 소수 자릿수는 **새 매매 입력에만**(매수 수량 · 매매 단가). 저장 판정에서 기준잔고 · 잔고 등록 · 입력 정정 · 전량매도 수량(서버 잔량과 정확히 같아야 함)은 형식 · 유한 · 양수만(경로별 입력 규칙은 r4 에서 정리 · §6-7). 전량매도 입력도 크기 한도 면제 · 매매대금 정확한 곱의 정밀도 = 두 값 자릿수 합 이상(어떤 크기에서도 정확) |

소급 시험(새): 기존 형식이 허용하던 값 8종(수량 10^15 · 평단 10^15 · 1e20 / 1e300 · 1e-9 · 긴 소수 · 비정형 종목코드 · 계좌 없음 · 빈 이름 · 사용자 계좌 30자)마다 읽기(V1) → 첫 변경(V2) → 다시 읽기 → 입력 정정 → 전량매도를 모든 층(보유 조회 · History · `load()` · OCI payload)에서 확인. 비정형 종목코드는 기존 규칙(POC3-08 · `PUT /holdings` 저장은 종목코드 형식 강제 · 422)대로이고 읽기 · 매매 · 전량매도는 정상. 상한을 기준잔고에 되돌리면 3건 실패로 잡힘.

### 6-7. 검증자 r4 REJECTED(2026-10-08) 정정 · 같은 부류 전수 점검

| 지적 | 원인 | 정정 |
|---|---|---|
| 기존 수량(`0.1234567` · `1000000000000000`)으로 정상 저장한 전량매도를 **단가만 정정**하면 422(소수 6자리 · 크기 상한) | 전량매도에는 기존 수량 예외가 있었지만 정정은 일반 새 입력 검사로 돌아갔다 — r3 정정 때 '한도는 새 입력에만' 을 명령별로만 보고, 기존 값이 다시 들어오는 경로를 계약 기준으로 열거하지 않았다 | 매매 수량 한도 판정을 **저장 경계 안 한 곳(`_check_new_quantity`)** 으로 모았다. 한도(소수 6자리 · 정수부 15자리 미만)는 **새로 입력한 수량에만** — 예외: ① 정정에서 원래 기록과 같은 수량(이미 받아들인 값) ② 그 기간의 잔량을 0 으로 만드는 매도(전량매도 · 분할매도로 잔량 전부 입력 · 정정 모두). 매수는 예외가 없어 재계산 전에, 매도는 재계산 뒤에 판정(422 · 쓰기 0). 이미 저장된 기록은 다시 검사하지 않는다 |

**같은 부류 전수 점검**(기존 값 · 이미 받아들인 값이 다시 들어오는 모든 경로 — 개발자 직접 + 독립 점검 1회 · 읽기 전용 · tmp 재현)에서 추가로 재현해 고친 것:

| 재현 | 정정 |
|---|---|
| 재매수(줄 지정)가 보낸 종목코드를 새 입력 형식으로 다시 검사 — 기존 비정형 종목코드 줄은 재매수 422 · 화면 저장 버튼도 비활성 | 재매수는 그 줄의 종목 · 계좌를 쓴다(서버 · 화면 · 형식 재검사 없음) |
| 입력 정정 모드 화면이 지수 표기로 읽히는 값(1e-7 · 1e21 · 1e300)을 콤마 처리하며 'e' 를 지워 다른 값(17 · 121 · 1,300)으로 채움 → 손대지 않고 저장해도 수량 · 평단이 바뀐 정정 기록(HEAD 부터 있던 결함 · 이번 단계에서 정정 기록으로 남게 됨) | 같은 값의 십진 표기로 채운다(`format.ts :: plainNumberText`) |
| 잔고 등록 명령만 매매 입력 한도(수량 소수 6 · 평단 소수 2 · 15자리 미만) — 같은 REGISTER 를 만드는 입력 정정 모드 새 줄은 기존 보유 입력 규칙이라 같은 값이 경로에 따라 200 / 422 · 결과서 r3 문구('잔고 등록은 형식 · 유한 · 양수만')와도 어긋남 | 잔고 등록 = 기존 보유 입력 규칙(형식 · 유한 · 양수 · float 범위) — PLAN §2-1 의 REGISTER 행에도 자릿수 한도가 없다 |
| 입력 정정 모드에서 평단만 고쳐도 float 로 나타낼 수 없는 정확한 잔량(예 `123456789012345.123456`)이 float 값으로 깎임 | 바꾸지 않은 칸은 이력의 정확한 값(History 와 같은 계산) · 정정 전 값(`before`)도 정확한 값 |
| 소문자 기존 종목코드 줄 — 화면이 대문자로 보내 '종목코드 변경' 422 → 입력 정정 저장 전체가 막힘(HEAD 는 대문자로 저장) | 종목코드는 공백 · 대소문자를 무시해 비교 · 줄의 종목코드는 기존 값 그대로 · 다른 종목코드는 여전히 422 |
| 이모지가 든 기존 30자 계좌 — 화면이 UTF-16 길이(31)로 세어 재매수 · 새 보유 저장 버튼 비활성(서버는 30자로 받음) | 코드 포인트로 센다(서버 `len` 과 같음) |
| 한도를 미루는 매도 · 전량매도 수량 `1e1000000` → 500 · 잔고 등록 `1e400` → 409 '손상' | float 범위 밖이면 422(쓰기 0) |

라이브 보유 32줄에는 위 값이 없다(읽기 전용 실측: 종목코드 모두 표준 형식 · 수량 · 평단 모두 정수 · 계좌 최대 4자 · 이모지 0). 독립 점검 에이전트는 최종 보고 전에 중단되어, 재현 스크립트 출력에서 결과를 옮겼다.

결함 없이 확인한 범위(독립 점검 출력): 기존 값 20종(수량 · 평단 각각 1e15 · 1e20 · 1e300 · 1e-9 · 0.1234567 · 0.1+0.2 · 1/3 · 둘 다 1e300 · 비정형 종목코드 · 계좌 없음 · 계좌 30자 · 이모지 계좌 · 빈 이름) × 20단계(조회 · History · 적용 상태 · OCI payload(V1 · V2) · 손대지 않은 입력 정정(V1 · V2) · 전량매도 · 단가 / 날짜(정정의 정정) / 시각 / 메모만 정정 · 취소 · 다시 전량매도 · 재매수 · 기간별 시장 흐름 · 지난 기간 단가 정정) — 비정형 종목코드는 입력 정정 저장 2단계 제외(POC3-08 규칙) · 기대와 다른 결과 0건. 흐름 4종(기준잔고 + 매수 + 분할매도 + 전량매도 + 매수 정정으로 다시 열림 → 옛 전량매도 단가 정정 · 입력 정정 8자리 수량 → 전량매도 → 단가 정정 · 입력 정정 새 줄 1e-9 → 전량매도 → 재매수 · 정정의 정정) 정상.

정정의 '원래 수량'(설계자 §12-2 확정): **이번 `supersedes_id` 가 가리키는 유효한 정정 대상 기록의 수량** — 구현 `_check_new_quantity` 가 바로 그 기록과 비교한다. 그 수량을 유지한 단가 · 날짜 · 시각 · 메모 정정은 한도를 새로 적용하지 않고, 더 이전 기록의 수량으로 되돌리는 입력은 새 수량으로 검사한다(잔량이 정확히 0 이 되는 매도는 잔량 0 예외 그대로).

시험(새 · 수정): 기존 값 9종 행렬에 **손대지 않은 입력 정정(기록 0 · 파일 그대로) · 단가만 정정 · 재매수(줄 지정) · 기간별 시장 흐름** 추가 · 원래 수량 예외만 받는 경우(매수 정정으로 더는 잔량 0 이 아닌 매도의 단가 정정) · 새 입력 한도(분할매도 잔량 전부 200 · 바꾼 수량 422 · 매수 정정 422) · 잔고 등록 규칙(두 경로 같은 값 200 · 형식 · 범위 밖 422) · 한도를 미루는 수량의 범위 밖 422 · 입력 정정의 정확한 값 유지 · 소문자 종목코드 · 화면(재매수 비정형 코드 저장 · 정정 창이 기존 정밀도 수량을 그대로 보냄 · 지수 표기 값 왕복 · 이모지 계좌).

## 7. 사용자 확인이 필요한 항목

1. **실화면 확인**(OCI pull · PC 재기동 뒤): 보유 표 · 줄 클릭 매매 / 정정 창(칸 정렬) · History · 시장 흐름 · 과거 보유 · 입력 정정 모드 · OCI 카드 미적용 표시. **확인을 위해 가짜 매매를 저장하거나 기존 32줄을 다시 입력하지 않는다**(설계 §11-3 · §12-4) — 실제 거래 입력은 필요할 때 한다(사용자 데이터 입력 = 아직 · 설계자 기록).
2. **보유 파일 백업 완료**(2026-10-09 07:05 · 사용자 승인 2026-10-08 · 검증자 VERIFIED 뒤): `state/holdings/backup/holdings_latest_pre_POC5-05_20261009.json` — 원본과 sha256 `62712039ac95794023c3dfaad68b374b960888fda450b6392426c25b4c7caf3b` 같음 · 5,701바이트 · 32줄 · 기존 형식 5필드 · 읽기 전용 · git 추적 제외(`.gitignore` `backup/`) · 앱이 읽지 않는 경로. 이 백업은 **배포 전 보유 복원용**이다(설계자 §12-4): 첫 저장 때 v1 → v2 로 바뀌며, v2 에 실제 기록을 저장한 뒤 이 백업만 덮어쓰면 새 기록은 복구되지 않는다 — 그때 되돌릴 필요가 생기면 변경 후 문서를 먼저 보존하고 변경분을 확인한다(자동 롤백 · 새 백업 서비스 없음).
3. 배포 순서(설계자 §12-4): 커밋 · push(사용자 승인) → **OCI pull**(보유 소비 변경 + 신규 의존 파일 함께 · 거래일 08:05 ~ 15:45 회피 · 휴장일에는 이 구간 적용 없음 — 2026-10-09 는 PC 캘린더 기준 휴장일 · 다음 거래일 10-12) → PC 재기동 · 실화면(위 1) → 기존 보유 그대로 첫 정상 수동 OCI 적용 → 개발자가 OCI 읽기 전용으로 확인(적용 파일 최상위 키 = `holdings` 하나 · 행 허용 5필드 · 개인 이력 / ID 없음 · PC 현재 보유와 일치) → POC5-05 종료 기록. 실제 첫 매매 · v2 저장 · 전량매도 · 다음 영업일 관찰은 종료 조건이 아니다.

## 8. 검증 실측 (2026-10-08)

### 8-1. 테스트

- POC5-05 백엔드(새 6파일 + 수정 4파일): `.venv/bin/python -m pytest tests/test_poc5_05_*.py tests/test_holdings_oci_apply.py tests/test_holdings_apply_status.py tests/test_run_holdings_publication.py -q` — §8-5 전체 회귀에 포함.
- POC5-05 백엔드 6파일(`tests/test_poc5_05_*.py`) → `170 passed` (r4 정정 뒤 최종 코드).
- 프론트: `npx vitest run` → `Test Files 30 passed (30)` · `Tests 371 passed (371)` · exit 0 · `tsc` · `eslint` exit 0(r4 정정 뒤 최종 코드).

### 8-2. 정적 검사

- `black --check`(변경 · 신규 Python 29파일) → `29 files would be left unchanged.` · `flake8` exit 0 · `py_compile` exit 0.
- `npx tsc --noEmit` exit 0 · `npx eslint`(holdings_manage · HoldingsManageView · lib/api) exit 0.

### 8-3. 변이 시험(핵심 계약을 되돌린 상태에서 새 테스트가 실패하는지)

| 되돌린 계약 | 결과 |
|---|---|
| 같은 날 seq 무시 | 실패로 잡힘 |
| BUY 기간도 첫 입력 BUY 를 맨 앞 고정 | 실패로 잡힘 |
| 매도분 원가를 평단 반올림으로 | 실패로 잡힘 |
| 닫힌 기간도 현재 보유로 | 실패로 잡힘 |
| 재시도 확인을 revision 확인 뒤로 | 실패로 잡힘 |
| V1 가상 기록을 표시 그대로 저장 | 실패로 잡힘 |
| 원자 교체 대신 직접 쓰기 | 실패로 잡힘 |
| 입력 정정 변화 없음인데 저장 | 실패로 잡힘 |
| OUT_OF_SYNC 뒤에도 pending false | 실패로 잡힘 |
| 종목명만 정정을 계산 경로에 포함(M1) | 실패로 잡힘 |
| 정상 빈 보유 skip 끄기(OCI 소비) | 실패로 잡힘(5건) |
| 이력 일관성 판정 끄기(r1 ①) | 실패로 잡힘(2건) |
| 매매대금 곱을 기본 정밀도로(r1 ②) | 실패로 잡힘(2건) |
| `fmt()` 를 기본 문맥 normalize 로(r1 ②) | 실패로 잡힘(2건) |
| 끊긴 연결 허용(r2) | 실패로 잡힘 |
| 기존 형식 판정을 표지 키만으로(반박 HIGH) | 실패로 잡힘(3건) |
| 기간 경계를 인접 기간만으로(반박 MEDIUM) | 실패로 잡힘(함수 직접 시험) |
| 같은 날 순번 겹침 허용(반박 LOW) | 실패로 잡힘 |
| NaN · Infinity 허용(반박 MEDIUM) | 실패로 잡힘 |
| 기준잔고에 입력 상한 소급(r3) | 실패로 잡힘(3건) |
| 정정에서 원래 수량 예외 제거(r4) | 실패로 잡힘(1건 · 전용 시험) |
| 잔량 0 매도 예외 제거(r4) | 실패로 잡힘(8건) |
| 정정 수량에 일반 한도(r3 코드 = r4 지적 결함) | 실패로 잡힘(6건) |
| 분할매도 수량에 일반 한도(r3 코드) | 실패로 잡힘(1건) |
| 매수 정정 수량 한도 검사 제거(r4) | 실패로 잡힘(1건) |
| 매도 수량 한도 검사 제거(r4) | 실패로 잡힘(2건) |
| 재매수 종목코드 재검사(r3 코드) | 실패로 잡힘(1건) · 화면 저장 버튼 검사 되돌림 = vitest 1건 |
| 잔고 등록에 매매 한도(r4 전 코드) | 실패로 잡힘(1건) |
| 한도를 미루는 값의 float 범위 검사 제거(r4) | 실패로 잡힘(2건) |
| 입력 정정: 바꾸지 않은 칸도 float 값(r4 전 코드) | 실패로 잡힘(1건) |
| 입력 정정: 종목코드 정규화 비교 제거(r4 전 코드) | 실패로 잡힘(1건) |
| 화면: 입력 정정 칸 `String(숫자)`(r4 전 코드) | vitest 실패로 잡힘(1건) |
| 화면: 계좌 글자 수 UTF-16(r4 전 코드) | vitest 실패로 잡힘(2건) |

r4 변이는 작업 폴더가 아닌 저장소 사본(scratchpad)에서 실행했다 — 대조 변이(모든 명령 422)가 68건 실패로 잡혀 사본 코드가 쓰였음을 확인.

### 8-4. 라이브 읽기 전용 확인

- 라이브 PC DB `state/decision/decision_evidence.sqlite`(`mode=ro`): 표 9개 · `personal_holdings_history` 없음(개정 1 표는 생성된 적 없음).
- 라이브 보유(읽기만): 32줄 · 종목 29 · (종목, 계좌) 중복 0 · 소수 수량 0 · ETF 26 / 개별주 3.
- PC 시세 DB(`mode=ro`): §PLAN 1-5 표.

### 8-5. 백엔드 전체 회귀 · 라이브 보호

- `caffeinate -i .venv/bin/python -m pytest tests -q -p no:cacheprovider` → `3258 passed, 1 warning in 547.86s (0:09:07)` · exit 0 · 2026-10-08 22:46:01 ~ 22:55:11(검증자 r4 정정 뒤 최종 코드).
- 회귀 전후 `state/` · `logs/` 229파일(`state/ml/research/` 제외) sha256 비교 → 차이 0 · `state/ml/research/` 924파일은 r3 최종 회귀 전(21:16) 목록과 비교 → 차이 0(합 1,153파일 · 라이브 쓰기 0).

## 9. git 상태

- `git status --short --untracked-files=all`(보고 직전 실측): 이 단계 파일 59개가 모두 staged(오른쪽 칸 공백 · `A` 36 · `M` 23 · r4 에서 새 파일 `tests/test_poc5_05_history_integrity.py` 1개 추가) · `??` 1건 = `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(사용자 소유 · 이 단계와 무관 · stage 하지 않음).
- 커밋 0 · push 0(검증 · 설계자 RESULT 판정 뒤 사용자 승인).
