# web/universe_builder.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
[U-STEP] 자동 유니버스 빌더
- config/data_sources.yaml의 universe_builder 섹션을 읽어
  여러 소스(정적 txt, CSV, 캐시 파일)를 합치고 정규화/중복제거/블랙리스트 적용 후
  최종 유니버스 파일(yf_universe.txt 등)로 떨어뜨립니다.
- 네트워크 호출 없음. 캐시/파일만 사용. 없는 소스는 [SKIP].
- 로깅: logs/universe_builder_YYYY-MM-DD.log
- 인자:
    --config  : 기본 config/data_sources.yaml
    --dry-run : 출력 파일에 쓰지 않고 요약만 로그
    --verbose : 소스별 상세 로그
"""

import argparse
import datetime as dt
import logging
import os
import sys
from typing import List, Set, Dict, Any

try:
    import yaml
except ImportError:
    print("[ERR] PyYAML이 필요합니다. venv에서 `pip install pyyaml` 후 재시도하세요.", file=sys.stderr)
    sys.exit(2)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGDIR = os.path.join(ROOT, "logs")
os.makedirs(LOGDIR, exist_ok=True)

def _setup_logger(verbose: bool = False) -> logging.Logger:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    logfile = os.path.join(LOGDIR, f"universe_builder_{today}.log")
    logger = logging.getLogger("universe_builder")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _read_lines_file(path: str, logger: logging.Logger) -> List[str]:
    symbols: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                symbols.append(line)
        logger.info(f"[READ] static list loaded: {path} (+{len(symbols)})")
    except FileNotFoundError:
        logger.info(f"[SKIP] static list missing: {path}")
    return symbols

def _read_csv_symbols(cfg: Dict[str, Any], logger: logging.Logger) -> List[str]:
    import csv
    path = cfg.get("path")
    col = cfg.get("symbol_col", "symbol")
    filters = cfg.get("filters", {})
    include_if = filters.get("include_if", [])
    exclude_if = filters.get("exclude_if", [])

    out: List[str] = []
    if not path or not os.path.exists(path):
        logger.info(f"[SKIP] csv missing: {path}")
        return out

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = (row.get(col) or "").strip()
                if not sym:
                    continue

                # include_if
                ok_inc = True
                for rule in include_if:
                    c = rule.get("column")
                    val = rule.get("equals")
                    if c not in row or str(row[c]).strip() != str(val):
                        ok_inc = False
                        break
                if not ok_inc:
                    continue

                # exclude_if
                excluded = False
                for rule in exclude_if:
                    c = rule.get("column")
                    val = rule.get("equals")
                    if c in row and str(row[c]).strip() == str(val):
                        excluded = True
                        break
                if excluded:
                    continue

                out.append(sym)
        logger.info(f"[READ] csv loaded: {path} (+{len(out)})")
    except Exception as e:
        logger.error(f"[ERR] csv read failed: {path} ({e})")
    return out

def _apply_rules(symbols: List[str], rules: Dict[str, Any], logger: logging.Logger) -> List[str]:
    s = symbols[:]

    if rules.get("uppercase", True):
        s = [x.upper() for x in s]

    for pref in rules.get("strip_prefixes", []):
        s = [x[len(pref):] if x.startswith(pref) else x for x in s]

    # 블랙리스트
    bl_path = rules.get("blacklist")
    blacklist: Set[str] = set()
    if bl_path and os.path.exists(bl_path):
        with open(bl_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                blacklist.add(line.upper())
        before = len(s)
        s = [x for x in s if x.upper() not in blacklist]
        logger.info(f"[FILTER] blacklist {bl_path} removed {before - len(s)}")

    if rules.get("dedup", True):
        before = len(s)
        s = sorted(set(s))
        logger.info(f"[FILTER] dedup {before} -> {len(s)}")

    return s

def _collect_from_queries(queries: List[Dict[str, Any]], logger: logging.Logger) -> List[str]:
    out: List[str] = []
    for q in (queries or []):
        cache_file = q.get("cache_file")
        if cache_file and os.path.exists(cache_file):
            out += _read_lines_file(cache_file, logger)
        else:
            desc = f"{q.get('provider')}:{q.get('market') or q.get('indices')}"
            logger.info(f"[SKIP] query(no cache): {desc}")
    return out

def build_universe(cfg_path: str, dry_run: bool, verbose: bool, logger: logging.Logger) -> int:
    logger.info("[RUN] universe builder start")
    cfg = _read_yaml(cfg_path)
    ub = (cfg or {}).get("universe_builder") or {}
    if not ub:
        logger.error("[ERR] universe_builder section missing in config")
        return 2

    outputs = ub.get("output", {})
    out_yf = outputs.get("yfinance", "data/universe/yf_universe.txt")
    out_krx = outputs.get("krx", "data/universe/krx_universe.txt")
    os.makedirs(os.path.dirname(os.path.join(ROOT, out_yf)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(ROOT, out_krx)), exist_ok=True)

    all_symbols: List[str] = []

    # static lists
    for path in ub.get("static_lists", []):
        all_symbols += _read_lines_file(os.path.join(ROOT, path), logger)

    # csv sources
    for c in ub.get("csv_sources", []):
        # 상대경로 보정
        c = dict(c)
        if "path" in c:
            c["path"] = os.path.join(ROOT, c["path"])
        all_symbols += _read_csv_symbols(c, logger)

    # query (cache only)
    all_symbols += _collect_from_queries(ub.get("queries", []), logger)

    logger.info(f"[INFO] collected raw symbols: {len(all_symbols)}")

    # rules
    symbols_final = _apply_rules(all_symbols, ub.get("rules", {}), logger)
    logger.info(f"[INFO] final symbol count: {len(symbols_final)}")

    if dry_run:
        logger.info("[DONE] dry-run: no files written")
        return 0

    # 현재는 yfinance 출력만 필수 사용. krx 출력은 동일본 생성(분기 필요 시 후속분기).
    for target in [out_yf, out_krx]:
        abs_path = os.path.join(ROOT, target)
        with open(abs_path, "w", encoding="utf-8") as f:
            for s in symbols_final:
                f.write(s + "\n")
        logger.info(f"[WRITE] {target} ({len(symbols_final)})")

    logger.info("[DONE] universe builder success")
    return 0

def main():
    parser = argparse.ArgumentParser(description="U-STEP universe builder")
    parser.add_argument("--config", default="config/data_sources.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logger = _setup_logger(verbose=args.verbose)
    # 작업 루트 이동
    os.chdir(ROOT)

    rc = build_universe(args.config, args.dry_run, args.verbose, logger)
    sys.exit(rc)

if __name__ == "__main__":
    main()
