# POC5-UI-02 개발 결과서 — EXISTING_CHECK_FLOW_CORRECTIONS (기존 보유 점검 화면 정정)

작성 2026-10-12 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS            = IMPLEMENTED_VERIFIED — 검증자 VERIFIED(2026-10-12 · 위험 NONE · 범위 폭주 NONE · 격리 사본 vitest 414 · tsc · eslint 0 · 결과서 §4-2 · §6-4 표현은 검증자가 직접 정정 = §6-3) · 설계자 RESULT PASS(2026-10-12) · 다음 = 사용자 승인 커밋 · push → 실화면 → 종료
DESIGNER_RESULT   = PASS(2026-10-12 · 재작업 0 · 결과서 §4 추가 변경 6건 수용 · §5 한계 수용 · 두 카드 제거 · 파일 삭제 계속 보류 · 거래량 · 종합 위험 감지 · seed · FDR 보호는 종료 범위와 구분 · OCI pull 없음) — 원문 = 설계서 §10 · 끝에 전달문 원문
STEP_ID           = POC5-UI-02 기존 보유 점검 화면 정정
DESIGN            = docs/ai_design/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_DESIGN_V1.md (V1 개정 1 · §9 설계자 PLAN 부분 판정 PARTIAL_PASS 원문 · 끝에 전달문 원문 2건)
PLAN              = docs/ai_plan/POC5/POC5-UI-02_EXISTING_CHECK_FLOW_CORRECTIONS_PLAN_V1.md (판정 반영 = 본문 정정 + §7)
INPUT             = docs/ai_design/POC5/POC5_BACKLOG_AND_REMAINING_FEATURES_REVIEW_2026-10-12.md(설계자 리뷰) · docs/ai_result/POC5/POC5_BACKLOG_SOURCE_AUDIT_2026-10-12.md(개발자 현행 소스 대조)
BASE_COMMIT       = d7d365f4
SCOPE             = frontend 화면 7파일 · 시험 3파일 · 관리 문서 5개. backend · API · DB · 수집 · 의존성 · cron · OCI 변경 0
NOT_DONE_BY_DECISION = 「오늘의 투자 점검」 '개발 중인 판단 기능' · '코스피 상세 지표' 두 안내 카드 제거 · 두 컴포넌트 삭제 · 관련 CSS 삭제(판정 §4-5 보류 — 카드 파일 · TodayInvestmentCheckView.tsx · globals.css 변경 0)
CHECKS            = tsc exit 0 · eslint exit 0 · vitest 33파일 414 passed(직전 406 → +8) · 화면 변이 8/8 검출 — §8
REVIEW            = 독립 검토 1회(읽기 전용) — 정렬 · 이동 · 카드 미변경 · 판정 준수 확인 · 지적 MEDIUM 3 · LOW 6 → 모두 반영(§6-2)
MOCKUP            = 없음(설계 §7 · 새 폼 · 창 없음)
```

## 0. 요약

- **「확인 근거」 사용자 선택 정렬 다섯**: 평가 비중(큰 값부터) · 손익률 · 5일 변화(기본) · 20일 변화 · KODEX200 대비(작은 값부터). 화면 숫자 그대로 정렬한다. 값이 없는 종목은 맨 뒤에 두고, 같은 값끼리와 값 없는 행끼리는 원래 순서를 지킨다. 행을 빼지 않고 다시 조회하지 않는다. 컨트롤은 「보유 현황」 정렬과 같은 양식이다.
- **원인 확인 이동**: 「확인 근거」 종목 상세의 버튼이 「개발·실험용」(`diagnostics`)이 아니라 **「데이터 상태」(`data_status`)** 로 간다. 문구는 '데이터 상태에서 원인 확인 →'.
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

1. **실화면**(커밋 · PC 재기동 뒤): 「확인 근거」 다섯 정렬 · '데이터 상태에서 원인 확인 →' 이동 · 「오늘의 투자 점검」 '내가 가진 ETF' 목록 위 '최근 5거래일 변화가 낮은 보유 ETF부터 최대 3개'.
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
