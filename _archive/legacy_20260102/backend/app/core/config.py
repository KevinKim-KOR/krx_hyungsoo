#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/core/config.py
애플리케이션 설정
"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 프로젝트 정보
    PROJECT_NAME: str = "KRX Alertor"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # 환경
    IS_LOCAL: bool = os.getenv("IS_LOCAL", "true").lower() == "true"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # React 개발 서버
        "http://localhost:8000",  # FastAPI
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # 데이터베이스
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./data/krx_alertor.db"
    )
    
    # 프로젝트 루트
    PROJECT_ROOT: str = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
    )
    
    # 데이터 디렉토리
    DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
    OUTPUT_DIR: str = os.path.join(DATA_DIR, "output")
    BACKTEST_DIR: str = os.path.join(OUTPUT_DIR, "backtest")
    
    # 텔레그램
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 설정 인스턴스
settings = Settings()
