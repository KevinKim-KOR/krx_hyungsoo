# UI 개선 시리즈 — 검증 요청 패키지 (검증자 BLOCKED 해소용)

- **수신**: 검증자(Codex)
- **발신**: 개발자
- **작성**: 2026-08-17
- **목적**: 검증자가 요구한 3가지(원본 요청문·승인문 / 결과서 경로 / 검증 대상 SHA·파일 목록)를 한 곳에 모은다.

---

## 0. 이 시리즈의 성격 (검증 기준 설정에 필요)

**설계서가 없다.** 전 구간이 **사용자 실화면 직접 지시**로 진행됐다. 사용자 명시:

> "UI 바꾸는 것은 제가 주도하는 것이니 그것은 설계자에게 안 넘깁니다."

따라서 **A-1(지시 일치) 검증의 기준 문서는 설계서가 아니라 아래 §1 의 사용자 지시문**이다.
POC3-08 과 같은 유형이며(`설계서 없는 사용자 실화면 직접 확정 UI 개선`), 그 선례를 따랐다.

**진행 절차**(매 화면 공통): 현재 구조 제시 → 목업(HTML)으로 목표 구조 승인 →
구현 → 실화면 확인 → 지적 반영 → 결과서 → 커밋.

---

## 1. 사용자 원본 지시문 (시간순 · 발췌 아님, 해당 대목 그대로)

### 1.1 UI 변경 요청

| # | 일자 | 원문 |
|---|---|---|
| U1 | 08-12 | "보유현황에 개발된 UI형태로 ETF비교하기의 그리드를 변경하고 싶습니다." |
| U2 | 08-13 | (목업 확인 후) "오오 좋습니다. 목업화면으로 전환합니다" |
| U3 | 08-13 | "여기에 표현할 것 / 티커 / 시장가 / NAV / 괴리율 … 클릭동작 오케이 … 12개월과 1년이 같은거면 하나로 … 다만 기본은 지금 개발한 것으로 하고 표형태도 별도 탭으로 있으면 좋은데 지금 표형태가 너무 답답해보여서 크기 조절만 해주세요." |
| U4 | 08-15 | "이제 바꿔야하는게 비교판단 하위의 화면들입니다. 보기가 너무 어려워서요. … ML과 관련된 메뉴를 하나 빼고 ML과 관련되어있는 것은 옮겨야 겠습니다." |
| U5 | 08-16 | "근데 data status는 원래 무슨 역할이었나요? 제대로 수집했는지 보는 것이었던 것 같은데 그것은 원래 사용해야하는거 아닌가요? 이것까지 분리해야 할 것 같고 순서를 진단->ML->나머지(현재 미사용?) 순서로 하는게 맞는 것 같습니다." |
| U6 | 08-16 | "UI적인 부분은 이제 괜찮은 것 같습니다. ETF비교하기부터 지금까지 개발했던 형태와 다른 점을 바꿀 준비 및 실행을 해주세요." |
| U7 | 08-16 | "2번부터 하고 1번을 하겠습니다." (2=손익 색 전환, 1=비교·판단 화면 개편) |
| U8 | 08-17 | "후보ETF의 참고점수는 필요없습니다. 차라리 간단한 사유나 키워드를 넣어주는게 나을 것 같은데요. 선택보유 상세는 무슨 내용이 나오는건가요?" |
| U9 | 08-17 | "화면 좋습니다. 이대로 진행하면 됩니다." |

### 1.2 비즈니스 로직(UI 외) 수정 승인

**승인 방식**: 개발자가 선택지를 제시하고 사용자가 택일하는 형식이었다. 아래는 제시된
질문·선택지와 사용자의 선택이다.

| # | 대상 | 개발자 질문(요지) | 사용자 선택 |
|---|---|---|---|
| A1 | **백엔드 — 보유 evidence 에 6·12개월 추가** | "보유 측 6개월·12개월 수익률을 추가할까요? (백엔드 변경)" / 선택지: `추가(권장)` · `지금은 1·3개월만으로` · `설계자에게 물어보기` | **`추가 (권장)`** |
| A2 | **카드 비교 기준** | "카드에서 무엇을 가장 크게 보여드릴까요?" / 선택지: `기간 수익률 4칸(권장)` · `지금처럼 손익률/참고점수` | **"기간 수익률 4칸, 그렇지만 보유는 현재 수익율이 제일 앞에"** |
| A3 | **전체 pytest 실패 1건 처리** | "전체 pytest 실패 1건을 어떻게 할까요?" / 선택지: `원인 잡고 가기(권장)` · `커밋하고 백로그로` · `변경을 되돌리기` | **`원인 잡고 가기`** |
| A4 | **손익 색 전환 범위** | "손익 색 국내 관례 전환을 어디까지 적용할까요?" | **`전 화면 일괄`** + 팔레트 **`안 B`**(전용 토큰 신설) |
| A5 | **stop 스크립트 주인 확인 가드** | "stop.sh 에 주인 확인을 넣을까요?" | **`넣기 — 맥+윈도우 둘 다`** |
| A6 | **백로그 정리 범위** | "백로그 보류 해소의 범위를 확인해주세요." | **`이미 해소된 것만 정리`** |
| A7 | **상시 실패 2건(`test_factor_signals`)** | (사용자가 먼저 지시) "① 실패 테스트 2건은 이번에 닫으세요. AAA/BBB/CCC 티커가 6자리 검증에 막힌 것 — 설계 판단이 아니라 fixture 문제입니다. 검증을 약화시키지 말고 티커를 실제 6자리로 바꾸면 끝입니다. \"2 failed\"가 상시화되면 진짜 실패가 그 뒤에 숨습니다." | (지시 그대로 이행) |
| A8 | **개별주 종목명 자동 조회** | 설계 요청으로 올렸던 건 | **철회** — "개별주 종목명 조회는 그냥 제가 한번 하면 되는건데 … 나중에 평가금액이나 홀딩스 평가에서만 안빠지면 안해도 됩니다." (조건 충족 실측 확인) |

**A1·A3 이 이번 BLOCKED 의 핵심 승인 근거**다. A1 은 백엔드 응답 필드 추가,
A3 은 그로 인해 드러난 테스트 격리 결함의 수정 방침이다.

---

## 2. 표준 7섹션 결과서 경로

이 시리즈는 **화면 단위로 결과서를 나눴다**. 검증 범위에 따라 필요한 것을 취하면 된다.

| 순서 | 결과서 경로 | 대상 |
|---|---|---|
| 1 | `docs/ai_result/POC3/POC3-WORKBENCH_GRID_CARD_CONVERSION_RESULT.md` | ETF 비교하기 후보·보유 탭 |
| 2 | `docs/ai_result/POC3/POC3-EVIDENCE_GRID_AND_STOP_GUARD_RESULT.md` | 확인 근거 + stop 스크립트 가드 |
| 3 | `docs/ai_result/POC3/POC3-PNL_COLOR_AND_BADGE_CONSISTENCY_RESULT.md` | 손익 색 전환 + 배지 규칙 통일 |
| 4 | `docs/ai_result/POC3/POC3-MARKET_DISCOVERY_CARD_CONVERSION_RESULT.md` | 요즘 잘 오르는 ETF (17→16열) |
| 5 | **`docs/ai_result/POC3/POC3-HOLDINGS_COMPARE_CARD_CONVERSION_RESULT.md`** | **보유와 비교 + 백엔드 확장 (UI 외 변경 §4.0)** |

**메뉴 재편(MenuKey 10→13)은 별도 결과서가 없다.** 커밋 `6d818d4d` 메시지와
`PROGRAM_TRUTH` §5.1 주석·`STATE_LATEST` 에 기록했다. **결과서 누락이며, 필요하면 작성한다.**

**보조 문서**
- 시리즈 종합: `docs/handoff/POC3/POC3_UI_IMPROVEMENT_SHARE_REPORT.md` (§7-A 에 UI 외 변경 3건)
- 현행 계약: `docs/PROGRAM_TRUTH.md` §5.1
- 진행 상태: `docs/STATE_LATEST.md`

---

## 3. 검증 대상 SHA · 범위 · 파일 목록

### 3.1 전체 시리즈

```
범위 : 1e1219e4..edd7fdeb   (1e1219e4 = 시리즈 직전 HEAD, POC3-08 Closeout)
실측 : 41 files changed, 3683 insertions(+), 709 deletions(-)
```

### 3.2 커밋 단위 (시간순)

| SHA | 제목 | 규모 |
|---|---|---|
| `c5d91056` | chore(env): 맥북 기동 스크립트 + 맥/PC 병행 작업 주의사항 문서 | 3 files, +308 |
| `08ceb771` | feat(workbench): ETF 비교하기 후보·보유 탭 그리드를 카드형으로 전환 | 8 files, +734/−249 |
| `3ccb12fd` | fix(workbench): 카드 그리드 실화면 지적 4건 + KODEX초과 필드명 버그 | 8 files, +224/−86 |
| `ba1aa315` | feat(evidence): 확인 근거 그리드 카드 전환 + stop 스크립트 주인 확인 가드 | 9 files, +394/−60 |
| `6d818d4d` | refactor(menu): ML 실험 신설 + 데이터 상태·OCI 운영 상태 복원·분리 | 13 files, +488/−163 |
| `528643eb` | test(factor-signals): 상시 실패 2건 해소 — fixture 티커 교체 | 4 files, +31/−21 |
| `2033d221` | feat(ui): 손익 색 국내 관례 전환(전용 토큰) + 보유 탭 배지 규칙 통일 | 12 files, +242/−34 |
| `363df258` | feat(market-discovery): 후보 17열 표 → 카드(기본)/표 3탭 전환 | 9 files, +660/−21 |
| **`edd7fdeb`** | **feat(compare): 보유와 비교 카드 전환 + 보유 기간 수익률 확장(6M·12M)** | 12 files, +748/−221 |

### 3.3 `edd7fdeb` 변경 파일 (UI 외 변경 포함 · 이번 BLOCKED 의 직접 대상)

```
M  app/api_holdings_market_evidence.py            ← UI 외 (API 응답 모델)
M  app/holdings_market_evidence.py                ← UI 외 (payload 확장)
M  tests/test_ml_job_runner.py                    ← UI 외 (테스트 격리)
M  frontend/app/components/HoldingsCompareView.tsx
A  frontend/app/components/holdings_compare/CompareCards.tsx
M  frontend/app/components/workbench/helpers.ts
M  frontend/lib/api/holdings.ts
M  frontend/app/globals.css
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_result/POC3/POC3-HOLDINGS_COMPARE_CARD_CONVERSION_RESULT.md
M  docs/handoff/POC3/POC3_UI_IMPROVEMENT_SHARE_REPORT.md
```

### 3.4 UI 외 변경만 뽑은 diff 명령

```bash
git show edd7fdeb -- app/holdings_market_evidence.py app/api_holdings_market_evidence.py tests/test_ml_job_runner.py
```

---

## 4. 검증 기준선 (실측)

| 항목 | 결과 | 측정 시점 |
|---|---|---|
| `black --check app tests scripts` | 276 files unchanged | 2026-08-17 |
| `flake8 app tests scripts` | 0 | 2026-08-17 |
| `npx tsc --noEmit` | 0 | 2026-08-17 |
| `npm run lint` | 0 | 2026-08-17 |
| `npx vitest run` | **167 passed (15 files)** | 2026-08-17 |
| 백엔드 전체 `pytest tests/ -q` | **1139 passed · 실패 0건 · 스레드 경고 0건** | 2026-08-17 |

**pytest 재현 조건**: autosend 플래그 4개를 명령 앞에 붙여야 한다. 붙이지 않으면
`test_runtime_runner_partial_delivery` 2건 + `test_low_frequency_push_operation` 1건이
환경 의존으로 실패한다(테스트가 개발자 `.env` 를 전제하는 기존 결함).

```bash
PUSH_AUTOSEND_ENABLED=true PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true \
PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true \
PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true .venv/bin/python -m pytest tests/ -q
```

---

## 5. 개발자가 스스로 신고하는 항목 (검증 전 고지)

검증자가 찾기 전에 개발자가 먼저 밝힌다.

1. **판단 오류 2회** — 전체 pytest 실패 1건에 대해 "제 변경과 무관" · "flaky 라 어쩌다 한 번"
   이라고 **측정 전에 결론**을 냈고, 베이스라인 대조로 둘 다 뒤집혔다. 최종 판정은
   "방아쇠는 이번 작업, 결함은 테스트 격리" 다. 경위는 `STATE_LATEST` 에 기록했다.
2. **보고 수치 정정 2회** — 손익 색 함수를 "두 곳" 으로 보고했다가 실제 **여섯 곳**,
   `HoldingsCompareView` 를 "14열 표" 로 보고했다가 실제 **6열 표 2개**.
3. **결과서 1건 누락** — 메뉴 재편(`6d818d4d`)에 결과서가 없다(§2).
4. **테스트 공백** — `MarketDiscoveryView`·`HoldingsCompareView` 계열은 원래 테스트가 없었고,
   `CandidateCards` 만 6건 신설했다. `CandidateTable`·`CompareCards` 는 테스트 없음.
5. **`stop.bat` PC 실행 미검증** — 맥에서 작성했다.
