# POC2 — PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 Conclusion

작성일: 2026-06-20 / FIX r1: 2026-06-20 (정식 PARAM runtime builder + UI 단일 버튼 + sync state 부재/손상 분리)
STEP: PUSH_COPY_AND_PARAM_UI
상태: DONE

---

## 1. 목표 요약

지시문 §3 — 두 가지 단일 목표:

1. **Telegram PUSH 본문을 사용자 친화 메시지로 정리**
   - 운영 진단 로그 형식(`param_id`, `kr_realtime_price_snapshot=unavailable` 등)
     을 사람이 읽을 수 있는 짧은 안내로 변환.
2. **사용자가 CLI 없이 UI 한 번으로 OCI 에 PARAM 을 적용할 수 있게 한다**
   - `[현재 기준 OCI 적용]` 단일 버튼 → create + approve + sync + verify
     자동 수행.

---

## 2. 구현 결과

작업은 2 commit 으로 분할 진행.

### Phase A — PUSH 사용자 표현 정리 (commit `2a65b277`)

#### 신규 파일

| 파일 | 역할 |
|---|---|
| `app/push_user_labels.py` | source key 8종 → 사용자 표시 라벨 매핑 (`SOURCE_USER_LABELS`, `user_label_for`, `user_labels_for`). 미등록 key 는 안전 fallback("기타 데이터"). |
| `app/push_user_copy.py` | 전체 unavailable 시 축약 메시지 (`build_all_unavailable_message`) + 일부 available 시 별도 확인 블록 (`render_unavailable_block`) + KST 시각 포맷 (`format_asof_for_user`) + push_kind 별 unavailable source key 추출 (`collect_unavailable_source_keys`). |

#### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `app/message_market_briefing.py` | 섹션 헤더를 사용자 표시명으로 정렬 (`[시장 내부 신호]` → `[ETF 후보 흐름]`, `[위험 패턴 참고]` → `[위험 참고 데이터]`, `[추가 확인 필요 외부 변수]` → `[별도 확인 필요 외부 변수]`). 전체 unavailable 시 사용자 중심 fallback. 일부 available 시 별도 확인 블록 추가. |
| `app/message_spike_alert.py` | 동일 패턴. `[ETF universe 변동성 확대 관찰]` → `[ETF 변동성 확대 관찰]`, `[기존 급락 ETF 주의 신호 (PUSH 3 재사용)]` → `[급락 ETF 주의 신호]`. |
| `app/draft_message.py` | holdings briefing 의 `runtime_package.generation_status="failed"` 시 사용자용 unavailable 메시지로 즉시 종료. `_extract_source_keys_from_status` helper 신설 (missing_sections + warnings → 매핑된 source key 추출). |
| `app/draft_three_push.py` | message builder 호출 직전 `collect_unavailable_source_keys()` 로 unavailable key 추출 후 `unavailable_source_keys` 인자로 주입. |
| `scripts/run_three_push_oci.py` | raw 기술 식별자 11종 본문 노출 차단 (`_FORBIDDEN_RAW_IDENTIFIERS` + `_check_raw_identifiers`). PC builder 가 사용자 메시지를 만들지만 OCI runner 가 이중 안전망 역할. 감지 시 `status=skipped, reason=raw_identifier_exposed`. |
| `tests/test_three_push_contract.py` | 새 섹션 헤더 / 새 타이틀 assertion 으로 정렬. |

#### 사용자 표시 라벨 (지시문 §4.2 그대로)

| 내부 source key | Telegram 사용자 표현 |
|---|---|
| `kr_realtime_price_snapshot` | 국내 ETF 시세 |
| `overnight_us_market_snapshot` | 밤사이 미국 시장 |
| `market_discovery_snapshot` | ETF 후보 흐름 |
| `holdings_snapshot` | 보유 종목 평가 |
| `nav_discount_snapshot` | NAV·괴리율 |
| `universe_momentum_snapshot` | 급등락 관찰 |
| `ml_baseline_v0` | 위험 참고 데이터 |
| `news_snapshot` | 주요 뉴스 |

#### 메시지 본문 예시 (전체 unavailable)

```
[시장 흐름 브리핑]

기준 시각: 6월 20일 14:14

오늘은 자동 확인 가능한 시장 데이터가 부족해
시장 해석을 보류합니다.

별도 확인 필요
• 국내 ETF 시세
• 밤사이 미국 시장
• ETF 후보 흐름
• 주요 뉴스

이 알림은 시장 확인용 정보이며 직접적인 매매 지시는 아닙니다.
```

---

### Phase B — PARAM 적용 UI 연결 (commit 이번 commit)

#### 신규 backend 파일

| 파일 | 역할 |
|---|---|
| `app/api_three_push_param.py` | `/three-push/param/state` (GET) + `/three-push/param/apply` (POST) router. state: latest PARAM 파일 + sync status 읽어 사용자 친화 dict 반환. apply: manual_seed PARAM 생성 + latest 승격 + `sync_three_push_runtime_param.py` subprocess 호출 + sync_status_latest.json 확인. 응답에 raw 식별자 (param_id / SSH target / remote path / 파일명 / raw stderr) 노출 0건. |

#### 수정 backend 파일

| 파일 | 변경 내용 |
|---|---|
| `app/api.py` | `three_push_param_router` import + include. |

#### 신규 frontend 파일

| 파일 | 역할 |
|---|---|
| `frontend/lib/api/threePushParam.ts` | TS API client (`fetchThreePushParamState`, `applyThreePushParamToOci`). apply timeout 120 초. |
| `frontend/app/components/ThreePushParamCard.tsx` | 현재 운영 기준 카드 + 단일 동작 버튼. 표시: 적용 기준 / OCI 반영 상태 / 마지막 적용 시각 / 사용자용 메시지. 진행 상태 단계 표시 (운영 기준 생성 중 → OCI 적용 중 → OCI 반영 확인 중 → 적용 완료). 실패 시 자동 refresh 로 기존 state 표시. |

#### 수정 frontend 파일

| 파일 | 변경 내용 |
|---|---|
| `frontend/app/components/ApprovalTelegramView.tsx` | `ThreePushParamCard` 를 `ThreePushDraftCard` 상단에 배치. |

#### 신규 테스트

| 파일 | 테스트 항목 |
|---|---|
| `tests/test_three_push_param_api.py` | (1) state 응답 형식 정확히 5개 필드 (status / display_label / applied_at / oci_verified / message). (2) display_label 이 raw 식별자가 아닌 사용자 친화 문자열. (3) apply 실패 시 raw 식별자 (param_id / ssh_target / remote_dir / TELEGRAM_BOT_TOKEN / scp 등) 응답 노출 0건 + status="failed" + oci_verified=false. |

---

## 3. AC 달성 현황

| AC | 내용 | 결과 |
|---|---|---|
| AC-1 | Telegram raw 기술 식별자 제거 | DONE — PC builder 가 사용자 메시지 생성 + OCI runner 가 11종 raw 식별자 노출 차단 이중 안전망 |
| AC-2 | 사용자 중심 unavailable 표현 | DONE — `SOURCE_USER_LABELS` 8종 매핑 |
| AC-3 | 전체 unavailable 메시지 축약 | DONE — `build_all_unavailable_message` |
| AC-4 | 일부 available 메시지 구조 | DONE — 헤더 + 본문 섹션 + 별도 확인 블록 + 짧은 주의 문장 |
| AC-5 | 현재 운영 기준 카드 | DONE — `ThreePushParamCard` (적용 기준 / OCI 상태 / 적용 시각) |
| AC-6 | 단일 적용 동작 | DONE — `POST /three-push/param/apply` 가 create + approve + sync + verify 동기 처리 |
| AC-7 | CLI 직접 실행 불필요 | DONE — UI 한 번으로 완료. 기존 CLI 는 smoke test 용으로 유지 |
| AC-8 | 적용 진행 상태 표시 | DONE — UI 단계 progress 표시 (생성 중 → 적용 중 → 확인 중 → 완료) |
| AC-9 | 실패 시 기존 PARAM 보호 | DONE — sync 스크립트가 atomic rename + verify 후 교체. 실패 시 latest 파일 변경 없음. UI 실패 시 자동 refresh 로 직전 state 표시 |
| AC-10 | secret 비노출 | DONE — token / chat_id / SSH key / remote path / raw command 응답 노출 0건. 테스트로 보호 |
| AC-11 | 기존 PARAM runtime guard 유지 | DONE — `scripts/run_three_push_runtime_oci.py` 의 guard 7종 (latest PARAM fail-closed / enabled_push_kinds / forbidden wording / secret 비노출 / enable flag / duplicate / Telegram 마스킹) 전부 보존. FIX r1 에서 raw 식별자 차단 §4-b 단계만 추가 (기존 guard 약화 0건) |
| AC-12 | 기존 산식 불변 | DONE — 메시지 본문의 helper 함수 (compute_topn / build_runtime_package 등) 산식 변경 0건 |
| AC-13 | 범위 통제 | DONE — ML 학습 / 위험 감지 / 점수·버킷 / 메인 판단 화면 / 신규 source 0건 |
| AC-14 | 문서 갱신 | DONE — STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY / 본 CONCLUSION |

---

## 4. 제외 범위 준수 확인

| 항목 | 결과 |
|---|---|
| ML 학습 / 튜닝 / 백테스트 | 0건 |
| 위험 감지 기능 | 0건 |
| 점수 / 버킷 산식 | 0건 |
| ETF 고밀도 메인 판단 화면 | 0건 |
| RSI 계산 | 0건 |
| 신규 시장 데이터 source | 0건 (`news_snapshot` 사용자 라벨만 등록, 실제 source 도입 0건) |
| PARAM 편집 UI | 0건 |
| PARAM 후보 다중 관리 | 0건 |
| 신규 DB | 0건 |
| 신규 scheduler framework | 0건 |
| crontab 구조 변경 | 0건 |
| BACKLOG Cleanup | 0건 |
| 매수 / 매도 / 비중 조절 판단 | 0건 |

---

## 5. 실행 방법

### Phase A: 메시지 빌더

PC 측에서 기존과 동일하게 `POST /runs/generate` (PUSH-1/3) 또는 `POST
/runs/generate-from-holdings` (PUSH-2) 호출 시 자동으로 사용자 친화 메시지 생성.

### Phase B: UI

```
http://localhost:3000 → Approval / Telegram → 현재 운영 기준 카드
→ [현재 기준 OCI 적용] 버튼 클릭 → 진행 단계 표시 → 결과 표시
```

API 직접 호출도 가능:
```bash
curl -X GET http://127.0.0.1:8000/three-push/param/state
curl -X POST http://127.0.0.1:8000/three-push/param/apply
```

---

## 6. 검증 결과 (FIX r1 최종)

- black / flake8: **PASS**
- backend pytest: **584 passed** (회귀 0). Phase A/B 시점은 581 passed 였으며
  FIX r1 에서 신규 테스트 3건 추가로 584 passed.
  - 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`) 은
    본 STEP 이전부터 존재하는 회귀 (universe / runtime probe 데이터 의존).
- frontend npm run lint: **PASS**
- frontend npm run build: **PASS**
- 신규 의존성: 없음

---

## 7. 보안 / 노출 차단 확인

| 확인 항목 | 결과 |
|---|---|
| Telegram 본문에 raw 기술 식별자 노출 | 0건 (PC builder + OCI runner 이중 차단) |
| `GET /three-push/param/state` 응답에 `param_id` / `manual_seed` / SSH 정보 | 0건 (테스트로 보호) |
| `POST /three-push/param/apply` 실패 시 raw stderr / scp 명령 노출 | 0건 (테스트로 보호) |
| frontend 화면에 `_` 포함 snake_case 라벨 노출 | 0건 (`display_label` 사용자 친화 변환) |
| token / chat_id / SSH key 응답 포함 | 0건 |

---

## 8. FIX r1 (검증자 1차 REJECTED 후속)

검증자 1차 REJECTED 사유 4건 모두 수용 및 해소.

### FIX-1 (A-1 / B-5) — 정식 PARAM runtime builder 의 raw 식별자 제거

**문제**: 정식 OCI runner (`scripts/run_three_push_runtime_oci.py`) 가 사용하는
`app/three_push_runtime_message_builder.py` 가 여전히 본문에 `param_id` /
`param_source` / `push_kind` / snake_case source key 를 직접 출력하고 있었음.
PC builder 만 사용자 메시지로 수정됐고 fallback runner 만 raw 식별자 차단이
적용된 상태.

**수정**: `build_runtime_message()` 를 사용자 중심으로 재작성.
- raw 식별자 본문 노출 0건 (PARAM 은 status 기록/duplicate guard 용으로만 사용).
- 전체 unavailable 시 `app.push_user_copy.build_all_unavailable_message()` 호출
  → 지시문 §4.3 예시 형식 그대로 (헤더 + 기준 시각 + 안내 + "별도 확인 필요"
  사용자 라벨 + 짧은 주의 문장).
- 일부 available 시 사용자 라벨 + `render_unavailable_block()` 호출 → §4.4.
- `PUSH_KIND_KOREAN["spike_or_falling_alert"]` 를 `"급등락·상승 관찰 신호"` 로
  정렬 (PUSH_KIND_HEADERS 와 일치).

### FIX-2 (A-1 / A-2 / B-5) — 정식 runner 에 raw 식별자 차단 안전망

**문제**: raw 식별자 차단이 fallback runner (`run_three_push_oci.py`) 에만
있고 정식 runtime runner (`run_three_push_runtime_oci.py`) 에는 없었음.

**수정**:
- `app/three_push_runner_common.py` 에 `FORBIDDEN_RAW_IDENTIFIERS` 상수 + `check_raw_identifiers()` 함수 추가.
- `scripts/run_three_push_runtime_oci.py` 의 message 검증 단계 (§4) 다음에 §4-b
  로 raw 식별자 검사 추가. 감지 시 `status=failed, reason=raw_identifier_exposed`.
- `scripts/run_three_push_oci.py` 의 로컬 검사 함수는 그대로 유지 (양쪽 runner
  공통 안전망).

### FIX-3 (A-3 / B-6) — 테스트 갱신

**문제**: `tests/test_three_push_runtime_message_builder.py` 가 `param_id` /
`param_source` / `push_kind` 가 본문에 포함되어야 한다는 구 계약을 검증.

**수정**: 새 사용자 메시지 계약에 맞게 8개 테스트 전면 재작성.
- `test_message_has_no_raw_identifiers` (parametrize 3종) — 본문에 raw 식별자
  노출 0건 검증.
- `test_message_all_unavailable_uses_user_centric_copy` — 모든 source unavailable
  시 지시문 §4.3 예시 문구 + 사용자 라벨 노출 확인.
- `test_message_partial_available_shows_user_labels` — 일부 available 시 사용자
  라벨 + 별도 확인 필요 블록 노출.
- 기존 unavailable / available 테스트는 새 라벨 기반으로 정렬.

### FIX-4 (A-1 / §5.3) — UI 단일 버튼 (상태 새로고침 제거)

**문제**: `ThreePushParamCard` 에 `[현재 기준 OCI 적용]` 외에 `[상태 새로고침]`
버튼이 추가로 있어 지시문 §5.3 "버튼은 하나만 둔다" 와 충돌.

**수정**: `[상태 새로고침]` 버튼 제거. 카드 마운트 시 자동 조회는 유지하며
사용자가 명시적으로 새로고침할 필요가 없도록 함.

### FIX-5 (B-1) — sync status JSON 부재 / 손상 분리

**문제**: `_read_sync_status()` 가 파일 부재와 JSON 손상을 같은 `{}` 로 반환해
운영 상태 손상 감지가 흐려짐.

**수정**:
- `_read_sync_status()` 가 `(state, payload)` 튜플 반환으로 변경.
  state 는 `SYNC_STATE_MISSING` / `SYNC_STATE_CORRUPTED` / `SYNC_STATE_OK` 3종.
- 손상은 logger.warning 로 기록 + 사용자에게는 `verification_required` 상태로
  표시 ("운영 상태 파일을 읽지 못했습니다. 한 번 더 적용 후 결과를 확인해 주세요.").
- `_read_latest_param_display_label()` 도 부재 / 손상 / 정상 3분리 + 손상 시
  logger.warning.

### FIX r1 검증

- pytest **584 passed** (회귀 0). 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`) 은 본 STEP 전부터 존재.
- black / flake8 PASS. frontend lint / build PASS.
- 정식 runtime builder 실측 — market_briefing / holdings_briefing / spike_or_falling_alert
  3종 모두 raw 식별자 노출 0건. 사용자 라벨로만 표시. 지시문 §4.3 예시와 일치.

---

## 9. 다음 단계 (사용자 결정 대기)

1. **BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP** — 기존 회귀 1건 정리.
2. **scheduled run 관찰 + 운영 진단 UI** — OCI runner status/history read-only.
3. **PARAM 후보 다중 관리 / 편집 UI** — 본 STEP 제외 항목. 정책 결정 후.
4. **PUSH-1 의 뉴스 source 도입** — `news_snapshot` 사용자 라벨만 등록됨.
