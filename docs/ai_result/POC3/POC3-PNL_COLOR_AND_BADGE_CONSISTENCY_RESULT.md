# POC3 — 손익 색 국내 관례 전환 + 배지 규칙 통일 (개발 결과서)

- **성격**: 설계서 없는 **사용자 실화면 직접 지시** UI 개선.
  설계자 배정 STEP 번호가 없어 파일명에 번호를 넣지 않는다.
- **작업일**: 2026-08-16 (맥북 환경)
- **상태**: **DONE (코드·검증 완료) · 사용자 실화면 확인 대기**
- **선행**: `POC3-WORKBENCH_GRID_CARD_CONVERSION_RESULT.md` · `POC3-EVIDENCE_GRID_AND_STOP_GUARD_RESULT.md`

**사용자 확정 작업 순서**: ① 확인 근거 → ② 백로그 → ③ 손익 색 → ④ 개별주.
**본 결과서는 ③ 과 그에 딸린 배지 규칙 통일**을 다룬다. ④ 는 철회됐다(§4).

---

## 1) 처리한 요구사항

| 요구사항 | 결과 |
|---|---|
| 손익 색을 국내 증권사 관례(상승 빨강 / 하락 파랑)로 전환 | **DONE** |
| 전용 토큰 신설 (안 B — 경고·링크 색과 분리) | **DONE** (`--pnl-up` / `--pnl-down`) |
| 전 화면 일괄 적용 | **DONE** (6개 지점) |
| 보유 탭 배지 규칙을 후보 탭과 일치 | **DONE** (사용자 "형태와 다른 점을 바꿔라") |
| 개별주 종목명 자동 조회 | **철회** (§4) |

### 1.1 손익 색 — 전용 토큰 신설

```css
--pnl-up: #d92d20;    /* 상승·이익 */
--pnl-down: #1570ef;  /* 하락·손실 */
```

기존에는 `--ok`(초록) / `--danger`(빨강)를 재사용했다. 국내 관례로 바꾸면 **상승에 `--danger`(위험) 색**을 쓰게 되어, 같은 화면의 경고 표시(`⚠ 자료 확인 필요` 등)와 의미가 섞인다. 그래서 경고·링크와 분리된 전용 토큰을 두는 안(안 B)을 사용자가 선택했다.

**⚠ 작업 중 정정** — 착수 전 보고에서 색 함수가 `pnlClass()` / `directionColor()` **두 곳**이라고 했으나, 전수 조사 결과 **여섯 곳**이었다.

| 지점 | 파일 | 영향 화면 |
|---|---|---|
| `.pnl-pos` / `.pnl-neg` | `globals.css` (← `pnlClass()`) | 보유 현황 · 승인 패널 · 근거 상세 |
| `directionColor()` | `workbench/helpers.ts` | ETF 비교하기 · 확인 근거 |
| `returnPctColor()` | `CandidateTable.tsx` | 요즘 잘 오르는 ETF |
| `returnColor()` | `holdings_compare/helpers.ts` | 보유와 비교 |
| `pnlSum` 인라인 | `DashboardView.tsx` | LEGACY 대시보드 |
| KODEX200 일간 등락 인라인 | `DashboardView.tsx` | LEGACY 대시보드 |

여섯 곳 모두 토큰을 참조하도록 바꿨다. **이제 방향 색 변경은 토큰 두 줄로 끝난다.**

**일부러 바꾸지 않은 것** — 방향이 아니라 **상태**를 뜻하는 색이다.

- `pctColor()` (`DataStatusView`) — 괴리율 **절대값** 5%↑ 위험. 상승/하락이 아니다.
- `badgeColor()` (`DashboardView`) — ok/warn/danger 상태 배지.
- `exposureColorByState()` · 중복 상태 색 (`holdings_compare/helpers.ts`) — 정상/불가 상태.

### 1.2 보유 탭 배지 규칙 통일

후보 탭은 데이터 상태가 정상이면 배지를 띄우지 않는데(2026-08-13 적용), 보유 탭은 정상 배지를 계속 띄우고 있었다. 같은 화면 두 탭의 규칙이 달랐다.

| 항목 | 이전 | 이후 |
|---|---|---|
| `보유` 배지 | **모든 행**에 상시 표시 | **제거** — 그 목록은 전부 보유 종목이라 정보량 0 |
| `NAV` · `구성종목` 정상(ok) | 회색 배지 표시 | **숨김** |
| `근거 정상` | 회색 배지 표시 | **숨김** |
| 이상 상태 | `⚠ NAV <상태>` · `근거 확인 불가` 등 | **그대로** |

결과적으로 **배지가 하나도 없으면 전부 정상**이고, 이상한 것만 눈에 띈다.

---

## 2) 변경된 파일 목록

| 파일 | 구분 |
|---|---|
| `frontend/app/globals.css` | 수정 (토큰 신설 + `.pnl-pos`/`.pnl-neg`) |
| `frontend/app/components/workbench/helpers.ts` | 수정 (`directionColor`) |
| `frontend/app/components/CandidateTable.tsx` | 수정 (`returnPctColor`) |
| `frontend/app/components/holdings_compare/helpers.ts` | 수정 (`returnColor`) |
| `frontend/app/components/DashboardView.tsx` | 수정 (인라인 2곳) |
| `frontend/app/components/workbench/HoldingTable.tsx` | 수정 (배지 규칙) |
| `frontend/app/components/JudgmentWorkbenchView.test.tsx` | 수정 (배지 테스트 재작성) |
| `docs/*` | PROGRAM_TRUTH · STATE_LATEST · 공유 보고서 · 백로그 · 본 문서(신규) |

`git diff --stat` 실측 (docs 포함 9파일): **79 insertions / 29 deletions**.

---

## 3) 신규 추가된 의존성

없음.

---

## 4) 지시문 외 변경

**개별주 종목명 자동 조회 철회 (§7 → 요청 없음)** — 사용자가 조건을 좁혔고(“종목명은 직접 입력하면 된다. 평가금액·홀딩스 평가에서만 안 빠지면 된다”), 그 조건이 이미 충족돼 있음을 실측 확인해 설계 요청을 철회했다.

```
069500 KODEX 200(ETF)    → name=KODEX 200   price=110,060
005930 삼성전자(개별주)     → name=삼성전자     price=274,500
000660 SK하이닉스(개별주)   → name=SK하이닉스   price=1,645,000
```

`TICKER_PATTERN` 은 개별주를 막지 않고(주석에 명시), 네이버 `stock/{ticker}/basic` 은 ETF·개별주 공통이며, `enrich_holdings` 는 ticker 종류를 가리지 않는다. **개별주도 시세·평가금액·손익이 정상 산출된다.**

---

## 5) 알려진 한계 / 미완성

1. **사용자 실화면 확인 대기.** 색 채도(`#d92d20` / `#1570ef`)가 적절한지는 실화면 기준이다.
2. **표로 남은 화면 6개** — `CandidateTable`(17열) · `HoldingsCompareView`(14열) ·
   `OverlapTab`(11) · `AISessionsListTab`(8) · `ConstituentsTab`(6) · `EvidenceDetails`(8).
   카드 전환은 화면별로 무엇을 접을지 결정이 필요해 미착수.
3. `확인 필요` 탭 미전환(항목 목록이라 성격이 다름).
4. LEGACY 대시보드에도 새 색이 적용된다. 참고용 화면이라 그대로 뒀다.

---

## 6) 다음 검증자(Codex)에게 알릴 점

1. **색 변경 지점이 보고보다 많았다.** 착수 전 "두 곳" 으로 보고했다가 전수 조사로 **여섯 곳**임을 확인하고 정정했다(§1.1). 방향 색과 상태 색을 구분해 **상태 색 3종은 의도적으로 제외**했으니 그 구분이 타당한지 확인 바람.
2. **배지 테스트 2건을 기대값 반전이 아니라 재작성했다.**
   - `NAV·구성종목 분리` — 정상 배지가 사라져 존재 검사가 불가능해졌다. **구성종목만 이상인 상황**을 만들어 그 쪽만 뜨고 NAV 는 안 뜨는지 검사하도록 바꿨다. 분리 계약을 이전보다 정확히 본다.
   - `Evidence 배지` — **2건으로 분리**. 정상이면 안 뜨는 것 + Evidence 부재 시 `근거 확인 불가` 가 뜨는 것.
   - vitest 160 → **161**.
3. 색은 전부 CSS 변수 참조다. 하드코딩 hex 는 `globals.css :root` 두 줄뿐이다.

---

## 7) 사용자 확인이 필요한 항목

1. **색 채도** — `#d92d20`(상승) · `#1570ef`(하락) 이 진하거나 흐리면 조정.
2. **보유 탭 배지 정리 결과** — 정상 종목의 종목명 줄이 깔끔해졌는지.
3. 표로 남은 6개 화면의 전환 순서 (§5-2). 1순위로 `CandidateTable`(17열) 목업 예정.
