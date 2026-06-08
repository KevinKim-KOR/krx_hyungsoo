# STATE_LATEST

최종 업데이트: 2026-06-08 (NAV / Discount Display FIX)

## 0. Canonical

- **Canonical state file**: `docs/STATE_LATEST.md` (본 파일)
- **Step detail files**: `docs/handoff/<step_file>.md` (Step 종료 후에만 생성)
- **Past accumulation archive**: [docs/handoff/STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md)
  — 2026-05-14 ~ 2026-06-07 사이 시간순 누적 본문. 본 정리 이후로는 더 이상 append 하지 않는다.
- 본 파일에는 현재 상태 / history 요약 / Open decisions / Index 만 둔다. **Step 상세는 append 하지 않는다.**

### Step 상세 파일 생성 규칙

```text
Step 상세 파일은 Step 종료 후 다음 Step 으로 넘어갈 때 생성한다.
진행 중 Step 의 상세 파일은 미리 만들지 않는다.
docs/STATE_LATEST.md 에는 요약만 남기고, 상세는 docs/handoff/<step_file>.md 에 둔다.
```

## 1. Current position

- **프로젝트 큰 흐름**:
  보유 현황 입력 → 시세/평가 계산 → 시장 후보 발굴(Market Discovery) → 구성종목 / 중복 분석(ETF Exposure)
  → 보유 vs 시장 Evidence → 판단 사유 있는 초안 생성(GenerateDraft) → 인간 승인 → OCI 전달 → Telegram 수신.
- **현재 완료 상태**: **NAV / Discount Display FIX** (2026-06-08).
  - 신규 read-only API `GET /market/nav-discount/latest` — 저장된 `etf_nav_daily` 전체 ETF 1136건을 1회 응답으로 노출 (외부 source 호출 X / refresh X).
  - Data Status 화면 재설계 — 전체 ETF NAV / 시장가 / 괴리율 표 + 검색(ticker/이름) + status 필터 + 괴리율 정렬 (괴리율 |abs| / 부호 / ticker).
  - Market Discovery CandidateTable — NAV / 시장가 / 괴리율 / asof / source / status 6 컬럼 직접 노출.
  - ETF Exposure NAV 카드 — asof / source / status 컬럼 보강 (이전 flag/source 한 컬럼).
  - Holdings Evidence NAV 라인 — asof / status 추가 (NAV·시장가·괴리율 옆).
  - 직전 STEP(Naver Universe 연동) 의 표시 누락 5건 모두 해소. 표시 매트릭스 4 화면 × 6 필드 = 모두 visible.
- **현재 진행 예정**: 사용자 결정 대기 (§6 Next action 참조).

## 2. Latest completed step

| Step | Status | Date | Detail |
| --- | --- | --- | --- |
| NAV / Discount Display FIX (전체 ETF 조회 영역 + 표시 매트릭스) | DONE | 2026-06-08 | [POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md](handoff/POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md) |

## 3. Recent history summary

| Step | Result | Summary | Detail |
| --- | --- | --- | --- |
| 2026-06-08 NAV / Discount Display FIX | DONE | GET /market/nav-discount/latest 신규 + Data Status 전체 ETF NAV 표 + MD/ETF Exposure/Holdings 표시 보강. 표시 매트릭스 충족. | [conclusion](handoff/POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md) |
| 2026-06-08 Naver ETF Universe NAV / 괴리율 연동 | DONE | universe 1회 호출(`etfItemList.nhn`) → `etf_nav_daily` upsert + 3개 화면 NAV 표시. TTL 30s + stale 재사용. 신규 API 0건. | [conclusion](handoff/POC2_NAVER_ETF_UNIVERSE_NAV_INTEGRATION_CONCLUSION.md) |
| 2026-06-07 ETF NAV / Discount Source Diagnosis 1차 (FIX) | DONE | NAV/괴리율 source 5건 실측. adopt 0 / hold_unstable 2 / unusable 3. flat_records + timeout 명시 + asof 키 확장 FIX. | commit `b5a80a3f` / [archive](handoff/STATE_LATEST_ARCHIVE.md) |
| 2026-06-06 ETF Exposure Data Unfolding 1차 | DONE | 구성종목 펼쳐보기 + 반복 핵심 종목 + 중복률 + Holdings Evidence State Bridge + ML readiness 9축. ML 방향성 2축 문서화. | commit `bce8f7fd` / [archive#0.1](handoff/STATE_LATEST_ARCHIVE.md) |
| 2026-06-06 Operational UI Cleanup 1차 | DONE | Dashboard 5-step 판단 흐름 + 6개 화면 role banner + Market Discovery 다음 단계 안내 + NAV 미연동 안내 ≥2 화면. | commit `62c77d7c` / [archive#0.1](handoff/STATE_LATEST_ARCHIVE.md) |

> 직전 5개를 제외한 이전 STEP (2026-06-01 이전 — Market Discovery Closeout / Constituents Naver Integration /
> Constituents Diagnosis / Constituents & Overlap / Market Regime / AI Sessions / Decision Evidence /
> AI 투자세션 복사용 문구 / Grid 사용성 FIX / 통합 후보 테이블 / 후보 정제 / SQLite Direct Refresh /
> TOP N 최소 표시 / PC UI Shell / FDR+SQLite Foundation / B 방향 전환 등) 은
> [docs/handoff/STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md) 에 전문 보존되어 있다.

## 4. Current evidence flow

- **Market Discovery**: SQLite 직접 계산 TOP N. 수동 refresh (6h cooldown). 시장 국면(KODEX200 필수 / KOSPI 보조) / 단기 흐름 / NAV(직접 컬럼 6개 — NAV/시장가/괴리율/asof/source/status) / 데이터 품질(`nav_discount`) 동봉.
- **ETF Exposure**: 구성종목 펼쳐보기(자동 open + 등락률 unavailable 컬럼) + 중복률 + 반복 핵심 종목 + Holdings Evidence State Bridge (명시 호출 버튼) + NAV/괴리율 카드(상위 5건 + asof/source/status) + ML readiness 9축.
- **Holdings Evidence**: `GET /holdings/market-evidence/latest` (read-only, 외부 fetch 0건). 보유 ETF × Market Discovery 후보 / 시장 국면 / 단기 흐름 / 구성종목 중복 / NAV·시장가·괴리율·asof·status·source(`etf_nav_daily` store 에서 read).
- **Data Status**: 전체 ETF NAV / 시장가 / 괴리율 조회 화면 (`GET /market/nav-discount/latest`). 검색 + status 필터 + 괴리율 정렬. 외부 source 호출 0건. 1136 ETF 1회 응답.
- **GenerateDraft**: 같은 evidence builder 재사용 — `draft_payload.holdings_market_evidence_snapshot` + `factor_signals` scope="holdings_market_evidence" + [판단 사유] bullet. 매수·매도·교체 어휘 0건.
- **Approval / Telegram**: 인간 승인 게이트 유지. 3-PUSH (보유 종목 상태 / 신규 ETF 관찰 후보 / 급락 ETF 주의). 자동 매매 X.
- **AI Sessions**: 외부 AI 답변 + 사용자 판단 기록. Market Discovery 후보 스냅샷 + 시장 국면 + 구성종목/중복률 / 단기 흐름 / 데이터 품질 / Decision Candidate 전부 포함.

## 5. Open decisions

| ID | 상태 | 내용 | 참조 |
| --- | --- | --- | --- |
| Q1 | OPEN | 여러 factor 를 붙일 수 있는 구조의 엔진이 될 것인가? | ASSUMPTIONS §2 |
| Q4 | OPEN | "잘 올라가는 섹터/ETF 발굴" 작동 단위 (운영 1개월 검증 필요) | ASSUMPTIONS §2 |
| Q6 | OPEN | 위험 감지 = "위험 구간 분류" — factor / threshold / label 어떻게 확정할 것인가? (시계열 적재 선행) | ASSUMPTIONS §2 / INTENT §9.5 |

## 6. Next action

- **다음 Step 후보 (사용자 결정 대기)**:
  1. ~~NAV / Discount Source Adoption~~ — **DONE (2026-06-08 Naver Universe NAV Integration)**.
  2. **NAV / 괴리율 시계열 누적** — 현재는 universe 1회 호출 = 단면 스냅샷. asof 일자별 누적이 위험 감지 축 2 의 시계열 후보로 직접 사용 가능 (ML readiness 카드의 NAV/괴리율 시계열 partial → available 승격 경로).
  3. **위험 감지 지표 시계열 적재 1차** — VKOSPI / Fear&Greed / 외국인·기관 수급 / 시장 폭 후보 진단. ML 2축 중 축 2 선행 조건.
  4. **구성종목 가격 시계열 source 진단** — ETF Exposure 화면에서 등락률 unavailable 해소.
  5. **MDD / Sharpe 계산 도입** — Phase 1 BACKLOG 항목.
- **하지 않을 것 (불변 원칙)**:
  - 자동 매매 / Telegram 문구 변경 / OCI push 자동화 (사용자 명시 승인 필요)
  - MongoDB 전환 (PROJECT_ORIGIN_INTENT §10 #2 — SQLite(시장) + JSON(holdings/Run) SSOT 분리)
  - ML / 백테스트 / threshold / label 확정 (Q6 답 나오기 전)
  - 매수·매도·교체 어휘 / 자동 클러스터링 / 대표 ETF 선정
- **사용자 결정 필요**: ✅ 위 4개 후보 중 다음 Step 선택.

## 7. Index

### 불변 앵커 (먼저 읽어야 하는 5개 문서)

- [docs/PROJECT_ORIGIN_INTENT.md](PROJECT_ORIGIN_INTENT.md) — 한 줄 정의 / 1년 뒤 목표 / 절대 하지 않을 것 / ML 2축 (§9.5)
- [docs/KILL_SWITCHES.md](KILL_SWITCHES.md) — KS-1 ~ KS-11 (단일 파일 책임 누적 / 의사결정 24시간 룰 등)
- [docs/ASSUMPTIONS.md](ASSUMPTIONS.md) — Open Question Q1 / Q4 / Q6 (활성 3개 한도)
- [docs/COLLAB_RULES.md](COLLAB_RULES.md) — 협업 규칙
- [docs/MASTER_PLAN.md](MASTER_PLAN.md) — 마스터 플랜

### Active reference (현 진행에 영향, 자주 갱신)

- [docs/handoff/POC2_B_NEXT_ACTIONS.md](handoff/POC2_B_NEXT_ACTIONS.md) — 빈자리 후속 원칙 + 다음 분기 후보
- [docs/handoff/POC2_FEATURE_INVENTORY.md](handoff/POC2_FEATURE_INVENTORY.md) — 기능 인벤토리
- [docs/handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md](handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md) — NAV 진단 1차 결과
- [docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md](handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md) — 구성종목 source 진단
- [docs/backlog/BACKLOG.md](backlog/BACKLOG.md) — Backlog (시계열 / NAV source / MDD / Sharpe / 구성종목 가격 / 위험감지 지표)
- [docs/ref/FRIEND_PROJECT_DATA_SOURCES_ANALYSIS.md](ref/FRIEND_PROJECT_DATA_SOURCES_ANALYSIS.md) — 친구 프로젝트 source / 주기 분석

### Step detail (Step 종료 후 생성된 상세 기록)

POC1 → POC2 초기:
- [POC1_step3_close_and_POC2_handoff.md](handoff/POC1_step3_close_and_POC2_handoff.md) — POC1 Step3 종결 + POC2 진입 1차
- [POC1_Step3_close_and_POC2_Step1_handoff.md](handoff/POC1_Step3_close_and_POC2_Step1_handoff.md) — POC1 Step3 종결 + POC2 Step1 완료 종합

POC2 Step 1A ~ 6:
- [POC2_Step1A_close.md](handoff/POC2_Step1A_close.md) / [POC2_Step2_close.md](handoff/POC2_Step2_close.md) / [Step2B](handoff/POC2_Step2B_close.md) / [Step2C](handoff/POC2_Step2C_close.md) / [Step2D](handoff/POC2_Step2D_close.md)
- [POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md](handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md)
- [POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md)
- [POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md](handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md)
- [POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md](handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md)
- [POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md)

POC2 Step 7 (3-PUSH realignment):
- [POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md](handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md)
- [POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md](handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md)
- [POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md](handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md)
- [POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md](handoff/POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md)
- [POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md)

POC2 Step 8 (3-PUSH 운영 1주기 검증) + 별도 Foundation:
- [POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md](handoff/POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md)
- [POC2_FDR_SQLITE_MARKET_DATA_FOUNDATION.md](handoff/POC2_FDR_SQLITE_MARKET_DATA_FOUNDATION.md) — FDR + SQLite 시장 데이터 기반 구축

2026-06-01 이후 (가장 최근 5개 STEP — §3 참조 + ARCHIVE 전문):
- 2026-06-07 NAV / Discount Source Diagnosis 1차 (FIX) → [STATE_LATEST_ARCHIVE §0](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-06 ETF Exposure Data Unfolding 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-06 Operational UI Cleanup 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-03 Holdings × Market Discovery Evidence 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-03 KS-10 Cleanup (API Client / Type 책임 분리) → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-01 이전 16개 STEP 시간순 누적 → [STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md) 전문

### Deprecated / redirect

- [docs/handoff/STATE_LATEST.md](handoff/STATE_LATEST.md) — 6줄 redirect stub. 본 파일과 ARCHIVE 로 안내. 더 이상 append 하지 않는다.
