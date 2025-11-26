# Oracle Cloud Git Pull 충돌 해결

**문제**: 캐시 파일 충돌로 Git Pull 실패  
**날짜**: 2025-11-26  
**상태**: 해결 방법 제시

---

## 🚨 문제 상황

```bash
ubuntu@krx-alertor-vm:~/krx_hyungsoo/logs$ git pull
error: Your local changes to the following files would be overwritten by merge:
        data/cache/ohlcv/^GSPC.parquet
        data/cache/ohlcv/^IXIC.parquet
        data/cache/ohlcv/^VIX.parquet
Please commit your changes or stash them before you merge.
Aborting
```

**원인**:
- 미국 시장 지표 조회 시 캐시 파일 생성/업데이트
- 캐시 파일이 Git에 추적되고 있음
- 로컬 변경사항과 원격 변경사항 충돌

---

## ✅ 해결 방법

### 방법 1: 캐시 파일 무시 (권장)

#### 1단계: 로컬 변경사항 제거
```bash
cd ~/krx_hyungsoo

# 캐시 파일 삭제
rm -f data/cache/ohlcv/^GSPC.parquet
rm -f data/cache/ohlcv/^IXIC.parquet
rm -f data/cache/ohlcv/^VIX.parquet

# 또는 전체 캐시 삭제
rm -rf data/cache/ohlcv/*.parquet
```

#### 2단계: Git Pull
```bash
git pull
```

#### 3단계: .gitignore 확인
```bash
# .gitignore에 캐시 파일이 있는지 확인
cat .gitignore | grep parquet
```

**예상 출력**:
```
# 캐시 파일
*.parquet
data/cache/**/*.parquet
```

만약 없다면 추가 필요 (다음 섹션 참고)

---

### 방법 2: Stash 사용

#### 1단계: 변경사항 임시 저장
```bash
cd ~/krx_hyungsoo
git stash
```

#### 2단계: Git Pull
```bash
git pull
```

#### 3단계: Stash 적용 (선택)
```bash
# 캐시 파일은 다시 생성되므로 stash 적용 불필요
# git stash pop
```

---

### 방법 3: 강제 Pull (주의)

```bash
cd ~/krx_hyungsoo

# 로컬 변경사항 완전히 버리고 원격과 동기화
git fetch --all
git reset --hard origin/main
```

**주의**: 로컬의 모든 변경사항이 사라집니다!

---

## 🔧 근본 원인 해결

### .gitignore에 캐시 파일 추가

#### 1단계: .gitignore 확인
```bash
cd ~/krx_hyungsoo
cat .gitignore
```

#### 2단계: 캐시 파일 패턴 추가 (없다면)
```bash
# .gitignore 편집
nano .gitignore

# 또는
vi .gitignore
```

**추가할 내용**:
```
# 캐시 파일
*.parquet
data/cache/**/*.parquet
data/cache/ohlcv/*.parquet

# 로그 파일
logs/*.log
logs/**/*.log

# 런타임 데이터
data/runtime/**
.state/**
```

#### 3단계: Git에서 캐시 파일 제거 (추적 중지)
```bash
# 파일은 유지하되 Git 추적만 중지
git rm --cached data/cache/ohlcv/*.parquet

# Commit
git add .gitignore
git commit -m "캐시 파일 .gitignore에 추가"
git push
```

---

## 🚀 자동화 스크립트

### 1. Git Pull 전 캐시 정리 스크립트

**파일**: `scripts/cloud/git_pull_safe.sh`

```bash
#!/bin/bash
# scripts/cloud/git_pull_safe.sh
# 안전한 Git Pull (캐시 파일 충돌 방지)

set -e

PROJECT_ROOT="/home/ubuntu/krx_hyungsoo"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/git_pull.log"

echo "================================================================================" | tee -a "$LOG_FILE"
echo "안전한 Git Pull 시작 - $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"

# 1. 캐시 파일 백업 (선택)
echo "[1/4] 캐시 파일 확인..." | tee -a "$LOG_FILE"
if [ -d "data/cache/ohlcv" ]; then
    CACHE_COUNT=$(ls -1 data/cache/ohlcv/*.parquet 2>/dev/null | wc -l)
    echo "  - 캐시 파일: ${CACHE_COUNT}개" | tee -a "$LOG_FILE"
fi

# 2. Git 상태 확인
echo "[2/4] Git 상태 확인..." | tee -a "$LOG_FILE"
if git diff --quiet && git diff --cached --quiet; then
    echo "  - 변경사항 없음" | tee -a "$LOG_FILE"
else
    echo "  - 변경사항 있음 → Stash" | tee -a "$LOG_FILE"
    git stash save "Auto stash before pull - $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
fi

# 3. Git Pull
echo "[3/4] Git Pull 실행..." | tee -a "$LOG_FILE"
if git pull --ff-only 2>&1 | tee -a "$LOG_FILE"; then
    echo "  - ✅ Pull 성공" | tee -a "$LOG_FILE"
else
    echo "  - ❌ Pull 실패" | tee -a "$LOG_FILE"
    exit 1
fi

# 4. 완료
echo "[4/4] 완료" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "안전한 Git Pull 완료 - $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
```

### 2. Crontab 수정

```bash
# 기존
0 8 * * * cd /home/ubuntu/krx_hyungsoo && bash scripts/cloud/git_pull_with_log.sh

# 변경
0 8 * * * cd /home/ubuntu/krx_hyungsoo && bash scripts/cloud/git_pull_safe.sh
```

---

## 📋 즉시 해결 (복사 & 붙여넣기)

```bash
# Oracle Cloud SSH 접속 후 실행

cd ~/krx_hyungsoo

# 1. 캐시 파일 삭제
rm -f data/cache/ohlcv/*.parquet

# 2. Git Pull
git pull

# 3. 테스트 실행
python3 -m core.strategy.us_market_monitor

# 4. 로그 확인
tail -20 logs/daily_regime_check.log
```

---

## 🔍 확인 방법

### 1. Git Pull 성공 확인
```bash
cd ~/krx_hyungsoo
git log --oneline -5
```

**예상 출력**:
```
00c06672 작업 세션 요약 문서 추가 (2025-11-26)
1b9a483c Streamlit UI archive로 이동 및 문서화
b5788486 미국 시장 지표 레짐 분석 개선
...
```

### 2. 미국 시장 지표 테스트
```bash
cd ~/krx_hyungsoo
python3 -m core.strategy.us_market_monitor
```

**예상 출력**:
```
INFO:core.strategy.us_market_monitor:🇺🇸 미국 시장 레짐 판단 시작
INFO:core.strategy.us_market_monitor:📊 미국 시장 지표 계산 시작 (3개)
INFO:core.strategy.us_market_monitor:📊 nasdaq_50ma 조회 시작: ^IXIC
INFO:core.strategy.us_market_monitor:✅ nasdaq_50ma 조회 성공: 252일 데이터
...
INFO:core.strategy.us_market_monitor:✅ 미국 시장 레짐: neutral (점수: 0.13)
```

### 3. Daily Regime Check 로그 확인
```bash
tail -50 ~/krx_hyungsoo/logs/daily_regime_check.log
```

---

## 🎯 예방 조치

### 1. .gitignore 업데이트 (PC에서)

```bash
# PC에서 실행
cd "E:\AI Study\krx_alertor_modular"

# .gitignore 확인
cat .gitignore | grep parquet

# 없다면 추가
echo "" >> .gitignore
echo "# 캐시 파일" >> .gitignore
echo "*.parquet" >> .gitignore
echo "data/cache/**/*.parquet" >> .gitignore

# Commit & Push
git add .gitignore
git commit -m ".gitignore에 캐시 파일 패턴 추가"
git push
```

### 2. 캐시 파일 Git 추적 중지 (PC에서)

```bash
# PC에서 실행
cd "E:\AI Study\krx_alertor_modular"

# Git 추적 중지 (파일은 유지)
git rm --cached data/cache/ohlcv/*.parquet 2>/dev/null || true

# Commit & Push
git commit -m "캐시 파일 Git 추적 중지"
git push
```

---

## 💡 참고

### 캐시 파일이 왜 생성되나?
- 미국 시장 지표 조회 시 yfinance가 데이터를 캐시
- 다음 조회 시 빠른 응답을 위해 캐시 사용
- `.parquet` 형식으로 저장

### 캐시 파일을 Git에 포함해야 하나?
- **아니오** (권장하지 않음)
- 이유:
  - 자주 변경됨 (매일 업데이트)
  - 용량이 큼 (수 MB)
  - 환경마다 다를 수 있음
  - 필요 시 자동 생성됨

### 캐시 파일 삭제해도 되나?
- **예** (안전함)
- 다음 조회 시 자동으로 재생성됨
- 단지 첫 조회가 조금 느려질 뿐

---

**작성일**: 2025-11-26  
**작성자**: Cascade AI  
**상태**: 해결 방법 제시
