# NAS 환경 구축 가이드 (DS220j)

## 🎯 목표

PC에서 개발한 전략을 NAS에서 자동 실행하여 24/7 운영

---

## 📋 전제 조건

- Synology DS220j
- DSM 7.x 이상
- SSH 접근 가능
- 최소 1GB 여유 공간

---

## 🔧 옵션 1: Docker 사용 (권장)

### 1-1. Docker 설치

```bash
# DSM 패키지 센터에서 "Docker" 검색 후 설치
# 또는 SSH에서:
sudo synopkg install Docker
```

### 1-2. Dockerfile 작성

프로젝트 루트에 `Dockerfile` 생성:

```dockerfile
FROM python:3.10-slim

# 작업 디렉토리
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# 환경변수
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul

# 헬스체크
HEALTHCHECK --interval=5m --timeout=3s \
  CMD python -c "import sys; sys.exit(0)"

# 기본 명령어
CMD ["python", "app.py", "scanner"]
```

### 1-3. Docker 이미지 빌드

```bash
# NAS에서
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
docker build -t krx-alertor:latest .
```

### 1-4. Docker 컨테이너 실행

```bash
# 일회성 실행
docker run --rm \
  -v /volume2/homes/Hyungsoo/krx/krx_alertor_modular:/app \
  -v /volume2/homes/Hyungsoo/krx/krx_alertor_modular/data:/app/data \
  krx-alertor:latest python app.py scanner

# 백그라운드 실행
docker run -d \
  --name krx-scanner \
  --restart unless-stopped \
  -v /volume2/homes/Hyungsoo/krx/krx_alertor_modular:/app \
  krx-alertor:latest
```

---

## 🔧 옵션 2: Miniconda 설치

### 2-1. Miniconda 다운로드 & 설치

```bash
# NAS SSH 접속 후
cd ~
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 설치 경로: /volume2/homes/Hyungsoo/miniconda3
# 초기화: yes
```

### 2-2. 환경 생성

```bash
# 새 터미널 또는 재접속
conda create -n krx python=3.10 -y
conda activate krx

# 의존성 설치
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
pip install -r requirements.txt
```

### 2-3. 환경 활성화 스크립트

`config/env.nas.sh` 수정:

```bash
#!/bin/bash
# Conda 환경 활성화
source ~/miniconda3/etc/profile.d/conda.sh
conda activate krx

export PYTHONPATH="/volume2/homes/Hyungsoo/krx/krx_alertor_modular:$PYTHONPATH"
export TZ="Asia/Seoul"
```

---

## 🔧 옵션 3: 클라우드 이전 (대안)

### 3-1. Google Cloud Run (권장)

**장점**:
- 무료 티어 (월 200만 요청)
- 자동 스케일링
- HTTPS 기본 제공

**단점**:
- 상태 저장 어려움 (DB는 별도 필요)

### 3-2. AWS Lambda

**장점**:
- 무료 티어 (월 100만 요청)
- EventBridge로 스케줄링

**단점**:
- 15분 실행 제한
- 복잡한 설정

### 3-3. Render.com

**장점**:
- 무료 티어 (750시간/월)
- Git 연동 자동 배포
- Cron Job 지원

**단점**:
- 비활성 시 슬립 (웜업 필요)

### 3-4. Railway.app

**장점**:
- 무료 티어 ($5 크레딧/월)
- 간단한 배포
- 환경변수 관리 쉬움

**단점**:
- 크레딧 소진 시 중단

---

## 📅 Cron 스케줄 설정

### NAS Cron 등록

```bash
# NAS에서
crontab -e

# 추가할 내용:
# 매일 16:00 - 일일 사이클 실행
0 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_daily_cycle.sh

# 매일 09:30 - 장 시작 전 스캐너
30 9 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_scanner.sh

# 매일 15:40 - 장 마감 전 스캐너
40 15 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/batch/run_scanner.sh
```

### Cron 로그 확인

```bash
# NAS에서
tail -f /var/log/cron.log
# 또는
tail -f /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/daily_cycle_*.log
```

---

## 🧪 테스트

### 수동 실행 테스트

```bash
# NAS에서
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# Docker 사용 시
docker run --rm -v $(pwd):/app krx-alertor:latest python app.py scanner

# Conda 사용 시
source config/env.nas.sh
python app.py scanner
```

### Git 자동 동기화 테스트

```bash
# NAS에서
bash scripts/linux/batch/update_from_git.sh
```

---

## 📊 모니터링

### 로그 확인

```bash
# 최근 로그
tail -50 logs/daily_cycle_*.log

# 에러만 필터
grep -i "error\|fail" logs/daily_cycle_*.log
```

### Telegram 알림 설정

`config.yaml`:

```yaml
notifications:
  channel: telegram
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
```

---

## 🚨 트러블슈팅

### 문제 1: pip 없음
→ **해결**: Docker 또는 Miniconda 사용

### 문제 2: 메모리 부족
→ **해결**: 스왑 파일 생성 또는 클라우드 이전

### 문제 3: Cron 실행 안됨
→ **해결**: 절대 경로 사용, 실행 권한 확인

```bash
chmod +x scripts/linux/batch/*.sh
```

---

## 💡 권장 사항

**DS220j 사양 고려**:
- CPU: Realtek RTD1296 (약함)
- RAM: 512MB~2GB (제한적)

**권장 방식**:
1. **단기**: Miniconda 설치 (가장 빠름)
2. **중기**: Docker 사용 (격리 환경)
3. **장기**: Render.com 이전 (무료 + 안정적)

---

## 📝 다음 단계

1. ✅ 환경 구축 (Docker 또는 Miniconda)
2. ✅ 의존성 설치 확인
3. ✅ 수동 실행 테스트
4. ✅ Cron 등록
5. ✅ Telegram 알림 테스트
6. ✅ 1주일 모니터링

---

**작성자**: Hyungsoo Kim  
**일시**: 2025-10-22  
**환경**: Synology DS220j
