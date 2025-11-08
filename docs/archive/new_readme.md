# 투자모델 프로젝트 개요 (v2 개정)

## 0. 당신의 역할
너는 나(Hyungsoo Kim)의 개인 개발 파트너이자 보조 프로그래머야.
항상 한국어로 대화하고, 코드 변경 전에는 반드시 나의 허락을 받아야 한다.
Python 기반의 프로젝트이며 Clean Architecture 원칙을 따른다.
모든 코드는 명확하고 재사용 가능해야 하며, 함수와 클래스의 역할이 분명해야 한다.
"""

## 1. 프로젝트 목표
- **핵심 목적**: 전략별 투자신호를 자동 생성하고 알림 발송, 백테스트·튜닝·룩백을 통해 전략 성능을 지속적으로 개선.
- **설계 철학**: 순차 처리, 재현성, 단일 책임, Clean Architecture.
- **적용 원칙**: 병렬처리 금지(튜닝 제외), 휴장일 캐시 재사용, 핵심 보유 종목(HOLD_CORE) 통합.

---

## 2. 시스템 로드맵
| 단계 | 목표 | 주요 산출물 |
|------|------|-------------|
| 1단계 | 전략 기반 신호 및 알림 발송 | 실시간 알림 리포트 |
| 2단계 | 백테스트 | 성과 리포트 (CAGR, MDD, Sharpe 등) |
| 3단계 | 튜닝 | 파라미터 탐색, 단순성 패널티 적용 |
| 4단계 | 룩백 | 리짐 분석 및 전략 회고 리포트 |

---

## 3. 런타임 환경
| 환경 | 역할 | 파이썬 버전 | 주요 작업 |
|------|------|--------------|-------------|
| NAS | 운영·알림 | 3.8 | 인입, 스캐너, 리포트 발송 |
| PC | 연구·분석 | 3.11+ | 백테스트, 튜닝, 룩백 |

---

## 4. 폴더 구조 (요약)
```
app/
  cli/
  services/backtest_api/
core/
  strategy/
  engine/
  risk/
  metrics/
extensions/
  backtest/
  tuning/
infra/
  data/      # pykrx, yfinance, naver 금융
  notify/    # Slack/TG
  storage/
configs/
reports/
scripts/
tests/
```

---

## 5. 주요 기능 요약
- **알림 시스템**: 전략별 TopN 신호 및 HOLD_CORE 반영.
- **백테스트 엔진**: 거래비용, 슬리피지, 리스크 규칙 반영.
- **튜닝 파이프라인**: Optuna 기반 탐색(병렬 예외 허용).
- **룩백 리포트**: 시장 리짐·핵심 보유 종목 성과 분석.

---

## 6. 설치 및 실행
### NAS (Py3.8)
```bash
uv pip install -e .
python -m app.cli.alerts run --date auto
```
### PC (Py3.11+)
```bash
uv pip install -e "[backtest,tuning]"
python -m app.cli.backtest run --inbox reports/pending --out reports/done
```

---

## 7. 품질 기준
- **테스트 커버리지**: 핵심 모듈 ≥ 90%
- **코드 검사**: `ruff`, `black`, `mypy`, `flake8`
- **로그 정책**: 모든 오류는 `send_verbose_log_to_slack()`으로 보고.

---

## 8. 주요 문서
- [ARCHITECTURE.md](ARCHITECTURE.md) — 시스템 구조 및 설계 원칙
- [STRATEGY_SPEC.md](STRATEGY_SPEC.md) — 전략 정의 및 검증 규칙
- [DATA_POLICY.md](DATA_POLICY.md) — 데이터 소스·보정·휴장일 처리
- [RUNBOOK.md](RUNBOOK.md) — 운영 절차 및 장애 대응

---

> v2에서는 개발 규칙(순차 처리·휴장일 정책·에러 로깅)과 HOLD_CORE 구조를 통합 반영했다.

