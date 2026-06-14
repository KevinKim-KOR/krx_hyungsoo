"""ETF NAV / Discount Source Diagnosis — POC2 1차 (2026-06-06).

진단 목적 (지시문 §3):
- ETF NAV / 시장가격 / 괴리율을 안정적으로 가져올 수 있는 source 후보를 실측
- source별 판정: adopt_candidate / hold_auth_required / hold_unstable / unusable
- 운영 fetcher 교체 X, source integration X — 본 STEP 은 진단만.

원칙 (지시문 §4.4):
- 외부 호출은 진단 목적의 최소 호출로 제한.
- 전체 universe 수집 금지.
- timeout 명시. 실패 격리.
- raw response 전문 저장 금지 — 필요한 field summary 만 저장.

진단 대상 source (지시문 §4.1 — 4 범주):
1. pykrx ETF NAV/괴리율 (get_etf_ohlcv_by_date / get_etf_price_deviation)
2. FinanceDataReader (FDR) DataReader(ticker) — 시장가격 추출 가능 여부
3. Naver Mobile ETF detail API — m.stock.naver.com/api/stock/<ticker>/integration
   계열에서 NAV 키 존재 여부
4. Naver Mobile ETF dedicated detail API — m.stock.naver.com/api/etf/<ticker>/...
   (이미 component 가 운영중 — NAV detail endpoint 추가 탐색)

진단 결과:
- state/market/nav_discount_source_diagnosis_latest.json
- docs/handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md

실행: ./.venv/Scripts/python.exe scripts/diagnose_nav_discount_source.py
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Windows 인코딩 안전화 (pykrx 가 cp949 환경에서 KeyError 발생 회피).
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 명시 socket-level timeout (지시문 §4.4 "timeout 명시").
# pykrx / FDR 은 내부적으로 urllib / requests 를 사용 — socket default timeout 으로
# 강제 timeout 보장 (Naver 호출은 별도 timeout 인자도 명시).
GLOBAL_SOCKET_TIMEOUT_SEC = 15
socket.setdefaulttimeout(GLOBAL_SOCKET_TIMEOUT_SEC)

# 진단 대상 sample ticker (지시문 §4.2) — 선택 사유는 리포트에 기록.
SAMPLE_TICKERS = [
    {
        "ticker": "069500",
        "name": "KODEX 200",
        "category": "domestic_representative",
        "reason": "국내 대표 ETF — 가장 거래량이 많고 NAV 공시가 안정적이라 추정",
    },
    {
        "ticker": "360750",
        "name": "TIGER 미국S&P500",
        "category": "overseas",
        "reason": "해외형 ETF — NAV 산정 / 기준시각이 국내와 다를 수 있음",
    },
    {
        "ticker": "411420",
        "name": "Market Discovery 후보 (테마/해외형)",
        "category": "market_discovery_candidate",
        "reason": "직전 STEP Constituents Source Diagnosis 와 동일 ticker 재사용",
    },
    {
        "ticker": "0015B0",
        "name": "KoAct 미국나스닥성장기업액티브",
        "category": "user_holding",
        "reason": "사용자 보유 ETF — 6자리 신형 ticker (액티브)",
    },
]

# pykrx 진단 날짜 (지시문 §4.2 + ASSUMPTIONS 최근 운영 기준).
# 가장 최근 영업일 후보 위주 — pykrx ETF NAV 데이터 적재 시점 불명확하므로 여러 시점 시도.
PYKRX_TEST_DATES = [
    "20260605",
    "20260604",
    "20260603",
    "20260530",
    "20260529",
    "20260528",
    "20260417",
    "20260331",
]

NAVER_TIMEOUT_SEC = 8
HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

ARTIFACT_JSON_PATH = Path("state/market/nav_discount_source_diagnosis_latest.json")
ARTIFACT_MD_PATH = Path("docs/handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Source #1: pykrx get_etf_ohlcv_by_date ─────────────────────────────


def diagnose_pykrx_ohlcv(ticker: str, yyyymmdd: str) -> dict:
    """pykrx get_etf_ohlcv_by_date 1회 호출 결과 dict.

    OHLCV 응답에 'NAV' 컬럼이 있는지가 핵심.
    """
    try:
        from pykrx import stock
    except Exception as e:  # noqa: BLE001
        return {
            "status": "import_failed",
            "error_type": f"{type(e).__name__}",
            "error": str(e),
        }
    try:
        df = stock.get_etf_ohlcv_by_date(yyyymmdd, yyyymmdd, ticker)
    except Exception as e:  # noqa: BLE001
        return {
            "status": "call_failed",
            "error_type": f"{type(e).__name__}",
            "error": str(e)[:200],
        }
    if df is None or df.empty:
        return {
            "status": "empty",
            "row_count": 0,
            "columns": [],
        }
    cols = [str(c) for c in df.columns]
    row = df.iloc[0].to_dict()
    nav_value = None
    market_price = None
    for cand in ("NAV", "기준가격", "기준가"):
        if cand in row:
            nav_value = float(row[cand]) if row[cand] is not None else None
            break
    for cand in ("종가", "Close", "close"):
        if cand in row:
            market_price = float(row[cand]) if row[cand] is not None else None
            break
    return {
        "status": "ok",
        "row_count": int(df.shape[0]),
        "columns": cols,
        "asof": yyyymmdd,
        "has_nav": nav_value is not None,
        "has_market_price": market_price is not None,
        "nav_sample": nav_value,
        "market_price_sample": market_price,
    }


# ─── Source #2: pykrx get_etf_price_deviation ──────────────────────────


def diagnose_pykrx_deviation(ticker: str, yyyymmdd: str) -> dict:
    """pykrx get_etf_price_deviation — 괴리율 직접 제공 여부 확인."""
    try:
        from pykrx import stock
    except Exception as e:  # noqa: BLE001
        return {
            "status": "import_failed",
            "error_type": f"{type(e).__name__}",
            "error": str(e),
        }
    try:
        df = stock.get_etf_price_deviation(yyyymmdd, yyyymmdd, ticker)
    except Exception as e:  # noqa: BLE001
        return {
            "status": "call_failed",
            "error_type": f"{type(e).__name__}",
            "error": str(e)[:200],
        }
    if df is None or df.empty:
        return {"status": "empty", "row_count": 0, "columns": []}
    cols = [str(c) for c in df.columns]
    row = df.iloc[0].to_dict()
    deviation = None
    for cand in ("괴리율", "deviation", "추적오차"):
        if cand in row:
            deviation = float(row[cand]) if row[cand] is not None else None
            break
    return {
        "status": "ok",
        "row_count": int(df.shape[0]),
        "columns": cols,
        "asof": yyyymmdd,
        "has_discount_rate": deviation is not None,
        "discount_rate_sample": deviation,
    }


# ─── Source #3: FDR DataReader(ticker) ──────────────────────────────────


def diagnose_fdr(ticker: str) -> dict:
    """FinanceDataReader — 시장 종가 제공 여부 (NAV 직접 제공 X 추정).

    FDR 은 KRX 시장 종가만 제공 — NAV 직접 제공 안 함. 그러나 시장가격은
    안정적이라 NAV source 와 결합 시 괴리율 계산 후보 가능.
    """
    try:
        import FinanceDataReader as fdr
    except Exception as e:  # noqa: BLE001
        return {
            "status": "import_failed",
            "error_type": f"{type(e).__name__}",
            "error": str(e),
        }
    try:
        # 최근 7거래일 시도.
        df = fdr.DataReader(ticker, "2026-05-25", "2026-06-06")
    except Exception as e:  # noqa: BLE001
        return {
            "status": "call_failed",
            "error_type": f"{type(e).__name__}",
            "error": str(e)[:200],
        }
    if df is None or df.empty:
        return {"status": "empty", "row_count": 0, "columns": []}
    cols = [str(c) for c in df.columns]
    last_row = df.iloc[-1].to_dict()
    market_price = None
    for cand in ("Close", "종가"):
        if cand in last_row:
            market_price = float(last_row[cand]) if last_row[cand] is not None else None
            break
    return {
        "status": "ok",
        "row_count": int(df.shape[0]),
        "columns": cols,
        "asof": str(df.index[-1].date()) if hasattr(df.index[-1], "date") else None,
        "has_nav": False,
        "has_market_price": market_price is not None,
        "has_discount_rate": False,
        "market_price_sample": market_price,
    }


# ─── Source #4: Naver Mobile stock integration API ──────────────────────


def _http_get_json(
    url: str, timeout: int
) -> tuple[Optional[int], Optional[dict], Optional[str]]:
    """단순 GET → (http_status, parsed_json, error)."""
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return (resp.status, json.loads(body), None)
            except Exception:  # noqa: BLE001
                return (resp.status, None, "json_decode_failed")
    except urllib.error.HTTPError as e:
        return (e.code, None, f"HTTPError: {e}")
    except urllib.error.URLError as e:
        return (None, None, f"URLError: {e}")
    except Exception as e:  # noqa: BLE001
        return (None, None, f"{type(e).__name__}: {e}")


def diagnose_naver_integration(ticker: str) -> dict:
    """Naver Mobile stock 통합 detail API — NAV/괴리율 키 존재 여부 탐색.

    URL: https://m.stock.naver.com/api/stock/<ticker>/integration
    공식 API 가 아니므로 차단 / schema 변경 위험 있다 (지시문 §5.3 hold_unstable 후보).
    """
    url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
    http_status, payload, err = _http_get_json(url, NAVER_TIMEOUT_SEC)
    if payload is None:
        return {
            "status": "call_failed",
            "http_status": http_status,
            "error_type": err,
        }
    # NAV / 괴리율 관련 키 후보 탐색.
    # 2026-06-07 FIX (검증자 A-2): 실측 응답에서 deviationRate (괴리율 직접) +
    # bizdate (asof) 키 추가 발견 → 후보 확장.
    keys = list(payload.keys())[:30]
    found_keys: dict[str, Any] = {}
    nav_keys = ("nav", "NAV", "etfNav", "navValue", "기준가", "basePrice", "totalNav")
    deviation_keys = (
        "deviation",
        "괴리율",
        "discount",
        "discountRate",
        "deviationRate",
        "deviationSign",
    )
    price_keys = ("closePrice", "currentPrice", "marketPrice", "종가")
    asof_keys = (
        "localTradedAt",
        "tradeDate",
        "asof",
        "baseDate",
        "bizdate",
        "stdDate",
    )

    def _scan(obj, path="$"):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in nav_keys:
                    found_keys.setdefault("nav", []).append(
                        {"path": f"{path}.{k}", "value": v}
                    )
                if k in deviation_keys:
                    found_keys.setdefault("deviation", []).append(
                        {"path": f"{path}.{k}", "value": v}
                    )
                if k in price_keys:
                    found_keys.setdefault("price", []).append(
                        {"path": f"{path}.{k}", "value": v}
                    )
                if k in asof_keys:
                    found_keys.setdefault("asof", []).append(
                        {"path": f"{path}.{k}", "value": v}
                    )
                _scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:3]):
                _scan(v, f"{path}[{i}]")

    _scan(payload)

    return {
        "status": "ok",
        "http_status": http_status,
        "top_level_keys": keys,
        "has_nav": "nav" in found_keys,
        "has_market_price": "price" in found_keys,
        "has_discount_rate": "deviation" in found_keys,
        "has_asof": "asof" in found_keys,
        "found_keys_summary": {k: v[:2] for k, v in found_keys.items()},
    }


# ─── Source #5: Naver ETF dedicated endpoint search ────────────────────


def diagnose_naver_etf_detail(ticker: str) -> dict:
    """Naver Mobile ETF dedicated endpoint 추정 탐색.

    component endpoint 는 이미 운영중이지만 NAV 전용 endpoint 후보 (basicInfo /
    overview 등) 가 있는지 확인.
    """
    candidates = [
        f"https://m.stock.naver.com/api/etf/{ticker}/basicInfo",
        f"https://m.stock.naver.com/api/etf/{ticker}/overview",
        f"https://m.stock.naver.com/api/etf/{ticker}/component",
    ]
    results = []
    for url in candidates:
        http_status, payload, err = _http_get_json(url, NAVER_TIMEOUT_SEC)
        item: dict[str, Any] = {
            "url_suffix": url.split(f"/{ticker}/")[-1],
            "http_status": http_status,
        }
        if payload is None:
            item["status"] = "call_failed"
            item["error_type"] = err
        else:
            keys = list(payload.keys())[:20] if isinstance(payload, dict) else []
            item["status"] = "ok"
            item["top_level_keys"] = keys
            # 빠른 NAV 키 탐색.
            text = json.dumps(payload)[:5000].lower()
            item["mentions_nav"] = "nav" in text or "기준가" in text
            item["mentions_deviation"] = (
                "deviation" in text or "괴리" in text or "discount" in text
            )
        results.append(item)
    return {"status": "ok", "candidates": results}


# ─── Aggregate + judgment ────────────────────────────────────────────────
# POC2 Cleanup (2026-06-14) — judge_* / _record_from / _build_flat_records /
# render_markdown 은 scripts/diagnose_nav_discount_source_helpers.py 로 분리
# (KS-10 trigger 해소). 기존 호출자 호환 위해 본 파일에서 re-export.
from scripts.diagnose_nav_discount_source_helpers import (  # noqa: E402, F401
    _build_flat_records,
    _record_from,
    judge_fdr,
    judge_naver_etf_detail,
    judge_naver_integration,
    judge_pykrx_deviation,
    judge_pykrx_ohlcv,
    render_markdown,
)


def _print(*args):
    """stdout 안전 출력 (cp949 환경 대비)."""
    msg = " ".join(str(a) for a in args)
    try:
        print(msg)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))


# AC-2 최소 필드 계약: source_id / ticker / http_status (or call_status) /
# has_nav / has_market_price / has_discount_rate / has_asof / error_type / judgment.


def run_diagnosis() -> dict:
    started_at = _utcnow_iso()
    _print(f"[START] NAV Discount Source Diagnosis @ {started_at}")

    # ─── Source #1: pykrx ohlcv (NAV + 시장가격) ─────────────────
    _print("\n=== Source #1: pykrx get_etf_ohlcv_by_date ===")
    pykrx_ohlcv_results: dict = {}
    found_date = None
    for sample in SAMPLE_TICKERS:
        ticker = sample["ticker"]
        pykrx_ohlcv_results[ticker] = {}
        # 첫 ticker 에서 사용 가능한 날짜를 찾으면, 이후 ticker 는 그 날짜만 호출 (외부 호출 최소화).
        dates_to_try = [found_date] if found_date else PYKRX_TEST_DATES
        for d in dates_to_try:
            if d is None:
                continue
            res = diagnose_pykrx_ohlcv(ticker, d)
            pykrx_ohlcv_results[ticker][d] = res
            _print(
                f"  pykrx_ohlcv {ticker} {d} -> "
                f"status={res.get('status')} has_nav={res.get('has_nav')} "
                f"has_price={res.get('has_market_price')}"
            )
            if res.get("status") == "ok" and found_date is None:
                found_date = d
                break
            if found_date and res.get("status") == "ok":
                break

    pykrx_ohlcv_judgment = judge_pykrx_ohlcv(pykrx_ohlcv_results)

    # ─── Source #2: pykrx price_deviation (괴리율 직접) ──────────
    _print("\n=== Source #2: pykrx get_etf_price_deviation ===")
    pykrx_dev_results: dict = {}
    for sample in SAMPLE_TICKERS:
        ticker = sample["ticker"]
        pykrx_dev_results[ticker] = {}
        dates_to_try = [found_date] if found_date else PYKRX_TEST_DATES[:3]
        for d in dates_to_try:
            if d is None:
                continue
            res = diagnose_pykrx_deviation(ticker, d)
            pykrx_dev_results[ticker][d] = res
            _print(
                f"  pykrx_dev {ticker} {d} -> "
                f"status={res.get('status')} "
                f"has_discount_rate={res.get('has_discount_rate')}"
            )
            if res.get("status") == "ok":
                break

    pykrx_dev_judgment = judge_pykrx_deviation(pykrx_dev_results)

    # ─── Source #3: FDR DataReader (시장가격 단독) ──────────────
    _print("\n=== Source #3: FinanceDataReader DataReader(ticker) ===")
    fdr_results: dict = {}
    for sample in SAMPLE_TICKERS:
        ticker = sample["ticker"]
        res = diagnose_fdr(ticker)
        fdr_results[ticker] = res
        _print(
            f"  fdr {ticker} -> status={res.get('status')} "
            f"has_price={res.get('has_market_price')}"
        )

    fdr_judgment = judge_fdr(fdr_results)

    # ─── Source #4: Naver Mobile stock integration ──────────────
    _print("\n=== Source #4: Naver Mobile stock integration API ===")
    naver_int_results: dict = {}
    for sample in SAMPLE_TICKERS:
        ticker = sample["ticker"]
        res = diagnose_naver_integration(ticker)
        naver_int_results[ticker] = res
        _print(
            f"  naver_int {ticker} -> http={res.get('http_status')} "
            f"has_nav={res.get('has_nav')} has_price={res.get('has_market_price')} "
            f"has_dev={res.get('has_discount_rate')}"
        )

    naver_int_judgment = judge_naver_integration(naver_int_results)

    # ─── Source #5: Naver ETF dedicated endpoint search ──────────
    _print("\n=== Source #5: Naver ETF dedicated endpoint candidates ===")
    naver_etf_results: dict = {}
    for sample in SAMPLE_TICKERS:
        ticker = sample["ticker"]
        res = diagnose_naver_etf_detail(ticker)
        naver_etf_results[ticker] = res
        _print(
            f"  naver_etf {ticker} -> "
            f"http={[c.get('http_status') for c in res.get('candidates', [])]} "
            f"nav_hits={sum(1 for c in res.get('candidates', []) if c.get('mentions_nav'))}"
        )

    naver_etf_judgment = judge_naver_etf_detail(naver_etf_results)

    finished_at = _utcnow_iso()
    _print(f"\n[END] @ {finished_at}")

    # 2026-06-07 FIX (검증자 A-1 / B-6): AC-2 최소 필드 계약 충족.
    # 각 smoke test 결과를 균일한 평탄 레코드 리스트로 노출 — 후속 자동 비교 가능.
    flat_records = _build_flat_records(
        pykrx_ohlcv_results=pykrx_ohlcv_results,
        pykrx_ohlcv_judgment=pykrx_ohlcv_judgment,
        pykrx_dev_results=pykrx_dev_results,
        pykrx_dev_judgment=pykrx_dev_judgment,
        fdr_results=fdr_results,
        fdr_judgment=fdr_judgment,
        naver_int_results=naver_int_results,
        naver_int_judgment=naver_int_judgment,
        naver_etf_results=naver_etf_results,
        naver_etf_judgment=naver_etf_judgment,
    )

    artifact: dict = {
        "schema_version": "nav_discount_source_diagnosis_v2",
        "started_at": started_at,
        "finished_at": finished_at,
        "samples": SAMPLE_TICKERS,
        "pykrx_test_dates": PYKRX_TEST_DATES,
        "timeouts": {
            "global_socket_timeout_sec": GLOBAL_SOCKET_TIMEOUT_SEC,
            "naver_http_timeout_sec": NAVER_TIMEOUT_SEC,
        },
        "flat_records": flat_records,
        "sources": {
            "pykrx_etf_ohlcv": {
                "source_id": "pykrx_etf_ohlcv",
                "category": "pykrx",
                "per_ticker": pykrx_ohlcv_results,
                "judgment": pykrx_ohlcv_judgment["judgment"],
                "reason": pykrx_ohlcv_judgment["reason"],
            },
            "pykrx_etf_price_deviation": {
                "source_id": "pykrx_etf_price_deviation",
                "category": "pykrx",
                "per_ticker": pykrx_dev_results,
                "judgment": pykrx_dev_judgment["judgment"],
                "reason": pykrx_dev_judgment["reason"],
            },
            "finance_data_reader": {
                "source_id": "finance_data_reader",
                "category": "fdr",
                "per_ticker": fdr_results,
                "judgment": fdr_judgment["judgment"],
                "reason": fdr_judgment["reason"],
            },
            "naver_mobile_stock_integration": {
                "source_id": "naver_mobile_stock_integration",
                "category": "naver_mobile",
                "per_ticker": naver_int_results,
                "judgment": naver_int_judgment["judgment"],
                "reason": naver_int_judgment["reason"],
            },
            "naver_mobile_etf_detail": {
                "source_id": "naver_mobile_etf_detail",
                "category": "naver_mobile",
                "per_ticker": naver_etf_results,
                "judgment": naver_etf_judgment["judgment"],
                "reason": naver_etf_judgment["reason"],
            },
        },
    }
    return artifact


def write_artifacts(artifact: dict) -> None:
    ARTIFACT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ARTIFACT_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2, default=str)
    _print(f"[WROTE] {ARTIFACT_JSON_PATH}")

    md = render_markdown(artifact)
    ARTIFACT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ARTIFACT_MD_PATH.open("w", encoding="utf-8") as f:
        f.write(md)
    _print(f"[WROTE] {ARTIFACT_MD_PATH}")


if __name__ == "__main__":
    artifact = run_diagnosis()
    write_artifacts(artifact)
