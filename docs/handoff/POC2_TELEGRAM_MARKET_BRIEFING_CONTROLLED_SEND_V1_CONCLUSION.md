# Telegram Market Briefing Controlled Send v1 — Conclusion (PARTIAL · Q5 절차 이탈)

작성일: 2026-07-18
성격: 신규 기능 개발 X. 기존 OCI Runtime · Telegram send · sent registry 계약을 그대로 사용해 `market_briefing` 을 실제 1회 발송하고 중복 차단을 실측.

## 1. revision

- OCI `git log --oneline -1`: `90f18f58 docs(universe-momentum-evidence-publication-v1): DONE closeout ...`
- 코드 변경 없음. 소스는 이전 STEP 종료 시점 그대로.

## 2. Preview 결과 (2026-07-18 14:32 KST)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode dry-run`

| 필드 | 값 |
|---|---|
| runtime_kst | 2026-07-18T14:32:23+09:00 |
| runtime_date_kst | 2026-07-18 |
| param_id (masked) | ****757435 |
| param_source | manual_seed |
| contentful_fact_count | 3 |
| selection_result_count | 10 |
| message_text_length | 393 |
| telegram_attempted | false |
| telegram_sent | false |

Raw `param_id` 는 확정된 Q2 계약 (사용자 보고 비노출) 에 따라 마스킹. 실측 OCI record 에는 원문 있으나 문서에는 마지막 6자리만 표기.

Preview 본문 (일부 축약):

```
[시장 흐름 브리핑]
기준 시각: 7월 18일 14:32
지금 확인된 항목 · 별도 확인 필요 · KODEX200 / KOSPI 최근 수익률 (2026-07-03 기준) ·
Market Discovery 후보 10종 상위 · "이 알림은 시장 확인용 정보이며 직접적인 매매 지시는 아닙니다."
```

- 금지 문구 없음 (Runner check_forbidden_wording 통과)
- Raw 기술 식별자 없음 (Runner check_raw_identifiers 통과)
- 개인정보 없음

## 3. Preview 부가 확인

### 3.1 Telegram 설정 (env 안전 조회)

| 항목 | 값 |
|---|---|
| telegram_token_configured | true |
| telegram_chat_configured | true |
| telegram_target_masked | ****5904 |

Token 원문 · chat ID 원문 미노출. env 전체 미출력.

### 3.2 Autosend flags

| flag | 값 |
|---|---|
| PUSH_AUTOSEND_ENABLED | true |
| PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED | true |
| PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED | true |
| PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED | true |

지시문 §6 준수: flag 변경 X (사용자 지시 확인-1 (c)).

### 3.3 자동 실행 위험 확인 (읽기 전용)

- crontab (사용자): 3개 등록.
  - PUSH-1 market_briefing 평일 08:00 KST
  - PUSH-2 holdings_briefing 평일 12:30 KST
  - PUSH-3 spike_or_falling_alert 평일 15:30 KST
- 시스템 crontab: 매치 없음
- systemd timer / service: 없음
- 실행 시점 KST: 2026-07-18 (토) 14:41. **모두 평일 필터(`1-5`) 밖 → 이번 세션 중 자동 실행 위험 없음**
- 결과: flag/스케줄 변경 없이 그대로 진행

### 3.4 Duplicate key 사전 상태

| 항목 | 값 |
|---|---|
| duplicate_key_contract | push_kind + "::" + param_id + "::" + runtime_date_kst |
| current_duplicate_key_exists (send 전) | false |
| sent_registry_total_before_send | 62 |

## 4. 사용자 발송 승인

- 승인 시점: Preview 전문 (2026-07-18 14:32 KST 기준) 전달 후.
- 승인 내용: chat ****5904 로 정확히 1회 발송.
- 재승인 조건 (Q5): market 기준일 / 본문 / contentful fact 수 / selection 수 / 주요 수치 중 하나라도 변경 시 재승인.

## 4.1 절차 이탈 (procedural deviation)

- **이탈 내용**: 지시문 Q5 계약 (사용자 승인 → 동일 dry-run 재실행 → 승인 preview 와 비교 → send) 중 **"동일 dry-run 재실행 → 비교" 단계가 생략** 됨.
- **경위**: 개발자는 Phase D.1 로 "send 직전 dry-run" 재실행을 안내했으나, 사용자가 곧바로 D.2 `--mode send` 를 실행. Phase D.1 record 는 생성되지 않음.
- **사후 확인**: send record 의 5필드 (`param_id` · `runtime_date_kst` · `contentful_fact_count` · `selection_result_count` · `message_text_length` 393) 가 승인 시점 preview 와 완전 일치. 사용자 수신 본문도 preview 본문과 기준 시각 표기만 차이 (14:32 → 14:42).
- **결과 판정**: 우연히 내용 변화가 없어 실질 위해 없음. 그러나 절차 자체는 계약 이탈. §11 AC 목록은 명문 항목 (AC-1~AC-7) 은 충족이지만, Q5 재확인 계약은 이탈로 기록.
- **재발 방지 (다음 STEP)**: send 직전 재확인 dry-run 을 사용자 실행 명령셋에서 **선행 단독 단계** 로 분리 안내하고, 재확인 record 를 사용자 회신에 요구한 후에만 send 명령을 안내.

## 5. 첫 발송 결과 (2026-07-18 14:42 KST)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send`

| 필드 | 값 |
|---|---|
| status | sent |
| runtime_kst | 2026-07-18T14:42:47+09:00 |
| runtime_date_kst | 2026-07-18 |
| param_id | ****757435 |
| param_source | manual_seed |
| contentful_fact_count | 3 |
| selection_result_count | 10 |
| message_text_length | 393 |
| duplicate_key | market_briefing::****757435::2026-07-18 |
| telegram_attempted | true |
| telegram_sent | true |
| error | null |

승인 시점 preview 대비 5필드 완전 동일. `runtime_kst` 시각 문자열만 14:32 → 14:42 로 변경.

## 6. 사용자 수신 확인

- 대상: chat ****5904 (올바른 대상)
- 도착 건수: 1건
- 본문: preview 와 의미상 완전 동일. 기준 시각 표기만 14:32 → 14:42 반영.
- 잘림 · 문자 깨짐 없음
- 내부 식별자 · 개인정보 · 금지 문구 없음
- 실측 회신: "텔레그램 수신했습니다" + 실제 수신 메시지 전문 (§5 record 의 msg 본문과 완전 일치)

## 7. sent registry 전후

| 시점 | count |
|---|---|
| 발송 전 | 62 |
| 첫 발송 후 | 63 (delta = +1) |
| 재실행 후 | 63 (delta = 0) |

## 8. 중복 차단 실측 (2026-07-18 14:44 KST)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send` (동일 키 재실행)

| 필드 | 값 |
|---|---|
| status | skipped |
| reason | duplicate_runtime |
| telegram_attempted | false |
| telegram_sent | false |
| duplicate_key | market_briefing::****757435::2026-07-18 (첫 발송과 완전 동일) |

Runner 로그: `중복 발송 차단: market_briefing::****757435::2026-07-18`

Telegram 두 번째 메시지 도착 없음 (사용자 실측 확인).

## 9. 실제 Telegram 발송 총 건수

- 이번 STEP: **1건** (market_briefing, chat ****5904, 2026-07-18 14:42 KST)
- Holdings briefing: 0건
- Spike or falling alert: 0건

## 10. 코드 변경 및 테스트

- 코드 변경: **없음**
- 신규 focused test: 없음 (지시문 §7 · 코드 변경이 없으므로)
- 전체 backend regression: 없음 (지시문 §7 · 코드 변경이 없으므로)

## 11. AC 충족

| AC | 상태 |
|---|---|
| AC-1 사용자 승인 전 발송 없음 | ✅ |
| AC-2 기존 Runtime send 경로로 market briefing 1회 발송 | ✅ |
| AC-3 올바른 Telegram 대상 1건 수신 | ✅ (chat ****5904) |
| AC-4 sent registry +1 | ✅ (62 → 63) |
| AC-5 동일 키 재실행 sender 미호출 + registry +0 | ✅ (skipped, 63 유지) |
| AC-6 내부 식별자·개인정보·금지 문구 없음 | ✅ (수신 메시지 본문 기준) |
| AC-7 Holdings·Spike 미발송, scheduler·PARAM·DB 계약 불변 | ✅ (오늘=토, cron 요일 필터 밖. 코드 변경 없음. DB schema 불변) |
| (참고) Q5 send 직전 재확인 dry-run | ⚠ 이탈 (§4.1 절차 이탈 참조. AC 명문 항목 아님) |

## 12. 지시문 §6 금지사항 준수

- Holdings briefing 실제 발송: X
- Spike alert 실제 발송: X
- Telegram API 직접 호출: X (기존 `telegram_send` 만 사용)
- 별도 전송 스크립트 작성: X
- 메시지 본문 수동 변경: X
- 중복 키 변경: X
- sent registry 삭제/수동 수정: X (오직 mark_sent 자동 기록)
- scheduler 활성화/변경: X
- PARAM 변경: X
- DB schema 변경: X
- 신규 source 연결: X
- Telegram 문구 개선: X
- 실패 후 자동 반복 재전송: X (첫 발송 성공)

## 13. 최종 상태

```
status = PARTIAL
next_step_gate = TELEGRAM_HOLDINGS_BRIEFING_CONTROLLED_SEND_V1
user_decision = (a) Q5 절차 이탈 수용 · 재발 방지 규칙 §4.1 적용 조건 하에 다음 STEP 진입
```

**PARTIAL 사유**: 발송·수신·중복 차단 실측 (AC-1~AC-7 명문 항목) 은 전부 충족. 그러나 지시문 Q5 확정 계약 "승인 → send 직전 재확인 dry-run → 내용 비교 → send" 순서 중 재확인 dry-run 단계가 이탈. 사후 소급 실행으로 계약을 충족할 수 없음 (재확인은 send **직전** 이어야 함). 지시문 §9 FAIL 목록 (승인 전 발송 · 잘못된 대상 · 두 번째 메시지 발송 · send 실패인데 registry 기록 · Holdings·Spike 동시 발송 · 내부 식별자 노출) 어디에도 해당하지 않아 FAIL 은 아님.

**사용자 최종 결정 (2026-07-18)**: **(a) 이탈 수용**. 이번 STEP 을 PARTIAL 로 종료하되 다음 STEP 진입 승인. §4.1 재발 방지 규칙 (send 직전 재확인 dry-run 을 사용자 실행 명령셋에서 선행 단독 단계로 분리 안내, 재확인 record 회신 받고서만 send 명령 안내) 은 다음 STEP (`Telegram Holdings Briefing Controlled Send v1`) 부터 무조건 적용.

다음 STEP 후보 (설계자 지시 대기): `Telegram Holdings Briefing Controlled Send v1`.
