# STATE_LATEST — KRX Alertor Modular (as of 2026-02-25)

## 1) 목표 (3줄)
- PC(조정석)에서 전략 파라미터 설정/백테스트/튜닝 → 결과를 근거로 승격(SSOT) → OCI(운영석)에서 안전장치(가드레일) 하에 운영 루프를 수행한다.
- “UI에서 실제로 되는/안 되는 것”을 기준으로 다음 액션을 결정한다. 문서는 참고이며, 최우선은 UI/로그/아티팩트 증거다.
- 최종 목적은 친구 프로젝트 수준 이상의 수익/안정성을 달성하되, 운영 자동화·재현성·감사추적을 갖춘다.

## 2) 시스템 구도 (PC ↔ OCI)
- PC Cockpit: 파라미터 설정(SSOT) / 백테스트 / Optuna 튜닝 / 번들 생성 및 Push
- OCI Operator: Auto Ops Cycle / Evidence Resolver / Manual Loop (prep→ticket→record) / Stage(SSOT)
- 핵심 원칙: Fail-Closed, Evidence-first, SSOT 기반, latest/snapshot 분리, token 기반 확인(단 DRY_RUN/REPLAY는 합리적 우회)

## 3) 현재 모드/환경
- Execution Gate: DRY_RUN (테스트 루프 반복 가능)
- Replay Mode: 사용 가능 (Data Basis: 2026-02-20 기준으로 검증 진행 이력 있음)
- Guardrails: SSOT화 완료 (LIVE/DRY_RUN/REPLAY 분리 정책 운용)

## 4) “UI 1회전 완주” 증거 (운영 루프)
- Stage: DONE_TODAY 도달(SSOT stage가 DONE으로 이동)
- Record: decision=EXECUTED / reason=SUBMITTED_VIA_DRAFT 확인
- 대표 산출물 경로(최신):
  - reports/live/reco/latest/reco_latest.json
  - reports/live/order_plan/latest/order_plan_latest.json
  - reports/live/order_plan_export/latest/order_plan_export_latest.json
  - reports/live/execution_prep/latest/execution_prep_latest.json
  - reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json
  - reports/live/manual_execution_record/latest/manual_execution_record_latest.json
  - reports/ops/summary/latest/ops_summary_latest.json

## 5) 주요 변경 로그 (P153~P169)
| P | 변경 요지 | 검증 증거(핵심 1줄) |
|---|---|---|
| P153 | RECO buy_count 산수 버그 수정 + Force Cascade 설계 시작 | RECO holding_actions(ADD 포함) 계산 일치 |
| P154 | Force Cascade(Reco→OrderPlan→Export) + UI 결과 보존 | Auto Ops 결과 1줄 표시 유지 |
| P155 | Fail-Fast/Always-Write Latest로 “침묵/화석 summary” 제거 | 오류시에도 latest 갱신 & 원인 노출 |
| P160-SSOT | Execution Guardrails 하드코딩 제거 → SSOT화 | execution_prep.safety.limits.applied 기록 |
| P161~P162 | Draft generate/submit 실제 경로 정정 + DRY_RUN 토큰 문제 제거 | Submit Success ↔ Record EXECUTED 정합 |
| P164 | 백테스트 엔진 Active 이식(app/backtest + run_backtest) | python -m app.run_backtest 로 latest/snapshot 생성 |
| P165 | MDD/Sharpe 실값 + equity_curve/daily_returns + Cockpit 백테스트 탭 | summary.mdd/sharpe 실값 + meta 시계열 포함 |
| P167-R | Optuna 튜닝 엔진 + prefetch/cache + tune_result 산출물 | n-trials 완료, 다운로드 0(프리페치), 결과 저장 |
| P168 | UI 용어 통일/한글 보강 + Best Params 적용 원클릭 | “적용→저장→백테스트” 한 호흡 |
| P169 | Backtest/Tuning 파라미터 SSOT 통합(state/params) + Git Trap 제거 | param_source.path+sha256 / git ls-files 빈값 |

## 6) 현재 남은 문제/리스크 TOP5
1) 데이터 소스 병목: yfinance 의존 시 유니버스 확장/튜닝에서 속도·차단 리스크
2) 유니버스가 아직 4종목 중심: 친구의 “5버킷 분산” 구조와 직접 비교가 어려움
3) 전략 옵션 부족: MA 타입 다양화(EMA/HMA), 리밸런싱 주기/모드(손절 vs 리밸런싱) 미구현
4) UI 일관성/한 호흡 UX는 아직 미완: 탭 이동/저장/푸시 흐름 복잡도 잔존
5) Git Trap 재발 가능성: state/latest 계열(특히 params/guardrails/cache)의 추적/동기화 정책 상시 점검 필요

## 7) 다음 액션
### 소스 수정 없이 가능한 3개
- (1) P169 SSOT 우선권/sha256가 PC↔OCI 모두 일치하는지 교차 확인
- (2) Full(3Y) 기준 universe 확장 후보 리스트(예: ETF 20~40개) 확정 및 backtest로 baseline 산출
- (3) 친구 프로젝트 비교 문서 기반 “우선 흡수 3개” 선정(버킷/리밸런싱/MA 타입)

### 소스 수정 필요한 3개
- (1) 데이터 소스 추상화 + 네이버/FDR 기반 캐시 강화(유니버스 확장 대비)
- (2) 5버킷 자산배분 + 리밸런싱 모드 도입(친구 핵심 흡수)
- (3) UI 정리 스프린트: 한글/용어/한 호흡 UX/SSOT Key 표준화

## 8) 현재 SSOT 파일 목록(경로)
- state/strategy_bundle/latest/strategy_bundle_latest.json
- state/params/latest/strategy_params_latest.json   (P169)
- state/guardrails/latest/guardrails_latest.json    (P160-SSOT)
- reports/backtest/latest/backtest_result.json       (P164~P165)
- reports/tune/latest/tune_result.json               (P167-R)

---

# MASTER_PLAN — KRX Alertor Modular (P170~)

## 1) 방향성 요약 (5줄)
- 친구 프로젝트의 “돈 버는 구조”는 전략식(MAPS)보다 **버킷 분산 + 리밸런싱 규율 + MA 다양화**에 가깝다.
- 우리는 이미 SSOT/가드레일/재현성/튜닝(Optuna)이라는 “기관급 뼈대”가 있으므로, 이제는 **수익구조(분산/리밸런싱)를 엔진에 이식**한다.
- 유니버스 확장 전제는 데이터 소스/캐시가 견뎌야 한다(대량 티커, 반복 튜닝).
- UI는 “언젠가”가 아니라 마일스톤으로 박고 정리한다(한 호흡 UX + 한글/용어 통일).
- 목표는 (1) 유니버스 4개 → 40개로 확장, (2) 버킷 분산/리밸런싱 옵션 탑재, (3) 튜닝→승격→운영 루프를 실제로 굴리는 것.

---

## Phase 1 (P170~P172) — 데이터/유니버스 확장 기반 닦기
### 목표
- 대량 티커(20~60개)에도 튜닝/백테스트가 버티는 데이터 파이프라인 구축
- 유니버스 확장(버킷별 ETF 리스트) 입력 체계 확립

### 산출물
- 데이터 소스 추상화(Provider 인터페이스) + 캐시 정책 문서
- universe 세트(버킷별 리스트) SSOT 또는 config
- backtest_result에 “버킷별 성과/기여” 확장(요약만)

### 완료조건(AC)
1) 티커 40개 prefetch 후 튜닝 n-trials 50을 “다운로드 0~최소화”로 완료
2) 캐시/params/guardrails 등 동적 파일 Git 비추적 유지
3) backtest/tune 결과 meta에 param_source/sha, cache_key, universe_hash 기록
4) PC↔OCI 결과가 같은 파라미터로 같은 meta.sha를 찍음(동일성)
5) 실패 시 원인(데이터/네트워크/결측) Fail-fast + evidence 남김

### 검증 방법
- `python -m app.run_backtest --mode full` (universe 40개)
- `python -m app.run_tune --mode full --n-trials 50 --seed 42`
- 결과 JSON의 meta: param_source.sha256, cache_key, universe_hash 확인

### 리스크/롤백
- yfinance 차단/속도 이슈 → Provider 전환(FDR/네이버) 또는 로컬 스냅샷 캐시로 롤백

---

## Phase 2 (P173~P175) — 친구 핵심 흡수: 5버킷/리밸런싱/MA 다양화
### 목표
- “전략 한 방”이 아니라 “구조(분산+규율)”를 이식해서 장기 성과/낙폭을 개선
- MA 타입/기간 다양화 및 리밸런싱 모드 선택 제공

### 산출물
- 버킷 정의 SSOT: bucket_sets.json (예: MOM/INNO/INDEX/DIV/HEDGE)
- 리밸런싱 주기 옵션(weekly/monthly) + 모드(손절형 vs 리밸런싱형)
- MA 타입 옵션(SMA/EMA/HMA 등) + 파라미터화
- backtest/tune 스코어링 확장(버킷 분산 페널티/보상)

### 완료조건(AC)
1) 5버킷 universe(각 5~15개)로 backtest full 3Y 수행
2) stop_loss 즉시매도 vs 리밸런싱 보유 모드 비교 리포트 자동 생성
3) MA 타입 변경이 성과에 반영되고, params_used에 정확히 기록
4) 튜닝이 “버킷/리밸런싱/MA”까지 포함해도 50~200 trials 수행 가능
5) 결과 비교(베이스 vs 개선) diff 리포트 제공

### 검증 방법
- 모드별 backtest 결과 비교 JSON 생성
- tune_result best_params 적용 후 backtest 재실행 및 diff 확인

---

## Phase 3 (P176) — UI 정리 스프린트 (필수 마일스톤)
### 목표
- “탭 여기저기 이동”을 줄이고, (설정→저장→실행→결과→승격) 흐름을 한 화면/한 호흡으로 통합
- 한글/약어 설명/용어 통일/SSOT key 표준화를 완성

### 산출물
- Cockpit UI 재구성(Workflow 중심)
- 용어 사전(한글+약어) + UI 툴팁 적용
- 버튼 3개 표준: 저장(로컬) / 반영(OCI) / 실행(백테스트/튜닝/AutoOps)

### 완료조건(AC)
1) “최적 파라미터 적용→바로 Full 백테스트”가 탭 이동 없이 가능
2) 어디서나 동일 키 이름(momentum_period/stop_loss/max_positions)만 사용
3) 실행 로그/결과 위치가 UI에 명확히 안내(경로/파일명)
4) 운영 모드(LIVE)에서 위험 버튼은 토큰 기반으로만 노출
5) UI 변경이 운영 루프(OCI)와 충돌하지 않음

---

## Phase 4 (P177~P179) — 승격/운영 루프 강화 (PC→OCI)
### 목표
- 튜닝 결과를 Live 승격하기 전 “승격 게이트(검증)”를 자동화
- 기록/감사/재현성 강화

### 산출물
- “승격 후보 리포트”(tune_result + backtest_result + diff + 리스크)
- 승격 버튼(토큰 기반) + 승격 이력 로그
- 운영 Runbook/rollback 문서

### 완료조건(AC)
1) 승격 전 체크리스트 자동 통과/실패가 evidence로 남음
2) 승격된 파라미터/버킷/MA/모드가 OCI SSOT에 반영
3) 운영 루프에서 DONE_TODAY까지 자동 진행 가능(필요 시 manual loop)

---

## P170~P179 백로그(초안)
- P170: Data Provider 추상화 + 캐시 정책 강화(대량 유니버스 대비)
- P171: Universe 확장 SSOT(버킷별 리스트) + UI 입력/검증
- P172: Backtest/Tune 결과에 universe_hash/cache_key 표준화
- P173: 리밸런싱 모드 도입(손절형 vs 리밸런싱형)
- P174: MA 타입 다양화(SMA/EMA/HMA) + 파라미터화
- P175: 친구 대비 리포트 자동 생성(버킷/리밸런싱/MA 효과)
- P176: UI 정리 스프린트(한 호흡/한글/용어)
- P177: 승격 게이트(검증 체크리스트 자동화)
- P178: 회귀 테스트/재현성 강화(seed, deterministic)
- P179: 운영 Runbook + rollback 확정

---

## 배포 규칙(OCI/NAS 영향 작업 시)
- 변경 커밋 후: `git status` 깨끗 → commit → push
- OCI 반영: `git pull && sudo systemctl restart krx-backend`
- 동적 state/latest는 Git 추적 금지(.gitignore + cached rm) 유지
