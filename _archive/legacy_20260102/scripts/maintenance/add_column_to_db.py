# -*- coding: utf-8 -*-
"""
DB 마이그레이션 스크립트
Holdings 테이블에 current_price 컬럼 추가
"""
import sqlite3
from pathlib import Path

# 프로젝트 루트 경로 계산
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "krx_alertor.db"

def migrate():
    print(f"Checking database at: {DB_PATH}")
    if not DB_PATH.exists():
        print("Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 컬럼 존재 여부 확인
    cursor.execute("PRAGMA table_info(holdings)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'current_price' in columns:
        print("Column 'current_price' already exists.")
    else:
        try:
            print("Adding 'current_price' column...")
            cursor.execute("ALTER TABLE holdings ADD COLUMN current_price FLOAT")
            conn.commit()
            print("Successfully added 'current_price' column.")
        except Exception as e:
            print(f"Error adding column: {e}")
            conn.rollback()
    
    conn.close()

if __name__ == "__main__":
    migrate()
