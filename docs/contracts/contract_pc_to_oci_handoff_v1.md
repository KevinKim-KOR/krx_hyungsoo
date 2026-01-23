# Contract: PC to OCI Handoff V1

**Version**: 1.0
**Date**: 2026-01-23
**Status**: ACTIVE

---

## 1. 개요

PC에서 백테스트/튜닝을 수행하고, OCI는 결과를 읽어서 운영 판정/알림만 수행하는 분리 구조를 정의합니다.

> 🖥️ **PC**: 무거운 연산 (백테스트, 튜닝, 시뮬레이션)
>
> ☁️ **OCI**: 가벼운 운영 (읽기, 표시, 알림 프리뷰, 스케줄 실행)

---

## 2. PC 역할 (Heavy Compute)

### 2-A. 담당 작업

| 작업 | 설명 |
|------|------|
| 백테스트 실행 | `core/backtest/` 전체 |
| 파라미터 튜닝 | 최적화/그리드 서치 |
| 데이터 수집 | PyKRX, FDR 등 외부 API |
| 전략 시뮬레이션 | Phase 9 Executor |
| 리포트 생성 | recon_summary, report_human, report_ai |

### 2-B. PC 산출물 (Git으로 전달)

| 파일 | 설명 |
|------|------|
| `reports/phase_c/latest/recon_summary.json` | 일일 정산 요약 |
| `reports/phase_c/latest/report_human.json` | 사람용 리포트 |
| `reports/phase_c/latest/report_ai.json` | AI 분석 리포트 |
| `state/live/decision_params.json` | 라이브 결정 파라미터 (신규) |

### 2-C. PC 전달 절차

```bash
# 1. 백테스트 실행
python -m app.run_backtest

# 2. 리포트 생성
python -m app.reconcile
python -m app.generate_reports

# 3. Git commit & push
git add reports/phase_c/latest/*.json state/live/*.json
git commit -m "Daily recon update - $(date +%Y-%m-%d)"
git push origin archive-rebuild
```

---

## 3. OCI 역할 (Light Operations)

### 3-A. 담당 작업

| 작업 | 설명 |
|------|------|
| Ops Cycle | 스케줄 실행 (09:05 KST) |
| Health Check | evidence, tickets 상태 모니터링 |
| 알림 프리뷰 | CONSOLE 전용 (외부 발송 금지) |
| 대시보드 | API 제공 + 정적 HTML |

### 3-B. OCI 금지 사항

| 금지 항목 | 이유 |
|-----------|------|
| ❌ 백테스트 실행 | CPU/메모리 부족 |
| ❌ 대용량 데이터 수집 | 스토리지/네트워크 비용 |
| ❌ 파라미터 튜닝 | 연산 오버헤드 |
| ❌ 외부 발송 | sender_enable=false 정책 |

### 3-C. OCI 동기화 절차

```bash
# OCI에서 최신 결과 가져오기
cd ~/krx_hyungsoo
git pull origin archive-rebuild

# 결과 확인
cat reports/phase_c/latest/recon_summary.json | head
```

---

## 4. Decision Params 스키마 (신규)

PC에서 생성하고 OCI에서 읽는 라이브 결정 파라미터입니다.

```json
{
  "schema": "DECISION_PARAMS_V1",
  "asof": "2026-01-23T21:00:00+09:00",
  "generated_by": "PC_BACKTEST",
  "params": {
    "regime_current": "BULL | BEAR | CHOP",
    "rsi_buy_threshold": 30,
    "rsi_sell_threshold": 70,
    "position_size_pct": 0.1,
    "stop_loss_pct": 0.05
  },
  "confidence_score": 0.85,
  "notes": "Auto-tuned from 2022-2025 backtest"
}
```

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-23 | 초기 버전 (Phase C-P.44) |
