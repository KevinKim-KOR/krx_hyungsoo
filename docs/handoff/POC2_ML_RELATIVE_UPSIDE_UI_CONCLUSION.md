# POC2 — ML 축1 상대상승 점수 실행 UI 연결 Conclusion

작성일: 2026-06-21
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
| `app/api_ml_relative_upside.py` | `POST /market/relative-upside/run` router. 동기 처리 — `scripts.run_ml_relative_upside_score_v0.main()` 을 직접 import 호출. 응답 5 필드 (status / asof_date / generated_at / scored_candidate_count / gpu_execution_used / message). 실패 / rc≠0 / meta.status≠ok 분기 처리. raw 식별자 (device name / loss / epoch / artifact path / traceback) 노출 0건. |

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
| `tests/test_api_ml_relative_upside.py` | 5 | 성공 5 필드 응답 / GPU 미확인 메시지 / 예외 시 기존 meta 파일 변경 0건 / rc≠0 → failed / meta.status≠ok → unavailable. 응답에 raw 식별자 노출 0건 검증. |

---

## 3. 완료 기준 (지시문) 달성 현황

| 항목 | 결과 |
|---|---|
| 1. UI 버튼으로 점수 계산 가능 | DONE — `RelativeUpsideRunCard` 버튼 1개 |
| 2. 계산 중 / 성공 / 실패 상태 표시 | DONE — badge 5종 (미실행 / 계산 중 / 완료 / 실패 / 데이터 부족) |
| 3. 성공 후 후보 표 점수 자동 갱신 | DONE — `onSuccess={loadTopn}` 콜백으로 `GET /market/topn/latest` 재호출 |
| 4. 기준일 / 실행 시각 / 후보 수 / GPU 여부 표시 | DONE — 5 필드 표시 |
| 5. 실패해도 기존 점수 유지 | DONE — `main()` 예외 raise 시 atomic write 가 호출되지 않아 파일 변경 0건 (단위 테스트 검증) |
| 6. 기존 모델 / feature / target / score 산식 불변 | DONE — `app/ml_relative_upside_features.py` / `_model.py` / `_score.py` 변경 0건 |
| 7. OCI / PUSH / PARAM 회귀 없음 | DONE — 관련 모듈 변경 0건 |
| 8. backend tests / black / flake8 / frontend lint / build 통과 | DONE — pytest 613 passed (608 → +5), 회귀 0 |

---

## 4. 데이터 계약

### POST /market/relative-upside/run 응답 (5 필드)

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
| backend pytest | **613 passed** (608 → +5 신규, 회귀 0). 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`) 은 본 STEP 이전부터 존재 |
| black | PASS |
| flake8 | PASS |
| frontend npm run lint | PASS |
| frontend npm run build | PASS |
| POST 실측 | status=ok, scored 1,111, gpu=true |
| 실패 시 기존 snapshot 보존 | 단위 테스트로 검증 (파일 content 변경 0건) |
| 응답 raw 식별자 노출 | 0건 (단위 테스트로 검증) |
| 신규 의존성 | 없음 |

---

## 8. 다음 단계 (사용자 결정 대기)

PC_OCI_ARCHITECTURE_DIRECTION 순서 그대로:

1. **ML 축2** — 위험 감지용 시계열 빈자리 하나 채우기 STEP. 본 STEP 의 UI 패턴
   재사용 가능.
2. **점수·위험·보유 비교가 모이는 PC 판단 화면**.
3. **OCI read model foundation** — PC 판단 화면 + ML 1차 결과 확보 뒤 진입.
