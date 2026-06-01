"""ETF 구성종목 외부 fetcher (POC2 — 2026-05-27).

본 모듈의 책임:
- 단일 ETF 의 (top_k, 구성종목 + 비중) 을 외부 소스에서 가져온다.
- 외부 의존성을 추상화 — 테스트는 dependency injection 으로 stub.

1차 구현 (지시문 §3 우선순위):
- pykrx `stock.get_etf_portfolio_deposit_file(date, ticker)` — KRX 공식 ETF PDF.
- KRX Open API / 다른 공식 경로는 별도 fetcher 추가로 확장 가능.

원칙 (지시문 §3 금지 항목):
- ETF명만 보고 구성종목 추정 X.
- AI 에게 구성종목 묻기 X.
- 비중 임의 생성 X.
- source 불명 데이터를 ok 처리 X.

수집 실패는 명시적 None / 예외로 반환한다 (호출자 service 가 unavailable
status 로 변환).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

PYKRX_SOURCE = "pykrx/get_etf_portfolio_deposit_file"
NAVER_STOCK_SOURCE = "naver_stock_etf_component"

# fetcher signature: (etf_ticker, asof_yyyymmdd_or_iso, top_k) → FetchResult
FetcherFn = Callable[[str, str, int], "FetchResult"]


@dataclass
class FetchedConstituent:
    rank: int
    constituent_ticker: Optional[str]
    constituent_name: Optional[str]
    weight_pct: Optional[float]
    # 2026-05-31 — Naver Stock ETFComponent 통합 (해외 종목 지원).
    # 국내 종목은 모두 None 가능. 해외 종목은 reuters_code / isin 중 1개 이상 필수.
    constituent_isin: Optional[str] = None
    constituent_reuters_code: Optional[str] = None
    market_type: Optional[str] = None


@dataclass
class FetchResult:
    status: str  # "ok" / "unavailable"
    source: str
    constituents: list[FetchedConstituent]
    etf_name: Optional[str] = None
    message: Optional[str] = None
    # 2026-05-31 — 응답이 명시한 기준일 (예: Naver referenceDate). service 가
    # 입력 asof 대신 이 값으로 저장 + cache check 수행한다. None 이면 입력
    # asof 그대로 사용 (기존 pykrx 동작 호환).
    effective_asof: Optional[str] = None


def _asof_to_yyyymmdd(asof: str) -> str:
    """'2026-05-26' → '20260526'. 이미 8자리면 그대로."""
    s = asof.replace("-", "")
    return s[:8]


def _to_optional_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pykrx_pdf_fetcher(etf_ticker: str, asof: str, top_k: int) -> FetchResult:
    """pykrx 기본 fetcher — KRX PDF. 호출 실패 / 빈 응답 시 unavailable."""
    try:
        from pykrx import (
            stock,
        )  # lazy import — pykrx 미설치 환경에서도 본 모듈 import 안전.
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message=f"pykrx_import_failed: {type(e).__name__}: {e}",
        )
    yyyymmdd = _asof_to_yyyymmdd(asof)
    try:
        df = stock.get_etf_portfolio_deposit_file(yyyymmdd, etf_ticker)
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message=f"pykrx_call_failed: {type(e).__name__}: {e}",
        )
    if df is None or len(df) == 0:
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message="no_data",
        )

    # pykrx PDF 컬럼: index=ticker, 비중(%) / 비중 (column 이름은 버전마다 차이).
    weight_col_candidates = ["비중", "비중(%)", "비중 (%)", "Weight"]
    weight_col = None
    for c in weight_col_candidates:
        if c in df.columns:
            weight_col = c
            break
    name_col = None
    for c in ("종목명", "이름", "Name"):
        if c in df.columns:
            name_col = c
            break

    # 비중 내림차순 정렬 후 top_k 추출.
    try:
        if weight_col is not None:
            df_sorted = df.sort_values(weight_col, ascending=False)
        else:
            df_sorted = df
        rows: list[FetchedConstituent] = []
        for rank_idx, (idx, raw) in enumerate(df_sorted.iterrows(), start=1):
            if rank_idx > max(1, top_k):
                break
            ticker = str(idx) if idx is not None else None
            name = None
            if name_col is not None:
                try:
                    name = str(raw[name_col]) if raw[name_col] is not None else None
                except Exception:  # noqa: BLE001
                    name = None
            weight = _to_optional_float(raw[weight_col]) if weight_col else None
            rows.append(
                FetchedConstituent(
                    rank=rank_idx,
                    constituent_ticker=ticker,
                    constituent_name=name,
                    weight_pct=weight,
                )
            )
        if not rows:
            return FetchResult(
                status="unavailable",
                source=PYKRX_SOURCE,
                constituents=[],
                message="parsed_empty",
            )
        return FetchResult(
            status="ok",
            source=PYKRX_SOURCE,
            constituents=rows,
            etf_name=None,
        )
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message=f"parse_error: {type(e).__name__}: {e}",
        )


def default_fetcher() -> FetcherFn:
    """기본 fetcher 인스턴스 — 2026-05-31 부터 Naver Stock ETFComponent 1차.

    이전 1차 (pykrx PDF) 는 Source Diagnosis 1차 결과 hold 로 분류된 상태.
    pykrx fetcher 함수는 본 모듈에 남아있으며 향후 chained fallback 시 호출
    가능 (현재 service 는 default 만 사용)."""
    return naver_stock_etf_component_fetcher


# ─── Naver Stock ETFComponent fetcher (POC2 — 2026-05-31) ──────────


# urllib 등 외부 호출을 service 가 stub 가능하도록 함수 단위로 분리.
NAVER_API_BASE = "https://stock.naver.com/api/domestic/detail"
NAVER_TIMEOUT_SEC = 10
NAVER_DEFAULT_PAGE_SIZE = 20
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://stock.naver.com/",
}


def _naver_http_get(url: str, timeout: float = NAVER_TIMEOUT_SEC) -> tuple[int, str]:
    """단일 GET. (http_status, body_text). 외부 의존성 격리 — 테스트는 patch."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers=NAVER_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code), ""


def _coerce_weight_string(raw) -> Optional[float]:
    """Naver 의 weight 는 string (예: "32.33"). 변환 불가 시 None.

    지시문 §6.1 — 0 임의 대체 금지. 변환 실패 row 는 service 에서 저장 제외.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            f = float(raw)
            if f != f:  # NaN
                return None
            return f
        except (TypeError, ValueError):
            return None
    s = str(raw).strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _build_constituent_key(
    item_code: Optional[str],
    reuters_code: Optional[str],
    isin: Optional[str],
    name: Optional[str],
) -> Optional[str]:
    """매칭 1차 키 (지시문 §6.3): 국내 ticker → 해외 reuters → ISIN → name.

    빈 문자열은 None 으로 정규화. 모두 비어있으면 None.
    """
    for v in (item_code, reuters_code, isin):
        if v and str(v).strip():
            return str(v).strip()
    if name:
        s = str(name).strip()
        if s:
            return f"name:{s.lower()}"
    return None


def naver_stock_etf_component_fetcher(
    etf_ticker: str, asof: str, top_k: int
) -> FetchResult:
    """Naver Stock ETFComponent API fetcher (지시문 §4~§6).

    요청 endpoint:
        https://stock.naver.com/api/domestic/detail/{ticker}/ETFComponent
            ?startIdx=0&pageSize=20

    응답은 top-level array (list[dict]). weight 는 string → float 변환,
    referenceDate 는 effective_asof 로 노출 (service 가 저장 + cache key 에
    그 값을 사용).
    """
    url = (
        f"{NAVER_API_BASE}/{etf_ticker}/ETFComponent"
        f"?startIdx=0&pageSize={NAVER_DEFAULT_PAGE_SIZE}"
    )
    try:
        http_status, body = _naver_http_get(url)
    except Exception as e:  # noqa: BLE001 — 네트워크 실패 격리.
        return FetchResult(
            status="unavailable",
            source=NAVER_STOCK_SOURCE,
            constituents=[],
            message=f"http_failed: {type(e).__name__}: {e}"[:200],
        )
    if http_status != 200:
        return FetchResult(
            status="unavailable",
            source=NAVER_STOCK_SOURCE,
            constituents=[],
            message=f"http_status_{http_status}",
        )
    import json

    try:
        data = json.loads(body) if body else None
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=NAVER_STOCK_SOURCE,
            constituents=[],
            message=f"json_parse_failed: {type(e).__name__}: {e}"[:200],
        )
    if not isinstance(data, list) or not data:
        return FetchResult(
            status="unavailable",
            source=NAVER_STOCK_SOURCE,
            constituents=[],
            message=(
                "no_data" if not data else f"unexpected_shape:{type(data).__name__}"
            ),
        )

    # referenceDate 를 응답에서 추출 (모든 item 동일 가정, 첫 item 에서).
    effective_asof: Optional[str] = None
    first = data[0]
    if isinstance(first, dict):
        ref = first.get("referenceDate")
        if ref and isinstance(ref, str):
            effective_asof = ref.strip() or None

    # 비중 내림차순 정렬 + top_k 추출.
    parsed: list[dict] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        w = _coerce_weight_string(raw.get("weight"))
        if w is None:
            # 비중 변환 실패 item 은 저장하지 않음 (지시문 §6.1 — 0 대체 금지).
            continue
        parsed.append(
            {
                "componentItemCode": raw.get("componentItemCode"),
                "componentName": raw.get("componentName"),
                "weight": w,
                "componentIsinCode": raw.get("componentIsinCode"),
                "componentReutersCode": raw.get("componentReutersCode"),
                "componentMarketType": raw.get("componentMarketType"),
            }
        )
    if not parsed:
        return FetchResult(
            status="unavailable",
            source=NAVER_STOCK_SOURCE,
            constituents=[],
            message="all_weights_invalid",
            effective_asof=effective_asof,
        )
    parsed.sort(key=lambda x: x["weight"], reverse=True)
    parsed = parsed[: max(1, top_k)]

    constituents: list[FetchedConstituent] = []
    for rank, p in enumerate(parsed, start=1):
        item_code = (
            str(p["componentItemCode"]).strip()
            if p["componentItemCode"] is not None
            else None
        )
        reuters = (
            str(p["componentReutersCode"]).strip()
            if p["componentReutersCode"] is not None
            else None
        )
        isin = (
            str(p["componentIsinCode"]).strip()
            if p["componentIsinCode"] is not None
            else None
        )
        constituents.append(
            FetchedConstituent(
                rank=rank,
                # 국내 종목은 item_code 그대로 ticker. 해외 종목은 item_code=None.
                constituent_ticker=item_code or None,
                constituent_name=(
                    str(p["componentName"]) if p["componentName"] else None
                ),
                weight_pct=float(p["weight"]),
                constituent_isin=isin or None,
                constituent_reuters_code=reuters or None,
                market_type=(
                    str(p["componentMarketType"])
                    if p["componentMarketType"] is not None
                    else None
                ),
            )
        )

    return FetchResult(
        status="ok",
        source=NAVER_STOCK_SOURCE,
        constituents=constituents,
        etf_name=None,
        effective_asof=effective_asof,
    )
