# STATE_LATEST moved

Canonical: [docs/STATE_LATEST.md](../STATE_LATEST.md)
Past archive: [STATE_LATEST_ARCHIVE.md](STATE_LATEST_ARCHIVE.md)

This file is non-canonical. Do not append step details here.

최종 갱신: 2026-07-26 (POC3-01 UI-1 Dashboard REMEDIATION — 검증자 VERIFIED_WITH_NOTES + UI 테스터(사용자) 확인 완료 · 개발자 몫 종료 · 설계자 POC3-02 설계 대기).
직전: POC3-01 UI-1 Dashboard 초안 (VERIFIED_WITH_NOTES · commit 596078f5) → 화면 왕복 재조회/timeout 실사용 결함 발견 → REMEDIATION.
REMEDIATION 내용: 시장 카드 lazy (최초 topn 자동 호출 안 함 · 버튼으로 1회 조회) · frontend 조회 상태 공유 queryCache (왕복 재호출 X·dedup·관련 읽기만 무효화) · 첫 화면 2열 재구성 · 최소 UI 테스트 Vitest+RTL (28 passed). 신규 API/DB/backend cache 없음. UI 테스터·검증자·사용자 확인 전 UI_PASS/PASS/DONE 아님.
POC3 진입: PC 판단 UI 재조합 (상태 Dashboard → 판정 Workbench → 실행 Operations Panel). 마스터 설계서 docs/handoff/POC3/POC3_PC_JUDGMENT_UI_RECOMPOSITION_MASTER_DESIGN_V1.md. POC3-01 = 첫 화면을 STEP 안내 → 오늘의 판단 상태 Dashboard 초안으로 전환 (frontend 2파일 · 기존 데이터 경로만 · lint/build 통과 · 검증 대기).
현재 canonical 순서: 1. Telegram Push Operating Boundary Amendment v1 (DONE) → 2. Low-Frequency Telegram Push Operation v1 (DONE) → 3. First Real Decision Cycle v1 (활성) → 4. PC 판단 흐름 차단 결함 해소 → 5. Decision Outcome Ledger v1 → 6. Universe·ML·factor·PC UI 품질 개선.
Low-Frequency 최종: Market 08:00 / Holdings 3슬롯 / Spike 7 tick + OCI 07:20 데이터 배치 (증분 시세 갱신 + SQLite Universe artifact + freshness) · OCI 실측 완료 (Spike sent · Telegram 실 수신) · 상세 POC2_LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1_CONCLUSION.md.
Telegram 운영 계약: 전역 일 3회 제한 제거 · Market 평일 08:00 · Holdings 평일 3 슬롯 · Spike 조건 발생형 · 평가/알림 구분 · OCI 제한적 런타임 가격 조회 허용 · Published Evidence read-only 유지.
OCI 자율 시장 데이터 (2026-07-26 구현 완료 · Low-Frequency Push v1 DONE): OCI 가 `승인 seed ticker ∪ 현재 Holdings ticker` 한정 일별 시세 증분 갱신 (기존 FDR 재사용) + SQLite Universe artifact 생성 + freshness 검증. 07:20 배치 후 Spike 가 결과만 소비 (외부 거래일 조회 없음). freshness = 당일 배치 success + artifact.price_data_as_of 일치 + 36h + 7달력일 상한.
현재 운영 상태: market_holdings_operation = ACTIVE · spike_operation = ACTIVE · low_frequency_push_operation = DONE. OCI 실측 완료 (배치 success · Spike sent · Telegram 실 수신).
모바일 상태: DEFERRED_BY_USER · 재개 시 Telegram Cockpit 부터.
상세: [POC2_OCI_AUTONOMOUS_MARKET_DATA_BOUNDARY_AMENDMENT_CONCLUSION.md](POC2_OCI_AUTONOMOUS_MARKET_DATA_BOUNDARY_AMENDMENT_CONCLUSION.md).
이전 앵커 (SUPERSEDED): [POC2_MOBILE_DECISION_OPERATING_SEQUENCE_ANCHOR.md](POC2_MOBILE_DECISION_OPERATING_SEQUENCE_ANCHOR.md).

---

Active Reference:
3-PUSH Runtime Package Contract
- path: docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md
- purpose: PC/OCI가 공유하는 three_push_runtime_package.v1 schema 계약
- usage: PUSH 후속 Step에서는 evidence package / runtime snapshot / message_text 설계 시 이 문서를 기준으로 한다.
