# POC5-UI-02 개발 결과서 — EXISTING_CHECK_FLOW_CORRECTIONS (기존 보유 점검 화면 정정)

작성 2026-10-12 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS            = IMPLEMENTED_VERIFIED_CLOSED(2026-10-12) — 1차 = 검증자 VERIFIED(2026-10-12 · 위험 NONE · 범위 폭주 NONE · 격리 사본 vitest 414 · tsc · eslint 0 · 결과서 §4-2 · §6-4 표현은 검증자가 직접 정정 = §6-3) · 설계자 RESULT PASS(2026-10-12) · 커밋 `9cfb535f` push · 실화면 = 계약 항목 통과 · 사용자 의견 2건 → 설계자 보완 판정(2026-10-12 · 설계서 §11 · UI-02 안에서 보완 · PLAN 재제출 · 재판정 없음) → 보완 로컬 구현(§11-2) → 검증자 변경분 VERIFIED(2026-10-12 · 위험 NONE · 범위 폭주 NONE · 격리 사본 vitest 423 · tsc · eslint 0 · 머리 BASE_COMMIT · SCOPE 는 검증자가 직접 정정 = §11-3) → 실화면 통과(2026-10-12 · 사용자 새로고침 확인 · 'KODEX200 대비' 정렬 제거 확인 뒤 네 가지 유지 결정 · §11-2 7)) → 보완 · 종료 커밋 push(사용자 승인 2026-10-12 · 커밋 번호 = `git log`) → 종료 · 인계 `docs/handoff/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_HANDOFF_2026-10-12.md`(§12)
DESIGNER_RESULT   = PASS(2026-10-12 · 재작업 0 · 결과서 §4 추가 변경 6건 수용 · §5 한계 수용 · 두 카드 제거 · 파일 삭제 계속 보류 · 거래량 · 종합 위험 감지 · seed · FDR 보호는 종료 범위와 구분 · OCI pull 없음) — 원문 = 설계서 §10 · 끝에 전달문 원문
STEP_ID           = POC5-UI-02 기존 보유 점검 화면 정정
DESIGN            = docs/ai_design/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_DESIGN_V1.md (V1 개정 1 · §9 설계자 PLAN 부분 판정 PARTIAL_PASS 원문 · 끝에 전달문 원문 2건)
PLAN              = docs/ai_plan/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_PLAN_V1.md (판정 반영 = 본문 정정 + §7)
INPUT             = docs/ai_design/POC5/POC5_BACKLOG_AND_REMAINING_FEATURES_REVIEW_2026-10-12.md(설계자 리뷰) · docs/ai_result/POC5/POC5_BACKLOG_SOURCE_AUDIT_2026-10-12.md(개발자 현행 소스 대조)
BASE_COMMIT       = 1차 d7d365f4 / 보완 9cfb535f
SCOPE             = 1차 frontend 화면 7파일 · 시험 3파일 · 관리 문서 5개 / 보완 frontend 화면 2파일 · 시험 2파일 · 문서 5개(총 9개 · §11-2). backend · API · DB · 수집 · 의존성 · cron · OCI 변경 0
NOT_DONE_BY_DECISION = 「오늘의 투자 점검」 '개발 중인 판단 기능' · '코스피 상세 지표' 두 안내 카드 제거 · 두 컴포넌트 삭제 · 관련 CSS 삭제(판정 §4-5 보류 — 카드 파일 · TodayInvestmentCheckView.tsx · globals.css 변경 0)
CHECKS            = 1차 tsc exit 0 · eslint exit 0 · vitest 33파일 414 passed(직전 406 → +8) · 화면 변이 8/8 검출 — §8 / 보완 tsc exit 0 · eslint exit 0 · vitest 33파일 423 passed(414 → +9) · 변이 10/10 검출 — §11-2
REVIEW            = 독립 검토 1회(읽기 전용) — 정렬 · 이동 · 카드 미변경 · 판정 준수 확인 · 지적 MEDIUM 3 · LOW 6 → 모두 반영(§6-2)
MOCKUP            = 없음(설계 §7 · 새 폼 · 창 없음)
```

## 0. 요약

- **「확인 근거」 사용자 선택 정렬** — 지금 **네 가지**: 평가 비중(큰 값부터) · 손익률 · 5일 변화(기본) · 20일 변화(작은 값부터). 1차(커밋 `9cfb535f`)는 'KODEX200 대비'까지 다섯이었고, 20일 변화와 순서가 같아 설계자 보완 판정으로 정렬 선택만 뺐다(값 표시는 그대로 · §11-2). 화면 숫자 그대로 정렬한다. 값이 없는 종목은 맨 뒤에 두고, 같은 값끼리와 값 없는 행끼리는 원래 순서를 지킨다. 행을 빼지 않고 다시 조회하지 않는다. 컨트롤은 「보유 현황」 정렬과 같은 양식이다.
- **종목 상세의 사유 · 이동**: 「확인 근거」 종목 상세의 버튼이 「개발·실험용」(`diagnostics`)이 아니라 **「데이터 상태」(`data_status`)** 로 간다. 1차 문구 '데이터 상태에서 원인 확인 →'는 보완 판정으로 **'전체 ETF NAV·괴리율 보기 →'** 로 바꾸고, 선택 종목의 사유는 상세 맨 위 **'자료 확인 안내'** 에서 바로 보인다(§11-2).
- **「오늘의 투자 점검」 최대 3개 설명**: '내가 가진 ETF' 목록 위에 '최근 5거래일 변화가 낮은 보유 ETF부터 최대 3개'(목록이 있을 때만). 선정 함수 · 숫자 변경 0. 'backend PUSH 와 동일 규칙' 주석을 PC(5거래일) · OCI 보유 브리핑(20거래일 하락 구간)이 다르다는 내용으로 고쳤다.
- **기록 정리**: 대조표에서 근거가 확인된 행만 BACKLOG · STATE · PROGRAM_TRUTH · 통합지도 · README 에 '2026-10-12 · POC5-UI-02' 정정으로 남겼다. 옛 설계 · 결과서 판정 원문은 바꾸지 않았다.
- **두 안내 카드는 그대로**(설계자 판정). 문서에도 화면 제거 · 기능 요구 폐기로 쓰지 않았다. 거래량 흐름 · 종합 위험 감지 = 미구현 요구 · 보완 후보, 공격·방어 · SuperTrend = 미구현 · 기존 제외 기록 · 불필요 입증 아님으로 구분했다.

## 1. 처리한 요구사항

| 항목 | 상태 | 근거 |
|---|---|---|
| 설계 §3-1 · 판정 §4-1 · 4-2 다섯 정렬(키 · 방향 · 결측 맨 뒤 · 동점 · 결측끼리 원래 순서 · 행 보존 · 재조회 0 · 기본 5일 · 손익률 = `pnl_rate_pct`) | DONE | `holdings_risk_evidence/helpers.ts :: sortEvidenceRows · SORT_SPEC · EVIDENCE_SORT_OPTIONS · DEFAULT_EVIDENCE_SORT` · `HoldingsRiskEvidenceSection.tsx` · 시험 §8 |
| 설계 §3-1 제목 · 부제 일치(위험 순위 표현 없음) | DONE | `HoldingsEvidenceView.tsx` 부제 '보유 ETF의 수치와 확인 근거입니다.' · 정렬 이름 · 힌트에 '위험' · '순위' 없음(시험) |
| 설계 §3-1 기존 선택 컨트롤 양식 · UI-01 선택 묶음 예외 | DONE | `.holdings-sortbar` · `.holdings-sort-seg`(「보유 현황」 정렬과 같은 클래스 · `globals.css` 변경 0) |
| 설계 §3-2 · 판정 §4-3 원인 확인 → 데이터 상태 | DONE | `HoldingsRiskEvidenceSection.tsx` `onNavigate("data_status")` · 문구 · 시험(이전에는 이동 시험 0) |
| 설계 §2 끝 · 판정 §4-3 최대 3개 설명 · 주석 정정 | DONE | `today/JudgmentQueueSection.tsx` · 시험(목록 있을 때만 · 없으면 안 보임) |
| 설계 §5 · 판정 §4-4 확인된 기록 정리 | DONE | §2 · §4-1 표 |
| 설계 §2 두 카드 제거 · 파일 삭제 · CSS 삭제 · '카드 없음' 시험 | NOT_DONE(판정 §4-5 보류) | 카드 파일 · `TodayInvestmentCheckView.tsx` · `globals.css` · 기존 카드 시험 변경 0 |
| 설계 §6 seed 차이표 | DONE(읽기 전용 · PLAN 부록) | 교체 승인 아님 · 파일 쓰기 0 |
| 설계 §6-1 FDR 보호 | 조건부 후속 유지(구현 0) | BACKLOG · STATE · PROGRAM_TRUTH 에 OCI 해소 · PC 잔여 · 조건부로 기록 |

## 2. 변경된 파일 목록

- 화면(수정)
  - `frontend/app/components/holdings_risk_evidence/helpers.ts`(정렬 helper 추가 · 기존 함수 변경 0)
  - `frontend/app/components/HoldingsRiskEvidenceSection.tsx`(정렬 상태 · 정렬 막대 · `shownRows` 정렬 · 이동 대상 · 문구 · 머리 주석)
  - `frontend/app/components/HoldingsEvidenceView.tsx`(부제 · 머리 주석)
  - `frontend/app/components/today/JudgmentQueueSection.tsx`(최대 3개 설명 · 안내 문장 · 주석)
  - `frontend/app/components/LeftSidebar.tsx`(「확인 근거」 메뉴 아래 안내 '오늘 먼저 볼 ETF와 근거' → '보유 ETF의 수치와 확인 근거')
  - `frontend/app/components/HoldingsView.tsx`(「보유 현황」 부제의 확인 근거 안내 문장 — 같은 표현으로)
  - `frontend/app/components/MainPanel.tsx`(주석)
- 시험(수정)
  - `frontend/app/components/holdings_risk_evidence/helpers.test.ts`(+4)
  - `frontend/app/components/HoldingsRiskEvidenceSection.test.tsx`(+4)
  - `frontend/app/components/TodayInvestmentCheckView.test.tsx`(기존 2개 시험에 단언 추가 · 카드 시험 변경 0)
- 문서
  - 신규: 설계서(사용자 전달 원문 + §9 판정 · 전달문) · PLAN · 이 결과서 · 설계자 리뷰 보관본 · 현행 소스 대조표
  - 수정: `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md` · `docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md` · `docs/README.md`
  - 수정(앞 단계 잔여): `docs/ai_plan/POC5/POC5-08_..._PLAN_V1.md`(price_basis 접미 '자산 분류' → '종목 구분 출처' 표현 정정 · R1 실행 중 발견)

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경

1. **정렬 힌트 한 줄**: 정렬 막대 오른쪽에 '큰 값부터 / 작은 값부터 · 값이 없는 종목은 맨 뒤'(선택에 따라). 「보유 현황」 정렬의 힌트(`holdings-sortbar-hint`)와 같은 양식이다. 위험 · 순위 표현 없음.
2. **통합지도 상태 칸 1곳 변경 · 2곳 메모 추가**: P-19는 '후속 개발' → '**부분 완료**'. B-038 · B-103은 독립 검토 반영 뒤 판정 값 '후속 개발'을 유지하고, 메모에 원장 요구분 구현을 기록했다(§6-2 M3). 근거는 POC5-01B ~ 04 원장 · 가격 결과 · 동기화 · R0/R1 구현과 운영 확인(2026-10-08 · 10-12)이다. 성과 해석 · 좋은 기간 선정은 미완료로 함께 적었다. 설계 §5 'B-038/B-103 현행 범위 반영'의 해석이다 — 검증자 · 설계자 확인 대상(§6).
3. **BACKLOG PARAM 항목 줄 위치 정정**: '처리' 2줄이 '항목' 줄 앞에 있어 바로 위 'runtime data source 확장' 항목에 붙어 보였다(대조표 지적). 두 줄을 PARAM 항목 아래로 옮겼다(내용 변경 0).
4. **POC5-08 PLAN 표현 정정 1건**(앞 단계 잔여 · stage 상태로 이어짐 · 위 §2).
5. **같은 표현 맞춤 2곳**(독립 검토 지적 · 설계 §3-1 '제목 · 부제 일치'): 「확인 근거」 메뉴 안내 · 「보유 현황」 부제가 「확인 근거」를 '오늘 먼저 볼 ETF와 근거'로 부르고 있어 '보유 ETF의 수치와 확인 근거'로 맞췄다.
6. **유한수가 아닌 값 처리**(독립 검토 지적 · 운영에서는 도달 불가): 응답에 `eval_amount` 칸이 아예 없으면 종목 통합이 손익률 · 비중을 NaN 으로 만들어 정렬 전체가 어긋날 수 있다. NaN 도 '값 없음'처럼 맨 뒤에 둔다(값을 만들어 내지 않음). 실제 backend 는 `eval_amount` 를 늘 null 기본값으로 직렬화한다.

## 5. 알려진 한계 / 미완성

1. **두 안내 카드는 사실과 다른 문구를 그대로 담는다**(판정으로 보류): '거래량 자료 미저장'(ETF · KODEX200 은 저장 중) · 공격·방어 · SuperTrend '후속 단계 검토' 등. 다음 설계 결정 때 다룬다.
2. **PC FDR 수동 갱신 보호 = 조건부 후속**(설계 §6-1 · 구현 0).
3. **seed 정합 = 사용자 결정 대기**(PLAN 부록 차이표 · 파일 쓰기 0).
4. `holdings_risk_evidence/helpers.ts :: lowestFiveDayRows` 는 이전부터 시험에서만 쓰이며 이번 정렬 규칙과 달라 재사용하지 않았다(손대지 않음).
5. **두 화면의 위쪽 순서가 다를 수 있다**(계약대로): 「확인 근거」 기본 5일 정렬은 '자료 확인 필요'(부분 자료 · 계좌 간 값 다름) 행도 값이 있으면 넣고 동점은 들어온 순서로 둔다. 「오늘의 투자 점검」 최대 3은 backend `select_top_holdings` 가 정상 상태 행만 고르고 동점은 종목코드 순서다. 그래서 두 화면 맨 위 종목이 다를 수 있다.

## 6. 다음 검증자(Codex)에게 알릴 점

1. **카드 미변경 확인**: `git diff` 에 `today/InDevelopmentSection.tsx` · `today/KospiDetailSection.tsx` · `TodayInvestmentCheckView.tsx` · `globals.css` 가 없다.
2. **정렬 규칙**: `sortEvidenceRows` 는 `(행, 들어온 순번)` 쌍으로 정렬해 같은 값 · `null` 끼리 들어온 순서를 지킨다. 입력 배열은 바꾸지 않는다. `null` 은 어느 방향에서나 맨 뒤다. 키 → (칸 · 방향)은 `Record<EvidenceSortKey, …>` 라 모르는 키에 대체 정렬이 없다.
3. **정렬 위치**: 빠른 보기('전체 / 자료 확인 필요') 필터 뒤에 정렬한다. 선택한 종목 상세(`selected`)는 정렬과 무관하다.
4. **문서**: 정정한 모든 줄은 '2026-10-12 · POC5-UI-02' 표기와 대조표 근거를 단다. 통합지도 P-19 상태 변경 · B-038/B-103 현행 구현 메모 추가(§4-2)와 P-12 · P-13 문구('제외 기록은 두되 재검토 가능 · 불필요 입증 아님')가 판정 §2 · §3 범위 안인지 봐 주시면 좋다.
5. BACKLOG 등록 항목 = **62**(`grep -c "^- \*\*항목\*\*" docs/backlog/BACKLOG.md` · 61 + 01B 누락 1줄).

### 6-2. 독립 검토(2026-10-12 · 읽기 전용 · 1회) 반영

| # | 지적 | 처리 |
|---|---|---|
| M1 | 동점 · 결측끼리를 종목코드 순으로 바꾸는 변이 · 표시값(소수 둘째 자리)으로 정렬하는 변이가 시험에서 살아남음(시험 자료 입력 순서가 우연히 알파벳 순 · 1.234 / 1.236 은 표시로도 다름) | 수정 — 입력을 종목코드 역순으로 · 1.2349 / 1.2341(둘 다 1.23) · 변이 재실행으로 검출 확인(§8) |
| M2 | PROGRAM_TRUTH FDR 파일 목록에 `market_benchmark_store.py`(지금 FDR 0) 잔존 · BACKLOG 는 '줄 번호가 다르다'고만 씀 | 수정 — 지금 FDR 호출 파일로 정정(`market_benchmark_batch.py` · `market_timeseries_naver_yahoo_adapter.py` · `kospi_history_closeout.py` · `vix_ingest.py`) · OPS-03 `7feddf2c` 이동 기록 |
| M3 | 통합지도 P-19 · P-20 · B 행의 근거를 'PLAN 판정 §2 · §3'으로 잘못 인용 · §6 판정 값에 없는 '부분 완료'를 B-038 · B-103 에 씀 · 합계 줄 낡음 | 수정 — 근거를 STATE(01B ~ 04 · 08 운영 확인 · POC4 결과) · 연구 결과서 · 대조표 §5-3 로 정정 · B-038 · B-103 판정 값은 '후속 개발' 그대로 두고 메모로 '현행 = 원장 요구분 구현' · 합계 줄에 '7-31 판정 값 · 이후는 행별 메모' 표기 · P-19 는 P 표의 기존 값 '부분 완료'(P-06 과 같은 값) 유지 |
| L4 | BACKLOG PARAM 옮긴 줄의 공백 누락 · '바로 위 항목 끝에 붙어 보였다' 설명 부정확 | 수정 — 공백 복원(내용 변경 0) · 설명을 'grep 으로 항목을 나누면 위 항목에 붙은 것처럼 잡힘'으로 |
| L5 | 「확인 근거」를 '오늘 먼저 볼 ETF와 근거'로 부르는 화면 문구 2곳 · 주석 1곳 잔존 | 수정 — §4-5 |
| L6 | 「확인 근거」 기본 정렬과 오늘 화면 최대 3 의 위쪽 순서가 다를 수 있음 | 한계로 기록(§5-5 · 계약대로) |
| L7 | 정렬 뒤 선택 상세 유지 · 방향 안내 문구 단언 없음 · 이동 시험 act 경고 | 수정 — 시험 2건 추가 · act 감쌈(경고 0) |
| L8 | NaN 이 정렬을 깨뜨림(운영 도달 불가) | 수정 — §4-6 · 시험 1건 |
| L9 | 주석 · 인용 사소(OCI 선정에 자료 확인 불가 포함 · '§229'는 줄 번호 · PLAN `:8`→`:9` · BACKLOG 10-12 줄이 10-11 줄 앞) | 수정 |

### 6-3. 검증자 문서 정정 (2026-10-12)

§4-2와 §6의 4번에 독립 검토 전 표현이 남아 있어 실제 통합지도와 대조해 정정했다. 상태 칸 변경은 P-19 한 곳이며, B-038 · B-103은 '후속 개발'을 유지하고 현행 구현 메모만 추가했다. 문서 두 곳의 설명만 정정했으며 코드 · 시험 변경은 없다.

## 7. 사용자 확인이 필요한 항목

1. **실화면**: 1차 항목은 통과(§11). 보완 실화면 = §11-2 의 7.
2. **seed 정합 결정**(UI-02 범위 밖 · PLAN 부록): PC seed(기본 후보 3개)를 OCI 승인본 20개에 맞출지.

## 8. 검증 실측 (2026-10-12)

- `npx tsc --noEmit` exit 0 · `npm run lint` exit 0
- `npx vitest run` — **33파일 414 passed**(직전 406)
  - `holdings_risk_evidence/helpers.test.ts` 14(+4: 키별 방향 · 결측 맨 뒤 + 동점 · 결측끼리 들어온 순서(종목코드 역순 입력) · 표시로 같아지는 값도 원래 숫자 + 행 수 · 입력 불변 + 자료 확인 필요 행도 값으로 · NaN 맨 뒤)
  - `HoldingsRiskEvidenceSection.test.tsx` 12(+4: 다섯 정렬 순서 · 기본값 · 재조회 0 · 방향 안내 · 위험/순위 문구 없음 / 빠른 보기와 함께 / 정렬 뒤 선택 상세 유지 / '데이터 상태' 이동)
  - `TodayInvestmentCheckView.test.tsx` 38(기존 2개 시험에 '최대 3개' 설명 · 안내 문장 · 목록 없으면 설명 없음 단언 추가)
- **화면 변이(저장소 파일 임시 변경 → 시험 → 즉시 복원)** 8/8 검출: 종목코드로 동률 깨기 · 결측끼리 종목코드 순 · 표시값으로 정렬 · 정렬 때 선택 해제 · 방향 안내 뒤집기 · NaN 을 값으로 취급 · 이동 대상 `diagnostics` · 결측 맨 앞.
- backend 코드 변경 0 → backend 전체 회귀 · 라이브 해시는 설계 §7 대로 생략.

## 9. git 상태

(보고 직전 실측 · 보고 메시지에 인용)

## 11. 실화면 확인 · 사용자 의견 판단 (2026-10-12)

- **반영 방식**: 커밋 `9cfb535f` push 뒤 PC 재기동 없이 브라우저 새로고침으로 확인했다. PC 백엔드(`uvicorn --reload`) · 화면(`next dev`)이 13:27 부터 파일 변경을 자동으로 다시 읽는 상태라 재기동이 더하는 확인이 없다(사용자 결정 2026-10-12 — 설계 §10-4-3 '재기동 뒤' 대신).
- **통과(사용자 확인)**: 정렬 버튼 다섯 · 기본 '5일 변화' · 정렬 순서 · 정렬 뒤 상세 유지 · 「오늘의 투자 점검」 '최근 5거래일 변화가 낮은 보유 ETF부터 최대 3개'.
- **사용자 의견 1 — '20일 변화'와 'KODEX200 대비' 정렬 순서가 같다**
  - 판단: **구현 결함 아님 · 설계 목록의 중복**. 'KODEX200 대비 20일' = 종목 20일 변화 − KODEX200 20일 변화(`app/short_term_momentum.py` · `r20 - b20` · `b20` 은 모든 종목에 같은 값)라 같은 수를 빼도 순서가 바뀌지 않는다. 두 정렬은 KODEX200 자료만 없는 드문 경우를 빼면 늘 같은 순서다. 정렬 다섯은 POC3-05 설계 229행 목록을 UI-02 설계 §3-1 이 그대로 지정한 것이다.
  - 사용자 영향: 버튼 하나가 새 순서를 주지 않는다(값 표시는 그대로 의미 있음).
- **사용자 의견 2 — '데이터 상태에서 원인 확인 →'이 고른 종목으로 가지 않는다**
  - 판단: **UI-02 지시(§3-2 `onNavigate("data_status")` · 새 경로 · 조회 금지)대로 구현됨 · 그러나 실제 사용성 결함**(UI-02 이전부터 있던 것 · UI-02 는 「개발·실험용」 → 「데이터 상태」로 일부만 고침).
  - 근거:
    - 「데이터 상태」(`DataStatusView.tsx`)는 전체 ETF NAV · 시장가 · 괴리율 표 + 검색 · 정렬뿐이다. 종목을 넘겨받는 입력이 없어 이동 뒤 직접 검색해야 한다.
    - 그 화면에는 「확인 근거」 '자료 확인 필요'의 주된 원인(5일 · 20일 가격 이력 부족 · 보유 시세 미확인 · 계좌 간 값 다름)이 나오지 않는다 — NAV 관련 상태만 있다.
    - 종목별 사유는 이미 받은 응답에 있다: `GET /holdings/market-evidence/latest` 의 `evidence_notes`(예 '단기 흐름은 데이터 부족으로 확인할 수 없습니다.' · `app/holdings_market_evidence.py :: _build_evidence_notes`) · `GET /holdings/enriched` 의 `price_missing` / `calc_missing`. 「확인 근거」 상세는 NAV 메시지만 보이고 이 사유들은 보이지 않는다(`evidence_notes` 표시 0).
    - POC3-05 설계 §4.5 · 이동표('「확인 근거」 unavailable 사유 → 원인 확인 → 「데이터 상태」' · '이동 버튼의 문구와 실제 도착 화면이 일치해야 한다')와 지금 목적지가 맞지 않는다. 버튼은 자료가 정상인 종목에도 보인다.
- 두 건 모두 승인된 범위 밖 변경이 필요해 개발자가 바로 고치지 않고 설계자에게 넘겼다 → **설계자 보완 판정(2026-10-12 · 설계서 §11 원문): UI-02 안에서 두 건을 보완하고 종료 · PLAN 재제출 · 재판정 없음** · 처리 = §11-2.

### 11-2. 보완 처리 결과 (2026-10-12 · 설계서 §11 · PLAN §8)

**1) 처리한 요구사항**

| 요구(설계서 §11) | 상태 | 근거 |
|---|---|---|
| §2 KODEX200 대비 정렬 선택만 제거 · 네 가지 · 기본 5일 · 기존 정렬 계약 그대로 | DONE | `holdings_risk_evidence/helpers.ts` — `EvidenceSortKey` · `SORT_SPEC` · `EVIDENCE_SORT_OPTIONS` 에서 `excess` 만 뺌 · `sortEvidenceRows` 본문 변경 0 |
| §2 'KODEX200 대비 20일' 값 · 단위 표시 유지 | DONE | 카드 줄 `KODEX200 대비 20일` · `fmtPctp` 변경 0 · 시험이 행마다 값(`-1.50%p` 등) 확인 |
| §3 선택 종목 상세 '자료 확인 안내' | DONE | `HoldingsRiskEvidenceSection.tsx` — `<h3>… 상세</h3>` 바로 아래 · 기존 `hre-detail-evidence` / `hre-detail-line` 양식(새 CSS 0) · NAV 안내(`NavConstituentsDetail`)는 그 아래 그대로 |
| §3 evidence_notes · 시세 · 계산 미확인 · 계좌 불일치 | DONE | `buildRiskEvidenceRows` 가 행에 내부 칸 `notes`(여러 계좌 같은 문구 한 번 · 들어온 순서) · `price_missing` · `calc_missing`(계좌 행 중 하나라도) · `evidence_conflict`(기존 판정) · `flow_unavailable` 을 보탬 · 문구 조립 = `evidenceGuidance` |
| §3 사유 미제공 문구 · 빈 영역 없음 · 정렬 바꿔도 유지 | DONE | 아래 '사유 미제공 규칙' · 안내가 없으면 영역 없음 · 안내는 `built.rows` 에서 선택 종목으로 찾음(정렬 · 빠른 보기와 무관) |
| §3 재조회 · 저장 · 새 등급 없음 · 묶음 · 산식 · 행 상태 · 선정 규칙 변경 0 | DONE | `need_check` · `five_d_sortable` · `aggregateHoldingsByTicker` · `lowestFiveDayRows` 변경 0 · 시험이 조회 1회씩 확인 |
| §4 버튼 '전체 ETF NAV·괴리율 보기 →' · `data_status` 유지 · 종목 전달 없음 | DONE | 문구만 변경 · `onNavigate("data_status")` 그대로 |
| §5 시험 · 검사 · 기록 | DONE | 아래 5) · 설계서 §11(원문) · PLAN §8 · PROGRAM_TRUTH(현재 동작 = 네 가지 · 상세에서 사유 · 커밋 `9cfb535f` 시점 다섯 · 옛 문구는 남김) · STATE |

- **사유 미제공 규칙(실데이터 확인 뒤 정함)**: 2026-10-12 PC 화면 응답(`GET /holdings/market-evidence/latest` · 읽기만)에서 29종목 모두 `evidence_notes` 가 3~4개였다(26종목 3개 · 3종목 4개). 백엔드 `_build_evidence_notes` 는 Market Discovery 후보 여부 문구를 늘 붙이고, 20거래일 KODEX200 대비 · 구성종목 · NAV 문구도 붙인다. 그래서 '안내가 하나도 없을 때만 사유 미제공 문구'로 하면 항목이 있는 종목에서는 그 문구가 나오지 않는다. 그래서 자료 확인 필요의 사유가 되는 넷 — 시세 미확인 · 계산 미확인 · 계좌 불일치 · 단기 흐름 `unavailable`(백엔드가 이때만 '단기 흐름은 데이터 부족으로 확인할 수 없습니다.'를 붙임) — 이 없는데 자료 확인 필요면 사유 미제공 문구를 먼저 보이고, 일반 문구는 그 아래 그대로 둔다. 문구를 골라 빼거나 원인을 덧붙이지 않는다.
- **계좌 불일치 문구**: '같은 종목의 계좌별 단기 흐름 값(상태 · 5일 · 20일 · KODEX200 대비)이 서로 다릅니다.' — 기존 판정이 비교하는 네 값 그대로.

**2) 변경된 파일 목록**

- `frontend/app/components/holdings_risk_evidence/helpers.ts`: 수정(정렬 키 정리 · 행 내부 칸 · `evidenceGuidance` · `NO_REASON_TEXT`)
- `frontend/app/components/HoldingsRiskEvidenceSection.tsx`: 수정(머리 주석 · '자료 확인 안내' 영역 · 버튼 문구)
- `frontend/app/components/holdings_risk_evidence/helpers.test.ts`: 수정
- `frontend/app/components/HoldingsRiskEvidenceSection.test.tsx`: 수정
- `docs/ai_design/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_DESIGN_V1.md`: 수정(§11 설계자 판정 원문 · 전달문 원문 옮김)
- `docs/ai_plan/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_PLAN_V1.md`: 수정(§8)
- `docs/ai_result/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_RESULT.md`: 수정(이 절 · STATUS · CHECKS · §0 · §7 · §11)
- `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`: 수정
- 신규 의존성 없음 · backend · API · DB · CSS 변경 0

**3) 지시문 외 변경**

- 내부 칸 `flow_unavailable` — 위 사유 미제공 규칙 때문에 보탬(설계 §3 '상세 조립에 필요한 frontend 내부 필드는 보완할 수 있다' 범위).
- 「확인 근거」 머리 주석 · 정렬 정의 옆 주석을 지금 동작으로 고침.

**4) 알려진 한계**

- 실데이터에서는 자료 확인 필요 종목이 지금 0개다(2026-10-12 응답 · 단기 흐름 status 32항목 모두 ok · 시세 · 계산 미확인 0 · 두 계좌 이상 종목 2개 모두 값 같음). 그래서 실화면에서는 모든 종목 상세에 일반 문구(Market Discovery 후보 여부 · 20거래일 KODEX200 대비 · 구성종목 · 일부 NAV)만 '자료 확인 안내'로 보인다. 사유 · 사유 미제공 분기는 시험 자료로만 확인했다(설계 §5 '실데이터에 없는 분기는 시험 자료').
- '20거래일 KODEX200 대비 단기 흐름 차이 …%p.' 문구는 카드의 'KODEX200 대비 20일' 값과 같은 수를 한 번 더 보인다(문구를 골라 빼지 않는다는 판정대로 그대로 둠).
- 계좌 불일치 종목의 목록 값은 기존 코드대로 첫 계좌 항목 값이다(`aggregateEvidenceByTicker` · 변경 0). 안내 문구는 '서로 다릅니다'까지만 말하고 어느 값을 보였는지는 말하지 않는다.
- 단기 흐름 `partial`(일부 값만 없음)일 때 백엔드는 사유 문구를 붙이지 않아, 안내는 사유 미제공 문구 + 일반 문구가 된다(추측해 덧붙이지 않음).

**5) 검사 실측 (2026-10-12)**

- `npx tsc --noEmit` exit 0 · `npm run lint` exit 0
- `npx vitest run` — **33파일 423 passed**(1차 414 → +9)
  - `holdings_risk_evidence/helpers.test.ts` 18(1차 14 → +4: 계좌 행 사유 모음 · 같은 문구 한 번 · 다른 종목 섞임 없음 / 사유 없는 자료 확인 필요 · 정상 빈 목록 / 일반 문구뿐인 partial → 사유 미제공 먼저 / unavailable 은 사유 미제공 없음 · 기존 정렬 시험은 네 가지로 고침)
  - `HoldingsRiskEvidenceSection.test.tsx` 17(1차 12 → +5 · UI-02 묶음 4 → 9 · 빠른 보기 시험은 그대로 · 나머지 8: 네 정렬 · 기본값 · KODEX200 대비 버튼 없음 · KODEX200 대비 20일 값 표시 · 재조회 0 / 선택 종목별 evidence_notes · 사유 미제공 먼저 / 시세 · 계산 미확인 / 계좌 불일치 · 같은 메모 한 번 / 사유 미제공 · 정상 종목 영역 없음 / 시장 근거 항목 없는 종목 / 정렬 바꿔도 상세 · 안내 유지 · 재조회 0 / 새 버튼 문구 · `data_status` · 1회 · 재조회 0)
- **변이(저장소 파일 임시 변경 → 두 시험 파일 → 즉시 복원)** 10/10 검출: 일반 문구 빼기 · 시세 / 계산 문구 바꾸기 · 사유 미제공 빼기 · 사유 미제공을 '안내 없을 때만'(이전 규칙)으로 · unavailable 을 사유로 안 봄 · 불일치 빼기 · 같은 문구 중복 허용 · 계산 미확인 모음 깨기 · 이동 대상 `diagnostics` · 안내를 선택 종목 아닌 첫 행에서.
- backend 코드 변경 0 → backend 회귀 · 라이브 해시는 설계 §11-5 대로 생략.

**6) 다음 검증자(Codex)에게 알릴 점**

- 사유 미제공 규칙(위 1) — 설계 표는 `evidence_notes` 를 '해당 종목의 기존 사유 문구'로 적었지만 실제로는 일반 문구가 늘 섞여 있다. 문구를 골라 빼지 않고, 사유 미제공 판단만 구조 칸(시세 · 계산 · 불일치 · `unavailable`)으로 했다. `unavailable` ↔ 백엔드 문구 대응은 `app/holdings_market_evidence.py :: _build_evidence_notes` 의 `elif short_term["status"] == STATUS_UNAVAILABLE` 분기에 의존한다.
- 다른 화면 · 공유 함수 변경 0: `aggregateHoldingsByTicker`(보유 비교와 공유) · `lowestFiveDayRows` · 「오늘의 투자 점검」 변경 0.

**7) 사용자 확인 — 실화면 통과 (2026-10-12 · 새로고침)**

- 확인 대상: 「확인 근거」 정렬 버튼 네 가지(KODEX200 대비 없음 · 카드의 'KODEX200 대비 20일' 값은 그대로) · 종목 상세 맨 위 '자료 확인 안내'(지금 실데이터에서는 일반 문구만 보임 — 위 4)) · 상세 아래 버튼 '전체 ETF NAV·괴리율 보기 →' → 「데이터 상태」.
- 사용자 질문 1 — '전체 ETF로 넘기는 것만 가능한가': 지금은 전체 표만 연다(설계서 §11-4 · 종목 전달 · 검색 자동 입력 없음). 선택 상세의 'NAV · 괴리율' 줄이 같은 NAV 저장소(`app/etf_nav_store`)의 그 종목 NAV · 시장가 · 괴리율 · 기준일을 이미 보이고, 「데이터 상태」 표가 더 보이는 것은 source · status 두 칸이라고 답했다. 사용자는 종목 전달 요청을 하지 않았다(설계자에게 넘길 것 없음).
- 사용자 질문 2 — 'KODEX200 대비 정렬이 없어졌다': 1차에는 있었고 보완 판정 §11-2 로 뺐다고 답했다. 실데이터 29종목(2026-10-12 응답)에서 '20일 변화' 순서와 'KODEX200 대비 20일' 순서가 같고, 모든 종목의 20일 변화 − KODEX200 대비 값이 -4.6652로 같았다. **사용자 결정: 지금대로 네 가지 · 실화면 통과로 보고 커밋 · 종료로 진행.**

**git 상태**: 보고 직전 실측 · 보고 메시지에 인용.

### 11-3. 검증자 문서 정정 (2026-10-12)

머리의 `BASE_COMMIT` · `SCOPE`가 1차 값만 표시하고 있어 1차와 보완을 구분했다. 이번 보완 기준은 `9cfb535f`이며 변경 범위는 화면 2개 · 시험 2개 · 문서 5개(총 9개)다. 최초 구현 당시의 값은 보존했다. 문서 메타만 정정했으며 코드 · 시험 변경은 없다.

## 12. 종료 (2026-10-12)

- 보완 코드 · 시험 · 문서 · 종료 기록 · 인계를 한 커밋으로 push했다(사용자 승인 2026-10-12 · 설계자 재판정 없음 · 설계서 §11-5). PC 화면은 자동 다시 읽기로 이미 반영됐다. OCI pull은 하지 않는다.
- 인계: `docs/handoff/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_HANDOFF_2026-10-12.md`.
- 종료 범위 밖(유지): 두 안내 카드 제거 · 파일 삭제 보류 · 거래량 흐름 · 종합 위험 감지 · seed 정합(사용자 결정 대기) · PC FDR 수동 갱신 보호(조건부).
