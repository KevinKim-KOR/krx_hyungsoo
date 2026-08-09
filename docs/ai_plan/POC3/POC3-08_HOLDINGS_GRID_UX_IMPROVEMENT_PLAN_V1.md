# POC3-08 종목 관리·보유 현황 그리드 UX 개선 — 개발 PLAN V1

- 작성일: 2026-08-06
- 문서 성격: 개발 PLAN (사용자 직접 지시 · UI 개선 · 설계서 없음)
- 지시 출처: 사용자 (2026-08-06, 실화면 스크린샷 + 요구 4건)
- backlog 근거: `project_krx_grid_design_backlog`(POC3-05 때 미룬 그리드 개선)
- 상태: 착수 가능 (사용자 확정 3건 반영)

---

## 1. 사용자 요구 (원문 기반)

1. **입력이 편했으면** — 종목 관리는 종목을 입력하는 화면이니까.
2. **입력 후 조회는 계좌별로** — 보유 현황에서 계좌별 조회.
3. **매입단가 등 숫자에 천단위 콤마** (지금 `84190` → `84,190`).
4. **OCI 적용 시각 이력** — 언제 OCI에 적용했는지 기록·표시.

**사용자 확정(2026-08-06):**
- 종목 관리 그리드 = **C 카드행**(입력감 우선).
- 입력 콤마 = **입력 중에도 콤마 표시**(매입단가·수량 모두).
- OCI 적용 이력 = **마지막 1건 지속 표시**(PARAM 과 동일 status 파일 패턴).

---

## 2. 현재 코드 실측

| # | 항목 | 현재 |
|---|---|---|
| 1 | 종목 관리 그리드 | `HoldingsManageView.tsx` `table.holdings-table` — 밋밋한 기본 테이블 |
| 2 | 보유 현황 계좌별 | `HoldingsView.tsx` 에 "전체/**계좌별**/ticker별" 구조 **이미 있음**(EnrichedSection). 시각 강조만 여지 |
| 3 | 입력 콤마 | 계산값(매입금액)은 `formatNumber` 콤마 O. **입력칸(매입단가·수량)은 raw** → 콤마 X |
| 4 | OCI 적용 시각 | `POST /holdings/apply` 가 `applied_at` 반환·표시하나 **직전 1회만**(state 저장 없음). 화면 재진입 시 사라짐 |

**핵심 주의**: `rowsToPayload` 는 `Number(r.avg_buy_price)` 로 저장 → 입력칸에 콤마를 넣으면 저장 전 콤마 제거 필수(`Number("84,190")`=NaN).

---

## 3. 개발 범위 (2 파트)

### 파트 1 — 프론트 UX (요구 1·2·3)
- **종목 관리 = C 카드행**: `table.holdings-table` → 카드행 grid 레이아웃. 행 간격·hover·포커스 링. 계좌 색 pill. 비중 막대(공통 개선).
- **입력 콤마**: 매입단가·수량 입력칸 표시값에 천단위 콤마(입력 중 실시간). 저장 시 콤마 제거해 숫자 전송. 소수점 수량 허용 유지.
- **보유 현황 계좌별 시각 강조**: 기존 계좌별 섹션에 계좌 헤더·소계 시각 정돈(신규 계산 없음, 기존 EnrichedSection 재사용). ※ 실제 강조 범위는 HoldingsView 실측 후 확정.

### 파트 2 — OCI 적용 이력 (요구 4, 백엔드 포함)
- **PC 로컬 status 저장**: `POST /holdings/apply` 성공/실패 시 `state/holdings/holdings_apply_status_latest.json` 기록(kind·status·applied_at·content_sha256). **PARAM 의 `param_sync_status_latest.json` 과 동일 패턴.**
- **조회 API**: `GET /holdings/apply/status` — 마지막 적용 상태 반환. (또는 기존 apply 응답 캐시 재사용 — 구현 시 최소 변경 선택)
- **화면 표시**: 종목 관리 OCI 적용 카드에 "마지막 OCI 적용: <시각> · <성공/실패>" 지속 표시(화면 재진입해도 남음).

> **manifest 무관**: 이 status 파일은 **PC 로컬 기록**이라, r5 에서 정합 문제로 없앤 OCI active manifest 와 **다르다**. active 정본(payload 1개) 계약을 건드리지 않는다. 정합 대상 아님(단순 "언제 적용했나" 기록).

---

## 4. 확인 필요 / 주의

- **Q(구현 중 확정)**: 보유 현황 계좌별 "시각 강조" 실제 범위 — HoldingsView 현재 구조 읽고 최소 변경으로. 신규 계산·API 안 만듦.
- **콤마 입력 UX**: `type="number"` 는 콤마 못 넣음 → `type="text" inputMode="numeric"` 로 바꾸고 표시만 콤마, 검증은 콤마 제거 후 숫자. min/step 검증은 로직으로 유지.
- **OCI status 파일**: PARAM 패턴 그대로. 신규 파일 1개(state/) — git-ignored state 라 배포 영향 없음(기존 param status 와 동일 취급).

## 5. 검증
- 프론트: tsc·eslint·vitest. 콤마 입력→저장 왕복(콤마 제거되어 숫자 저장) 테스트.
- 백엔드: black·flake8·py_compile. status 저장·조회 단위 테스트.
- 실화면: 입력 편의·계좌별 조회·콤마·적용 이력 = 사용자 실화면 확인(레이아웃 자동 테스트 미탐지).

## 6. 커밋 분할 (제안)
1. 파트 1 프론트 UX (카드행·콤마·계좌별 시각)
2. 파트 2 OCI 적용 이력 (백엔드 status + 화면 표시)
3. 개발 결과서 → (검증 필요 시 검증자)

## 7. 범위 밖 (안 함)
- 신규 투자 지표·factor·매매 로직. OCI runner·crontab 변경. active manifest 부활. 신규 외부 데이터 source.
