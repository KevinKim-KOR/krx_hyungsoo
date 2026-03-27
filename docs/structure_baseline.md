# 구조 정리 기준선 (Structure Baseline)

asof: 2026-03-27

## 진입점 계약

### PC 측 (로컬)
| 진입점 | 호출 방법 | 포트 |
|---|---|---|
| `pc_cockpit/cockpit.py` | `streamlit run pc_cockpit/cockpit.py` | 8501 |
| `backend/main.py` | `uvicorn backend.main:app --port 8000` | 8000 |

배포 스크립트:
- `start.bat` — 백엔드(8000) + OCI Bridge(8001) + Cockpit(8501) 동시 기동
- `stop.bat` — 포트 기반 프로세스 종료

### OCI 측 (서버)
| 진입점 | 호출 방법 |
|---|---|
| `backend/main.py` | `deploy/oci/run_backend.sh` → uvicorn backend.main:app |

### CLI 진입점 (app/run_*.py)
| 파일 | 호출 | 역할 |
|---|---|---|
| `app/run_tune.py` | `python -m app.run_tune` | Optuna 튜닝 |
| `app/run_backtest.py` | `python -m app.run_backtest` | Full Backtest |
| `app/run_ops_cycle.py` | `python -m app.run_ops_cycle` | 일일 운영 사이클 |
| `app/run_ticket_worker.py` | `python -m app.run_ticket_worker` | 티켓 실행 워커 |
| `app/run_live_cycle.py` | `python -m app.run_live_cycle` | 라이브 사이클 |
| `app/run_live_fire_ops.py` | `python -m app.run_live_fire_ops` | 라이브 실행 |
| `app/run_push_delivery_cycle.py` | `python -m app.run_push_delivery_cycle` | 푸시 배달 |
| `app/run_push_send_cycle.py` | `python -m app.run_push_send_cycle` | 푸시 발송 |
| `app/run_spike_push.py` | `python -m app.run_spike_push` | 스파이크 알림 |
| `app/run_ops_drill.py` | `python -m app.run_ops_drill` | 운영 드릴 |
| `app/run_holding_watch.py` | `python -m app.run_holding_watch` | 보유 감시 |
| `app/run_evidence_health_check.py` | `python -m app.run_evidence_health_check` | 증빙 헬스체크 |
| `app/run_git_transport.py` | `python -m app.run_git_transport` | Git 전송 |
| `app/run_ticket_reaper.py` | `python -m app.run_ticket_reaper` | 티켓 정리 |

## 비활성 코드 (삭제 대상)

| 파일 | 줄수 | 사유 |
|---|---|---|
| `pc_cockpit/cockpit_new.py` | 1,541 | cockpit.py 구버전, import/호출 없음 |
| `pc_cockpit/cockpit_fixed.py` | 1,502 | cockpit.py 구버전, import/호출 없음 |
| `pc_cockpit/snippet_backtest.py` | 65 | 코드 조각, import/호출 없음 |
| `app/run_holding_watch_restored.py` | 376 | null bytes 포함, SyntaxError |
| `temp_replace.py` | 67 | 프로젝트 루트 일회성 스크립트 |

## cockpit.py 데드 함수 격리 (S1-B, 2026-03-27)

아래 6개 함수를 `pc_cockpit/legacy_panels.py`로 이동 완료 (cockpit.py에서 삭제, 815줄 제거):

| 함수 | 원래 줄 범위 | 줄수 | 격리 위치 |
|---|---|---|---|
| `render_params` | 822-1021 | 200 | legacy_panels.py |
| `render_reco` | 1022-1078 | 57 | legacy_panels.py |
| `render_review` | 1384-1473 | 90 | legacy_panels.py |
| `render_guardrails_legacy` | 1475-1603 | 129 | legacy_panels.py |
| `render_backtest_legacy` | 1605-1735 | 131 | legacy_panels.py |
| `render_tune_legacy` | 1737-1939 | 203 | legacy_panels.py |

## 분리 완료 모듈 (P205-STEP1A)

### pc_cockpit/services/
- `config.py` — 상수, 경로, 유틸리티
- `json_io.py` — JSON I/O, 파라미터 저장
- `promotion_verdict.py` — 승격 판정 I/O wrapper (cockpit 로컬, core 사용) (S3)
- `live_approval.py` — LIVE 승인/철회
- `backend.py` — 백엔드 연결

### pc_cockpit/views/ (S2 추가)
- `tune_card.py` — 튜닝 결과 카드
- `parameter_editor.py` — SSOT 파라미터 편집 폼
- `ops_daily.py` — 데일리 운영 탭 (P144) 렌더러
- `workflow.py` — 워크플로우 허브 (P170-UI) 렌더러
- `replay_controller.py` — Replay 모드 컨트롤러
- `timing.py` — 보유 타이밍 분석 (P136) 렌더러
- `portfolio_editor.py` — 포트폴리오 편집기 (P136.5) 렌더러

### app/tuning/
- `results_io.py` — 원자적 파일 쓰기
- `exports.py` — CSV/메타데이터 내보내기
- `summary_render.py` — 검산 요약 MD 렌더러
- `promotion_gate.py` — 승격 판정 I/O wrapper (튜닝 파이프라인)
- `promotion_verdict_core.py` — 승격 판정 공유 코어 (순수 로직, I/O 없음) (S3)
