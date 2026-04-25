"""환경변수 표준 진입점 — POC 전체에서 .env + os.environ 처리의 단일 진입점.

설계 원칙 (DEV_RULES 9철칙 #7 + #9 준수):
- import 시점에 .env 자동 로드 (python-dotenv).
- 필수 환경변수는 require_env(key) — 누락 시 명확한 EnvConfigError raise.
- 선택 환경변수는 optional_env(key, default=None) — 누락 시 default 반환.
- 암묵 fallback 금지: 선택값이라도 default 는 명시되어야 한다.
- OS 환경변수가 .env 보다 우선 (셸 세션에서 export 된 값이 이긴다).

향후 새 환경변수 도입 시 동일 패턴 사용:
    from app.config import require_env, optional_env
    api_key = require_env("SOMETHING_API_KEY")
    timeout = int(optional_env("SOMETHING_TIMEOUT", default="10"))

이 모듈은 import 만 해도 .env 가 로드되므로, 환경변수에 의존하는 어떤
모듈보다 먼저 import 되어야 한다 (보통 app/api.py 상단).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 프로젝트 루트의 .env 를 로드. override=False 로 OS 환경변수 우선.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)


class EnvConfigError(Exception):
    """필수 환경변수 누락 또는 빈 값 — fail-loud 예외."""


def require_env(key: str) -> str:
    """필수 환경변수 조회. 누락/빈 값이면 EnvConfigError.

    호출 예:
        token = require_env("TELEGRAM_BOT_TOKEN")
    """
    value = os.environ.get(key)
    if not value:
        raise EnvConfigError(
            f"필수 환경변수 {key!r} 가 설정되지 않았습니다. "
            f".env 또는 셸 환경변수에 채워주세요. "
            f"견본: {_ENV_PATH.parent / '.env.example'}"
        )
    return value


def optional_env(key: str, default: Optional[str]) -> Optional[str]:
    """선택 환경변수 조회. 누락 시 default 반환.

    default 는 명시 인자 — 호출자가 의도를 드러내야 한다 (암묵 fallback 금지).
    """
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value
