# -*- coding: utf-8 -*-
"""
infra/storage/sqlite.py
SQLite 저장소 어댑터
"""
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, Session

# Base = declarative_base()  # core.db에서 import 예정

class SQLiteStorage:
    """SQLite 저장소"""
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        echo: bool = False
    ):
        self.db_path = db_path or "krx_alertor.sqlite3"
        self.engine = sa.create_engine(f"sqlite:///{self.db_path}", echo=echo)
        self.Session = sessionmaker(bind=self.engine)
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """세션 컨텍스트 매니저"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def initialize(self) -> None:
        """DB 초기화 (테이블 생성)"""
        from core.db import Base  # 순환 참조 방지
        Base.metadata.create_all(self.engine)
    
    def insert_prices(
        self,
        df: pd.DataFrame,
        table_name: str = "price_daily"
    ) -> None:
        """가격 데이터 삽입"""
        df.to_sql(
            table_name,
            self.engine,
            if_exists="append",
            index=True
        )
    
    def query_to_df(self, query: sa.sql.Select) -> pd.DataFrame:
        """쿼리 결과를 DataFrame으로 변환"""
        with self.session() as session:
            result = session.execute(query)
            return pd.DataFrame(result.fetchall(), columns=result.keys())