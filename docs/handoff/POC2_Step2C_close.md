# POC2 Step 2C 종결 — Holdings UI Compaction & Account Grouping

작성일: 2026-04-29
작성자: 개발자(VSCode Claude)
상태: 구현 + 자동 검증 게이트 통과 (black/flake8/pytest 76 passed/frontend lint+build). Codex 검증 1라운드 REJECTED → 보고 정확성(섹션 2 git status 일치) 수정 후 완료 처리. 운영 E2E 자연 검증은 다음 사용자 실행 시점에서 발생.
대상 독자: 다음 챕터 진입자

---

## 1. 단계 목적 (한 줄)

보유 종목이 많아도 화면에서 읽을 수 있게 압축하고, holdings 를 계좌 그룹별로 구분할 수 있게 한다. Telegram / OCI / 상태 모델은 건드리지 않는다.

---

## 2. 사용자(설계자) 결정 사항 반영

| Q | 결정 | 적용 위치 |
|---|---|---|
| holding_id 도입 여부 | 도입 안 함. holdings_latest.json 스키마 변경 최소화 | `app/holdings.py::Holding` |
| React key 조합 | source_index + ticker + account_group + avg_buy_price | HoldingsClient / RunPanel |
| 입력 UX | HTML `<datalist>` (추천값 5개 + 직접 입력) | `frontend/app/components/HoldingsClient.tsx` |
| 계좌별 요약 표시 순서 | 첫 등장 순(insertion order) | `groupByAccount` |
| compact table 정렬 | holdings 배열 순서 그대로 | 자동 정렬 미도입 |
| 계좌별 요약 위치 | 항상 펼친 상태 + compact summary rows. 흐름: 전체요약 → 계좌별요약 → compact table | `OverallSummaryCard` / `AccountSummaryCards` / `CompactHoldingsTable` |
| 정규화 진입점 | 단일 helper `normalize_account_group` 1곳. 저장/draft/load 모두 거침 | `app/holdings.py` |
| 중복 정책 | (ticker, account_group, avg_buy_price) 삼중조합만 차단 (분할매수 허용) | `validate_holdings` |
| 시세 확인 vs 평가 계산 | Step 2B `_is_priced` ≠ `_is_calc_available` 그대로 재사용. 계산은 calc_available 만 | `compute_summary` / `computeSummaryFor` |
| Telegram message compaction | 변경 없음 — Step 2B 정책 그대로 유지 | `app/draft_message.py` 미수정 |

---

## 3. account_group 정책 (Step 2C 핵심)

### 3.1 의미
- 사용자가 보유 종목을 어떤 계좌 그룹으로 볼지 구분하는 표시용 라벨이다.
- 세금/법적 계좌 판정값이 아니다. 실제 계좌번호도 아니다. 증권사 API 연동값이 아니다.

### 3.2 기본 추천값
일반 / ISA / 연금 / 오픈뱅킹 / 기타. 사용자 직접 입력 허용 예: 키움-일반, 토스-일반, 미래-ISA, 연금저축-삼성.

### 3.3 정규화 / 검증 (백엔드 단일 helper)
```
normalize_account_group(value):
  None / "" / 공백        → "일반"
  문자열 아님              → HoldingsValidationError
  trim 후 30자 초과        → HoldingsValidationError (조용히 자르지 않는다)
  isa / Isa / ISA          → "ISA"
  일반 / 연금 / 오픈뱅킹 / 기타 → trim 후 표준 표기
  그 외 사용자 커스텀      → trim 만 (의미 변경 금지, 예: "Kiwoom-ISA" 그대로)
```
프론트엔드 `maxLength=30` 은 보조 방어. 최종 책임은 백엔드.

### 3.4 하위 호환성
- 기존 `state/holdings/holdings_latest.json` 의 항목에 `account_group` 키가 없어도 백엔드 `_coerce_holding` 에서 "일반" 으로 정규화. 파일 자체 강제 마이그레이션 안 함 (다음 [보유 종목 저장] 시 자연 발생).
- 과거 run 의 `draft_payload.recommendations[]` 에 `account_group` / `source_index` 가 없어도 RunPanel 의 `normalizeRec` 가 "일반" / 행 인덱스 fallback 으로 안전 렌더.

---

## 4. UI 구조 (Step 2C 재편)

### 4.1 흐름
```
1. 보유 종목 입력 폼 (HoldingsClient.tsx 상단)
   - 컬럼: 종목코드 / 종목명 / 계좌(datalist) / 수량 / 매입단가 / 매입금액 / 매입비중 / 삭제
   - 계좌 빈 값 → 백엔드에서 "일반" 정규화

2. 시세평가 섹션 (HoldingsClient.tsx 하단, 저장된 holdings 기준)
   ├─ 전체 요약 카드 (OverallSummaryCard)
   │   · 보유 종목 수 / 시세 확인·미확인 / 계산 정보 부족(있을 때만) / 총 매입금액
   │   · 평가금액·평가손익·평가수익률 (평가 계산 N개 기준 라벨, calc_available_count > 0 일 때만)
   │   · "계산 불가" (calc_available_count == 0 일 때)
   │   · ⚠ 경고 (시세 미확인 또는 계산 정보 부족 종목 있을 때)
   ├─ 계좌별 요약 (AccountSummaryCards)
   │   · 첫 등장 순. 계좌별 시세 확인/미확인/계산 정보 부족 카운트 + 총 매입금액 + 평가지표.
   │   · 계좌의 시세 확인 0개 → "계산 불가"
   └─ Compact Holdings Table (CompactHoldingsTable)
       · 컬럼: ▶ / 계좌 / 종목 / 손익(평가손익+수익률) / 시장비중 / 판단 / 상태
       · 행 클릭 또는 ▶ 클릭 → 상세 펼침 (DetailRowFields: 수량/단가/매입금액/매입비중/현재가/평가금액/기준시각/출처)
       · 펼침 기본 접힘. 동일 run polling 데이터 갱신 시 동일 항목 펼침 상태 유지.

3. 승인 화면 (RunPanel.tsx, run 생성 후 같은 compact UI 재사용)
   - draft_payload.recommendations[] 를 normalizeRec 으로 정규화 후 동일 구조 표시.
```

### 4.2 React key 정책
- compact row key = `${source_index}|${ticker}|${account_group}|${avg_buy_price}`
- ticker / account_group + ticker / run_id + ticker + account_group 만으로 만들지 않는다 (분할매수 충돌).
- 과거 payload 에 source_index 가 없으면 normalizeRec 가 행 인덱스로 fallback.

### 4.3 펼침 상태 유지 메커니즘
- 컴포넌트 메모리 `Set<string>`.
- items / recs 갱신 시 `useEffect` 가 유효한 키만 보존하고 사라진 키만 정리.
- 새 run 으로 전환되면 컴포넌트 remount 로 자연 초기화.

---

## 5. 변경 / 신규 파일

수정 (9건, git tracked):
- `app/api.py` — HoldingItem.account_group / EnrichedHoldingResponse.account_group / source_index
- `app/holdings.py` — Holding.account_group, normalize_account_group helper, 중복 정책 완화, load 하위 호환
- `app/holdings_enrich.py` — EnrichedHolding.account_group / source_index, to_recommendation_dict 출력에 두 키 포함
- `tests/test_poc1_loop.py` — Step2C 신규 13건 + 기존 2건(중복 정책 / expected_keys) 갱신
- `frontend/lib/api.ts` — HoldingItem / EnrichedHolding 타입 확장
- `frontend/app/components/HoldingsClient.tsx` — 입력폼 account_group + datalist + maxLength=30, EnrichedSection 을 OverallSummaryCard + AccountSummaryCards + CompactHoldingsTable 구조로 전면 교체
- `frontend/app/components/RunPanel.tsx` — HoldingsCompactView + normalizeRec 호환, 동일 compact UI, polling 펼침 상태 유지
- `frontend/app/globals.css` — summary-card / account-summary / compact-table / detail-fields / pnl 색상 등 스타일
- `docs/backlog/BACKLOG.md` — POC2 Step 2C deferred 12건 추가 (요청 11건 + 프론트 공용 모듈 추출 1건)

git 외 작업:
- `docs/handoff/NEXT_SESSION_HANDOFF.md` — 새 세션 진입 지시문에서 명시 요청된 1회용 인계 문서 삭제. 이전 세션 untracked 상태에서 만들어진 파일이라 git status 에 흔적 없음.

---

## 6. 검증 게이트 통과 기록

```
.venv/Scripts/black.exe --check app/ tests/   → exit 0 (16 files unchanged)
.venv/Scripts/flake8.exe  app/ tests/         → exit 0
.venv/Scripts/python.exe -m pytest tests/ -q  → 76 passed (기존 63 + Step2C 신규 13)
cd frontend && npm run lint                   → PASS
NEXT_PUBLIC_API_BASE=... npm run build        → PASS (4 static pages)
```

테스트 추가 항목 (13건):
- `test_step2c_account_group_default_when_missing`
- `test_step2c_account_group_custom_persisted`
- `test_step2c_account_group_blank_normalized_to_general`
- `test_step2c_account_group_over_30_chars_rejected`
- `test_step2c_account_group_default_label_case_normalized`
- `test_step2c_account_group_normalize_helper_unit`
- `test_step2c_holdings_load_legacy_file_without_account_group`
- `test_step2c_duplicate_policy_allows_split_avg_price`
- `test_step2c_duplicate_policy_blocks_exact_triple`
- `test_step2c_new_draft_payload_includes_account_group`
- `test_step2c_old_draft_payload_without_account_group_still_loadable`
- `test_step2c_old_draft_payload_renders_through_run_endpoint`
- `test_step2c_calc_missing_not_zeroed_per_account_group_aggregation`

---

## 7. Codex 검증 결과 처리

1라운드: REJECTED — A-2 보고 정확성(섹션 2 의 NEXT_SESSION_HANDOFF.md 삭제가 git status 와 불일치).
조치: 코드 수정 0건. 보고서 섹션 2 를 git status 결과와 1:1 일치하도록 갱신, "git 외 작업" 으로 분리 표기. JSON `known_limits` 에 처리 메모 추가.
B-2 / B-3 (UI 로직 중복 / 파일 책임 과다, 경미): 코드 변경 없이 BACKLOG "프론트 compact UI 공용 모듈 추출" 1건으로 등재. 트리거(동시 변경 2회 / 동일 버그 / ~600 라인) 발생 시 별도 STEP 진입.

---

## 8. 알려진 한계 / 미완성

- 운영 E2E 자연 검증 미수행 — 사용자 디바이스에서 [시세 갱신] → 초안 → 승인 → Telegram 수신 시각 검증은 다음 사용자 실행 시점.
- UI 자동 브라우저 테스트 미도입 — compact table / polling 펼침 상태는 코드 구현만. 자동 UI 테스트 추가는 별도 STEP / BACKLOG.
- compact table 의 "판단" 컬럼은 holdings 단계 정책상 'HOLD' 고정.
- 모바일 협소 화면은 가로 스크롤만 (BACKLOG).
- 펼침 상태는 컴포넌트 메모리만 — F5 / 새 run 전환 시 초기화 (BACKLOG).
- 기존 holdings_latest.json 의 account_group 누락은 다음 [보유 종목 저장] 시 자연 마이그레이션. 강제 재작성 스크립트 미제공.

---

## 9. 다음 챕터 진입자에게

### 건드리지 말아야 할 것 (Step 2C 까지 확정 계약)
- 5 state 모델 / 4필드 draft_payload / handoff 5필드
- holdings 식별 규약 (recommendations 첫 항목에 quantity 또는 avg_buy_price)
- 외부 fetch 는 `POST /market/refresh` 단 1곳에서만
- draft_payload 메타 flag(`price_missing/calc_missing`) 추가 금지
- `_is_priced` ≠ `_is_calc_available` 분리. 평가 집계는 calc_available 만
- action 은 'HOLD' 고정. score 도입 금지
- Telegram 메시지 compaction 정책 (Step 2B). 종목별 매입 상세 추가 금지
- 메시지 split / snapshot / history / 전일 대비 변화 감지 도입 금지
- "실시간" 단어 사용 금지
- account_group 은 표시/그룹용 라벨. 계좌번호/세금/증권사 API 로 확장 금지
- React key 정책: source_index + ticker + account_group + avg_buy_price 4 요소 모두 포함
- 동일 ticker 분할매수(같은 account_group 다른 avg_buy_price) 허용 — 단일 ticker 차단으로 되돌리지 말 것

### 즉시 진행 가능한 후보
- (A) 운영 E2E 자연 검증 — 사용자 디바이스에서 18+ 종목 실 Telegram 수신 형식 확인
- (B) POC2-Step2A — pykrx EOD fallback (BACKLOG 트리거 충족 시)
- (C) ML 연결 / factor 추천 (Phase 1 격리 모듈 활용)
- (D) 프론트 compact UI 공용 모듈 추출 (BACKLOG 트리거 충족 시)

---

## 10. 한 줄 당부

POC2 Step 2C 의 핵심 — **account_group 은 라벨이고, compact table 은 가독성이며, 누락은 0 이 아니다** — 를 깨지 말고 위에 쌓아라. 계좌 라벨에 계좌번호/세금 의미를 부여하는 순간, 이번 단계가 의도적으로 미룬 11+ deferred 가 한꺼번에 살아난다.
