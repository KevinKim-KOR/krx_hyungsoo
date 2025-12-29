# Cloud 배포 가이드

**최종 업데이트**: 2025-12-08

> **참고**: 백테스트/튜닝은 PC에서만 실행됩니다. Cloud는 알림 및 포트폴리오 관리용입니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Oracle Cloud                          │
│                                                          │
│  [API 서버] ←──→ [SQLite DB] ←──→ [리포트 스크립트]     │
│   :8000              krx_alertor.db                      │
│                                                          │
│  Cron Jobs:                                              │
│  - 09:00 장시작 알림                                     │
│  - 15:30 손절 모니터링                                   │
│  - 16:00 일일 리포트                                     │
│  - 토 10:00 주간 리포트                                  │
└─────────────────────────────────────────────────────────┘
           ↑
      HTTP API
           ↑
┌─────────────────────────────────────────────────────────┐
│                       PC                                 │
│                                                          │
│  [웹 브라우저] ──→ http://cloud-ip:8000                 │
│  [백테스트/ML] ──→ 로컬 실행                            │
└─────────────────────────────────────────────────────────┘
```

## 1. Cloud 서버 설정

### 1.1 프로젝트 클론
```bash
cd ~
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git
cd krx_hyungsoo
```

### 1.2 Python 환경 설정
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 1.3 환경 변수 설정
```bash
cp .env.example .env
nano .env
```

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DB_URL=sqlite:///data/krx_alertor.db
```

### 1.4 DB 초기화 및 마이그레이션
```bash
# DB 테이블 생성
python -c "from core.db import init_db; init_db()"

# current_price 컬럼 추가 (기존 DB가 있는 경우)
python scripts/maintenance/add_column_to_db.py
```

### 1.5 API 서버 systemd 서비스 등록
```bash
sudo nano /etc/systemd/system/krx-api.service
```

```ini
[Unit]
Description=KRX Alertor API Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/krx_hyungsoo
Environment="PATH=/home/ubuntu/krx_hyungsoo/venv/bin"
ExecStart=/home/ubuntu/krx_hyungsoo/venv/bin/uvicorn api_holdings:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable krx-api
sudo systemctl start krx-api
sudo systemctl status krx-api
```

### 1.6 방화벽 설정 (Oracle Cloud)
Oracle Cloud Console에서:
1. Networking > Virtual Cloud Networks > VCN 선택
2. Security Lists > Default Security List
3. Ingress Rules 추가:
   - Source: 0.0.0.0/0 (또는 PC IP만)
   - Protocol: TCP
   - Destination Port: 8000

```bash
# 서버 내 방화벽도 열기
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

## 2. Cron 설정

```bash
crontab -e
```

```cron
# 환경 변수
SHELL=/bin/bash
PATH=/home/ubuntu/krx_hyungsoo/venv/bin:/usr/local/bin:/usr/bin:/bin

# 장시작 알림 (평일 09:00)
0 9 * * 1-5 cd /home/ubuntu/krx_hyungsoo && /home/ubuntu/krx_hyungsoo/venv/bin/python scripts/nas/market_open_alert.py >> logs/cron.log 2>&1

# 가격 업데이트 (평일 15:35, 장 마감 직후)
35 15 * * 1-5 cd /home/ubuntu/krx_hyungsoo && /home/ubuntu/krx_hyungsoo/venv/bin/python -c "from extensions.automation.price_updater import PriceUpdater; PriceUpdater().update_prices()" >> logs/cron.log 2>&1

# 일일 리포트 (평일 16:00)
0 16 * * 1-5 cd /home/ubuntu/krx_hyungsoo && /home/ubuntu/krx_hyungsoo/venv/bin/python scripts/nas/daily_report_alert.py >> logs/cron.log 2>&1

# 주간 리포트 (토요일 10:00)
0 10 * * 6 cd /home/ubuntu/krx_hyungsoo && /home/ubuntu/krx_hyungsoo/venv/bin/python scripts/nas/weekly_report_alert.py >> logs/cron.log 2>&1
```

## 3. PC 설정

### 3.1 웹 대시보드 접속
브라우저에서 `http://CLOUD_IP:8000` 접속

### 3.2 프론트엔드 API URL 변경
`web/dashboard/.env` 파일 생성:
```env
VITE_API_URL=http://CLOUD_IP:8000
```

`web/dashboard/src/pages/Holdings.tsx` 수정:
```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// fetch 호출 시
const holdingsRes = await fetch(`${API_URL}/api/v1/holdings`)
```

## 4. PC에서 보유종목 수정 시 Cloud 반영

### 방법 1: Cloud API 직접 호출 (권장)
PC 웹 브라우저에서 Cloud API에 직접 접속하여 수정
- URL: `http://CLOUD_IP:8000`
- 종목 추가/삭제가 즉시 Cloud DB에 반영됨

### 방법 2: DB 파일 동기화
PC에서 수정 후 Cloud로 DB 파일 복사:
```bash
# PC에서 실행
scp data/krx_alertor.db ubuntu@CLOUD_IP:~/krx_hyungsoo/data/
```

## 5. 운영 체크리스트

### 매일
- [ ] 텔레그램 알림 수신 확인
- [ ] Cloud API 서버 상태 확인: `curl http://CLOUD_IP:8000`

### 매주
- [ ] 로그 확인: `tail -100 logs/cron.log`
- [ ] 디스크 용량 확인: `df -h`

### 종목 변경 시
- [ ] Cloud 웹 UI에서 직접 수정
- [ ] 또는 PC에서 수정 후 DB 동기화

## 6. 트러블슈팅

### API 서버가 안 뜰 때
```bash
sudo systemctl status krx-api
sudo journalctl -u krx-api -n 50
```

### 리포트가 안 올 때
```bash
# 수동 실행 테스트
cd ~/krx_hyungsoo
source venv/bin/activate
python scripts/nas/daily_report_alert.py
```

### DB 연결 오류
```bash
# DB 파일 권한 확인
ls -la data/krx_alertor.db

# DB 테이블 확인
sqlite3 data/krx_alertor.db ".tables"
sqlite3 data/krx_alertor.db "SELECT COUNT(*) FROM holdings WHERE quantity > 0"
```
