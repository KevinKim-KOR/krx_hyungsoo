# P205-STEP3 종료 문서: Backtest 5축 메타데이터 가드

> **Closeout** — 이 문서는 P205-STEP3 종료 시점의 스냅샷입니다.

asof: 2026-03-29

## 범위

Backtest 결과에 실제 사용된 5축 파라미터 메타를 남기고,
승격 판정이 SSOT-Backtest 5축 일치를 검사하도록 강화.

## 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `app/run_backtest.py` | `meta.used_params_5axes` 필드 추가 |
| `app/tuning/promotion_verdict_core.py` | `used_params_match_ssot` 계산 + mismatch 시 PROMOTE 강등 |
| `pc_cockpit/views/tune_card.py` | 승격 판정 패널에 "Backtest 파라미터 일치 여부" 1줄 추가 |

## 핵심 동작

- `backtest_result.json`에 `meta.used_params_5axes` (5축) 기록
- `promotion_verdict.json`에 `used_params_match_ssot` (true/false/null) 추가
- `used_params_match_ssot=false`이면 verdict가 `PROMOTE_CANDIDATE`가 되더라도 `REVIEW_REQUIRED`로 강등
- UI 승격 판정 패널에 "Backtest 파라미터 일치 여부: 예/아니오" 표시

## 검증 결과

- 5축 일치 → `used_params_match_ssot: true`
- 1축(entry_threshold) 불일치 → `used_params_match_ssot: false`, 사유 추가
- 기존 산출물(equal_3way, objective_breakdown, sensitivity 등) 무결성 유지
