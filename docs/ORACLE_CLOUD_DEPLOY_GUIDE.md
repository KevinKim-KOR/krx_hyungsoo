# Oracle Cloud 배포 가이드 (Phase 4.5)

## 🎯 **목표**

FastAPI + HTML 대시보드를 Oracle Cloud Free Tier에 배포

---

## 📋 **사전 준비**

### **1. Oracle Cloud 계정** ✅
```
✅ 계정 생성 완료
✅ Free Tier 활성화
```

### **2. VM 인스턴스 생성**
```
Shape: VM.Standard.E2.1.Micro (Free Tier)
OS: Ubuntu 22.04 LTS
Block Volume: 200GB (Free Tier)
```

---

## 🚀 **배포 단계**

### **Step 1: VM 인스턴스 생성**

#### **1.1 Oracle Cloud Console 접속**
```
https://cloud.oracle.com
→ Compute → Instances → Create Instance
```

#### **1.2 인스턴스 설정**
```
Name: krx-alertor-vm
Image: Ubuntu 22.04 LTS
Shape: VM.Standard.E2.1.Micro (Always Free)
Boot Volume: 50GB
```

#### **1.3 네트워크 설정**
```
VCN: 기본 VCN 사용
Subnet: Public Subnet
Public IP: 자동 할당
```

#### **1.4 SSH 키 설정**
```
SSH 키 생성 (로컬):
ssh-keygen -t rsa -b 4096 -f ~/.ssh/oracle_cloud_key

Public Key 업로드:
~/.ssh/oracle_cloud_key.pub 내용 복사
```

---

### **Step 2: 방화벽 설정**

#### **2.1 Oracle Cloud 보안 규칙**
```
Compute → Instances → krx-alertor-vm
→ Virtual Cloud Network → Security Lists
→ Ingress Rules 추가:

1. HTTP (포트 80)
   Source: 0.0.0.0/0
   Destination Port: 80

2. HTTPS (포트 443)
   Source: 0.0.0.0/0
   Destination Port: 443

3. FastAPI (포트 8000) - 임시
   Source: 0.0.0.0/0
   Destination Port: 8000
```

#### **2.2 Ubuntu 방화벽 설정**
```bash
# SSH 접속
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<PUBLIC_IP>

# 방화벽 설정
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

---

### **Step 3: 서버 환경 구축**

#### **3.1 시스템 업데이트**
```bash
sudo apt update && sudo apt upgrade -y
```

#### **3.2 Docker 설치**
```bash
# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose 설치
sudo apt install docker-compose -y

# 사용자 권한 추가
sudo usermod -aG docker $USER
newgrp docker

# 설치 확인
docker --version
docker-compose --version
```

#### **3.3 Git 설치**
```bash
sudo apt install git -y
```

---

### **Step 4: 프로젝트 배포**

#### **4.1 프로젝트 클론**
```bash
cd ~
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git
cd krx_hyungsoo
```

#### **4.2 환경 변수 설정**
```bash
# .env 파일 생성
cat > backend/.env << EOF
IS_LOCAL=false
DEBUG=false
DATABASE_URL=sqlite:///./data/krx_alertor.db
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
EOF
```

#### **4.3 데이터 디렉토리 생성**
```bash
mkdir -p data/output/backtest
```

#### **4.4 Docker 빌드 및 실행**
```bash
# Docker 이미지 빌드
docker-compose build

# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

### **Step 5: Nginx 설정 (선택)**

#### **5.1 Nginx 설치**
```bash
sudo apt install nginx -y
```

#### **5.2 Nginx 설정**
```bash
sudo nano /etc/nginx/sites-available/krx-alertor
```

```nginx
server {
    listen 80;
    server_name <YOUR_DOMAIN_OR_IP>;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### **5.3 Nginx 활성화**
```bash
sudo ln -s /etc/nginx/sites-available/krx-alertor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### **Step 6: SSL 인증서 (Let's Encrypt)**

#### **6.1 Certbot 설치**
```bash
sudo apt install certbot python3-certbot-nginx -y
```

#### **6.2 SSL 인증서 발급**
```bash
sudo certbot --nginx -d <YOUR_DOMAIN>
```

#### **6.3 자동 갱신 설정**
```bash
sudo certbot renew --dry-run
```

---

## 🧪 **테스트**

### **1. 헬스 체크**
```bash
curl http://<PUBLIC_IP>:8000/health
```

### **2. 대시보드 접속**
```
http://<PUBLIC_IP>:8000
```

### **3. API 문서**
```
http://<PUBLIC_IP>:8000/api/docs
```

---

## 🔧 **관리 명령어**

### **Docker 관리**
```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f

# 컨테이너 재시작
docker-compose restart

# 컨테이너 중지
docker-compose down

# 컨테이너 삭제 및 재시작
docker-compose down && docker-compose up -d
```

### **Git 업데이트**
```bash
cd ~/krx_hyungsoo
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 📊 **모니터링**

### **시스템 리소스**
```bash
# CPU, 메모리 사용량
htop

# 디스크 사용량
df -h

# Docker 리소스
docker stats
```

### **로그 확인**
```bash
# FastAPI 로그
docker-compose logs backend

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 🐛 **트러블슈팅**

### **문제 1: 포트 8000 접속 안됨**
```bash
# 방화벽 확인
sudo ufw status

# Docker 컨테이너 확인
docker-compose ps

# 포트 사용 확인
sudo netstat -tulpn | grep 8000
```

### **문제 2: Docker 빌드 실패**
```bash
# Docker 로그 확인
docker-compose logs

# 캐시 삭제 후 재빌드
docker-compose build --no-cache
```

### **문제 3: 메모리 부족**
```bash
# 메모리 확인
free -h

# Swap 메모리 추가
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 🎯 **다음 단계**

### **완료 후**
```
✅ 대시보드 접속 확인
✅ API 테스트
✅ 도메인 연결 (선택)
✅ SSL 인증서 설정 (선택)
```

### **개선 사항**
```
1. React 프론트엔드로 업그레이드
2. PostgreSQL 데이터베이스 전환
3. Redis 캐싱 추가
4. CI/CD 파이프라인 구축
```

---

**Oracle Cloud 배포 가이드 완성!** 🎉  
**Free Tier 활용!** 💰  
**Docker 컨테이너화!** 🐳  
**Nginx + SSL 지원!** 🔒
