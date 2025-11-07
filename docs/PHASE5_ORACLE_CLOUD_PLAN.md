# Phase 5: Oracle Cloud 배포 계획

## 🎯 목표

NAS 대신 Oracle Cloud에 시스템을 배포하여 안정성과 확장성 확보

---

## 📋 배포 계획

### 1. Oracle Cloud 환경 설정

#### 1.1 인스턴스 생성
- **타입**: VM.Standard.E2.1.Micro (Always Free Tier)
- **OS**: Ubuntu 22.04 LTS
- **스토리지**: 50GB Boot Volume
- **네트워크**: Public IP 할당

#### 1.2 보안 설정
- **방화벽**: 
  - SSH (22)
  - HTTP (80)
  - HTTPS (443)
  - Streamlit (8501)
- **SSH 키**: 생성 및 등록

---

### 2. 시스템 환경 구성

#### 2.1 기본 패키지 설치
```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python 3.10 설치
sudo apt install python3.10 python3.10-venv python3-pip -y

# Git 설치
sudo apt install git -y

# 기타 도구
sudo apt install htop vim curl wget -y
```

#### 2.2 프로젝트 클론
```bash
cd /home/ubuntu
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git
cd krx_hyungsoo
```

#### 2.3 Python 환경 설정
```bash
# 가상환경 생성
python3.10 -m venv venv

# 활성화
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
pip install -r requirements_dashboard.txt
```

---

### 3. 서비스 설정

#### 3.1 Systemd 서비스 (신호 생성)

**파일**: `/etc/systemd/system/krx-realtime.service`

```ini
[Unit]
Description=KRX Realtime Signal Service
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/krx_hyungsoo
Environment="PATH=/home/ubuntu/krx_hyungsoo/venv/bin"
ExecStart=/home/ubuntu/krx_hyungsoo/venv/bin/python nas/app_realtime.py

[Install]
WantedBy=multi-user.target
```

#### 3.2 Systemd 서비스 (대시보드)

**파일**: `/etc/systemd/system/krx-dashboard.service`

```ini
[Unit]
Description=KRX Dashboard Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/krx_hyungsoo
Environment="PATH=/home/ubuntu/krx_hyungsoo/venv/bin"
ExecStart=/home/ubuntu/krx_hyungsoo/venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 3.3 서비스 등록 및 시작
```bash
# 서비스 등록
sudo systemctl daemon-reload

# 대시보드 시작
sudo systemctl enable krx-dashboard
sudo systemctl start krx-dashboard

# 상태 확인
sudo systemctl status krx-dashboard
```

---

### 4. Cron 스케줄 설정

**파일**: `/etc/cron.d/krx-scheduler`

```bash
# 장 시작 알림 (09:00)
0 9 * * 1-5 ubuntu cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/nas/market_open_alert.py

# 상승 ETF 알림 (10:00~15:00, 매 1시간)
0 10-15 * * 1-5 ubuntu cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/nas/rising_etf_alert.py

# EoD 신호 (16:00)
0 16 * * 1-5 ubuntu cd /home/ubuntu/krx_hyungsoo && venv/bin/python nas/app_realtime.py

# 레짐 변경 (16:30)
30 16 * * 1-5 ubuntu cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/nas/regime_change_alert.py

# 주간 리포트 (일요일 09:00)
0 9 * * 0 ubuntu cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/nas/weekly_report.py

# 로그 정리 (02:00)
0 2 * * * ubuntu cd /home/ubuntu/krx_hyungsoo && bash scripts/nas/cleanup_logs.sh

# DB 백업 (03:00)
0 3 * * * ubuntu cd /home/ubuntu/krx_hyungsoo && bash scripts/nas/backup_db.sh
```

---

### 5. Nginx 리버스 프록시 (선택)

#### 5.1 Nginx 설치
```bash
sudo apt install nginx -y
```

#### 5.2 설정 파일

**파일**: `/etc/nginx/sites-available/krx-dashboard`

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 5.3 활성화
```bash
sudo ln -s /etc/nginx/sites-available/krx-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### 6. SSL 인증서 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx -y

# 인증서 발급
sudo certbot --nginx -d your-domain.com

# 자동 갱신 확인
sudo certbot renew --dry-run
```

---

## 🔧 NAS vs Oracle Cloud 비교

| 항목 | NAS (DS220j) | Oracle Cloud |
|------|-------------|--------------|
| CPU | Dual-core 1.4GHz | 1 OCPU (2.0GHz+) |
| RAM | 2GB | 1GB (Free Tier) |
| 스토리지 | 로컬 HDD | 50GB SSD |
| 네트워크 | 가정용 인터넷 | 클라우드 네트워크 |
| 안정성 | 중간 | 높음 |
| 확장성 | 낮음 | 높음 |
| 비용 | 전기세 | 무료 (Free Tier) |
| 접근성 | DDNS 필요 | Public IP |

---

## 📝 마이그레이션 체크리스트

### 사전 준비
- [ ] Oracle Cloud 계정 생성
- [ ] VM 인스턴스 생성
- [ ] SSH 키 생성 및 등록
- [ ] 방화벽 규칙 설정

### 환경 설정
- [ ] Ubuntu 업데이트
- [ ] Python 3.10 설치
- [ ] Git 클론
- [ ] 가상환경 생성
- [ ] 의존성 설치

### 설정 파일
- [ ] `secret/config.yaml` 복사 (텔레그램 설정)
- [ ] DB 파일 복사 (선택)
- [ ] 로그 디렉토리 생성

### 서비스 설정
- [ ] Systemd 서비스 등록
- [ ] Cron 스케줄 설정
- [ ] Nginx 설정 (선택)
- [ ] SSL 인증서 (선택)

### 테스트
- [ ] 수동 신호 생성 테스트
- [ ] 텔레그램 알림 테스트
- [ ] 대시보드 접속 테스트
- [ ] Cron 작업 테스트

### 모니터링
- [ ] 로그 확인
- [ ] 서비스 상태 확인
- [ ] 리소스 사용량 확인

---

## 🚀 배포 절차

### 1단계: 인스턴스 준비 (1시간)
- Oracle Cloud 계정 생성
- VM 인스턴스 생성
- SSH 접속 확인

### 2단계: 환경 구성 (1시간)
- 시스템 업데이트
- Python 및 의존성 설치
- 프로젝트 클론

### 3단계: 서비스 설정 (1시간)
- Systemd 서비스 등록
- Cron 스케줄 설정
- 설정 파일 복사

### 4단계: 테스트 (30분)
- 수동 실행 테스트
- 알림 테스트
- 대시보드 테스트

### 5단계: 모니터링 (지속)
- 1주일 모니터링
- 로그 확인
- 성능 최적화

---

## 💡 추가 고려사항

### 데이터 백업
- Oracle Object Storage 활용
- 주기적 DB 백업
- 로그 아카이빙

### 모니터링
- Prometheus + Grafana (선택)
- 시스템 리소스 모니터링
- 알림 실패 감지

### 보안
- SSH 키 기반 인증
- 방화벽 최소 권한
- 정기적 보안 업데이트

### 비용 최적화
- Free Tier 한도 확인
- 리소스 사용량 모니터링
- 불필요한 서비스 중지

---

## 📚 참고 자료

- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- [Ubuntu Server Guide](https://ubuntu.com/server/docs)
- [Systemd Service](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
