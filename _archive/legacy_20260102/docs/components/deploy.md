# Deploy Module (`deploy/`)

**Last Updated**: 2026-01-01
**Purpose**: 배포 스크립트 및 설정

---

## 📊 File Usage Summary

| File | Status | Used By |
|------|--------|---------|
| `run_daily.sh` | ✅ **ACTIVE** | Linux/NAS 크론 |
| `run_daily.ps1` | ✅ **ACTIVE** | Windows 스케줄러 |

---

## 📄 Files

| File | Status | Description |
|------|--------|-------------|
| `run_daily.sh` | ✅ ACTIVE | Linux 일일 배치 스크립트 |
| `run_daily.ps1` | ✅ ACTIVE | Windows 일일 배치 스크립트 |

---

## 🚀 일일 실행

### Windows - ✅ ACTIVE
```powershell
./deploy/run_daily.ps1
```

### Linux/NAS - ✅ ACTIVE
```bash
./deploy/run_daily.sh
```

---

## 📋 실행 흐름
1. 거래일 확인
2. EOD 데이터 수집
3. 전략 신호 생성 (`app.cli.alerts scan`)
4. Paper Trading 실행 (`paper_trade_phase9.py`)
5. 알림 전송

---

## ⚠️ Idempotency
동일 날짜에 여러 번 실행해도 안전합니다 (SKIP 처리).
