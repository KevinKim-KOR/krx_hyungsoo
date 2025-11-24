# Oracle Cloud 텔레그램 알림 수정 가이드

## 📋 문제 진단

### 증상
```
ERROR:__main__:❌ 텔레그램 알림 전송 실패 (result=False)
INFO:__main__:  - 레짐 유지 알림: ❌ 실패
INFO:__main__:  - 매도 신호 알림: ❌ 실패
```

### 원인
1. **`TelegramNotifier.send_message()` 반환값 없음**
   - 성공/실패를 반환하지 않아 항상 `None` → `False`로 평가
   
2. **환경 변수 미로드**
   - Oracle Cloud crontab에서 `.env` 파일 로드 안됨
   - `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 없음

3. **`enabled=false` 기본값**
   - 환경 변수 없으면 `enabled=false`로 초기화
   - 메시지 전송하지 않고 로그만 출력

---

## ✅ 수정 사항

### 1. `TelegramNotifier.send_message()` 반환값 추가

**변경 전**:
```python
def send_message(self, message: str, parse_mode: str = 'Markdown'):
    if not self.enabled:
        logger.info(f"[텔레그램 알림]\n{message}")
        return  # ❌ None 반환
    
    try:
        # ... 전송 로직
        logger.info(f"텔레그램 메시지 전송 성공")
        # ❌ 반환값 없음
    except Exception as e:
        logger.error(f"텔레그램 전송 실패: {e}")
        # ❌ 반환값 없음
```

**변경 후**:
```python
def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
    if not self.enabled:
        logger.info(f"[텔레그램 알림 - 비활성화 모드]\n{message}")
        return False  # ✅ 명시적 반환
    
    try:
        # ... 전송 로직
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"텔레그램 메시지 전송 성공")
        return True  # ✅ 성공 반환
    except Exception as e:
        logger.error(f"텔레그램 전송 실패: {e}")
        return False  # ✅ 실패 반환
```

### 2. `daily_regime_check.py` 환경 변수 로드

**추가된 코드**:
```python
# 환경 변수 로드 (.env 파일)
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ 환경 변수 로드: {env_file}")
    else:
        print(f"⚠️ .env 파일 없음: {env_file}")
except ImportError:
    print("⚠️ python-dotenv 패키지 없음")
```

### 3. 환경 변수 확인 로직 개선

**추가된 로그**:
```python
logger.info(f"텔레그램 설정 확인:")
logger.info(f"  - TELEGRAM_ENABLED: {enabled}")
logger.info(f"  - BOT_TOKEN 존재: {bool(bot_token)}")
logger.info(f"  - CHAT_ID 존재: {bool(chat_id)}")

# enabled=false여도 토큰/ID 있으면 활성화
if not enabled and bot_token and chat_id:
    logger.info("  - TELEGRAM_ENABLED=false이지만 토큰/ID 있음 → 활성화")
    enabled = True
```

---

## 🚀 Oracle Cloud 적용 방법

### 1단계: SSH 접속
```bash
ssh ubuntu@your-oracle-cloud-ip
```

### 2단계: Git Pull (최신 코드)
```bash
cd /home/ubuntu/krx_hyungsoo
git pull
```

**예상 출력**:
```
Updating a7604319..dfcdc429
Fast-forward
 extensions/automation/telegram_notifier.py | 15 ++++--
 scripts/nas/daily_regime_check.py          | 54 +++++++++++++++++--
 scripts/cloud/setup_env.sh                 | 49 +++++++++++++++++
 3 files changed, 118 insertions(+), 7 deletions(-)
```

### 3단계: 환경 변수 설정
```bash
bash scripts/cloud/setup_env.sh
```

**예상 출력**:
```
================================================================================
Oracle Cloud 환경 변수 설정
================================================================================

✅ .env 파일 생성 완료: /home/ubuntu/krx_hyungsoo/.env
✅ 파일 권한 설정: 600 (소유자만 읽기/쓰기)

생성된 환경 변수:
--------------------------------------------------------------------------------
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=***MASKED***
TELEGRAM_CHAT_ID=***MASKED***
TG_TOKEN=***MASKED***
TG_CHAT_ID=***MASKED***
ENV=cloud
PYTHONPATH=/home/ubuntu/krx_hyungsoo
TZ=Asia/Seoul
--------------------------------------------------------------------------------

================================================================================
설정 완료!
================================================================================
```

### 4단계: python-dotenv 설치 (필요시)
```bash
pip3 install python-dotenv
```

### 5단계: 테스트 실행
```bash
cd /home/ubuntu/krx_hyungsoo
python3 scripts/nas/daily_regime_check.py
```

**예상 출력**:
```
✅ 환경 변수 로드: /home/ubuntu/krx_hyungsoo/.env
================================================================================
일일 레짐 감지 시작 - 2025-11-25 09:00:01
================================================================================

텔레그램 설정 확인:
  - TELEGRAM_ENABLED: True
  - BOT_TOKEN 존재: True
  - CHAT_ID 존재: True

✅ 텔레그램 알림 전송 성공

================================================================================
일일 레짐 감지 완료 - 2025-11-25 09:00:15
실행 시간: 14.23초

텔레그램 알림 전송 결과:
  - 레짐 유지 알림: ✅ 성공
  - 매도 신호 알림: ✅ 성공
================================================================================
```

### 6단계: 텔레그램 확인
- 텔레그램 앱에서 메시지 수신 확인
- 레짐 유지 알림 또는 레짐 변화 알림

---

## 📊 로그 분석

### 성공 케이스
```
INFO:__main__:텔레그램 설정 확인:
INFO:__main__:  - TELEGRAM_ENABLED: True
INFO:__main__:  - BOT_TOKEN 존재: True
INFO:__main__:  - CHAT_ID 존재: True
INFO:__main__:✅ 텔레그램 알림 전송 성공
INFO:__main__:  - 레짐 유지 알림: ✅ 성공
```

### 실패 케이스 1: 환경 변수 없음
```
⚠️ .env 파일 없음: /home/ubuntu/krx_hyungsoo/.env
INFO:__main__:텔레그램 설정 확인:
INFO:__main__:  - TELEGRAM_ENABLED: False
INFO:__main__:  - BOT_TOKEN 존재: False
INFO:__main__:  - CHAT_ID 존재: False
ERROR:__main__:❌ 텔레그램 알림 전송 실패 (result=False)
ERROR:__main__:   가능한 원인:
ERROR:__main__:   1. TELEGRAM_ENABLED=false
ERROR:__main__:   2. BOT_TOKEN 또는 CHAT_ID 없음
```

**해결**: `bash scripts/cloud/setup_env.sh` 실행

### 실패 케이스 2: 네트워크 오류
```
INFO:__main__:텔레그램 설정 확인:
INFO:__main__:  - TELEGRAM_ENABLED: True
INFO:__main__:  - BOT_TOKEN 존재: True
INFO:__main__:  - CHAT_ID 존재: True
ERROR:__main__:텔레그램 전송 실패: ConnectionError...
ERROR:__main__:❌ 텔레그램 알림 전송 실패 (예외): ConnectionError
```

**해결**: 
- 네트워크 연결 확인
- `ping api.telegram.org`
- 방화벽 설정 확인

---

## 🔍 문제 해결

### 1. .env 파일 확인
```bash
cat /home/ubuntu/krx_hyungsoo/.env
```

**예상 출력**:
```
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk
TELEGRAM_CHAT_ID=7457035904
...
```

### 2. 환경 변수 수동 확인
```bash
cd /home/ubuntu/krx_hyungsoo
source .env
echo "TELEGRAM_ENABLED: $TELEGRAM_ENABLED"
echo "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "TELEGRAM_CHAT_ID: $TELEGRAM_CHAT_ID"
```

### 3. Python에서 환경 변수 확인
```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/krx_hyungsoo/.env')
print('TELEGRAM_ENABLED:', os.getenv('TELEGRAM_ENABLED'))
print('BOT_TOKEN exists:', bool(os.getenv('TELEGRAM_BOT_TOKEN')))
print('CHAT_ID exists:', bool(os.getenv('TELEGRAM_CHAT_ID')))
"
```

### 4. 텔레그램 API 직접 테스트
```bash
curl -X POST "https://api.telegram.org/bot8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "7457035904", "text": "테스트 메시지"}'
```

---

## 📝 체크리스트

- [ ] Git pull 완료
- [ ] `bash scripts/cloud/setup_env.sh` 실행
- [ ] `.env` 파일 생성 확인
- [ ] `python3-dotenv` 설치 확인
- [ ] `python3 scripts/nas/daily_regime_check.py` 테스트
- [ ] 텔레그램 메시지 수신 확인
- [ ] 로그에서 "✅ 성공" 확인
- [ ] Crontab 정상 동작 확인 (내일 09:00)

---

## 🎯 요약

### 문제
- `TelegramNotifier.send_message()` 반환값 없음
- 환경 변수 로드 안됨
- `enabled=false` 기본값

### 해결
- ✅ 반환값 추가 (`True`/`False`)
- ✅ `.env` 파일 자동 로드
- ✅ 환경 변수 확인 로직 개선
- ✅ 상세 로그 출력

### 다음 단계
1. Oracle Cloud SSH 접속
2. `git pull`
3. `bash scripts/cloud/setup_env.sh`
4. `python3 scripts/nas/daily_regime_check.py` (테스트)
5. 텔레그램 알림 수신 확인

---

**Git Commit**: `dfcdc429` - "텔레그램 발송 실패 원인 수정"
