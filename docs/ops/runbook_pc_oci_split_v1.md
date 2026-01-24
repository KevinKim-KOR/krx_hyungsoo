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

### 4-B. 자동 스케줄 (09:05 KST) - D-P.54

> ✅ **통합 스크립트**: `deploy/oci/daily_ops.sh` 하나로 전체 운영

```bash
# 수동 실행
bash deploy/oci/daily_ops.sh
echo "exit=$?"
# exit 0: COMPLETED/WARN OK
# exit 2: BLOCKED (정상 차단)
# exit 3: 운영 장애

# cron 설정 (09:05 KST)
crontab -e
# 추가: 5 9 * * * cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
```

**daily_ops.sh 5단계 흐름:**
1. `git pull` (PC 번들 동기화)
2. Backend health check
3. Ops Summary regenerate + 검증
4. Live Cycle run + 검증
5. Snapshot resolver 확인

### 4-C. 실행 결과 확인

```bash
# Ops Cycle 최신 결과
curl -s http://127.0.0.1:8000/api/ops/scheduler/latest | head

# Ops Summary
curl -s http://127.0.0.1:8000/api/ops/summary/latest | head

# Health
curl -s http://127.0.0.1:8000/api/ops/health
```

### 4-D. Live Cycle 1분 검증 (D-P.51)

> ✅ **권장**: 아래 스크립트 하나로 전체 검증 완료

```bash
# 1-minute check script (권장)
bash deploy/oci/check_live_cycle.sh
echo "exit=$?"
# 기대값: exit=0 + 요약 1줄 출력
```

수동 확인이 필요한 경우:

```bash
# Live Cycle 실행
curl -X POST "http://127.0.0.1:8000/api/live/cycle/run?confirm=true"

# 최신 영수증 요약
curl -s http://127.0.0.1:8000/api/live/cycle/latest | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("rows",[{}])[0]; print("result=",r.get("result"),"decision=",r.get("decision"),"snapshot_ref=",r.get("snapshot_ref"))'

# delivery_actual 확인
curl -s http://127.0.0.1:8000/api/live/cycle/latest | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("rows",[{}])[0]; print("delivery=",(r.get("push") or {}).get("delivery_actual"))'
```

### 4-E. Ops Summary 1분 검증 (D-P.53.1)

> ⚠️ **금지 패턴**:
> - `curl | python3 - <<'PY'` (heredoc이 stdin을 덮어씀)
> - `eval "$PYTHON_OUTPUT"` (Python 리스트 문법이 bash 명령으로 실행됨)
> - 로컬 파일 직접 접근 (`cat`, `head -c`) -> **resolver API만 사용**
> 
> ✅ **권장 패턴**:
> - `python3 -c '...'` 또는 `check_*.sh` 스크립트 사용
> - ref 전달 시 **URL 인코딩**: `--data-urlencode "ref=${REF}"`

```bash
# 1-minute check script (권장)
bash deploy/oci/check_ops_summary.sh
echo "exit=$?"
# 기대값: exit=0 (WARN도 OK)
```

수동 확인이 필요한 경우:

```bash
# Summary 재생성
curl -X POST "http://127.0.0.1:8000/api/ops/summary/regenerate?confirm=true"

# 최신 summary 확인
curl -s http://127.0.0.1:8000/api/ops/summary/latest | python3 -c 'import json,sys; d=json.load(sys.stdin); row=(d.get("rows") or [d])[0]; print("overall_status=",row.get("overall_status")); print("top_risks=",[r.get("code") for r in row.get("top_risks",[])])'
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
