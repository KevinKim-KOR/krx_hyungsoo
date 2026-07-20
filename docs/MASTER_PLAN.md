# MASTER_PLAN

이 프로젝트의 목적은 **AI와 함께 투자 방향을 찾는 것**이다. 운영 전제는 **직장인형 저빈도, K6/EOD 기준, 본업 우선**이며, 새 프로젝트는 Phase 1에서 검증된 자산 중 **독립 ML 모듈, OCI crontab 구조(daily_ops / spike_watch / holding_watch), Telegram 연동**만 살리고 나머지는 화이트리스트 기반으로 다시 시작한다. 성공 기준은 **친구의 긍정적 반응**, **4070s가 실제 ML 작업을 돌리는 상태**, **와이프가 이해할 수 있는 UI**이며, 1차 성과 판정은 **추천 ETF 평균 수익률**과 **같은 기간 KODEX 200 대비 초과 성과**로 본다. 친구 프로젝트 통째 이식, MongoDB 전환, 복잡도 증식은 범위 밖이다. :contentReference[oaicite:1]{index=1} :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

## 인간 승인 게이트 위치 정정 (2026-07-19, Holdings–Market PENDING Judgment Draft v1)

이전 2단계 "인간 최종 승인 게이트" 는 **정보 PUSH 앞** 이 아니라 **PENDING 투자 판단 초안 ↔ 실제 투자 행동** 사이에 둔다.

```text
정보 PUSH (Market briefing · Holdings briefing · Spike alert ·
  OCI evidence · artifact publication)
  ↓ (사용자 승인 게이트 없음, 자동 발송/발행)

PENDING 판단 초안 (GenerateDraft → PENDING_APPROVAL 저장)
  ↓ (인간 승인 게이트 · Approve / Reject)

실제 투자 행동 (매수 · 매도 · 비중 변경 · 종목 교체 · 주문 실행)
  · Approve 전에는 주문 또는 확정된 투자 행동으로 진행하지 않는다.
  · Reject 는 기록만 남기고 종료한다.
  · 자동 매매는 금지 (KS-1).
```

### 정보 PUSH 자동 정책

다음은 매 발송 전 사용자 승인을 요구하지 않는다:

- Market briefing (평일 08:00 KST)
- Holdings briefing (평일 12:30 KST)
- Spike alert (평일 15:30 KST, no-signal 시 미발송)
- OCI evidence · artifact publication (사용자 승인 하 controlled publication 완료 후 정기 발행)

계약:
- 중복 차단: `push_kind + param_id + runtime_date_kst` (KST 오늘) UNIQUE
- 장문 자동 분할: Telegram 4096 자 초과 시 `_split_message_for_telegram` 순차 전송 · `(i/N)` header · `partial_delivery` boolean
- no-signal 미발송: universe candidate=0 이면 sender 미호출
- 실제 발송 이력: `state/three_push/oci_runtime_history.jsonl` · `runtime_sent_registry` DB

### 인간 승인 게이트 (PENDING → 투자 행동)

- 진입점: `POST /runs/generate-from-holdings` (기존 GenerateDraft)
- 저장 상태: `PENDING_APPROVAL` (기존, JSON 파일 store)
- 승인 API: `POST /runs/{run_id}/approve` · 거절: `POST /runs/{run_id}/reject`
- UI: 기존 `RunPanel` · Approve · Reject 버튼
- 신규 승인 UI / DB / factor / threshold / 알고리즘 신설 금지

### 매수 · 매도 어휘 경계

- **정보 PUSH · 일반 evidence 화면**: 직접적인 매매 지시 금지. 안내 문구 "이 값은 매수/매도 지시가 아닙니다" 계속 사용.
- **PENDING 판단 초안**: 판단 목적상 매수 · 매도 관련 표현 사용 가능. 단:
  - 기존 GenerateDraft 가 제공하는 표현만 사용
  - 새 BUY / SELL 결정 규칙 추가 금지
  - PENDING 문구가 자동 주문 또는 확정 판단을 의미하지 않음
  - 최종 결정은 인간 승인 게이트 통과 후 사용자가 실행

이력:
- 3-PUSH Controlled Send Stage (Market · Holdings · Spike) 실제 발송 · 중복 차단 · partial_delivery · no-signal 계약 완비 (2026-07-18 ~ 2026-07-19)
- Holdings–Market PENDING Judgment Draft v1 (2026-07-19): 실제 PENDING 초안 1건 생성 · 화면 확인 · 부수효과 없음

## 현재 구현 우선 원칙 (2026-07-03, 마스터플랜 보완)

아래 원칙은 기존 1~5단계 (+6단계 확장) 구조·순서·승인 게이트·완료 조건을 대체하지 않는다. 각 단계 안에서 **무엇을 먼저 구현할지** 정하는 우선순위 기준으로만 사용한다.

```text
시장 전체 흐름을 먼저 읽고,
그 다음 보유 ETF가 그 흐름에 편승하는지를 본다.
개별 ETF 상세 분석은 필요한 소수 종목에 대한
선택적 확인 도구로 사용한다.
```

세부 흐름·역할 고정·다음 활성 Step 은 `docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md` 를 참조한다. 본 마스터플랜의 단계 체계 자체는 변경되지 않는다.

## 1단계. 데이터 수집 및 추천 초안 생성
K6/EOD 기준으로 시장 데이터를 수집하고, holdings와 결합하여 추천/상태 **초안**을 만든다. 이 단계의 산출물은 실행본이 아니라 **PENDING 상태의 승인 대기안**이다.  
- 연결 Open Question: **Q2, Q3** :contentReference[oaicite:4]{index=4}  
- 관련 Kill Switch: **KS-1, KS-3** :contentReference[oaicite:5]{index=5}  
- 완료 기준: **시장 데이터 1회 수집 → holdings 결합 → PENDING 추천 초안 1건 생성까지 완료되고, 백엔드 데이터와 화면 표시가 일치한다.**

## 2단계. 인간 최종 승인 게이트 구축
추천 초안과 OCI 전달 사이에 **Approve / Reject** 게이트를 둔다. **Approve 전에는 OCI 푸쉬, 후속 실행, 알림 발송이 금지**되며, Reject는 기록만 남기고 종료한다. 시스템은 자동 실행이 아니라 **인간 승인 기반 전진 구조**여야 한다.  
- 연결 Open Question: **Q2, Q3** :contentReference[oaicite:6]{index=6}  
- 관련 Kill Switch: **KS-1, KS-2, KS-3** :contentReference[oaicite:7]{index=7}  
- 완료 기준: **동일한 PENDING 초안에 대해 Approve 시에만 OCI 전달과 알림이 실행되고, Reject 시에는 아무 푸쉬도 발생하지 않음이 확인된다.**

## 3단계. 설명 가능한 판단 UI 구축
사용자가 추천 결과를 보고 승인 여부를 판단할 수 있도록, 입력값·판단 이유·추천 ETF/보유 상태·승인 대기 상태를 한 화면에서 읽히게 만든다. 화면은 전문 용어보다 **이유와 상태**가 먼저 보이도록 단순해야 한다.  
- 연결 Open Question: **Q3** :contentReference[oaicite:8]{index=8}  
- 관련 Kill Switch: **KS-1, KS-2, KS-5** :contentReference[oaicite:9]{index=9}  
- 완료 기준: **한 번의 추천 사이클에서 사용자가 화면만 보고 승인/거절을 결정할 수 있을 정도로 이유, 상태, 다음 액션이 끊기지 않고 이해된다.**

## 4단계. factor/ML 확장 및 4070s 검증
Phase 1에서 살려온 독립 ML 자산을 새 구조에 연결하고, 첫 factor 추가 난이도와 실제 연산 부하를 함께 검증한다. 핵심은 “확장 가능한가”와 “4070s가 실제로 돌아가는가”를 동시에 보는 것이다.  
- 연결 Open Question: **Q1, L-2** :contentReference[oaicite:10]{index=10}  
- 관련 Kill Switch: **KS-3, KS-8, KS-9** :contentReference[oaicite:11]{index=11}  
- 완료 기준: **새 factor 1개를 추가해 비교 가능한 ML 산출물 1세트를 만들고, 4070s에서 실제 배치 실행 로그 또는 사용 증거를 확보한다.**

## 5단계. 저빈도 운영 정착 및 예외 감시 편입
기본 운영은 K6/EOD 저빈도 루프로 유지하되, **급변 상황은 spike_watch / holding_watch로 별도 감시**하여 추가 알림을 허용한다. 이 예외 감시는 기본 승인 구조를 우회하는 자동 매매가 아니라, **추가 관찰·추가 알림 축**으로만 작동해야 한다.  
- 연결 Open Question: **Q2, Q3 최종 판정** :contentReference[oaicite:12]{index=12}  
- 관련 Kill Switch: **KS-4, KS-5, KS-6** :contentReference[oaicite:13]{index=13}  
- 완료 기준: **기본 저빈도 운영과 급변 예외 감시가 함께 동작하면서도 알림 과다와 과잉 교체 없이 성과 판정이 가능하다.**

## 6단계. OCI read model foundation (확장 단계)
**기존 5단계까지의 순서는 바꾸지 않는다**. 본 단계는 **PC 판단 화면 (3단계 확장)
과 ML 1차 결과 (4단계 확장) 가 확보된 뒤**의 확장 단계로 기록한다. PC 분석·판단
평면과 OCI 운영·조회 평면을 분리해, OCI 가 외부 / 모바일에서 마지막 published
데이터와 운영 상태를 조회할 수 있는 **read-only 환경**으로 확장한다.

- 연결 결정 기록: **`docs/handoff/PC_OCI_ARCHITECTURE_DIRECTION.md`** (원본),
  `docs/PROJECT_ORIGIN_INTENT.md` §7 운영 원칙 (PC 분석 평면 / OCI 운영·조회
  평면 분리), `docs/ASSUMPTIONS.md` §3 A-6.
- 관련 Kill Switch: **KS-1 (자동 매매 금지), KS-2 (인간 승인 게이트)** — 본
  단계는 read-only 조회만 추가하며, 자동 실행 / 새 자동 매매 경로를 추가하지
  않는다.
- 본 단계가 다루지 않는 것:
  - 신규 DB 도입 또는 full DB migration (PC SQLite 는 PC 작업용 기준 저장소로
    유지).
  - PC ML 이 OCI DB 를 직접 원격으로 읽는 구조.
  - PC SQLite 즉시 폐기.
  - 모바일 UI 구체 구현 (모바일 UI 후순위 원칙 유지 — PROJECT_ORIGIN_INTENT §7).
- 완료 기준: **PC 승인 / 발행 시점에 OCI 로 read-only published snapshot 이
  전달되고, OCI 측에서 마지막 published 데이터 + 운영 상태 + 기준 시각 + 데이터
  신선도를 read-only 로 조회할 수 있다.**
- **저장소 결정 정정 (2026-07-07 사용자 확정, 단계 순서 미변경)**:
  - OCI SQLite (`state/market/market_data.sqlite`) 는 **활성 운영·조회 기준 DB** 다.
  - PC SQLite 는 OCI publication 기반 **분석 복제본** 이다 (원격 write 금지).
  - **PARAM 은 DB version / approval / active pointer 로 관리** 한다 (JSON 파일 아님).
  - JSON 은 **로그 · archive · API transport** 만 허용. 활성 데이터 저장 · 동기화 ·
    운영 입력으로 사용하지 않는다.
  - 향후 모바일 조회는 **OCI SQLite read-only** 기반으로 구현한다.
  - 위 결정으로 이전 문구 "snapshot 구체 형식 (versioned SQLite snapshot /
    read-only JSON artifact / 제한된 조회용 SQLite copy 등) 은 본 단계 진입 직전
    별도 결정" 은 **SQLite 중심 · JSON transport 제한** 방향으로 확정.
  - 감사 근거: `docs/handoff/POC2_OCI_ACTIVE_DATA_BOUNDARY_AUDIT_V1_CONCLUSION.md`.

이 MASTER_PLAN의 목적은 기능을 벌리는 것이 아니라, **데이터 수집 → PENDING 초안 → 인간 승인 → OCI 전달/알림 → factor 확장 → 저빈도 운영 + 예외 감시 → OCI read-only 조회 평면 확장**의 짧고 검증 가능한 루프를 완성하는 데 있다. Open Question은 질문으로 남겨 관리하고, Kill Switch가 발동하면 토론하지 말고 즉시 멈춘다. :contentReference[oaicite:14]{index=14} :contentReference[oaicite:15]{index=15}