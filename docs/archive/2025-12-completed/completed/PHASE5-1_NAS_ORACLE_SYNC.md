# Phase 5-1: NAS ↔ Oracle 데이터 연동

**작성일**: 2025-11-17  
**상태**: 진행 예정  
**예상 기간**: 1~2일  
**담당**: PC/NAS 환경 설정 + Oracle 연동

---

## 🎯 **목표**

NAS에서 생성한 실시간 운영 데이터를 Oracle Cloud로 주기적으로 동기화하여, Oracle 대시보드에서 실제 포트폴리오/손절/신호 데이터를 조회 가능하게 만들기

---

## 📋 **작업 체크리스트**

### **1단계: 동기화 파일 구조 설계** ⬜
- [ ] 동기화할 데이터 항목 정의
- [ ] JSON 파일 포맷 설계
- [ ] NAS 출력 경로 결정
- [ ] Oracle 수신 경로 결정

### **2단계: NAS 측 준비** ⬜
- [ ] 동기화 디렉토리 생성
- [ ] 데이터 생성 스크립트 작성
- [ ] SSH 키 설정 (NAS → Oracle)
- [ ] rsync 테스트

### **3단계: Oracle 측 준비** ⬜
- [ ] 동기화 수신 디렉토리 생성
- [ ] SSH 키 등록
- [ ] 디스크 용량 확인
- [ ] 방화벽 확인 (SSH 포트 22)

### **4단계: 동기화 스크립트 작성** ⬜
- [ ] NAS → Oracle rsync 스크립트
- [ ] 에러 핸들링
- [ ] 로그 기록
- [ ] 텔레그램 알림 (선택)

### **5단계: FastAPI 수정** ⬜
- [ ] 동기화된 파일 읽기 로직
- [ ] API 응답에 실시간 데이터 반영
- [ ] 에러 처리 (파일 없을 때)

### **6단계: 크론 설정** ⬜
- [ ] NAS cron 스케줄 등록
- [ ] 동기화 주기 결정 (5분/1시간/일)
- [ ] 테스트 실행

### **7단계: 통합 테스트** ⬜
- [ ] NAS에서 데이터 생성
- [ ] 동기화 실행
- [ ] Oracle API 확인
- [ ] 대시보드 UI 확인

---

## 📁 **파일 구조 설계**

### **NAS 측 (데이터 생성)**

```
/volume2/homes/Hyungsoo/krx/krx_alertor_modular/
└── data/
    └── sync/                           # 동기화 전용 디렉토리
        ├── portfolio_snapshot.json     # 포트폴리오 현황
        ├── backtest_results.json       # 최신 백테스트 결과
        ├── signals_today.json          # 오늘의 매매 신호
        ├── stop_loss_targets.json      # 손절 대상 종목
        ├── alerts_history.json         # 알림 히스토리
        └── market_regime.json          # 현재 시장 레짐
```

### **Oracle 측 (데이터 수신)**

```
~/krx_hyungsoo/
└── data/
    └── sync/                           # NAS에서 동기화된 파일
        ├── portfolio_snapshot.json
        ├── backtest_results.json
        ├── signals_today.json
        ├── stop_loss_targets.json
        ├── alerts_history.json
        └── market_regime.json
```

---

## 📊 **동기화 데이터 포맷**

### **1. portfolio_snapshot.json**

```json
{
  "timestamp": "2025-11-17T16:00:00",
  "total_assets": 10500000,
  "cash": 2000000,
  "stocks_value": 8500000,
  "total_return_pct": 5.2,
  "daily_return_pct": 0.3,
  "holdings": [
    {
      "code": "069500",
      "name": "KODEX 200",
      "quantity": 100,
      "avg_price": 35000,
      "current_price": 35500,
      "return_pct": 1.43
    }
  ]
}
```

### **2. backtest_results.json**

```json
{
  "timestamp": "2025-11-17T10:00:00",
  "jason_strategy": {
    "cagr": 39.02,
    "sharpe": 1.71,
    "mdd": -23.51,
    "total_return": 153.88
  },
  "hybrid_strategy": {
    "cagr": 27.05,
    "sharpe": 1.51,
    "mdd": -19.92,
    "total_return": 96.80
  }
}
```

### **3. signals_today.json**

```json
{
  "timestamp": "2025-11-17T15:30:00",
  "signals": [
    {
      "code": "069500",
      "name": "KODEX 200",
      "signal_type": "buy",
      "price": 35500,
      "reason": "MAPS 점수 상위 10위",
      "confidence": 0.85
    }
  ]
}
```

### **4. stop_loss_targets.json**

```json
{
  "timestamp": "2025-11-17T16:00:00",
  "strategy": "hybrid",
  "targets": [
    {
      "code": "088980",
      "name": "맥쿼리인프라",
      "return_pct": -8.75,
      "threshold": -5.0,
      "current_value": 146770,
      "loss_amount": -14079
    }
  ]
}
```

### **5. alerts_history.json**

```json
{
  "timestamp": "2025-11-17T16:00:00",
  "alerts": [
    {
      "timestamp": "2025-11-17T15:30:00",
      "type": "stop_loss",
      "message": "손절 대상 6개 종목 발견",
      "level": "warning"
    }
  ]
}
```

### **6. market_regime.json**

```json
{
  "timestamp": "2025-11-17T16:00:00",
  "current_regime": "bull",
  "ma50": 35000,
  "ma200": 33000,
  "trend_strength": 85.0,
  "volatility": "low",
  "confidence": 92.0
}
```

---

## 🔧 **구현 상세**

### **1. NAS 데이터 생성 스크립트**

**파일**: `scripts/sync/generate_sync_data.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/sync/generate_sync_data.py
동기화용 JSON 데이터 생성
"""
import json
from datetime import datetime
from pathlib import Path

def generate_portfolio_snapshot():
    """포트폴리오 스냅샷 생성"""
    # TODO: 실제 DB에서 데이터 조회
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_assets": 10500000,
        "cash": 2000000,
        "stocks_value": 8500000,
        "total_return_pct": 5.2,
        "daily_return_pct": 0.3,
        "holdings": []
    }
    return data

def generate_backtest_results():
    """백테스트 결과 생성"""
    # TODO: 최신 백테스트 결과 로드
    data = {
        "timestamp": datetime.now().isoformat(),
        "jason_strategy": {
            "cagr": 39.02,
            "sharpe": 1.71,
            "mdd": -23.51,
            "total_return": 153.88
        },
        "hybrid_strategy": {
            "cagr": 27.05,
            "sharpe": 1.51,
            "mdd": -19.92,
            "total_return": 96.80
        }
    }
    return data

def main():
    """메인 함수"""
    sync_dir = Path(__file__).parent.parent.parent / "data" / "sync"
    sync_dir.mkdir(parents=True, exist_ok=True)
    
    # 각 파일 생성
    files = {
        "portfolio_snapshot.json": generate_portfolio_snapshot(),
        "backtest_results.json": generate_backtest_results(),
        # TODO: 나머지 파일들
    }
    
    for filename, data in files.items():
        filepath = sync_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ {filename} 생성 완료")

if __name__ == "__main__":
    main()
```

---

### **2. NAS → Oracle 동기화 스크립트**

**파일**: `scripts/sync/sync_to_oracle.sh`

```bash
#!/bin/bash
# scripts/sync/sync_to_oracle.sh
# NAS에서 Oracle Cloud로 데이터 동기화

# 설정
NAS_SYNC_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/sync"
ORACLE_USER="ubuntu"
ORACLE_HOST="168.107.51.68"
ORACLE_SYNC_DIR="~/krx_hyungsoo/data/sync"
SSH_KEY="/volume2/homes/Hyungsoo/.ssh/oracle_cloud_key"
LOG_FILE="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/sync.log"

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 동기화 실행
log "🚀 동기화 시작"

rsync -avz --progress \
    -e "ssh -i $SSH_KEY" \
    "$NAS_SYNC_DIR/" \
    "$ORACLE_USER@$ORACLE_HOST:$ORACLE_SYNC_DIR/"

if [ $? -eq 0 ]; then
    log "✅ 동기화 성공"
else
    log "❌ 동기화 실패"
    # TODO: 텔레그램 알림
    exit 1
fi

log "✨ 동기화 완료"
```

---

### **3. Oracle FastAPI 수정**

**파일**: `backend/app/api/v1/dashboard.py` (수정)

```python
from pathlib import Path
import json
from datetime import datetime

SYNC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sync"

@router.get("/summary", response_model=DashboardResponse)
async def get_dashboard_summary():
    """대시보드 요약 - 동기화된 데이터 우선 사용"""
    
    # 1. 동기화된 파일 확인
    snapshot_file = SYNC_DIR / "portfolio_snapshot.json"
    
    if snapshot_file.exists():
        # 동기화된 실시간 데이터 사용
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return DashboardResponse(
            total_assets=data["total_assets"],
            cash=data["cash"],
            stocks_value=data["stocks_value"],
            total_return_pct=data["total_return_pct"],
            daily_return_pct=data["daily_return_pct"],
            # ...
        )
    else:
        # 동기화 파일 없으면 DB 조회 (기존 로직)
        # ...
```

---

### **4. NAS Cron 설정**

```bash
# NAS SSH 접속 후
crontab -e

# 5분마다 데이터 생성 + 동기화
*/5 * * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/generate_sync_data.py >> /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/generate.log 2>&1
*/5 * * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/sync_to_oracle.sh

# 또는 1시간마다
0 * * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/generate_sync_data.py >> /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/generate.log 2>&1
0 * * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/sync_to_oracle.sh
```

---

## 🧪 **테스트 시나리오**

### **1. 로컬 테스트 (NAS)**

```bash
# 1) 데이터 생성
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
python scripts/sync/generate_sync_data.py

# 2) 파일 확인
ls -lh data/sync/
cat data/sync/portfolio_snapshot.json
```

### **2. 동기화 테스트 (NAS → Oracle)**

```bash
# 1) 수동 동기화
bash scripts/sync/sync_to_oracle.sh

# 2) Oracle에서 확인
ssh -i ~/.ssh/oracle_cloud_key ubuntu@168.107.51.68
cd ~/krx_hyungsoo/data/sync
ls -lh
cat portfolio_snapshot.json
```

### **3. API 테스트 (Oracle)**

```bash
# Oracle VM에서
curl http://localhost:8000/api/v1/dashboard/summary | jq

# 로컬 PC에서
curl http://168.107.51.68:8000/api/v1/dashboard/summary | jq
```

### **4. 대시보드 확인**

브라우저에서:
- `http://168.107.51.68:8000`
- 홈 화면에서 실시간 데이터 표시 확인

---

## 🔒 **보안 고려사항**

### **1. SSH 키 관리**

```bash
# NAS에서 SSH 키 생성 (이미 있으면 스킵)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/oracle_cloud_key

# 공개 키를 Oracle에 등록
ssh-copy-id -i ~/.ssh/oracle_cloud_key.pub ubuntu@168.107.51.68

# 권한 설정
chmod 600 ~/.ssh/oracle_cloud_key
```

### **2. 방화벽 (Oracle)**

- SSH 포트 22는 이미 열려 있어야 함 (기본)
- 필요 시 특정 IP만 허용 (NAS 공인 IP)

---

## 📊 **예상 결과**

### **동기화 전 (현재)**
- Oracle 대시보드: 더미 데이터 또는 빈 값
- 모바일 접속: 가능하지만 실제 데이터 없음

### **동기화 후 (목표)**
- Oracle 대시보드: NAS의 실시간 데이터 표시
- 모바일 접속: 현재 포트폴리오, 손절 대상, 신호 등 실시간 조회
- 자동 업데이트: 5분/1시간마다 최신 데이터 반영

---

## 🎯 **다음 단계**

Phase 5-1 완료 후:
- **Phase 5-2**: 머신러닝 모델 (PC)
- **Phase 5-5**: UI/UX 고도화 (Oracle)

---

## 📚 **참고 문서**

- `docs/PHASE5_PLAN.md` - Phase 5 전체 계획
- `docs/PHASE4.5_COMPLETE.md` - Phase 4.5 완료 문서
- `backend/README.md` - 백엔드 API 문서

---

**작성자**: Cascade AI  
**최종 수정**: 2025-11-17  
**다음 업데이트**: Phase 5-1 시작 시
