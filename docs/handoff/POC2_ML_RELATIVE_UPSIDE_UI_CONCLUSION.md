# POC2 — ML 축1 상대상승 점수 실행 UI 연결 Conclusion

작성일: 2026-06-21 / FIX r1: 2026-06-21 (실패 분기 기존 snapshot 보존 + 응답 6 필드 정정 + meta 손상 분리 + 테스트 격리) / FIX r2: 2026-06-21 (stale 주석/문서 정합성 정정)
STEP: ML_RELATIVE_UPSIDE_UI
상태: DONE

---

## 1. 목표 요약

지시문 단일 목표: 기존 `relative_upside_score_v0` 실행을 Market Discovery UI 에
연결한다. 사용자가 CLI 없이 화면에서 상대상승 참고점수를 계산하고, 정상 실행
여부를 확인할 수 있게 한다.

본 STEP 은 §2.29 "ML 축1 — 후보 ETF 상대상승 참고점수 v0" 의 후속이며, 모델 /
feature / target / score 산식은 그대로 둔다.

---

## 2. 구현 결과

### 신규 backend

| 파일 | 역할 |
|---|---|
| `app/api_ml_relative_upside.py` | `POST /market/relative-upside/run` router. 동기 처리 — `scripts.run_ml_relative_upside_score_v0.main()` 을 직접 import 호출. 응답 6 필드 (status / asof_date / generated_at / scored_candidate_count / gpu_execution_used / message). 실패 / rc≠0 / meta 손상 / meta.status≠ok 4분기 처리 (FIX r1 — 손상 분리). raw 식별자 (device name / loss / epoch / artifact path / traceback) 노출 0건. |

### 수정 backend

| 파일 | 변경 |
|---|---|
| `app/api.py` | `ml_relative_upside_router` import + include. |

### 신규 frontend

| 파일 | 역할 |
|---|---|
| `frontend/lib/api/mlRelativeUpside.ts` | TS API client. POST 동기 호출 timeout 120s. |
| `frontend/app/components/RelativeUpsideRunCard.tsx` | Market Discovery 후보 목록 상단 카드. 상태 / 기준일 / 마지막 계산 / 점수 반영 후보 수 / GPU 실행 표시. 단일 버튼 `[상대상승 점수 계산]`. running 중 중복 클릭 차단. 실패 시 기존 result 유지 + 사용자용 generic 실패 메시지. |

### 수정 frontend

| 파일 | 변경 |
|---|---|
| `frontend/app/components/MarketDiscoveryView.tsx` | `RelativeUpsideRunCard` 를 `MarketContextCard` 다음에 배치. `onSuccess={loadTopn}` 으로 성공 시 후보 표 자동 재조회. |

### 신규 테스트

| 파일 | 건수 | 범위 |
|---|---|---|
| `tests/test_api_ml_relative_upside.py` | 7 | 성공 6 필드 응답 / GPU 미확인 메시지 / 예외 시 기존 meta 파일 변경 0건 / rc≠0 → failed / meta.status≠ok → unavailable / meta 손상 → unavailable / **main() unavailable 분기에서 기존 score snapshot 파일 덮어쓰기 0건** (A-1 핵심 검증). 응답에 raw 식별자 노출 0건 검증. 모든 테스트 monkeypatch 로 `RUN_META_PATH` / `SCORE_SNAPSHOT_PATH` 격리 (B-6 — 운영 artifact 오염 차단). |

---

## 3. 완료 기준 (지시문) 달성 현황

| 항목 | 결과 |
|---|---|
| 1. UI 버튼으로 점수 계산 가능 | DONE — `RelativeUpsideRunCard` 버튼 1개 |
| 2. 계산 중 / 성공 / 실패 상태 표시 | DONE — badge 5종 (미실행 / 계산 중 / 완료 / 실패 / 데이터 부족) |
| 3. 성공 후 후보 표 점수 자동 갱신 | DONE — `onSuccess={loadTopn}` 콜백으로 `GET /market/topn/latest` 재호출 |
| 4. 기준일 / 실행 시각 / 후보 수 / GPU 여부 표시 | DONE — 사용자용 4 표시 항목 + status / message |
| 5. 실패해도 기존 점수 유지 | DONE — (a) `main()` 예외 raise 시 atomic write 가 호출되지 않아 파일 변경 0건. (b) **FIX r1**: `main()` 의 `model is None` 또는 `inference_rows` 빈 분기에서 빈 snapshot 저장 코드를 제거 → 기존 `SCORE_SNAPSHOT_PATH` 그대로 유지. `RUN_META_PATH` 만 갱신 (이력 추적, `snapshot_path=""` 명시). 단위 테스트 `test_main_unavailable_branch_does_not_overwrite_existing_snapshot` 로 검증. |
| 6. 기존 모델 / feature / target / score 산식 불변 | DONE — `app/ml_relative_upside_features.py` / `_model.py` / `_score.py` 변경 0건 |
| 7. OCI / PUSH / PARAM 회귀 없음 | DONE — 관련 모듈 변경 0건 |
| 8. backend tests / black / flake8 / frontend lint / build 통과 | DONE — pytest 613 passed (608 → +5), 회귀 0 |

---

## 4. 데이터 계약

### POST /market/relative-upside/run 응답 (6 필드)

```json
{
  "status": "ok" | "failed" | "unavailable",
  "asof_date": "YYYY-MM-DD" | null,
  "generated_at": "ISO-8601" | null,
  "scored_candidate_count": number | null,
  "gpu_execution_used": true | false | null,
  "message": "사용자용 상태 문장"
}
```

응답에 포함하지 않는 것 (지시문 — 일반 UI 노출 금지):
- CUDA device name
- loss / epoch
- artifact path / snapshot path
- raw traceback
- shell command
- feature vector

### 사용자 친화 message 분기

| 분기 | message |
|---|---|
| 성공 + GPU=true | "상대상승 참고점수 계산이 완료되었습니다." |
| 성공 + GPU=false | "계산은 완료됐지만 GPU 실행은 확인되지 않았습니다." |
| `main()` 예외 raise | "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다." |
| `main()` rc≠0 | (동일 — failed 분기) |
| `main()` rc=0 이지만 meta.status≠ok | "계산은 시도했지만 점수를 생성하지 못했습니다. 기존 점수는 유지됩니다." |
| run meta 파일 손상 (JSON parse 실패) — FIX r1 신규 분기 | "운영 상태 파일을 읽지 못했습니다. 기존 점수는 유지됩니다." (응답 `status=unavailable`) |

---

## 5. 실측 결과

### POST 실측 (2026-06-21)

```json
{
  "status": "ok",
  "asof_date": "2026-06-19",
  "generated_at": "2026-06-20T15:49:18.513003+00:00",
  "scored_candidate_count": 1111,
  "gpu_execution_used": true,
  "message": "상대상승 참고점수 계산이 완료되었습니다."
}
```

CUDA RTX 4070 SUPER 학습 + 1,111 후보 점수 부여 + 응답에 device name / loss / NVIDIA / artifact path 노출 0건.

### 단위 테스트

5건 모두 PASS. 핵심:
- `test_run_failure_preserves_existing_snapshot` — `main()` 이 `secret_path=/etc/x` 를 포함한 `RuntimeError` raise → 응답 status=failed + 응답 텍스트에 `secret_path` 노출 0건 + 기존 meta 파일 content 변경 0건.
- `test_run_success_returns_user_only_fields` — 성공 응답에 `NVIDIA` / `device_name` / `loss` / `epoch` / `snapshot_path` / `Traceback` 노출 0건.

### 회귀 확인

- pytest 608 → 613 (+5 신규, 회귀 0).
- `app/ml_relative_upside_features.py` / `_model.py` / `_score.py` / `scripts/run_ml_relative_upside_score_v0.py` 변경 0건.
- `scripts/run_three_push_runtime_oci.py` / `app/three_push_runtime_message_builder.py` / `app/api_three_push_param.py` 변경 0건.
- 기존 `GET /market/topn/latest` 응답 구조 (candidates 머지 포함) 변경 0건.

---

## 6. 제외 범위 준수 확인

| 항목 | 결과 |
|---|---|
| 모델 구조 변경 | 0건 |
| 신규 factor | 0건 |
| 학습 기간 확장 | 0건 |
| 튜닝 | 0건 |
| 위험 ML 결합 | 0건 |
| 점수 threshold / 등급 / 버킷 | 0건 |
| OCI / PARAM / Telegram 변경 | 0건 |
| 신규 DB | 0건 |
| 신규 scheduler | 0건 |
| 새 메뉴 / 새 화면 | 0건 (기존 Market Discovery 화면에 카드 1개 추가) |
| 모바일 화면 | 0건 |

---

## 7. 검증 결과

| 항목 | 결과 |
|---|---|
| backend pytest | **615 passed** (608 → +7 신규 FIX r1 후, 회귀 0). 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`) 은 본 STEP 이전부터 존재 |
| black | PASS |
| flake8 | PASS |
| frontend npm run lint | PASS |
| frontend npm run build | PASS |
| POST 실측 | status=ok, scored 1,111, gpu=true |
| 실패 시 기존 snapshot 보존 | 단위 테스트로 검증 (파일 content 변경 0건) |
| 응답 raw 식별자 노출 | 0건 (단위 테스트로 검증) |
| 신규 의존성 | 없음 |

---

## 8. FIX r1 (검증자 1차 REJECTED 후속)

검증자 1차 REJECTED 사유 4건 모두 수용 및 해소.

### FIX-1 (A-1 / A-2) — 실패 시 기존 score snapshot 보존

**문제**: `scripts/run_ml_relative_upside_score_v0.py:169-196` 의 unavailable/failed
분기에서 `display_scores={}` 인 빈 snapshot 을 `save_score_snapshot()` 으로
저장 → 기존 정상 점수를 빈 snapshot 으로 덮어쓰는 결함. 보고서는 "기존 점수
유지" 라고 했으나 실제 코드는 그렇지 않음.

**수정**: 해당 분기에서 `save_score_snapshot()` 호출 제거. `RUN_META_PATH` 만
갱신 (status=failed/unavailable + `snapshot_path=""` 명시 — "snapshot 저장 안
함"). 기존 `SCORE_SNAPSHOT_PATH` 는 그대로 유지.

**검증**: `test_main_unavailable_branch_does_not_overwrite_existing_snapshot` —
정상 snapshot 기록 후 `train_walk_forward` 가 model=None 반환하도록 patch +
`list_etf_tickers` / `fetch_price_history` stub. main() 호출 후 snapshot 파일
content 변경 0건 + run meta 의 `snapshot_path=""` 확인.

### FIX-2 (A-3) — CONCLUSION 응답 필드 수 5 → 6 정정

**문제**: 응답에 `status` 가 포함된 6 필드인데 CONCLUSION 문서는 "5 필드"
라고 표기 (지시문 문구 그대로 옮기다 status 누락).

**수정**: §2 신규 backend 표 / §4 데이터 계약 헤더 / §3 5번 셀의 "5 필드"
표기를 모두 6 필드로 정정.

### FIX-3 (B-1) — run meta 손상 / 부재 분리

**문제**: `_read_run_meta()` 가 파일 부재 / JSON 손상 / 타입 불일치를 모두
`{}` 로 흡수 → 손상과 데이터 부족이 응답에서 구분되지 않음.

**수정**: `(state, payload)` 튜플 반환 — `META_STATE_MISSING` /
`META_STATE_CORRUPTED` / `META_STATE_OK` 3분리. 손상 시 logger.warning + 사용자
응답에 별도 메시지 ("운영 상태 파일을 읽지 못했습니다. 기존 점수는 유지됩니다.").

**검증**: `test_run_meta_corrupted_returns_unavailable` — `not a valid json {{{`
를 meta 파일에 작성 후 POST 호출. 응답 status=unavailable + "운영 상태 파일을
읽지 못했습니다" 메시지 + raw 식별자 노출 0건.

### FIX-4 (B-6) — 테스트가 실제 runtime artifact 직접 수정하는 문제 차단

**문제**: 기존 테스트 5건이 `state/ml/relative_upside_score_run_latest.json`
실제 경로를 직접 write → 운영 artifact 오염 위험. 또한 frontend API 주석에
"subprocess" 라고 stale 표기.

**수정**:
- `isolated_meta` fixture 추가 — `tmp_path` 로 `RUN_META_PATH` /
  `SCORE_SNAPSHOT_PATH` monkeypatch 격리. 모든 7 테스트가 fixture 사용.
- `frontend/lib/api/mlRelativeUpside.ts` 주석을 "backend 는 같은 프로세스 내
  scripts.run_ml_relative_upside_score_v0.main() 직접 import 호출 — subprocess
  가 아님" 으로 정정.

### FIX r1 검증

- pytest **615 passed** (608 + 7 신규, 회귀 0).
- black / flake8 PASS. frontend lint / build PASS.
- 실제 운영 artifact (`state/ml/relative_upside_score_*.json`) 변경 0건 —
  모든 테스트가 tmp_path 격리.

---

## 9. FIX r2 (검증자 2차 REJECTED 후속)

검증자 2차 REJECTED 사유 (A-2 보고 정확성 / A-3 산출물 정합성) — FIX r1 의 코드
변경은 통과됐으나 문서/주석 stale 정합성이 남아있다는 지적. 3건 정정.

### FIX r2-1 — `docs/STATE_LATEST.md` L28 stale "응답 5 필드"

**문제**: FIX r1 commit 에 STATE_LATEST §1 본문 L28 의 "응답 5 필드" 표기가
잔존. CONCLUSION 문서만 수정하고 STATE_LATEST 본문은 놓침.

**수정**: L28 본문을 "응답 6 필드 (status / asof_date / generated_at /
scored_candidate_count / gpu_execution_used / message)" 로 정정 + "실패 /
rc≠0 / meta 손상 / meta.status≠ok 4분기 처리 (FIX r1 — 손상 분리)" 명시.

### FIX r2-2 — `app/api_ml_relative_upside.py` docstring stale

**문제**: 모듈 docstring 에 "동기 처리 (subprocess 실행 대기 후 응답)" 표현이
남아 있음 (실제는 직접 import 호출). "실패 시 기존 run meta 는 그대로" 도 실제
unavailable/failed 분기에서 run meta 가 이력 추적용으로 갱신되는 동작과 충돌.

**수정**:
- "동기 처리 — 같은 프로세스 내 함수 호출 대기 후 응답 (사용자 결정 2026-06-21).
  subprocess 가 아니라 main() 을 직접 import 해서 호출" 로 정정.
- "실패 시 기존 정상 score snapshot 은 삭제 / 초기화 / 빈값 덮어쓰기 X" 의
  2층 보호 메커니즘을 명시 ((a) 예외 raise 시 atomic write 호출 안 됨 /
  (b) FIX r1 — main() 의 unavailable/failed 분기에서 save_score_snapshot()
  호출 자체 제거).
- "실패 분기에서 score snapshot 은 유지된다. run meta 는 이력 추적을 위해
  main() 의 unavailable/failed 분기에서도 갱신될 수 있다 (snapshot_path='')"
  로 정확하게 표기.

### FIX r2-3 — `scripts/run_ml_relative_upside_score_v0.py` L90 stale 주석

**문제**: `KODEX200_TICKER not in all_tickers` 분기의 주석 "failed snapshot
저장 후 종료" 가 실제 동작 (run meta 만 저장 + snapshot 미저장) 과 불일치.

**수정**: "score snapshot 저장하지 않고 기존 SCORE_SNAPSHOT_PATH 그대로 유지
(FIX r1 — 실패 시 기존 점수 보존). run meta 만 status=failed +
snapshot_path='' 로 저장 (이력 추적용)" 로 정정.

### FIX r2 검증

- 정정 대상 외 코드 변경 0건 (주석/문서/docstring 만 변경).
- pytest 7건 PASS (격리된 test_api_ml_relative_upside.py — 동작 회귀 없음).
- black / flake8 PASS.
- 실제 운영 artifact 변경 0건.

---

## 10. 다음 단계 (사용자 결정 대기)

PC_OCI_ARCHITECTURE_DIRECTION 순서 그대로:

1. **ML 축2** — 위험 감지용 시계열 빈자리 하나 채우기 STEP. 본 STEP 의 UI 패턴
   재사용 가능.
2. **점수·위험·보유 비교가 모이는 PC 판단 화면**.
3. **OCI read model foundation** — PC 판단 화면 + ML 1차 결과 확보 뒤 진입.
