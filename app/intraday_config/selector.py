"""POC3-02C-OPS-01 — 사업군 자동 분류 · 대표/대체 ETF 선정.

설계자 §10-2 확정 규칙만 구현한다. **새 산식을 만들지 않는다.**

## 분류 (토큰 사전)

- PC 가 **공식 기초지수명**을 토큰 사전으로 자동 분류한다.
- 사전은 코드 하드코딩이 아니라 **번들 데이터**다 — 버전과 함께 승인된다.
- 한 지수는 **최대 한 사업군**에만 배정한다.
- **긴 토큰 우선 매칭** — `AI반도체` 가 `반도체` 보다 먼저다.
- 충돌하거나 매칭되지 않으면 **임의 분류하지 않고 제외·기록**한다.

## 대표 선정

```text
적격  국내 주식형 · 비레버리지 · 비인버스 · 비합성
      광의시장지수 · 파생전략 제외
대표  시가총액 1위        (시총 = 상장좌수 × 무조정 종가)
대체  시가총액 2위
동률  ticker 오름차순
```

대표 1개 + 대체 1개만 둔다. **대체는 평상시 조회하지 않고 대표 조회 실패 시에만**
쓴다(§10-2).

**"오늘 많이 올랐다" 는 선정에 쓰지 않는다.** 대표 선정과 당일 급등락 판정은
분리한다(§3-1).

**보유 여부는 선정 입력이 아니다** (§10-3(1)).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

RULE_VERSION = "sector_rep.v1"

# 광의 시장지수 — 사업군이 아니다. **완전일치**로만 뺀다(부분 추측 금지).
BROAD_INDEX_NAMES = frozenset(
    {
        "코스피",
        "코스피 200",
        "코스피 200 TR",
        "코스피 100",
        "코스피 200 중소형주",
        "코스닥",
        "코스닥 150",
        "코스닥 150 TR",
        "KRX 300",
        "KRX 100",
        "코리아 밸류업 지수",
    }
)

# 파생 전략 — 기초 사업군 흐름이 아니라 옵션·배당 전략이다.
STRATEGY_PATTERN = re.compile(
    r"커버드콜|위클리|타겟|프리미엄|버퍼|Covered\s*Call|Buffer", re.IGNORECASE
)


TOKEN_DICTIONARY_PATH = Path("state/intraday_config/token_dictionary_v1.json")
TOKEN_DICTIONARY_SCHEMA = "intraday_token_dictionary.v1"


class TokenDictionaryError(RuntimeError):
    """사전 데이터 파일을 읽을 수 없다. **코드 상수로 되돌아가지 않는다.**"""


def load_token_dictionary(
    path: Optional[Path] = None,
) -> tuple[dict[str, list[str]], str]:
    """번들 데이터 파일에서 사전을 읽는다 (설계서 §10-2).

    반환 `(사전, 원본 sha256)`.

    **코드 하드코딩 금지 계약**이라 기본값 fallback 을 두지 않는다 — 파일이
    없거나 깨졌으면 올린다. 조용히 옛 사전으로 분류하면 승인된 내용과 실제
    분류가 갈린다.
    """
    p = path or TOKEN_DICTIONARY_PATH
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise TokenDictionaryError(f"사전 파일을 읽을 수 없다: {p} ({e})") from e
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise TokenDictionaryError(f"사전 파일이 JSON 이 아니다: {p}") from e

    if body.get("schema_version") != TOKEN_DICTIONARY_SCHEMA:
        raise TokenDictionaryError(
            f"사전 schema_version 불일치: {body.get('schema_version')!r}"
        )
    sectors = body.get("sectors")
    if not isinstance(sectors, dict) or not sectors:
        raise TokenDictionaryError("사전에 sectors 가 없다")
    out: dict[str, list[str]] = {}
    for k, v in sectors.items():
        if not isinstance(k, str) or not k.strip():
            raise TokenDictionaryError(f"사업군 키가 문자열이 아니다: {k!r}")
        if (
            not isinstance(v, list)
            or not v
            or not all(isinstance(t, str) and t.strip() for t in v)
        ):
            raise TokenDictionaryError(f"사업군 {k!r} 의 토큰 목록이 비정상이다")
        out[k] = list(v)
    return out, hashlib.sha256(raw).hexdigest()


def default_token_dictionary(path: Optional[Path] = None) -> dict[str, list[str]]:
    """번들 사전만 반환하는 helper. 원천은 항상 데이터 파일이다."""
    return load_token_dictionary(path)[0]


def classify(index_name: str, dictionary: dict[str, list[str]]) -> Optional[str]:
    """지수명 → 사업군 키. 없으면 `None`.

    **긴 토큰 우선** 매칭이다. 서로 다른 사업군의 토큰이 동시에 걸리면
    **충돌로 보고 `None`** 을 돌려준다 — 임의로 하나를 고르지 않는다.
    """
    hits: list[tuple[int, str]] = []
    for sector, tokens in dictionary.items():
        for tok in tokens:
            if tok and tok in index_name:
                hits.append((len(tok), sector))
    if not hits:
        return None
    hits.sort(key=lambda x: -x[0])
    best_len = hits[0][0]
    top = {s for ln, s in hits if ln == best_len}
    if len(top) > 1:
        return None  # 같은 길이 토큰이 서로 다른 사업군을 가리킨다 — 충돌
    return hits[0][1]


def _num(x: Any) -> Optional[float]:
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def load_official_rows(csv_path: Path) -> list[dict[str, str]]:
    """공식 ETF 기본정보 CSV (cp949)."""
    return list(csv.DictReader(io.open(csv_path, encoding="cp949")))


def is_eligible(row: dict[str, str]) -> tuple[bool, Optional[str]]:
    """적격성 — `OPS-02B-1` 검증 계약을 그대로 쓴다."""
    if (row.get("기초자산분류") or "").strip() != "주식":
        return False, "not_equity"
    if (row.get("추적배수") or "").strip() != "일반":
        return False, "leveraged_or_inverse"
    if "합성" in (row.get("복제방법") or ""):
        return False, "synthetic"
    if (row.get("기초시장분류") or "").strip() != "국내":
        return False, "not_domestic"
    idx = (row.get("기초지수명") or "").strip()
    if idx in BROAD_INDEX_NAMES:
        return False, "broad_market_index"
    if STRATEGY_PATTERN.search(idx):
        return False, "strategy_overlay"
    return True, None


def latest_closes(db_path: Path) -> tuple[str, dict[str, float]]:
    """무조정 계열 최신 거래일의 종가. 반환 `(date, {ticker: close})`."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        asof = con.execute(
            "SELECT MAX(date) FROM krx_etf_daily_price_unadjusted"
        ).fetchone()[0]
        if not asof:
            return "", {}
        rows = con.execute(
            "SELECT ticker, close FROM krx_etf_daily_price_unadjusted WHERE date=?",
            (asof,),
        ).fetchall()
        return asof, {t: c for t, c in rows if c}
    finally:
        con.close()


def evaluation_input_hash(
    *, csv_path: Path, data_asof: str, rule_version: str, dictionary_keys: list[str]
) -> str:
    """데이터·기준일·규칙 변경 감지용 (§10-3(1)). **계산 이력에만** 쓴다.

    보유 목록은 **넣지 않는다** — 선정 입력이 아니다.
    """
    csv_hash = (
        hashlib.sha256(csv_path.read_bytes()).hexdigest() if csv_path.exists() else ""
    )
    payload = "|".join(
        [csv_hash, data_asof, rule_version, ",".join(sorted(dictionary_keys))]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def build_sectors(
    *,
    csv_path: Path,
    db_path: Path,
    dictionary: Optional[dict[str, list[str]]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """사업군별 대표·대체를 산출한다.

    반환 `(sectors, excluded, data_asof)`.
    `excluded` 에는 **분류되지 않았거나 충돌한** 지수를 남긴다 — 조용히 버리지
    않는다(§10-2).
    """
    d = dictionary or default_token_dictionary()
    rows = load_official_rows(csv_path)
    asof, closes = latest_closes(db_path)

    buckets: dict[str, list[dict[str, Any]]] = {}
    excluded: list[dict[str, Any]] = []
    unclassified: dict[str, int] = {}

    for r in rows:
        ok, why = is_eligible(r)
        if not ok:
            continue
        idx = (r.get("기초지수명") or "").strip()
        ticker = (r.get("단축코드") or "").strip()
        if not idx or not ticker:
            continue
        sector = classify(idx, d)
        if sector is None:
            unclassified[idx] = unclassified.get(idx, 0) + 1
            continue
        shares, px = _num(r.get("상장좌수")), closes.get(ticker)
        buckets.setdefault(sector, []).append(
            {
                "ticker": ticker,
                "short_name": (r.get("한글종목약명") or "").strip(),
                "index_agency": (r.get("지수산출기관") or "").strip(),
                "index_name": idx,
                "market_cap": (shares * px) if (shares and px) else None,
            }
        )

    for idx, n in sorted(unclassified.items()):
        excluded.append({"index_name": idx, "etf_count": n, "reason": "unclassified"})

    sectors: list[dict[str, Any]] = []
    for sector in sorted(buckets):
        items = buckets[sector]
        # 시총이 **있는** 후보만 대표가 될 수 있다. 예전에는 결측을 `or 0.0` 으로
        # 메워 종목코드 오름차순으로 뽑고도 `metric="market_cap"` 이라 적었다 —
        # 근거 없는 선정을 근거 있는 것처럼 기록하는 fallback 이었다.
        priced = [x for x in items if x["market_cap"] is not None]
        unpriced = [x for x in items if x["market_cap"] is None]
        for x in unpriced:
            excluded.append(
                {
                    "index_name": x["index_name"],
                    "ticker": x["ticker"],
                    "etf_count": 1,
                    "reason": "no_market_cap",
                }
            )
        if not priced:
            # 사업군 전체가 시총 미상이면 **대표를 만들지 않는다.** 조용히
            # 버리지도 않는다 — 사유를 남긴다.
            excluded.append(
                {
                    "index_name": sector,
                    "etf_count": len(items),
                    "reason": "sector_no_market_cap",
                }
            )
            continue
        # 시총 1위 · 동률이면 ticker 오름차순 (§10-2).
        priced.sort(key=lambda x: (-x["market_cap"], x["ticker"]))
        items = priced
        rep = items[0]
        alt = items[1] if len(items) > 1 else None
        sectors.append(
            {
                "sector_key": sector,
                # 판단 C — 공식 토큰 그대로. 임의 라벨을 만들지 않는다.
                "sector_label": sector,
                "representative": {
                    "ticker": rep["ticker"],
                    "short_name": rep["short_name"],
                    "index_agency": rep["index_agency"],
                    "index_name": rep["index_name"],
                },
                "alternate": (
                    {
                        "ticker": alt["ticker"],
                        "short_name": alt["short_name"],
                        "index_agency": alt["index_agency"],
                        "index_name": alt["index_name"],
                    }
                    if alt
                    else None
                ),
                "selection_basis": {
                    "metric": "market_cap",
                    "rule_version": RULE_VERSION,
                    "candidate_count": len(items),
                    # 실제 값을 남긴다 — 값이 없으면 선정 근거가 없다는 뜻이고,
                    # 그 상태는 위에서 이미 제외된다.
                    "representative_market_cap": rep["market_cap"],
                    "alternate_market_cap": (alt or {}).get("market_cap"),
                    "unpriced_candidate_count": len(unpriced),
                },
            }
        )
    return sectors, excluded, asof


__all__ = [
    "BROAD_INDEX_NAMES",
    "RULE_VERSION",
    "STRATEGY_PATTERN",
    "build_sectors",
    "classify",
    "default_token_dictionary",
    "evaluation_input_hash",
    "is_eligible",
    "latest_closes",
    "load_official_rows",
]
