"""POC3-OPS-01A — 보유 브리핑 **형식 미리보기** 생성 (발송 없음).

현재 시점 `RECENT_DECLINE` 이 0건일 수 있어, 구현 후 아무 메시지도 오지 않으면
사용자가 형식을 확인할 수 없다. 과거 종가로 선정 로직을 그대로 돌려 **본문
문자열만** 만든다.

계약 (PLAN §3.3):
  - **Telegram 을 호출하지 않는다.**
  - 과거 장중 현재가는 저장돼 있지 않으므로 **종가를 분자로 쓴다.**
    이는 실제 OPEN 재현이 아니다 → `basis = EOD_CLOSE_PROXY` 로 명시한다.
  - 헤더에 실행시각(`09:14` 등)을 쓰지 않는다. 기준일만 적는다.
  - 산출물은 운영 상태와 **디렉터리를 분리**한다 (`state/three_push/previews/`).
  - 운영 메시지에는 이 설명을 넣지 않는다 (preview 전용).

실행:
  python scripts/build_holdings_selection_preview.py --basis-date 2026-06-30
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.runtime_evidence.holdings_selection import (  # noqa: E402
    LOOKBACK_TRADING_DAYS,
    TRADING_DAY_AXIS_TICKER,
    select_holdings,
)
from app.runtime_evidence.holdings_selection_source import (  # noqa: E402
    average_buy_prices,
)
from app.runtime_evidence.holdings_selection_render import (  # noqa: E402
    PREVIEW_HEADER,
    render_groups,
)

BASIS = "EOD_CLOSE_PROXY"
PREVIEW_DIR = _PROJECT_ROOT / "state" / "three_push" / "previews"
PREVIEW_PATH = PREVIEW_DIR / "holdings_selection_preview_latest.json"
DEFAULT_DB = _PROJECT_ROOT / "state" / "market" / "market_data.sqlite"
DEFAULT_HOLDINGS = _PROJECT_ROOT / "state" / "holdings" / "holdings_latest.json"
KST = timezone(timedelta(hours=9))


class _CloseQuote:
    """과거 종가를 현재가 자리에 넣는 proxy. 실제 장중 시세가 아니다."""

    def __init__(self, close: float, date: str):
        self.current_price = close
        self.price_asof = f"{date}T15:30:00+09:00"


def _load_holdings(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("holdings") or raw.get("items") or []


def _history_upto(
    con: sqlite3.Connection, ticker: str, basis_date: str
) -> list[tuple[str, float]]:
    cur = con.execute(
        "SELECT date, close FROM etf_daily_price "
        "WHERE ticker = ? AND close IS NOT NULL AND close > 0 AND date <= ? "
        "ORDER BY date ASC",
        (ticker, basis_date),
    )
    return [(r[0], float(r[1])) for r in cur.fetchall()]


def build_preview(
    *,
    basis_date: str,
    db_path: Path = DEFAULT_DB,
    holdings_path: Path = DEFAULT_HOLDINGS,
) -> dict[str, Any]:
    holdings = _load_holdings(holdings_path)
    tickers = sorted({h["ticker"] for h in holdings if h.get("ticker")})

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        history = {t: _history_upto(con, t, basis_date) for t in tickers}
        # 설계자 확정 2026-09-05 — 기준일은 거래일 축에서 고른다.
        axis_dates = [
            d for d, _ in _history_upto(con, TRADING_DAY_AXIS_TICKER, basis_date)
        ]
    finally:
        con.close()

    quotes: dict[str, Any] = {}
    for t, rows in history.items():
        if rows and rows[-1][0] == basis_date:
            quotes[t] = _CloseQuote(rows[-1][1], basis_date)

    # basis_date 를 '실행일' 로 두면 기준일은 그보다 앞선 20번째 거래일이 되고,
    # 분자는 basis_date 종가가 된다 (EOD_CLOSE_PROXY 의 정의 그대로).
    selected = select_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes=quotes,
        today_kst=basis_date,
        axis_dates=axis_dates,
        avg_buy_prices=average_buy_prices(holdings),
    )
    body = "\n".join(
        [PREVIEW_HEADER, f"과거 종가 기준: {basis_date}", "", *render_groups(selected)]
    ).rstrip()

    return {
        "schema_version": "holdings_selection_preview.v1",
        "basis": BASIS,
        "basis_date": basis_date,
        "generated_at_kst": datetime.now(timezone.utc)
        .astimezone(KST)
        .strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "note": (
            "과거 장중 현재가가 저장돼 있지 않아 종가를 분자로 사용했다. "
            "실제 OPEN·MIDDAY 재현이 아니다. 형식 확인 전용이며 발송하지 않는다."
        ),
        "lookback_trading_days": LOOKBACK_TRADING_DAYS,
        "holdings_record_count": len(holdings),
        "unique_ticker_count": len(tickers),
        "selected_count": len(selected),
        "selected": [
            {
                "ticker": i.ticker,
                "name": i.name,
                "account_count": i.account_count,
                "reasons": i.reasons,
                "drawdown_20d_pct": i.drawdown_20d_pct,
            }
            for i in selected
        ],
        "message_text": body,
        "message_text_length": len(body),
        "telegram_sent": False,
    }


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="보유 브리핑 형식 미리보기 (발송 없음)")
    p.add_argument("--basis-date", required=True, help="과거 종가 기준일 YYYY-MM-DD")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--db", default=None)
    p.add_argument("--holdings", default=None)
    args = p.parse_args(argv)

    payload = build_preview(
        basis_date=args.basis_date,
        db_path=Path(args.db) if args.db else DEFAULT_DB,
        holdings_path=Path(args.holdings) if args.holdings else DEFAULT_HOLDINGS,
    )
    out_dir = Path(args.out_dir) if args.out_dir else PREVIEW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / PREVIEW_PATH.name
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(payload["message_text"])
    print()
    print(
        json.dumps(
            {
                "basis": payload["basis"],
                "basis_date": payload["basis_date"],
                "selected_count": payload["selected_count"],
                "message_text_length": payload["message_text_length"],
                "telegram_sent": payload["telegram_sent"],
                "out_path": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
