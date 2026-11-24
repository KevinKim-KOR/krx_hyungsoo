# ETF Constituents Source Diagnosis (POC2 1차)

실행 시각 (UTC): `2026-05-31T13:37:04Z`

본 문서는 ETF 구성종목 수집 실패 원인의 단계적 격리 + Naver Mobile API
smoke test 결과 (지시문 §4 / §5 / §6) 의 실측 기록입니다. 결과는 임의
추정 없이 호출 1건당 실제 응답만 남깁니다.

## 1. pykrx PDF 진단

- 분류: **pykrx_operational_issue**
- PDF 운영 판정: **hold**
- 총 호출 15회 / ok 0 / no_data 15 / call_failed 0 / import_failed 0

| ticker | asof | status | rows | error |
|---|---|---|---|---|
| `069500` (대표 시장 (KODEX 200)) | 2026-05-27 | **no_data** | 0 |  |
| `069500` (대표 시장 (KODEX 200)) | 2026-05-26 | **no_data** | 0 |  |
| `069500` (대표 시장 (KODEX 200)) | 2026-05-15 | **no_data** | 0 |  |
| `069500` (대표 시장 (KODEX 200)) | 2026-04-30 | **no_data** | 0 |  |
| `069500` (대표 시장 (KODEX 200)) | 2026-03-31 | **no_data** | 0 |  |
| `139260` (국내 섹터 (TIGER 200 IT)) | 2026-05-27 | **no_data** | 0 |  |
| `139260` (국내 섹터 (TIGER 200 IT)) | 2026-05-26 | **no_data** | 0 |  |
| `139260` (국내 섹터 (TIGER 200 IT)) | 2026-05-15 | **no_data** | 0 |  |
| `139260` (국내 섹터 (TIGER 200 IT)) | 2026-04-30 | **no_data** | 0 |  |
| `139260` (국내 섹터 (TIGER 200 IT)) | 2026-03-31 | **no_data** | 0 |  |
| `411420` (테마/해외형 (Market Discovery 후보)) | 2026-05-27 | **no_data** | 0 |  |
| `411420` (테마/해외형 (Market Discovery 후보)) | 2026-05-26 | **no_data** | 0 |  |
| `411420` (테마/해외형 (Market Discovery 후보)) | 2026-05-15 | **no_data** | 0 |  |
| `411420` (테마/해외형 (Market Discovery 후보)) | 2026-04-30 | **no_data** | 0 |  |
| `411420` (테마/해외형 (Market Discovery 후보)) | 2026-03-31 | **no_data** | 0 |  |

## 2. Naver Mobile ETF Component API smoke test

- 운영 분류: **unusable**
- asof/update 후보 필드 (top-level): 없음

| ticker | http | json | rows | code field | name field | weight field |
|---|---|---|---|---|---|---|
| `069500` (대표 시장 (KODEX 200)) | 404 | no | 0 | - | - | - |
| `139260` (국내 섹터 (TIGER 200 IT)) | 404 | no | 0 | - | - | - |
| `411420` (테마/해외형 (Market Discovery 후보)) | 404 | no | 0 | - | - | - |

## 3. KRX Open API / 공식 provider 후속 필요 여부

- **True**

조건 (지시문 §8): pykrx 날짜 보정 실패 + 대표 ETF 테스트 실패 + Naver
smoke test 실패 셋이 모두 충족되면 후속 필요.

## 4. 다음 단계 후보 (지시문 §21)

- C. KRX Open API / Official Provider Source Design

## 5. JSON artifact

- `state/market/constituents_source_diagnosis_latest.json`