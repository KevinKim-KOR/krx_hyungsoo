# -*- coding: utf-8 -*-
"""
sector_autotag.py
- Security.name (ETF명) 기반으로 자동 섹터 분류
- 규칙: keywords -> sector
- 실행 시 sectors_map.csv 자동 업데이트
"""

from __future__ import annotations
import re
import pandas as pd
from sqlalchemy import select
from core.db import SessionLocal, Security

# 키워드 → 섹터 매핑 규칙
SECTOR_RULES = {
    # 방산/우주/국방
    r"(방산|국방|우주)": "방산우주",
    # 원자력/SMR
    r"(원자력|SMR)": "원자력",
    # AI/인공지능
    r"(AI|인공지능)": "AI",
    # 반도체
    r"(반도체|칩)": "반도체",
    # 2차전지/배터리
    r"(2차|배터리|전지)": "2차전지",
    # 신재생/태양광/풍력
    r"(태양광|풍력|재생에너지|신재생|그린)": "신재생",
    # 헬스케어/바이오
    r"(바이오|헬스케어|제약)": "헬스케어",
    # 중국/차이나
    r"(차이나|중국)": "중국",
    # 미국/글로벌
    r"(미국|글로벌|World|글로)": "글로벌",
    # ETF 이름에 기타
    r"(리츠|부동산)": "리츠부동산",
    r"(금속|구리|철강|자원|원자재)": "원자재",
}

DEFAULT_SECTOR = "기타"


def autotag_sectors(output_csv: str = "sectors_map.csv"):
    with SessionLocal() as s:
        secs = s.execute(select(Security)).scalars().all()

    rows = []
    for sec in secs:
        code = str(sec.code)
        name = str(sec.name)
        sector = None
        for pat, secname in SECTOR_RULES.items():
            if re.search(pat, name, flags=re.IGNORECASE):
                sector = secname
                break
        if not sector:
            sector = DEFAULT_SECTOR
        rows.append({"code": code, "sector": sector, "name": name})

    df = pd.DataFrame(rows).drop_duplicates("code").sort_values("sector")
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[완료] {output_csv} 생성 (총 {len(df)} 종목)")
    print(df.head(20))


if __name__ == "__main__":
    autotag_sectors()
