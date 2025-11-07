#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/test_telegram.py
텔레그램 연결 테스트 스크립트
"""
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 60)
print("텔레그램 연결 테스트")
print("=" * 60)
print()

# 1. 설정 파일 확인
print("1. 설정 파일 확인")
print("-" * 60)

config_file = PROJECT_ROOT / "secret" / "config.yaml"
print(f"설정 파일 경로: {config_file}")
print(f"파일 존재: {config_file.exists()}")

if config_file.exists():
    print(f"파일 크기: {config_file.stat().st_size} bytes")
    
    # 설정 내용 확인 (민감 정보 마스킹)
    import yaml
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if 'telegram' in config:
        print("✅ telegram 섹션 존재")
        
        if 'bot_token' in config['telegram']:
            token = config['telegram']['bot_token']
            masked_token = token[:10] + "..." + token[-5:] if len(token) > 15 else "***"
            print(f"✅ bot_token: {masked_token}")
        else:
            print("❌ bot_token 없음")
        
        if 'chat_id' in config['telegram']:
            print(f"✅ chat_id: {config['telegram']['chat_id']}")
        else:
            print("❌ chat_id 없음")
    else:
        print("❌ telegram 섹션 없음")
else:
    print("❌ 설정 파일 없음")
    sys.exit(1)

print()

# 2. 모듈 import 테스트
print("2. 모듈 import 테스트")
print("-" * 60)

try:
    from extensions.notification.telegram_sender import TelegramSender
    print("✅ TelegramSender import 성공")
except Exception as e:
    print(f"❌ TelegramSender import 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 3. TelegramSender 초기화
print("3. TelegramSender 초기화")
print("-" * 60)

try:
    sender = TelegramSender()
    print("✅ TelegramSender 초기화 성공")
except Exception as e:
    print(f"❌ TelegramSender 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 4. 텔레그램 메시지 전송 테스트
print("4. 텔레그램 메시지 전송 테스트")
print("-" * 60)

test_message = f"""
🧪 *텔레그램 연결 테스트*

📅 시간: {datetime.now():%Y-%m-%d %H:%M:%S}
🖥️ 호스트: NAS
📍 위치: {PROJECT_ROOT}

이 메시지가 수신되면 텔레그램 연결이 정상입니다!
"""

print("메시지 전송 중...")
print()

try:
    result = sender.send_custom(test_message.strip(), parse_mode='Markdown')
    
    if result:
        print("✅ 메시지 전송 성공!")
        print()
        print("텔레그램 앱에서 메시지를 확인하세요.")
    else:
        print("❌ 메시지 전송 실패")
        print()
        print("가능한 원인:")
        print("1. Bot Token이 잘못되었습니다")
        print("2. Chat ID가 잘못되었습니다")
        print("3. 네트워크 연결 문제")
        print("4. 텔레그램 API 제한")
except Exception as e:
    print(f"❌ 에러 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("테스트 완료")
print("=" * 60)
