#!/usr/bin/env python3
from pathlib import Path
from typing import List
import yaml

ROOT = Path(__file__).resolve().parents[2]

def load_universe() -> List[str]:
    """config/data_sources.yaml 의 universe.etfs 를 읽어 리스트로 반환.
       없거나 잘못되면 합리적 디폴트로 폴백."""
    cfg = ROOT / "config" / "data_sources.yaml"
    if cfg.exists():
        try:
            y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            etfs = (((y.get("universe") or {}).get("etfs")) or [])
            etfs = [str(x).strip() for x in etfs if str(x).strip()]
            if etfs:
                # 중복 제거+안정 정렬
                return sorted(dict.fromkeys(etfs))
        except Exception:
            pass
    # 폴백(현재 캐시에 존재하던 기본 셋)
    return ["069500.KS","133690.KS","091160.KS","305720.KS","373220.KS","005930.KS","000660.KS"]
