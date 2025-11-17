# NAS ↔ Oracle 동기화 스크립트

**Phase**: 5-1  
**목적**: NAS에서 생성한 실시간 데이터를 Oracle Cloud로 동기화

---

## 📁 파일 구조

```
scripts/sync/
├── generate_sync_data.py    # 동기화 데이터 생성 (Python)
├── sync_to_oracle.sh         # Oracle로 동기화 (Bash)
└── README.md                 # 이 파일
```

---

## 🚀 사용 방법

### 1. 데이터 생성 (NAS/PC 공통)

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular  # NAS
# 또는
cd "E:\AI Study\krx_alertor_modular"  # PC

python scripts/sync/generate_sync_data.py
```

**생성 파일** (`data/sync/`):
- `portfolio_snapshot.json` - 포트폴리오 현황
- `backtest_results.json` - 백테스트 결과
- `signals_today.json` - 매매 신호
- `stop_loss_targets.json` - 손절 대상
- `alerts_history.json` - 알림 히스토리
- `market_regime.json` - 시장 레짐

### 2. Oracle로 동기화 (NAS 전용)

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
bash scripts/sync/sync_to_oracle.sh
```

**동작**:
1. 사전 조건 확인 (SSH 키, 파일 존재)
2. rsync로 파일 전송
3. 텔레그램 알림 (선택)

---

## ⚙️ 설정

### SSH 키 설정 (NAS)

```bash
# 1. SSH 키 생성 (없으면)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/oracle_cloud_key

# 2. 공개 키를 Oracle에 등록
ssh-copy-id -i ~/.ssh/oracle_cloud_key.pub ubuntu@168.107.51.68

# 3. 권한 설정
chmod 600 ~/.ssh/oracle_cloud_key
```

### 텔레그램 알림 (선택)

`.env` 파일에 추가:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 🔄 자동화 (Cron)

### 5분마다 동기화

```bash
crontab -e

# 추가
*/5 * * * * cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python scripts/sync/generate_sync_data.py >> logs/sync/generate.log 2>&1
*/5 * * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/sync_to_oracle.sh
```

### 1시간마다 동기화

```bash
0 * * * * cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python scripts/sync/generate_sync_data.py >> logs/sync/generate.log 2>&1
0 * * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/sync_to_oracle.sh
```

### 일 1회 (장 마감 후)

```bash
0 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python scripts/sync/generate_sync_data.py >> logs/sync/generate.log 2>&1
5 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/sync_to_oracle.sh
```

---

## 📊 로그 확인

```bash
# 데이터 생성 로그
tail -f logs/sync/generate.log

# 동기화 로그
tail -f logs/sync/sync_$(date +%Y%m%d).log

# 에러 확인
grep -i error logs/sync/*.log
```

---

## 🐛 문제 해결

### SSH 연결 실패

```bash
# 연결 테스트
ssh -i ~/.ssh/oracle_cloud_key ubuntu@168.107.51.68

# 권한 확인
ls -l ~/.ssh/oracle_cloud_key
# -rw------- (600)이어야 함

# 권한 수정
chmod 600 ~/.ssh/oracle_cloud_key
```

### rsync 실패

```bash
# 수동 rsync 테스트
rsync -avz -e "ssh -i ~/.ssh/oracle_cloud_key" \
    /volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/sync/ \
    ubuntu@168.107.51.68:~/krx_hyungsoo/data/sync/
```

### 데이터 생성 실패

```bash
# Python 경로 확인
which python
which python3

# 의존성 확인
pip list | grep -E "pandas|pykrx"

# 수동 실행 (디버깅)
python scripts/sync/generate_sync_data.py
```

---

## 📚 관련 문서

- `docs/PHASE5-1_NAS_ORACLE_SYNC.md` - Phase 5-1 상세 가이드
- `docs/PHASE5_PLAN.md` - Phase 5 전체 계획
- `backend/README.md` - FastAPI 백엔드 문서

---

**작성일**: 2025-11-17  
**버전**: 1.0.0  
**상태**: ✅ 구현 완료
