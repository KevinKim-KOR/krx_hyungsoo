# Decision Draft Preview v1 — Conclusion (DONE)

작성일: 2026-07-03
측정 방식: `wc -l` (Bash) 통일.

기존 보유·후보 비교 화면 선택 ETF 상세 영역에, 선택 ETF 하나에 대한 저장 없는
`판단 근거 미리보기` 를 추가. 서버가 결정적으로 조립한 텍스트 (LLM 미사용).

---

## 1. 기존 PENDING 초안과 임시 preview 의 분리 원칙

지시문 §4 정책 그대로:

| 구분 | 기존 일일 PENDING 초안 | 이번 STEP preview |
|---|---|---|
| 대상 | 전체 포트폴리오 | 선택 ETF 1건 |
| 생성 진입점 | `POST /runs/generate` (기존) | `POST /decision-draft/preview` (신규) |
| 저장 | `store.save(run)` | 저장 없음 (프론트엔드 메모리) |
| 승인 흐름 | PENDING → APPROVED / REJECTED | 미연결 |
| OCI 전달 | 있음 | 미연결 |
| Telegram | 있음 | 미연결 |
| DB write | 있음 | 0건 |

`generate_draft`, `store.save`, PENDING 상태 흐름은 이번 STEP 에서 재사용 X — Q2 확정 답변에 따라 순수 preview 조립 함수 신설.

---

## 2. preview endpoint 저장 없이 동작하는 사실

`POST /decision-draft/preview` 구현 (`app/api_decision_draft_preview.py`) 은:
- DB write 0건.
- 파일 write 0건.
- 외부 시세 호출 0건 (SQLite / 기존 서비스 read only).
- ML 실행 시작 0건.
- 자동 재시도 0건.

자동 테스트로 검증:
- `test_endpoint_does_not_touch_pending_draft` — `store.save` 를 fake 로 감시 → 호출 0건.
- `test_endpoint_does_not_call_external_price_sources` — `FinanceDataReader.DataReader` 를 raise 로 감시 → 호출 0건.

---

## 3. 보유·후보 각 1개 실측 결과 (자동 테스트 기반)

지시문 §4 실측 요구는 외부 사용자 조작이 아닌 자동 fixture 로 결정적 텍스트 조립을 확인:

| 케이스 | 검증 |
|---|---|
| 보유 ETF (069500) | `test_endpoint_holding_ok` — status=ok / preview_text 존재 / evidence_as_of.target_as_of_date="2026-07-02" |
| 후보 ETF (379800) | `test_endpoint_candidate_ok` — status=ok / target_kind="candidate" |
| 알 수 없는 ticker (999999) | `test_endpoint_unknown_ticker_returns_short_error` — status=error / 짧은 안내 문구 / 내부 정보 미노출 |
| 잘못된 target_kind | `test_endpoint_invalid_kind_returns_short_error` — status=error |
| 응답 필드 화이트리스트 | `test_endpoint_response_does_not_leak_internals` — 6개 허용 필드 외 존재 X, LLM 관련 문구 미포함 |

preview_text 는 5 섹션 (대상·검토 맥락 / 확인된 근거 / 시장 참고 / 주의·미확인 / AI에게 추가로 물어볼 질문) 을 포함 (`test_build_preview_text_holding` / `test_build_preview_text_candidate`).

---

## 4. 생성 중 대상 변경 처리 결과 (지시문 §8.4 / AC-9)

`DecisionDraftPreviewCard.tsx` 의 요청 식별자 (`currentReqIdRef`) 로 처리:
- 요청 시작 시 `++currentReqIdRef.current` 로 새 id 발급.
- 응답 도착 시 시작 시점 id vs 현재 id 비교 → 다르면 응답 폐기.
- 대상 (targetKind, ticker) 이 바뀌면 `useEffect` 로 `result / error` 초기화 + id 증가.

늦게 도착한 이전 ETF 응답이 새 ETF 에 표시되지 않음.

---

## 5. 실패·시간 초과 화면 동작 (지시문 §8.6 / AC-10)

- `postDecisionDraftPreview` 는 `core.ts::request` 를 사용 — 기본 timeout 재사용. 새 timeout / retry / worker / queue 도입 0건.
- 실패 (`status: "error"` 또는 fetch reject) 시 카드 하단에 "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요." 단일 문구 노출.
- 기존 PENDING draft 로 fallback / raw evidence 대체 표시 / 이전 preview 재사용 0건.

---

## 6. 기존 VIX 카드 / 시장 요약을 수정하지 않은 사실 (AC-12)

이번 STEP 은 `HoldingsCompareView.tsx` + 그 산하 `holdings_compare/` 폴더에서만 변경:
- `HoldingsCompareView.tsx` — 보유 row 클릭 상태 추가 + 우측 상세 카드에 preview 카드 삽입.
- `holdings_compare/DecisionDraftPreviewCard.tsx` — 신규 카드.

변경하지 않은 파일 (지시문 §8.1 준수):
- `MarketDiscoveryView.tsx`
- `MarketContextCard.tsx`
- `MarketRiskReferenceCard.tsx`
- `MarketRiskReferenceCard` 안 VIX 20거래일 sparkline 로직
- 기존 보유·후보 표 구조 (테이블 header/row 기본 구조는 유지, `<tr onClick>` 이벤트만 추가)

---

## 7. 승인·OCI·Telegram 제외 사실 (AC-13 / §9)

- 승인 상태 필드 반영 0건 (기존 `Run.state` 흐름 미참조).
- OCI outbox / delivery 호출 0건.
- Telegram 발송 0건.
- 자동 BUY / SELL / HOLD 판단 0건.
- 새 ML factor / ML 축2 0건.
- 새 endpoint 는 오직 `POST /decision-draft/preview` 하나. 기존 endpoint 계약 변경 0건.
- 응답 필드 화이트리스트: `status`, `target_kind`, `ticker`, `preview_text`, `evidence_as_of`, `message`.

---

## 8. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 테스트 | **708 passed** (691 → 708, 전용 파일 17 케이스 (초기 12 + FIX r1 +2 + FIX r2 +1 + FIX r3 +2)) |
| black | PASS |
| flake8 | PASS |
| frontend lint | PASS |
| frontend build | PASS |

전용 테스트 파일 17 케이스 — `tests/test_decision_draft_preview.py` (초기 12 + FIX r1 +2 + FIX r2 +1 + FIX r3 +2):
- service 단위 5건: holding / candidate 텍스트 조립 / 금지 표현 미포함 / invalid kind / empty ticker
- endpoint 통합 7건: holding OK / candidate OK / unknown ticker error / invalid kind error / 응답 화이트리스트 / PENDING 미터치 / 외부 시세 미호출

---

## 9. 변경 파일 목록

**app/**:
- `decision_draft_preview_service.py`: 신규 (선택 ETF 텍스트 조립).
- `api_decision_draft_preview.py`: 신규 (`POST /decision-draft/preview`).
- `api.py`: 수정 (router include).

**tests/**:
- `test_decision_draft_preview.py`: 신규 (12 케이스).

**frontend/**:
- `lib/api/decisionDraftPreview.ts`: 신규 (API client).
- `lib/api/index.ts`: 수정 (barrel export).
- `app/components/holdings_compare/DecisionDraftPreviewCard.tsx`: 신규 (카드).
- `app/components/HoldingsCompareView.tsx`: 수정 (보유 선택 상태 + preview 카드 삽입).
- `app/globals.css`: 수정 (스타일 최소).

**docs/**:
- `STATE_LATEST.md`, `handoff/POC2_B_NEXT_ACTIONS.md`, `handoff/POC2_FEATURE_INVENTORY.md`: 수정.
- `handoff/POC2_DECISION_DRAFT_PREVIEW_V1_CONCLUSION.md`: 신규 (본 파일).

---

## 10. AC 충족 (지시문 §10)

| AC | 결과 |
|---|---|
| AC-1 보유·후보 각 1개 preview 생성 가능 | ✅ |
| AC-2 기존 PENDING 미터치 | ✅ (자동 테스트) |
| AC-3 새 DB 테이블 / 이력 저장 없음 | ✅ |
| AC-4 5구역 포함 | ✅ (`test_build_preview_text_holding`) |
| AC-5 세 기준일 분리 표시 | ✅ (응답 + 카드) |
| AC-6 미확인 상태 숨기지 않음 | ✅ (주의·미확인 섹션) |
| AC-7 구성종목 중복 not_loaded 자동 조회 없음 | ✅ (`_build_holding_evidence_lines`) |
| AC-8 외부 시세·ML 실행 시작 없음 | ✅ (자동 테스트) |
| AC-9 대상 변경 시 이전 결과 미표시 | ✅ (요청 식별자 폐기) |
| AC-10 실패 시 짧은 오류 + 재시도 | ✅ (FAILURE_TEXT) |
| AC-11 보유·후보 각각 성공·미확인·실패·대상 변경 | ✅ (테스트 커버) |
| AC-12 시장 요약 / VIX 카드 미수정 | ✅ |
| AC-13 자동 매매·승인·OCI·Telegram·ML 변경 없음 | ✅ |
| AC-14 backend / black / flake8 / frontend lint / build | ✅ |

---

## 10.1 FIX r1 (2026-07-03, 사용자 화면 이슈)

**증상**: 실제 UI 에서 보유 ETF `367760` (RISE 네트워크인프라) 선택 후 preview 생성 시 "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요." 오류 표시.

**원인**: `app/api_decision_draft_preview.py::_load_holdings_evidence` 안에서 `from app.holdings import load_holdings_from_file` 로 존재하지 않는 심볼 import. 실제 함수는 `app.holdings.load()`. broad `except Exception` 이 ImportError 를 삼켜 사용자에게는 일반 실패 문구만 노출됨.

**초기 자동 테스트 사각지대**: `stub_evidence` fixture 가 `_load_holdings_evidence` / `_load_candidate_evidence` 를 stub 으로 대체하여 실제 import path 를 검증하지 않았음.

**FIX r1 코드 수정**:
- `from app.holdings import load as load_holdings` 로 정정.
- broad except 안에 `logger.warning(traceback.format_exc())` 추가.

**FIX r2 (일부만 유효)**:
- `hasattr` 기반 심볼 assert 테스트 추가. 모듈 네임스페이스에 옛 오타 심볼이 존재하는지 여부는 확인 가능.
- **한계 (검증자 지적)**: `_load_holdings_evidence` 함수 **내부의 잘못된 import 문** 이 재도입되면 broad except 가 ImportError 를 삼켜 함수는 여전히 None 반환. hasattr 테스트로는 이 회귀를 직접 감지하지 못함.

**FIX r3 (r2 한계 근본 해소)** — 설계자 승인 (Option A + C):
- **코드**: `_load_holdings_evidence` / `_load_candidate_evidence` 의 broad `except Exception` 을 삭제하고, 데이터 오류 (`FileNotFoundError` / `json.JSONDecodeError` / `HoldingsValidationError` / `sqlite3.Error`) 만 catch 하여 `None` 반환. 프로그래머 오류 (`ImportError` / `AttributeError` / `TypeError` / `NameError` / `ModuleNotFoundError`) 는 **삼키지 않고 propagate**.
- **endpoint 경계**: `post_decision_draft_preview` 안에서 loader 호출을 `try/except Exception` 으로 감싸 프로그래머 오류도 catch 하되, **사용자 응답 body 는 계약 그대로** (`status="error"` + "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."). traceback 은 endpoint 안 logger.error 로 서버 로그에만 기록.
- **테스트가 실제로 보장하는 범위**:
  - `test_load_holdings_evidence_propagates_programmer_error` / `test_load_candidate_evidence_propagates_programmer_error` — `monkeypatch.delattr(app.holdings, "load")` 후 loader 호출 시 `AttributeError / ImportError / TypeError` 중 하나가 propagate 됨을 assert. 심볼 오타 재도입 시 loader 직접 호출 테스트가 실패한다.
  - `test_endpoint_maintains_user_friendly_response_on_programmer_error` — loader 를 `raise ImportError(...)` 로 monkeypatch 한 상태에서 endpoint 응답이 여전히 `status_code=200 / status="error" / 짧은 문구` 이며 body 에 `ImportError` / `traceback` 문자열이 미노출됨을 assert.
  - `test_load_*_returns_dict_or_none_in_normal_state` — 정상 상태 스모크 (이 자체로는 오타를 잡지 못함).
- **실측 셀프 검증 (Bash)**: `del app.holdings.load` 후 (1) loader 직접 호출 → `ImportError` propagate 확인, (2) endpoint 호출 → `status=error` + body 에 `ImportError` / `Traceback` 미노출 확인.

**정직한 검증 범위 요약**:
- ✅ loader 직접 호출 테스트가 import / symbol 오류 (프로그래머 오류) 를 잡는다.
- ✅ endpoint 는 프로그래머 오류가 발생해도 사용자 친화 실패 응답 (`status="error"` + 짧은 문구) 을 유지한다.
- ✅ 응답 body 에 traceback / 심볼 정보 미노출.
- ⚠️ hasattr 심볼 assert 만으로는 함수 내부 import 회귀를 직접 감지하지 못한다는 r2 한계는 r3 의 propagate 방식으로 대체 해소됨.

**실측 확인**: 기본 SQLite + holdings_latest.json 상태에서 loader 가 실제 dict 반환 확인 (RISE 네트워크인프라 367760). `TestClient` 를 통한 endpoint 실호출도 `status=ok` 확인.

**backend 전체 테스트 경과**: 초기 703 → FIX r1 후 705 → FIX r2 후 706 → FIX r3 후 **708 passed**. 전용 테스트 파일은 초기 12 → r1 후 14 → r2 후 15 → r3 후 17 케이스.

---

## 11. 알려진 한계 (Known Limits)

### 11.1 preview 는 LLM 미사용 결정적 텍스트

- 상태: Q1 확정 답변. 사용자가 결과를 복사해 외부 AI 웹사이트에 입력하여 해석 요청.
- 이번 STEP 은 LLM / API 키 / 프롬프트 / 모델 메타데이터 없음. 후속 STEP 에서 LLM 연동을 결정할 경우 신규 논의.

### 11.2 preview 는 SQLite / 기존 서비스 스냅샷 시점 기준

- `compute_topn()` 등 기존 read only 함수를 각 요청마다 호출 — 캐시 X.
- 요청 시점의 SQLite 상태를 반영.

---

## 12. 다음 작업 후보 (사용자 결정 대기)

1. **위험 evidence / 시장 국면 / 추세 전환 거리** — 본 STEP 확보 evidence 위에서 진입.
2. **ML 축2** (위험 감지).
3. **선택 ETF preview 를 외부 LLM 웹으로 복사하는 안내 UI** (선택 사양).
4. 기타 BACKLOG 항목.
