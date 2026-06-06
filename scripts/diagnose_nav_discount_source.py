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


def judge_pykrx_ohlcv(per_ticker_results: dict) -> dict:
    """pykrx ohlcv 결과를 source-level 로 통합 판정."""
    any_ok = False
    any_has_nav = False
    any_has_price = False
    for ticker, dates in per_ticker_results.items():
        for r in dates.values():
            if r.get("status") == "ok":
                any_ok = True
                if r.get("has_nav"):
                    any_has_nav = True
                if r.get("has_market_price"):
                    any_has_price = True
    if not any_ok:
        return {
            "judgment": "unusable",
            "reason": "모든 ticker × 날짜 조합에서 ok 응답 0건 (empty / call_failed).",
        }
    if any_has_nav and any_has_price:
        return {
            "judgment": "adopt_candidate",
            "reason": (
                "ohlcv 응답에 NAV + 시장가격 동시 제공. 기존 etf_nav_daily schema "
                "(nav / market_price) 와 직접 매핑 가능."
            ),
        }
    if any_has_nav:
        return {
            "judgment": "hold_unstable",
            "reason": "NAV 만 제공되거나 시장가격 키 매핑 실패.",
        }
    return {
        "judgment": "hold_unstable",
        "reason": "ohlcv 응답에 NAV 키 부재.",
    }


def judge_pykrx_deviation(per_ticker_results: dict) -> dict:
    any_ok = False
    any_has_dev = False
    for ticker, dates in per_ticker_results.items():
        for r in dates.values():
            if r.get("status") == "ok":
                any_ok = True
                if r.get("has_discount_rate"):
                    any_has_dev = True
    if not any_ok:
        return {
            "judgment": "unusable",
            "reason": "모든 ticker × 날짜 조합 empty / call_failed.",
        }
    if any_has_dev:
        return {
            "judgment": "adopt_candidate",
            "reason": "괴리율 직접 제공. 기존 compute_discount_rate_pct 와 충돌 없음.",
        }
    return {
        "judgment": "hold_unstable",
        "reason": "응답은 있으나 괴리율 키 매핑 실패.",
    }


def judge_fdr(per_ticker_results: dict) -> dict:
    ok_count = 0
    price_count = 0
    for r in per_ticker_results.values():
        if r.get("status") == "ok":
            ok_count += 1
            if r.get("has_market_price"):
                price_count += 1
    if ok_count == 0:
        return {
            "judgment": "unusable",
            "reason": "FDR DataReader 응답 0건.",
        }
    if price_count >= 1:
        return {
            "judgment": "hold_unstable",
            "reason": (
                "FDR 은 시장 종가만 제공 — NAV 직접 제공 안 함. NAV source 와 결합 "
                "시 괴리율 계산 후보. 단독 adopt_candidate 아님."
            ),
        }
    return {
        "judgment": "unusable",
        "reason": "FDR 응답은 있으나 시장가격 키 매핑 실패.",
    }


def judge_naver_integration(per_ticker_results: dict) -> dict:
    ok_count = 0
    nav_count = 0
    price_count = 0
    dev_count = 0
    asof_count = 0
    for r in per_ticker_results.values():
        if r.get("status") == "ok":
            ok_count += 1
            if r.get("has_nav"):
                nav_count += 1
            if r.get("has_market_price"):
                price_count += 1
            if r.get("has_discount_rate"):
                dev_count += 1
            if r.get("has_asof"):
                asof_count += 1
    if ok_count == 0:
        return {
            "judgment": "unusable",
            "reason": "Naver integration API 모든 ticker call_failed.",
        }
    if nav_count == ok_count and price_count == ok_count and dev_count == ok_count:
        return {
            "judgment": "hold_unstable",
            "reason": (
                f"NAV / 시장가격 / 괴리율 모두 {ok_count}/{ok_count} 제공 "
                f"(asof={asof_count}/{ok_count}). 비공식 endpoint — schema 변경 / 차단 "
                "위험 + 운영 안정성 별도 검증 권장. 안정성 진단 후 adopt 승격 가능."
            ),
        }
    if nav_count > 0 and price_count > 0:
        return {
            "judgment": "hold_unstable",
            "reason": (
                f"NAV={nav_count}/{ok_count} / 시장가격={price_count}/{ok_count} / "
                f"괴리율={dev_count}/{ok_count} / asof={asof_count}/{ok_count}. "
                "비공식 endpoint — 운영 안정성 별도 검증 권장."
            ),
        }
    return {
        "judgment": "hold_unstable",
        "reason": (
            f"NAV={nav_count}/{ok_count} / 시장가격={price_count}/{ok_count} / "
            f"괴리율={dev_count}/{ok_count} / asof={asof_count}/{ok_count}. 키 매핑 불완전."
        ),
    }


def judge_naver_etf_detail(per_ticker_results: dict) -> dict:
    """ETF dedicated endpoint — 404 가 많으면 unusable / NAV 키 흔적 있으면 hold."""
    any_200 = False
    any_nav_mention = False
    for r in per_ticker_results.values():
        for c in r.get("candidates", []):
            if c.get("http_status") == 200:
                any_200 = True
                if c.get("mentions_nav"):
                    any_nav_mention = True
    if not any_200:
        return {
            "judgment": "unusable",
            "reason": "ETF dedicated endpoint 후보 모두 HTTP 200 응답 0건.",
        }
    if any_nav_mention:
        return {
            "judgment": "hold_unstable",
            "reason": (
                "ETF dedicated endpoint 일부 응답 + NAV / 괴리 단어 흔적. 비공식 "
                "endpoint — schema 검증 + 안정성 추가 진단 필요."
            ),
        }
    return {
        "judgment": "hold_unstable",
        "reason": "응답은 있으나 NAV / 괴리 흔적 부재.",
    }


def _print(*args):
    """stdout 안전 출력 (cp949 환경 대비)."""
    msg = " ".join(str(a) for a in args)
    try:
        print(msg)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))


# AC-2 최소 필드 계약: source_id / ticker / http_status (or call_status) /
# has_nav / has_market_price / has_discount_rate / has_asof / error_type / judgment.


def _record_from(
    source_id: str,
    ticker: str,
    res: dict,
    judgment: str,
    extra: Optional[dict] = None,
) -> dict:
    rec = {
        "source_id": source_id,
        "ticker": ticker,
        "call_status": res.get("status"),
        "http_status": res.get("http_status"),
        "has_nav": bool(res.get("has_nav")),
        "has_market_price": bool(res.get("has_market_price")),
        "has_discount_rate": bool(res.get("has_discount_rate")),
        "has_asof": bool(res.get("has_asof") or res.get("asof") is not None),
        "error_type": res.get("error_type"),
        "judgment": judgment,
    }
    if extra:
        rec.update(extra)
    return rec


def _build_flat_records(
    *,
    pykrx_ohlcv_results: dict,
    pykrx_ohlcv_judgment: dict,
    pykrx_dev_results: dict,
    pykrx_dev_judgment: dict,
    fdr_results: dict,
    fdr_judgment: dict,
    naver_int_results: dict,
    naver_int_judgment: dict,
    naver_etf_results: dict,
    naver_etf_judgment: dict,
) -> list[dict]:
    """source × ticker 단위 균일 레코드 리스트 — AC-2 필드 계약 충족."""
    records: list[dict] = []

    # pykrx ohlcv: ticker 당 마지막 시도 결과 1건 (가장 최근 시도).
    for ticker, dates in pykrx_ohlcv_results.items():
        last_res = None
        last_date = None
        for d, r in dates.items():
            last_res, last_date = r, d
            if r.get("status") == "ok":
                break
        if last_res is not None:
            records.append(
                _record_from(
                    "pykrx_etf_ohlcv",
                    ticker,
                    last_res,
                    pykrx_ohlcv_judgment["judgment"],
                    {"attempted_date": last_date},
                )
            )

    for ticker, dates in pykrx_dev_results.items():
        last_res = None
        last_date = None
        for d, r in dates.items():
            last_res, last_date = r, d
            if r.get("status") == "ok":
                break
        if last_res is not None:
            records.append(
                _record_from(
                    "pykrx_etf_price_deviation",
                    ticker,
                    last_res,
                    pykrx_dev_judgment["judgment"],
                    {"attempted_date": last_date},
                )
            )

    for ticker, res in fdr_results.items():
        records.append(
            _record_from(
                "finance_data_reader",
                ticker,
                res,
                fdr_judgment["judgment"],
            )
        )

    for ticker, res in naver_int_results.items():
        records.append(
            _record_from(
                "naver_mobile_stock_integration",
                ticker,
                res,
                naver_int_judgment["judgment"],
            )
        )

    for ticker, res in naver_etf_results.items():
        # naver_etf_detail 은 candidate 마다 다른 endpoint — ticker 당 1건으로 요약.
        candidates = res.get("candidates", []) if isinstance(res, dict) else []
        any_200 = any(c.get("http_status") == 200 for c in candidates)
        any_nav = any(c.get("mentions_nav") for c in candidates)
        any_dev = any(c.get("mentions_deviation") for c in candidates)
        summary = {
            "status": "ok" if any_200 else "call_failed",
            "http_status": next(
                (c.get("http_status") for c in candidates if c.get("http_status")),
                None,
            ),
            "has_nav": any_nav,
            "has_market_price": False,
            "has_discount_rate": any_dev,
            "has_asof": False,
        }
        records.append(
            _record_from(
                "naver_mobile_etf_detail",
                ticker,
                summary,
                naver_etf_judgment["judgment"],
                {"candidates_checked": len(candidates)},
            )
        )

    return records


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


def render_markdown(artifact: dict) -> str:
    lines = []
    lines.append("# ETF NAV / Discount Source Diagnosis 1차")
    lines.append("")
    lines.append(f"작성: {artifact['finished_at']}")
    lines.append("성격: 진단 전용 — 운영 fetcher 교체 / source integration 없음.")
    lines.append("")
    lines.append("## 1. 진단 대상 sample ticker")
    lines.append("")
    lines.append("| ticker | name | category | reason |")
    lines.append("| --- | --- | --- | --- |")
    for s in artifact["samples"]:
        lines.append(
            f"| `{s['ticker']}` | {s['name']} | {s['category']} | {s['reason']} |"
        )
    lines.append("")
    lines.append("## 2. source별 판정")
    lines.append("")
    lines.append("| source_id | category | judgment | 핵심 사유 |")
    lines.append("| --- | --- | --- | --- |")
    for sid, src in artifact["sources"].items():
        lines.append(
            f"| `{sid}` | {src['category']} | **{src['judgment']}** | {src['reason']} |"
        )
    lines.append("")
    lines.append("## 3. source별 상세")
    lines.append("")
    for sid, src in artifact["sources"].items():
        lines.append(f"### {sid}")
        lines.append("")
        lines.append(f"- judgment: **{src['judgment']}**")
        lines.append(f"- reason: {src['reason']}")
        lines.append("")
        lines.append("샘플 결과 (ticker × 최초 ok / 최후 시도):")
        lines.append("")
        for ticker, content in src["per_ticker"].items():
            if isinstance(content, dict) and "status" in content:
                lines.append(
                    f"  - `{ticker}`: status={content.get('status')} "
                    f"has_nav={content.get('has_nav')} "
                    f"has_price={content.get('has_market_price')} "
                    f"has_dev={content.get('has_discount_rate')}"
                )
            elif isinstance(content, dict):
                # dates dict.
                for d, r in content.items():
                    lines.append(
                        f"  - `{ticker}` @ {d}: status={r.get('status')} "
                        f"has_nav={r.get('has_nav')} "
                        f"has_price={r.get('has_market_price')} "
                        f"has_dev={r.get('has_discount_rate')}"
                    )
        lines.append("")
    lines.append("## 4. 기존 schema fit")
    lines.append("")
    lines.append(
        "- `etf_nav_daily` 컬럼: etf_ticker / asof / nav / market_price / "
        "discount_rate_pct / source / status / message."
    )
    lines.append(
        "- pykrx 후보가 `adopt_candidate` 일 경우 시장가격은 ohlcv 종가, NAV 는 "
        "NAV 컬럼, source 라벨은 `pykrx/etf_ohlcv` 권장."
    )
    lines.append(
        "- 괴리율은 source 가 직접 제공하면 그 값을 우선 사용, 그렇지 않으면 기존 "
        "`compute_discount_rate_pct(nav, market_price)` 재사용."
    )
    lines.append("")
    lines.append("## 5. K6 / EOD 방어 가능성")
    lines.append("")
    lines.append(
        "- pykrx 후보: 단일 호출 1초 내외 / 1ticker = 1API call. 10개 후보 + delay 적용 "
        "가능, 30초 budget 안에 들어옴. cache-first / 실패 격리 패턴 적용 가능."
    )
    lines.append(
        "- Naver mobile 후보: 비공식 — 차단 / schema 변경 위험. K6 적용은 채택 결정 후 "
        "별도 운영 안정성 STEP 에서 검증."
    )
    lines.append("")
    lines.append("## 6. 결론 / 다음 STEP 추천")
    lines.append("")
    adopt_sources = [
        sid
        for sid, src in artifact["sources"].items()
        if src["judgment"] == "adopt_candidate"
    ]
    if adopt_sources:
        lines.append(
            f"- adopt_candidate 발견: {', '.join(adopt_sources)}. 다음 STEP 후보: "
            "`NAV_DISCOUNT_SOURCE_INTEGRATION_1` — 본 진단 결과를 입력으로 운영 "
            "fetcher 교체 설계."
        )
    else:
        lines.append(
            "- adopt_candidate 0건. 다음 STEP 후보: 사용자 결정 — 다른 빈자리 (구성종목 "
            "가격 시계열 / 위험 감지 지표 시계열) 로 이동하거나 KRX OPEN API "
            "(auth_required) 확보 검토."
        )
    lines.append("")
    lines.append("## 7. 본 STEP 에서 하지 않은 것")
    lines.append("")
    lines.append("- 운영 NAV fetcher 교체.")
    lines.append("- NAV / 괴리율 source integration.")
    lines.append("- 전체 universe NAV 수집 / 정기 job 추가.")
    lines.append("- 신규 API / 괴리율 threshold 변경 / Telegram 변경.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    artifact = run_diagnosis()
    write_artifacts(artifact)
