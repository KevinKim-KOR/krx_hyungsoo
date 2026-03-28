# P205 구조 정리 종료 문서 (Structure Cleanup Closeout)

asof: 2026-03-28

## 구조 정리 범위 요약

| Phase | 내용 | 커밋 수 |
|---|---|---|
| S0 | 비활성 파일 5개 삭제 + 구조 기준선 문서 | 1 |
| S1 | cockpit.py dead function 6개 → legacy_panels.py 격리 | 2 |
| S2 | cockpit.py 분해 (1,974→78줄, views/ 5개 모듈) | 7 |
| S3 | 승격 판정 로직 단일화 (promotion_verdict_core.py) | 3 |
| S4 | generate_ops_summary.py 분해 (1,150→273줄, ops_summary/ 패키지) | 4 |
| S5 | backend/main.py 라우터 분해 (4,844→108줄, routers/ 16개) | 10 |
| 후속 | shadowed 7쌍 정리, lint 정리 | 2 |

총 커밋: 29개

## 핵심 파일 변화

| 파일 | 이전 줄수 | 이후 줄수 | 감소율 |
|---|---|---|---|
| `pc_cockpit/cockpit.py` | 1,974 | 78 | -96% |
| `app/run_tune.py` | (주석 경로 수정만) | — | — |
| `app/generate_ops_summary.py` | 1,150 | 305 | -73% |
| `backend/main.py` | 4,844 | 108 | -98% |
| `app/tuning/promotion_gate.py` | 314 | 95 | -70% |
| `pc_cockpit/services/promotion_verdict.py` | 231 | 41 | -82% |

## 최종 구조 상태

### backend/routers/ (신규, 16개 모듈)

| 라우터 | 라우트 수 | 도메인 |
|---|---|---|
| core.py | 6 | /, status, signals, history, raw, validation |
| reporting.py | 10 | contract5, diagnosis, gatekeeper, report, recon |
| evidence.py | 5 | evidence resolve, index, health |
| tickets.py | 6 | ticket CRUD, board, reaper |
| deps.py | 3 | dependency status, snapshot |
| ops.py | 15 | daily, health, scheduler, summary, drill, postmortem, live_fire, cycle |
| push.py | 14 | push 전체 (delivery, send, preview, daily_status, incident, spike, holding) |
| portfolio.py | 9 | portfolio, reco, order_plan, export |
| execution_gate.py | 12 | gate, emergency_stop, approvals, window, allowlist, preflight |
| manual_execution.py | 8 | execution_prep, ticket, record, draft, submit |
| secrets.py | 3 | secrets status, self_test |
| real_sender.py | 2 | real sender enable |
| settings.py | 11 | mode, settings, spike, watchlist, transport |
| operator.py | 1 | sync_cycle |
| strategy_bundle.py | 2 | bundle latest, snapshot |
| live_cycle.py | 2 | live cycle latest, run |

### 공유 유틸리티

| 파일 | 역할 |
|---|---|
| `backend/utils.py` | logger, safe_read_*, 경로 상수 (main.py에서 추출) |
| `app/tuning/promotion_verdict_core.py` | 승격 판정 순수 로직 (I/O 없음) |
| `app/ops_summary/paths.py` | ops summary 경로 상수 |
| `app/ops_summary/helpers.py` | ops summary 유틸리티 |
| `app/ops_summary/risk_aggregator.py` | 리스크 계산 로직 |

### 비활성 보존 파일

| 파일 | 성격 |
|---|---|
| `pc_cockpit/legacy_panels.py` | cockpit.py 데드 함수 6개 보존 (S1-B) |
| `backend/routers/_shadowed_archive.py` | shadowed 2차 정의 7쌍 참조용 보존 (import 금지) |

### shadowed 7쌍 정리 완료

아래 7개는 동일 경로에 2번 등록되어 매칭되지 않던 dead code.
활성 라우터에서 제거하고 `_shadowed_archive.py`에 참조용으로 보존.

| 경로 | live 핸들러 | 제거된 shadowed |
|---|---|---|
| GET /api/reco/latest | get_reco_latest_v1 | get_reco_latest_v2 |
| POST /api/reco/regenerate | regenerate_reco_v1 | regenerate_reco_v2 |
| POST /api/portfolio/upsert | upsert_portfolio_api_v1 | upsert_portfolio_api_v2 |
| POST /api/order_plan/regenerate | regenerate_order_plan_v1 | regenerate_order_plan_api_v2 |
| GET /api/order_plan/latest | get_order_plan_latest_v1 | get_order_plan_latest_api_v2 |
| POST /api/execution_prep/prepare | prepare_execution | prepare_execution_api |
| POST /api/manual_execution_ticket/regenerate | regenerate_manual_execution_ticket | regenerate_execution_ticket_api |

## 남은 부채

### 일반 lint debt

- backend/routers/ 전체에 E501 (line too long) 다수 잔존
- backend/routers/ 일부에 E402 (module level import not at top) 잔존
- `backend/dry_run.py`에 F401 1건
- 차단 이슈(E999/F821)는 0건

### 구조 정리 후속 후보

- shadowed 7쌍의 v2를 v1 대체로 승격하는 작업 (비즈니스 결정 필요)
- `pc_cockpit/legacy_panels.py` 완전 삭제 (데드 코드이므로 언제든 가능)
- 비활성 파일 5개 (`cockpit_new.py`, `cockpit_fixed.py` 등) — S0에서 기록만, 삭제 미수행

## 기능 마스터플랜 복귀

구조 정리(S0~S5)가 완료되어 **기존 기능 개발 마스터플랜으로 복귀 가능**합니다.

복귀 시 유의사항:
- backend 라우트 추가/수정은 `backend/routers/` 해당 모듈에서 수행
- cockpit UI 추가/수정은 `pc_cockpit/views/` 해당 모듈에서 수행
- 승격 판정 규칙 변경은 `app/tuning/promotion_verdict_core.py` 한 곳에서 수행
- ops summary 로직 변경은 `app/ops_summary/risk_aggregator.py`에서 수행
