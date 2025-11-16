# Oracle Cloud 배포 가이드 (Streamlit)

## 🎯 **목표**

Oracle Cloud Free Tier에 Streamlit 대시보드 배포

---

## 📋 **사전 준비**

### **1. Oracle Cloud 계정** ✅
```
✅ 가입 완료
✅ Free Tier 활성화
```

### **2. 로컬 테스트 완료** ✅
```
✅ Streamlit 대시보드 정상 작동
✅ 모든 페이지 확인
✅ 데이터 로드 확인
```

---

## 🚀 **Step 1: VM 인스턴스 생성**

### **1.1 Oracle Cloud 콘솔 접속**
```
https://cloud.oracle.com/
```

### **1.2 Compute 인스턴스 생성**
```
1. 메뉴 > Compute > Instances
2. "Create Instance" 클릭

설정:
- Name: krx-dashboard
- Image: Ubuntu 22.04 (Canonical)
- Shape: VM.Standard.E2.1.Micro (Free Tier)
  * 1 OCPU
  * 1 GB RAM
  * Always Free!
- VCN: 기본 VCN 사용
- Subnet: Public Subnet
- Public IP: Assign a public IPv4 address ✅
- SSH Keys: 
  * Generate SSH key pair 다운로드
  * 또는 기존 public key 업로드
```

### **1.3 인스턴스 생성 완료**
```
Public IP 주소 확인:
예: 123.456.789.012

SSH 접속 테스트:
ssh -i <private-key> ubuntu@123.456.789.012
```

---

## 🔧 **Step 2: 방화벽 설정**

### **2.1 Oracle Cloud 방화벽**
```
1. VCN Details > Security Lists
2. Default Security List 선택
3. "Add Ingress Rules" 클릭

규칙 추가:
- Source CIDR: 0.0.0.0/0
- Destination Port: 8501 (Streamlit)
- Description: Streamlit Dashboard

규칙 추가 (HTTPS):
- Source CIDR: 0.0.0.0/0
- Destination Port: 443
- Description: HTTPS
```

### **2.2 Ubuntu 방화벽**
```bash
# SSH 접속 후
sudo ufw allow 8501/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status
```

---

## 📦 **Step 3: 환경 구축**

### **3.1 시스템 업데이트**
```bash
sudo apt update
sudo apt upgrade -y
```

### **3.2 Python 설치**
```bash
# Python 3.10 설치
sudo apt install -y python3.10 python3.10-venv python3-pip
python3.10 --version
```

### **3.3 Git 설치**
```bash
sudo apt install -y git
git --version
```

---

## 🎯 **Step 4: 프로젝트 배포**

### **4.1 프로젝트 클론**
```bash
cd ~
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git
cd krx_hyungsoo
```

### **4.2 가상환경 생성**
```bash
python3.10 -m venv venv
source venv/bin/activate
```

### **4.3 의존성 설치**
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install streamlit plotly
```

### **4.4 환경 변수 설정**
```bash
# .env 파일 생성
nano .env

# 내용 입력
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# 저장: Ctrl+X, Y, Enter
```

---

## 🚀 **Step 5: Streamlit 실행**

### **5.1 테스트 실행**
```bash
streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
```

### **5.2 브라우저 접속**
```
http://123.456.789.012:8501
```

### **5.3 정상 작동 확인**
```
✅ 대시보드 로드
✅ 모든 페이지 확인
✅ 데이터 표시 확인
```

---

## 🔄 **Step 6: 백그라운드 실행 (systemd)**

### **6.1 서비스 파일 생성**
```bash
sudo nano /etc/systemd/system/streamlit-dashboard.service
```

### **6.2 서비스 설정**
```ini
[Unit]
Description=Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/krx_hyungsoo
Environment="PATH=/home/ubuntu/krx_hyungsoo/venv/bin"
ExecStart=/home/ubuntu/krx_hyungsoo/venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **6.3 서비스 시작**
```bash
sudo systemctl daemon-reload
sudo systemctl enable streamlit-dashboard
sudo systemctl start streamlit-dashboard
sudo systemctl status streamlit-dashboard
```

### **6.4 로그 확인**
```bash
sudo journalctl -u streamlit-dashboard -f
```

---

## 🔒 **Step 7: SSL 인증서 설정 (HTTPS)**

### **7.1 도메인 연결 (선택)**
```
1. 도메인 구매 (예: example.com)
2. DNS A 레코드 추가
   - Name: dashboard
   - Type: A
   - Value: 123.456.789.012
   - TTL: 3600

결과: dashboard.example.com → 123.456.789.012
```

### **7.2 Nginx 설치**
```bash
sudo apt install -y nginx
```

### **7.3 Nginx 설정**
```bash
sudo nano /etc/nginx/sites-available/streamlit
```

```nginx
server {
    listen 80;
    server_name 123.456.789.012;  # 또는 dashboard.example.com

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

```bash
sudo ln -s /etc/nginx/sites-available/streamlit /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### **7.4 Let's Encrypt SSL (도메인 있을 때)**
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d dashboard.example.com
```

---

## 🔐 **Step 8: 보안 강화**

### **8.1 기본 인증 추가**
```bash
# htpasswd 설치
sudo apt install -y apache2-utils

# 사용자 생성
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Nginx 설정 수정
sudo nano /etc/nginx/sites-available/streamlit
```

```nginx
server {
    listen 80;
    server_name 123.456.789.012;

    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://localhost:8501;
        # ... 나머지 설정
    }
}
```

```bash
sudo systemctl restart nginx
```

### **8.2 IP 화이트리스트 (선택)**
```nginx
server {
    listen 80;
    server_name 123.456.789.012;

    # 특정 IP만 허용
    allow 1.2.3.4;      # 집 IP
    allow 5.6.7.8;      # 회사 IP
    deny all;

    location / {
        proxy_pass http://localhost:8501;
        # ... 나머지 설정
    }
}
```

---

## 🔄 **Step 9: 자동 업데이트 스크립트**

### **9.1 업데이트 스크립트 생성**
```bash
nano ~/update-dashboard.sh
```

```bash
#!/bin/bash
cd /home/ubuntu/krx_hyungsoo
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart streamlit-dashboard
echo "Dashboard updated successfully!"
```

```bash
chmod +x ~/update-dashboard.sh
```

### **9.2 업데이트 실행**
```bash
~/update-dashboard.sh
```

---

## 📊 **Step 10: 모니터링**

### **10.1 시스템 리소스 확인**
```bash
# CPU, 메모리 사용률
htop

# 디스크 사용량
df -h

# 네트워크 연결
netstat -tulpn | grep 8501
```

### **10.2 로그 모니터링**
```bash
# Streamlit 로그
sudo journalctl -u streamlit-dashboard -f

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 🐛 **트러블슈팅**

### **문제 1: 포트 접속 안 됨**
```bash
# 방화벽 확인
sudo ufw status

# 포트 리스닝 확인
sudo netstat -tulpn | grep 8501

# Oracle Cloud Security List 확인
# 웹 콘솔에서 Ingress Rules 확인
```

### **문제 2: Streamlit 실행 안 됨**
```bash
# 로그 확인
sudo journalctl -u streamlit-dashboard -n 50

# 수동 실행 테스트
cd /home/ubuntu/krx_hyungsoo
source venv/bin/activate
streamlit run dashboard/app.py
```

### **문제 3: 메모리 부족**
```bash
# 스왑 파일 생성 (1GB)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 📝 **체크리스트**

### **배포 전**
```
✅ Oracle Cloud VM 생성
✅ 방화벽 설정 (8501, 443)
✅ SSH 접속 확인
```

### **배포 중**
```
✅ Python 설치
✅ Git 클론
✅ 의존성 설치
✅ Streamlit 실행
✅ 브라우저 접속 확인
```

### **배포 후**
```
✅ systemd 서비스 등록
✅ Nginx 리버스 프록시
✅ SSL 인증서 (선택)
✅ 기본 인증 (선택)
✅ 자동 업데이트 스크립트
```

---

## 🎯 **최종 접속 URL**

### **HTTP (기본)**
```
http://123.456.789.012:8501
```

### **Nginx 프록시 (80포트)**
```
http://123.456.789.012
```

### **HTTPS (도메인 + SSL)**
```
https://dashboard.example.com
```

---

## 💡 **추가 개선 사항**

### **1. 데이터 동기화**
```bash
# NAS에서 Oracle Cloud로 데이터 동기화
rsync -avz -e ssh /volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/ \
  ubuntu@123.456.789.012:/home/ubuntu/krx_hyungsoo/data/
```

### **2. 자동 백업**
```bash
# Cron 설정
crontab -e

# 매일 새벽 3시 백업
0 3 * * * /home/ubuntu/backup-dashboard.sh
```

### **3. 성능 최적화**
```python
# dashboard/app.py
import streamlit as st

# 캐싱 활용
@st.cache_data(ttl=3600)
def load_data():
    # 데이터 로드
    pass
```

---

## 🎉 **배포 완료!**

### **성공 확인**
```
✅ Oracle Cloud VM 실행 중
✅ Streamlit 대시보드 접속 가능
✅ 모든 페이지 정상 작동
✅ 보안 설정 완료
✅ 자동 재시작 설정
```

### **다음 단계**
```
1. Phase 5: ML + 포트폴리오 최적화
2. 대시보드에 ML 결과 추가
3. FastAPI + React 전환 (선택)
```

---

**Oracle Cloud 배포 준비 완료!** 🚀  
**언제든지 배포 시작하세요!** ✅
