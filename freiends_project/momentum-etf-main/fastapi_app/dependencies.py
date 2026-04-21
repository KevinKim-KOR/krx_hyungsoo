"""FastAPI 공통 의존성."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """내부 API 토큰 검증. 모든 내부 라우트의 Depends 로 사용한다."""
    expected_token = os.getenv("FASTAPI_INTERNAL_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FASTAPI_INTERNAL_TOKEN 환경변수가 필요합니다.",
        )

    if x_internal_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="내부 API 토큰이 올바르지 않습니다.",
        )
