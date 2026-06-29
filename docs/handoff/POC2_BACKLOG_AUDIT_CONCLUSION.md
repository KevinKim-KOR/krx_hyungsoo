# POC2 — BACKLOG 전수 감사·정리 CONCLUSION

작성일: 2026-06-29
성격: BACKLOG 정리 STEP 종료 기록. 코드·UI·API·데이터 계약·OCI·Telegram 변경 0건.

---

## 1. 지시 단일 목표

1270 라인 누적 BACKLOG 를 다음 Step 우선순위 판단 가능한 상태로 정리. 본 STEP 은
분석·문서 작업만 수행하고 기능 변경 0건.

---

## 2. 처리 절차

1. BACKLOG.md 16개 구획 1270 라인 전수 읽기 (Read 4회 + Agent 1회 위임 분석).
2. 각 항목을 5분류 (완료 / 현재 결함 / 중복 / 폐기 / 유지) 로 판정. 모호 항목 ❓ 표시.
3. 사용자에게 ❓ 항목 일괄 확인 (AskUserQuestion 3건, 모호 11건 일괄 판정).
4. 유지 항목만 통일 포맷 (항목 / 보류 사유 / 보류된 위험 / 재검토 트리거 4필드) 으로
   BACKLOG.md 재작성.
5. 현재 결함 2건은 STATE_LATEST.md §5 Open decisions 로 escalate.
6. STATE_LATEST §1 / §5 / §7 + POC2_B_NEXT_ACTIONS §0 동기화.

---

## 3. 5분류 판정 결과 (총 약 109건)

| 분류 | 건수 | 처리 |
| --- | --- | --- |
| 완료 (RESOLVED 처리) | 23 | BACKLOG.md "폐기 / 완료 정리 기록" 부록에 일괄 명시 |
| 폐기 (DISCARDED) | 11 | 동일 부록에 일괄 명시 |
| 중복 (DEDUPED) | 9 | 동일 부록에 일괄 명시 |
| 현재 결함 (DEFECT) | 2 | STATE_LATEST §5 D-1 / D-2 escalate |
| 유지 (HOLD) | 65 | 통일 포맷으로 재작성 |

---

## 4. 사용자 모호 항목 일괄 판정 (2026-06-29)

| 항목 (라인) | 사용자 판정 | 근거 |
| --- | --- | --- |
| L148 AI 투자세션 ETF 구성 수집 | 완료 → 제거 | Naver ETFComponent 채택과 구성종목 evidence 경로 흡수 |
| L400 보유 종목 상태 브리핑 상세 UI | 완료 → 제거 | 보유·후보 비교 v1 + 선택 후보 상세 영역 흡수 |
| L1067 Next.js UI 세분화 | 폐기 → 제거 | 사용자 가치 아닌 구현 방식 포괄 표현. 실제 구조부채는 KS-10 Step 에서 trigger·near-threshold 파일만 대상 |
| L1155 spike_watch / holding_watch 연계 | 완료 → 제거 | 3-PUSH 운영 경로에 급등락 / 보유 PUSH 흡수 |
| L828 market_cache 영속화 / 다중 환경 | 폐기 → 제거 | 과거 다중 환경 캐시 공유 구상. PC=분석/OCI=조회 분리 방향과 불일치 |
| L892 holdings 자동 불러오기 (KIS/CSV) | 폐기 → 제거 | 외부 연동 범위 확대. 향후 실제 수기 입력 병목 확인 시 새 과제로 재제안 |
| L360 SQLite 영구 보존 운영 정책 | 폐기 → 제거 | JSON SSOT·PARAM handoff 방향과 불일치. OCI read model 설계 시 새로 결정 |
| L14 ML 학습 / factor / threshold 후속 | 유지 → 통일 포맷 | 항목: "상대상승 축1 이후 factor·threshold·위험 축2 검토". 보류 사유: 상대상승 v0 는 첫 baseline. 보류된 위험: 성급한 점수 확장은 사용자 evidence 왜곡. 재검토 트리거: Cleanup 완료 후 시계열 기반 확보 + 다음 ML Step 단일 목표 확정 시 |
| L539 Layer B 급락 임계값 | STEP7C 통합 | 본질 동일. 단일 항목 "위험 evidence 의 급락·국면 경계 검증" 으로 통합 |

---

## 5. 유지 항목 16 카테고리 재구성 (4필드 91 항목)

| § | 카테고리 | 항목 수 |
| --- | --- | --- |
| 1 | ML / Factor / Threshold | 2 |
| 2 | 위험 evidence / 시계열 / 데이터 품질 | 6 |
| 3 | NAV / 시장 데이터 source | 17 |
| 4 | Market Discovery / Universe | 4 |
| 5 | ETF 구성종목 / 중복률 | 5 |
| 6 | 시장 국면 / Regime | 1 |
| 7 | 판단 근거 저장 (decision evidence) | 1 |
| 8 | Holdings / 포트폴리오 구조 | 8 |
| 9 | Message / Telegram / 알림 | 9 |
| 10 | UI / Frontend | 8 |
| 11 | OCI / Delivery / Operations | 11 |
| 12 | Snapshot / History / Audit | 1 |
| 13 | Universe / Cache 후순위 | 5 |
| 14 | Layer 활성 관리 (ASSUMPTIONS 연계) | 5 |
| 15 | 항구적 가드 정책 | 2 |
| 16 | 메타 / 검증 항목 | 3 |
| **합계 (BACKLOG 본문)** | | **91 항목 (grep 실측 4필드 각 91건 1:1)** |
| 부록 (외부 escalate) | 현재 결함 → STATE_LATEST §5 D-1 / D-2 | 2 |

> §3 의 17 / §11 의 11 등은 기존 BACKLOG 의 sub-bullet 을 별도 항목으로 분리하면서
> 발생. 1차 5분류 판정 시점의 유지 분류 결과 (sub-bullet 미승격 상태) 와 재작성 후 91 항목 의 차이 26 항목은 sub-bullet 승격분.
> 현재 결함 2건은 본 BACKLOG 외부 (STATE_LATEST.md §5 D-1 / D-2) 에 escalate.

---

## 6. STATE_LATEST escalate 결함 2건

### D-1 — test_three_push_contract 회귀
- **위치**: `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint`
- **상태**: Clean tree 에서도 실패. PARAM Handoff Step (2026-06-18) 이후 지속.
- **원인 추정**: spike_or_falling_alert 의 generate-from-unified endpoint 흐름이
  message_text 를 빈 / None 으로 채우는 회귀.
- **이전 우회**: 직전 Step `OCI_THREE_PUSH_OPERATION_REGISTRATION` 도 동일 회귀를
  BACKLOG 로 남기고 통과.
- **다음 액션 후보**: spike alert generate flow 의 message_text 빌더 호출 경로 추적
  + runtime builder 와의 분기 확인.

### D-2 — market_refresh_service in-memory state 재시작 시 소실
- **위치**: `app/market_refresh_service.py`
- **상태**: in-memory state + threading.Lock 으로 single-flight 구현. 서버 재시작 시
  running / last_success_at 모두 소실.
- **위험**: 다음 POST 시 6h cooldown 가드 깨짐 → 중복 수집 가능. frontend polling 이
  idle 로 인식하고 마지막 결과 못 받음.
- **다음 액션 후보**: market_refresh_log 마지막 row 의 unfinished 상태 감지 + 재기
  처리 + last_success_at 도 log 에서 복원. service module 의 reset / replay 함수
  도입.

---

## 7. 변경 산출물

| 파일 | 변경 | Measure-Object -Line |
| --- | --- | --- |
| `docs/backlog/BACKLOG.md` | 전면 재작성 (4필드 91 항목, 부록 / 완료·폐기·중복 기록 본 문서로 이전) | 451 |
| `docs/STATE_LATEST.md` | §1 prepend + §5 D-1/D-2 escalate + §7 BACKLOG audit 포인터 + r2 stale 정렬 | 375 |
| `docs/handoff/POC2_B_NEXT_ACTIONS.md` | §0 본 STEP 결과 prepend + 직전 §0 → §0-prev + r2 stale 정렬 | 796 |
| `docs/handoff/POC2_BACKLOG_AUDIT_CONCLUSION.md` | 신규 (본 문서) + r2 / r3 stale 정렬 | 99 |

**검증자 1차 REJECTED 후속 (2026-06-29, A-1 / A-2 / A-3)**: BACKLOG 항목들이 3필드 형태로 작성되어 지시문의 4필드 형식 위반 + 부록 (완료·폐기·중복 정리 기록 + 현재 결함 escalate) 이 본문에 잔존해 AC-5 위반 + 라인수 보고가 실측과 불일치 + CONCLUSION 신규 파일 untracked. 4건 모두 재작성으로 정정 — 91 항목 4필드 명시 / BACKLOG 본문에서 부록 전부 제거 → 본 문서에만 보존 / 보고서 라인수 표기를 Measure-Object -Line 실측값으로 정정 / CONCLUSION 파일 staged 처리.

**검증자 2차 REJECTED 후속 (2026-06-29, A-2 / A-3 stale 정합성)**: FIX r1 보고 라인수가 r1 추가 Edit 직후 실측과 불일치 + STATE_LATEST 최종 업데이트 날짜 / 라인수 표기 + NEXT_ACTIONS 유지 항목 수 + CONCLUSION §5 헤더의 과거 1차 판정 수치 잔존. 6개 위치 일괄 정정 (grep 전체 위치 확인 후 일괄) — STATE_LATEST 최종 업데이트 → 2026-06-29 BACKLOG 전수 감사 / STATE_LATEST BACKLOG 라인수 → Measure-Object -Line 기준 실측값 / 부록 라인수 표기 → 4필드 91 항목 / NEXT_ACTIONS 유지 항목 수 → 91 항목 (sub-bullet 26 승격 포함) / CONCLUSION §5 헤더 → 4필드 91 항목 / 본 §7 표의 4 파일 라인수 모두 r2 실측값으로 정정.

**검증자 3차 REJECTED 후속 (2026-06-29, A-2 / A-3 stale 정합성 r3)**: r2 후 STATE_LATEST §1 본문의 CONCLUSION 라인수 표기 + 본 §7 r2 정정 기록 본문 안의 과거 수치 인용 (4 파일 라인수 + 1차 판정 수치 + 변경 전 표현) 이 grep 시 stale 매치 발생. 3건 정정 — STATE_LATEST §1 CONCLUSION 라인수 → r3 실측값 / 본 §7 정정 기록 본문에서 과거 수치 인용 제거 → 추상화 표기 / §5 footnote 정정 표기 추상화.

코드·UI·API·데이터 계약·OCI·Telegram·테스트·schema·DB 변경 0건.

---

## 8. 다음 분기 권고 (사용자 결정 대기)

본 STEP 정리 결과 권고 우선순위:

1. **D-1 / D-2 결함 해소 STEP** (1~2일 분량). 본 STEP escalate 직후 처리 권고.
2. **위험 evidence 시계열 적재** (BACKLOG §2). ML 위험 축2 선행 조건.
3. **ML factor·threshold 1차 검증** (BACKLOG §1). 상대상승 v0 baseline 후속.
4. **OCI read model foundation** (PC_OCI_ARCHITECTURE_DIRECTION §5 4번 단계).
5. **runtime data source 확장** (BACKLOG §11). PUSH 메시지의 운영 컨텍스트 가치 향상.

본 권고는 사용자 결정 대기 — 자동 진행 0건.
