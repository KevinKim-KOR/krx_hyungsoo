# POC6-25 개발 PLAN V1 — 보유 시세 · 평가금액의 미확인 표시 정정

작성 2026-11-07 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS = PLAN 제출 → 설계자 PLAN 판정 PASS(2026-11-07 · Q1 (a) · 범위 = current_price · eval_amount 의 세 표시) · 사용자 한 묶음 승인(2026-11-07 · §5 네 항목) → 구현
         → 사용자 실화면 확인 → 검증자 r1 VERIFIED → 설계자 최종 RESULT PASS(2026-11-07 · docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_RESULT_DECISION_2026-11-07.md)
         → 종료 커밋 e8760d90 push 완료(승인 ④) → IMPLEMENTED_VERIFIED_CLOSED(2026-11-07)
PLAN 판정 = docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_PLAN_DECISION_2026-11-07.md(A 판정 · B 통합설계 V1.1 · 원 설계 · 이 PLAN 보다 우선)
DESIGN = docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_DESIGN_V1.md
범위   = 설계 §4 접점만 읽기 확인(원인 재조사 · 목업 없음 · 코드 · 설정 · 데이터 변경 0)
```

## 1. 두 표시의 실제 접점(`frontend/app/components/EnrichedHoldingsSection.tsx` 한 파일)

| 표시 | 지금 코드 | 결함 경로 |
|---|---|---|
| 보유 행 '매입 X → 현재 Y' | `HoldingRow` · `curText = fmtMoney(it.current_price)` → `curText ? 현재 <b>{curText}</b> : <span className="muted">현재 확인 불가</span>` | 값 없음이면 `fmtMoney(null)` = '0원'(`toFiniteNumber(null)` = 0) → '현재 0원' · 대체 분기는 도달하지 않음 |
| 행 상세 '평가금액' | `DetailRowFields` · `ev = fmtMoney(it.eval_amount)` → `if (ev) lines.push(["평가금액", ev])` | 값 없음이면 '0원' 줄이 생김 |

입력 필드 = `/holdings/enriched` 행의 `current_price` · `eval_amount`(서버는 유효 시세가 없으면 둘 다 null). 다른 컴포넌트 · 공통 함수는 바꾸지 않는다.

## 2. 최소 변경

```text
행:   curText = it.current_price == null ? null : fmtMoney(it.current_price)
      대체 글 '현재 확인 불가' → '현재 미확인'(설계 §3 문구 · 같은 muted 자리 · 매입가 그대로)
상세: it.current_price == null → ["현재가", "미확인"](판정 Q1 (a)) · 아니면 지금처럼 fmtMoney(값)
      it.eval_amount == null → ["평가금액", "평가 불가"] · 아니면 지금처럼 fmtMoney(값)
      (값 없음이어도 항목은 숨기지 않고 그 자리에 표시)
```

- 분기는 형식화 전 `== null`(null · 누락) 하나. 숫자 0 은 지금처럼 '0원'(0 과 미확인을 함께 처리하는 조건 없음).
- 계산 · 데이터 · API · 배치 · 펼침 · 기준시각 · 출처 줄 · 부분 합계 경고 · POC6-24 자금 카드 / 비중 무변경.
- 파일 크기: 735줄 → 약 738줄(KS-10 근접 850 미만).

## 3. 시험 · 검사

- 기존 렌더 시험 `EnrichedHoldingsSection.eval.test.tsx`(가상 행 `calcRow` · `unpricedRow` 재사용)에 묶음 하나 추가 — 실제 `EnrichedSection` 을 렌더하고 행을 눌러 상세를 편다.
  - 시세 없는 행: '현재 미확인' 있음 · '현재 0원' 없음 · 매입가 그대로 · 상세 '현재가 미확인' · '평가금액 평가 불가'.
  - 정상 행: 행 현재가 · 상세 현재가 · 상세 평가금액이 지금과 같은 금액 글.
  - 명시적 0(가상 `current_price: 0` · `eval_amount: 0`): '0원' 유지.
  - 값 누락(필드 없음): null 과 같음.
- 수정 전 코드에서 미확인 경로의 결함 단언이 실패하는지(재현) 먼저 보고, 정정 뒤 통과를 본다(정상 · 0원 대조는 수정 전에도 통과할 수 있음).
- 완료 때 한 번: `npx tsc --noEmit` · `npm run lint` · `npx vitest run` 전체 · 프런트 build(§5 ②). 백엔드 무변경 → 전체 pytest · 라이브 DB 검사 · 변이 시험 제외(설계 §5-5).

## 4. 설계자 확인 요청(실제 접점에서 나온 것만)

**Q1 — 같은 상세의 '현재가' 줄.** 상세 `DetailRowFields` 의 '현재가'(`cur = fmtMoney(it.current_price)`)도 같은 값 · 같은 원인으로 시세가 없을 때 '현재가 0원'으로 보인다. 설계 §1 의 두 건에는 없다.
- (a) **확정**(판정 A-2): 이번에 같이 고친다 — 시세가 없으면 '현재가 미확인'. 같은 필드 · 같은 컴포넌트 한 줄이며, 고치지 않으면 행은 '현재 미확인'인데 펼친 상세는 '현재가 0원'이라 이 Step 의 목표(0 과 미확인 구분)가 같은 행 안에서 깨진다.
- (b) 설계 §4 대로 사실만 기록하고 이번에는 두 건만 고친다.

그 밖에 확인한 사실(고치지 않음 · 보고만): 상세 '매입비중'(`fmtPct(it.buy_weight_pct)`)도 null 이면 '0%'가 되지만, 서버는 매입 합계가 0일 때만 null 을 내고 보유 저장 검증이 수량 · 평단 > 0 을 강제해 실제로는 생기지 않는다.

## 5. 승인 요청 범위(PLAN 판정 뒤 한 묶음)

승인 기록: 2026-11-07 사용자 '한 묶음 모두 승인 (권장)' — 아래 1 ~ 4 전부(판정 B-6 · 프런트 일시 중지 · 재기동 포함).

1. §2 구현 · §3 가상 응답 렌더 시험(실제 보유 · 시세 데이터 변경 · 새 시세 조회 없음).
2. **프런트 build**: 전역 훅 조건대로 프런트 `next dev`(:3000)만 잠시 중지 → 저장소 밖 격리 사본에서 build → 원래 프런트 다시 켜기(창을 닫아도 남게 백그라운드) → :3000 HTTP 200 확인. 백엔드(:8000) 유지 · build 에 실제 저장소 `.next` 를 사용하거나 삭제하지 않음(사본의 build 산출물과 원래 dev 서버가 정상 사용 · 갱신하는 `.next` 는 구분) · 훅 변경 · 우회 없음. (POC6-24 의 일회성 승인을 재사용하지 않음.)
3. 사용자 실화면: 실제 「보유 현황」에서 정상 행 · 상세 배치가 그대로인지 확인(미확인 사례가 실제 보유에 없으면 그 경우는 §3 렌더 시험으로 갈음 · 결과서에 금액 · 계좌 정보 없음).
4. 검증자 확인 · 설계자 최종 RESULT 뒤 코드 · 문서 커밋 · push(OCI · 운영 변경 없음 · 사용자 handoff 제외).

## 6. 하지 않는 것

공통 `fmtMoney` · `toFiniteNumber` 정비 · 다른 호출자 · 다른 화면 일괄 정정 · 자금 / 보유 저장 · API · DB · 시세 수집 · 외부 조회 · OCI · PUSH · PARAM · 연구 / ML · Cleanup · 새 카드 · 메뉴 · 상태 체계.
