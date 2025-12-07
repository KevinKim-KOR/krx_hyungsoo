from sqlalchemy import create_engine, String, Integer, Float, Date, DateTime
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func
from typing import Optional
from pathlib import Path
import os

# DB URL 설정
project_root = Path(__file__).parent.parent
DB_PATH = project_root / "data" / "krx_alertor.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DB_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class Security(Base):
    __tablename__ = "securities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(8))   # KS/KQ 등
    type: Mapped[str] = mapped_column(String(16))    # ETF/STOCK 등
    yahoo_ticker: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

class PriceDaily(Base):
    __tablename__ = "prices_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    date: Mapped[Date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

class PriceRealtime(Base):
    __tablename__ = "prices_realtime"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    ts: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    price: Mapped[float] = mapped_column(Float)

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    weight: Mapped[float] = mapped_column(Float)  # 0~1 비중

class Holdings(Base):
    """보유 종목 테이블"""
    __tablename__ = "holdings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)  # 보유 수량
    avg_price: Mapped[float] = mapped_column(Float)  # 평균 매수가
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 현재가 (최근 업데이트 기준)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

def init_db():
    """데이터베이스 초기화"""
    Base.metadata.create_all(bind=engine)

def get_db_connection():
    """DB 연결 반환 (레거시 호환)"""
    import sqlite3
    return sqlite3.connect(str(DB_PATH))
