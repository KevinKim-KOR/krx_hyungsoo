# PC ↔ OCI 분리 운영 Runbook V1

**Version**: 1.0
**Date**: 2026-01-23
**Status**: ACTIVE

---

## 1. 개요

PC에서 백테스트를 실행하고, OCI에서 결과를 읽어 운영하는 분리 워크플로우입니다.

---

## 2. 일일 워크플로우

```
┌─────────────────────────────────────────────────────────┐
│  PC (Windows)                                           │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ 백테스트    │ → │ 리포트 생성  │ → │ Git Push     │ │
│  │ 실행        │   │              │   │              │ │
│  └─────────────┘   └──────────────┘   └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  OCI (Ubuntu)                                           │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ Git Pull    │ → │ Ops Cycle    │ → │ Health/Drill │ │
│  │ (수동/자동) │   │ (09:05 KST)  │   │ 확인         │ │
│  └─────────────┘   └──────────────┘   └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 3. PC 작업 (매일)

### 3-A. 백테스트 실행

```powershell
cd "E:\AI Study\krx_alertor_modular"
.\.venv\Scripts\Activate.ps1

# 백테스트 실행
python -m app.run_backtest

# 정산 실행
python -m app.reconcile

# 리포트 생성
python -m app.generate_reports
```

### 3-B. 결과 확인

```powershell
# 최신 리포트 확인
cat reports\phase_c\latest\recon_summary.json | head
```

### 3-C. Git Push

```powershell
git add reports/phase_c/latest/*.json
git add state/live/*.json  # 있을 경우
git commit -m "Daily recon update - $(Get-Date -Format 'yyyy-MM-dd')"
git push origin archive-rebuild
```

---

## 4. OCI 작업

### 4-A. 수동 동기화 (필요 시)

```bash
cd ~/krx_hyungsoo
git pull origin archive-rebuild
```

### 4-B. 자동 스케줄 (09:05 KST)

cron이 `deploy/run_ops_cycle.sh`를 실행합니다.

```bash
# cron 확인
crontab -l
# 출력: 5 9 * * * cd /home/ubuntu/krx_hyungsoo && ./deploy/run_ops_cycle.sh ...
```

### 4-C. 실행 결과 확인

```bash
# Ops Cycle 최신 결과
curl -s http://127.0.0.1:8000/api/ops/scheduler/latest | head

# Ops Summary
curl -s http://127.0.0.1:8000/api/ops/summary/latest | head

# Health
curl -s http://127.0.0.1:8000/api/ops/health
```

### 4-D. Live Cycle 검증 (D-P.50)

```bash
# Live Cycle 실행
curl -X POST "http://127.0.0.1:8000/api/live/cycle/run?confirm=true"

# 최신 영수증 파싱 (권장 방식)
curl -s http://127.0.0.1:8000/api/live/cycle/latest | python -c '
import json,sys
d=json.load(sys.stdin)
r=d.get("rows",[{}])[0]
print("result=", r.get("result"), "decision=", r.get("decision"), "reason=", r.get("reason"))
print("delivery_actual=", ((r.get("push") or {}).get("delivery_actual")))
print("bundle=", (r.get("bundle") or {}).get("decision"), "stale=", (r.get("bundle") or {}).get("stale"))
print("reco=", (r.get("reco") or {}).get("decision"), (r.get("reco") or {}).get("reason"))
print("snapshot_ref=", r.get("snapshot_ref"))
'

# snapshot_ref 검증 (null 아닌지 확인)
REF="$(curl -s http://127.0.0.1:8000/api/live/cycle/latest \
| python -c 'import json,sys; d=json.load(sys.stdin); r=d.get("rows",[{}])[0]; print(r.get("snapshot_ref") or "")')"
echo "REF=$REF"
curl -i "http://127.0.0.1:8000/api/evidence/resolve?ref=${REF}" | head -20

# delivery_actual=CONSOLE_SIMULATED 확인 (외부발송 0)
curl -s http://127.0.0.1:8000/api/live/cycle/latest | python -c '
import json,sys
d=json.load(sys.stdin)
r=d.get("rows",[{}])[0]
da = (r.get("push") or {}).get("delivery_actual")
if da == "CONSOLE_SIMULATED":
    print("✅ PASS: delivery_actual=CONSOLE_SIMULATED")
else:
    print("❌ FAIL: delivery_actual=", da)
'
```

---

## 5. 실패 시 롤백

### 5-A. OCI에서 이전 버전으로 되돌리기

```bash
cd ~/krx_hyungsoo

# 가장 최근 2개 커밋 확인
git log --oneline -5

# 이전 커밋으로 되돌리기 (예시)
git checkout HEAD~1 -- reports/phase_c/latest/
```

### 5-B. 안전장치 확인

```bash
# DRY_RUN 유지 확인
cat state/execution_gate.json

# sender_enable=false 확인
cat state/real_sender_enable.json
```

---

## 6. 담당 분리 요약

| 항목 | PC | OCI |
|------|:--:|:---:|
| 백테스트 | ✅ | ❌ |
| 데이터 수집 | ✅ | ❌ |
| 파라미터 튜닝 | ✅ | ❌ |
| 리포트 생성 | ✅ | ⚠️ (regenerate만) |
| Ops Cycle | ❌ | ✅ |
| Health/Drill | ❌ | ✅ |
| 알림 프리뷰 | ❌ | ✅ (CONSOLE) |
| 대시보드 | ⚠️ (로컬) | ✅ |

---

## 7. 관련 문서

| 문서 | 경로 |
|------|------|
| Handoff Contract | [contract_pc_to_oci_handoff_v1.md](../contracts/contract_pc_to_oci_handoff_v1.md) |
| OCI Scheduler | [runbook_oracle_cloud_scheduler_v1.md](runbook_oracle_cloud_scheduler_v1.md) |
| Deploy Runbook | [runbook_deploy_v1.md](runbook_deploy_v1.md) |
