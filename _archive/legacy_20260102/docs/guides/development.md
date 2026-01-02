# RUNBOOK — 운영 및 배포 매뉴얼 (v2)

## 1. 목적
본 문서는 투자모델 시스템의 **일일 운영 절차**, **NAS↔PC 파이프라인**, **장애 대응 정책**, **Slack 로그 규칙**을 정의한다.

---

## 2. 일일 운영 흐름
```mermaid
graph TD;
  A[데이터 인입 (NAS)] --> B[스캐너 실행]
  B --> C[TopN + HOLD_CORE 반영]
  C --> D[알림 발송 및 로그 기록]
  D --> E[백테스트 요청 파일 생성]
  E --> F[PC 백테스트 실행]
  F --> G[리포트 생성 및 NAS 동기화]
```

| 단계 | 환경 | 스크립트 | 설명 |
|------|------|-----------|------|
| 1 | NAS | `scripts/linux/jobs/run_ingest_eod.sh` | pykrx/네이버 데이터 인입 |
| 2 | NAS | `scripts/linux/jobs/run_scanner.sh` | 전략별 TopN 신호 생성 |
| 3 | NAS | `scripts/linux/jobs/run_report_eod.sh` | 알림 발송, Slack 기록 |
| 4 | NAS | `scripts/linux/jobs/run_backtest_request.sh` | 백테스트 요청 JSON 생성 |
| 5 | PC | `app/cli/backtest.py` | 요청 감지 → 백테스트 실행 |
| 6 | NAS | `scripts/linux/jobs/sync_reports.sh` | 결과 리포트 동기화 |

---

## 3. NAS ↔ PC 파이프라인
### A. 파일 기반 (기본)
- NAS → `reports/pending/*.json` 생성.
- PC 감시 후 `app.cli.backtest`로 처리.

```bash
watchmedo shell-command \
  --patterns="*.json" \
  --command='python -m app.cli.backtest run --inbox reports/pending --out reports/done'
```

### B. REST API 기반 (선택)
- PC에서 FastAPI 서비스(`app/services/backtest_api`) 실행.
- NAS에서 요청:
```bash
curl -X POST http://pc:8000/backtest?strategy=momentum_topN_v1
```

| 방식 | 장점 | 단점 |
|------|------|------|
| 파일 기반 | 단순·안정 | 약간의 지연 |
| REST API | 즉시성 | PC 상시 구동 필요 |

---

## 4. 로그 및 예외 처리
### 로그 규칙
| 수준 | 설명 |
|------|------|
| DEBUG | 내부 디버깅 |
| INFO | 정상 실행 로그 |
| WARNING | 데이터 결측·불완전 |
| ERROR | 실행 실패 |

- 모든 `ERROR` 로그는 `send_verbose_log_to_slack()`으로 Slack 채널 전송.
- 로그 포맷:
```
[YYYY-MM-DD HH:MM:SS] [LEVEL] [EVENT] rc=0 details=... elapsed=1234ms
```

### 예외 처리 원칙
| 상황 | 조치 |
|------|------|
| 거래 데이터 부족 | 해당 종목 제외, INFO 로그 |
| 비정상 데이터 | 함수 스킵, ERROR 로그 |
| 거래정지/폐지 | 제외 후 사유 기록 |
| 휴장일 | 캐시 재사용, 알림 생성은 다음 거래일 기준 |

---

## 5. 장애 대응 절차
| 증상 | 원인 | 조치 |
|------|------|------|
| 데이터 누락 | 네트워크/API 제한 | `_run_generic.sh --retry` 재시도 |
| Slack 알림 실패 | 토큰 만료 | `configs/notify.yaml` 갱신 |
| 백테 요청 누락 | 권한 오류 | `chmod 777 reports/pending` |
| 리포트 미전송 | NAS 연결 실패 | 수동 `rsync` 재동기화 |
| 파이썬 오류 | 버전 불일치 | core=3.8 / extensions=3.11 확인 |

---

## 6. 배포 절차
```bash
git pull origin main
# NAS
uv pip install -e .
# PC
uv pip install -e "[backtest,tuning]"
pytest -q
git add -A
git commit -m "deploy: daily runbook sync"
git push
```

---

## 7. 모니터링 및 Slack 알림
- Slack 채널: `#invest_ops`
- 주요 알림 이벤트:
  - 데이터 인입 실패 (WARNING)
  - 백테스트 완료 (INFO)
  - 오류 발생 (ERROR)
- 메시지 예시:
```
[ERROR] KRX Ingest Failed — pykrx Timeout (2025-10-24)
```

---

## 8. 백업 및 보안 정책
- NAS → 외장 백업: 매주 일요일 `rsync`
- 민감정보: `.env` 파일 분리, Git 제외
- 데이터 보존: `reports/`, `data/cache/` 30일 단위 압축 보존

---

## 9. 향후 개선
- Slack 통합 리포트 요약 자동화
- NAS 장애 감지 및 재시작 스크립트 자동화
- Airflow 기반 워크플로 관리 검토

> v2에서는 `Slack 로그`, `휴장일 캐시 처리`, `예외 대응 규칙`이 보강되었으며 NAS–PC 파이프라인 구조가 명확히 정리되었다.

