"""POC5-09 — PC 화면용 가격 흐름 기준일 정정 (설계서 §9-4 · PLAN §7).

공유 builder(`build_holdings_market_evidence`)의 결과는 PUSH · 초안 · 런타임 근거도
쓰므로 바꾸지 않는다. 이 모듈은 PC 화면 API 가 그 결과의 **깊은 사본**만 고치게 한다.

- 날짜 키와 단기 흐름 값은 **같은 읽기**에서 나온다(설계 §10-2-1): 종목 · KODEX200 각각 같은
  행 조건의 최근 저장 가격 행(`fetch_recent_price_rows`)을 한 번 읽고, 그 행으로 날짜(i 번째 행 =
  `series[-(i+1)]`)와 5 · 10 · 20일 값(기존 산식 `_window_return_pct`)을 함께 만든다. builder 가
  앞서 따로 읽어 계산한 값에 나중에 읽은 날짜를 붙이지 않는다. 그 값으로 만든 단기 흐름 메모 한
  줄도 이 사본 값에 맞춰 바꾼다.
- PC 비교 기준일 = KODEX200(단기 흐름의 비교 계열) 최신 저장 가격 날짜. 오늘이나 기대
  거래일과 비교하지 않는다.
- 종목 기준일이 다르면 현재 비교값(5/10/20일 · KODEX200 대비)을 비우고 status 를
  unavailable 로 둔다. 기준일은 같지만 n일 비교 기간 시작이 다르면 그 KODEX200 대비만
  비운다 — status 는 ok 그대로라 자기 5일 값으로 최대 3개 후보에 남는다(판정 §9-4-3 '기준일에
  맞는 유효 후보'). 비운 KODEX200 대비 20일 메모는 빠진다.
- 최대 3개 · 자료 확인 필요 건수는 고친 사본으로 기존 `summarize_holdings` 를 다시
  불러 만든다(날짜가 맞는 후보 안에서 기존 5일 · 동점 규칙으로 채움).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable, Optional

from app.market_data_store import DEFAULT_DB_PATH, fetch_recent_price_rows
from app.market_summary_composer import summarize_holdings
from app.short_term_momentum import (
    KODEX200_TICKER,
    MIN_TRADING_DAYS_FOR_OK,
    _window_return_pct,
)

WINDOWS = (5, 10, 20)
# 기준일 1행 + 가장 긴 비교 기간 20행 = 단기 흐름이 ok 가 되는 최소 행 수.
RECENT_ROWS = MIN_TRADING_DAYS_FOR_OK
assert RECENT_ROWS == max(WINDOWS) + 1
# builder 가 단기 흐름 unavailable 일 때 붙이는 문구(holdings_market_evidence._build_evidence_notes).
FLOW_SHORT_NOTE = "단기 흐름은 데이터 부족으로 확인할 수 없습니다."

COMPARISON_OK = "ok"
COMPARISON_DATE_MISMATCH = "date_mismatch"
COMPARISON_WINDOW_MISMATCH = "window_mismatch"
COMPARISON_UNAVAILABLE = "unavailable"

_FLOW_KEYS = (
    "return_5d_pct",
    "return_10d_pct",
    "return_20d_pct",
    "excess_vs_kodex200_5d_pctp",
    "excess_vs_kodex200_10d_pctp",
    "excess_vs_kodex200_20d_pctp",
)

RowsByTicker = dict[str, list[tuple[str, float, Optional[int], str]]]


def load_recent_price_rows(
    tickers: Iterable[str], *, db_path: Path = DEFAULT_DB_PATH
) -> RowsByTicker:
    """종목마다 최근 저장 가격 행을 1회씩 읽는다(KODEX200 포함 · 중복 종목 1회)."""
    out: RowsByTicker = {}
    for t in [*tickers, KODEX200_TICKER]:
        if t not in out:
            out[t] = fetch_recent_price_rows(t, limit=RECENT_ROWS, db_path=db_path)
    return out


def _dates(rows_desc: list) -> dict[str, Any]:
    return {
        "end": rows_desc[0][0] if rows_desc else None,
        "start": {
            n: (rows_desc[n][0] if len(rows_desc) > n else None) for n in WINDOWS
        },
    }


def _flow_from_rows(rows_desc: list, bench_desc: list) -> dict[str, Any]:
    """날짜와 **같은 읽기**의 행으로 단기 흐름 값을 다시 구한다(설계 §10-2-1).

    산식은 builder 와 같은 `short_term_momentum._window_return_pct`(series[-(n+1)] → series[-1]) ·
    상태 규칙도 같다(종목 · KODEX200 모두 21행 이상이면 ok). 그래서 두 읽기 사이 자료가 바뀌지
    않았다면 builder 값과 같고, 바뀌었다면 이 읽기의 날짜와 맞는 값이 된다.
    """
    out: dict[str, Any] = {"status": "unavailable", **{k: None for k in _FLOW_KEYS}}
    if len(rows_desc) < RECENT_ROWS or len(bench_desc) < RECENT_ROWS:
        return out
    series = [(r[0], r[1]) for r in reversed(rows_desc)]
    bench = [(r[0], r[1]) for r in reversed(bench_desc)]
    out["status"] = "ok"
    for n in WINDOWS:
        r = _window_return_pct(series, n)
        b = _window_return_pct(bench, n)
        out[f"return_{n}d_pct"] = r
        out[f"excess_vs_kodex200_{n}d_pctp"] = (
            (r - b) if (r is not None and b is not None) else None
        )
    return out


def _short_term_note(stm: dict) -> Optional[str]:
    # holdings_market_evidence._build_evidence_notes 의 단기 흐름 한 줄과 같은 규칙 · 문구.
    status = stm.get("status")
    if status == "ok":
        v = stm.get("excess_vs_kodex200_20d_pctp")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f"20거래일 KODEX200 대비 단기 흐름 차이 {v:+.2f}%p."
        return None
    if status == "unavailable":
        return FLOW_SHORT_NOTE
    return None


def _replace_short_term_note(
    item: dict, old: Optional[str], new: Optional[str]
) -> None:
    """builder 가 만든 단기 흐름 한 줄(old)만 이 사본의 값에 맞는 줄(new)로 바꾼다."""
    notes = list(item.get("evidence_notes") or [])
    if old is not None and old in notes:
        i = notes.index(old)
        if new is None:
            notes.pop(i)
        else:
            notes[i] = new
    elif new is not None:
        # builder 순서: Market Discovery 후보 문구 다음이 단기 흐름 줄.
        notes.insert(min(1, len(notes)), new)
    item["evidence_notes"] = notes


def _normalize_item(item: dict, mine_rows: list, bench_rows: list) -> str:
    """판정 순서 = 기준일 비교 → 이력 길이 → 비교 기간(검증자 r1 · 판정 §9-4-2).

    | 종목 행 | KODEX200 행 | 기준일 | 비교 기간 | 결과 |
    |---|---|---|---|---|
    | 0 | 아무 | — | — | unavailable(저장 가격 없음) |
    | 1 이상 | 0 | — | — | unavailable(비교 기준일 없음) |
    | 1 이상 | 1 이상 | 다름 | — | date_mismatch(이력이 짧아도) |
    | 21 미만 또는 KODEX200 21 미만 | | 같음 | — | unavailable(이력 부족) |
    | 21 | 21 | 같음 | 같음 / 다름 | ok / window_mismatch |
    """
    builder_stm = item.get("short_term_momentum")
    builder_stm = builder_stm if isinstance(builder_stm, dict) else {}
    old_note = _short_term_note(builder_stm)
    mine = _dates(mine_rows)
    bench = _dates(bench_rows)
    stm = _flow_from_rows(mine_rows, bench_rows)
    if (
        mine["end"] is not None
        and bench["end"] is not None
        and mine["end"] != bench["end"]
    ):
        stm = {"status": "unavailable", **{k: None for k in _FLOW_KEYS}}
        comparison = COMPARISON_DATE_MISMATCH
        new_note: Optional[str] = None  # 사유는 price_dates(기준일 불일치)로 보인다
    elif stm["status"] != "ok":
        comparison = COMPARISON_UNAVAILABLE
        new_note = FLOW_SHORT_NOTE
    else:
        comparison = COMPARISON_OK
        for n in WINDOWS:
            if mine["start"][n] != bench["start"][n]:
                stm[f"excess_vs_kodex200_{n}d_pctp"] = None
                comparison = COMPARISON_WINDOW_MISMATCH
        new_note = _short_term_note(stm)
    item["short_term_momentum"] = {**builder_stm, **stm}
    _replace_short_term_note(item, old_note, new_note)
    return comparison


def apply_pc_price_basis(evidence: dict, rows_by_ticker: RowsByTicker) -> dict:
    """builder 결과의 깊은 사본에 가격 기준일 정정을 적용해 돌려준다(원본 불변).

    rows_by_ticker 는 `load_recent_price_rows` 결과(보유 종목 + KODEX200).
    """
    out = copy.deepcopy(evidence)
    holdings: list[dict] = out.get("holdings") or []
    bench = _dates(rows_by_ticker[KODEX200_TICKER])

    mismatched: list[dict] = []
    seen: set[str] = set()
    for item in holdings:
        ticker = item.get("ticker")
        mine_rows = rows_by_ticker[ticker]
        mine = _dates(mine_rows)
        comparison = _normalize_item(item, mine_rows, rows_by_ticker[KODEX200_TICKER])
        item["price_dates"] = {
            "end_date": mine["end"],
            "start_date_5d": mine["start"][5],
            "start_date_20d": mine["start"][20],
            "comparison": comparison,
        }
        if comparison == COMPARISON_DATE_MISMATCH and ticker not in seen:
            seen.add(ticker)
            mismatched.append(
                {"ticker": ticker, "name": item.get("name"), "end_date": mine["end"]}
            )

    out["price_basis"] = {
        "reference_date": bench["end"],
        "reference_ticker": KODEX200_TICKER,
        "kodex200_start_date_5d": bench["start"][5],
        "kodex200_start_date_20d": bench["start"][20],
        "date_mismatch": mismatched,
    }

    # builder 와 같은 규칙(수익률 · 단기 흐름 둘 다 unavailable)으로 고친 사본에서 다시 센다.
    summary = out.get("summary")
    if isinstance(summary, dict):
        summary["evidence_unavailable_count"] = sum(
            1
            for it in holdings
            if (it.get("returns") or {}).get("status") == "unavailable"
            and (it.get("short_term_momentum") or {}).get("status") == "unavailable"
        )

    judgment = out.get("judgment_summary")
    if isinstance(judgment, dict):
        judgment["holdings"] = summarize_holdings(holdings)
    return out
