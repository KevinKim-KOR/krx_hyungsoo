"""POC7-04 관심 ETF 한 건의 주간 판단 근거와 AI 검토 — 맥북 로컬 연구 CLI(PLAN V1 · 판정 2026-11-24).

```text
serve [--port P] [--end D] [--no-open]   연구 서버(127.0.0.1 전용) — 화면 · 저장 · 다시 열기 · 브라우저 열기
page --ticker T [--end D]                 한 장만 만들기(저장 안 되는 파일 · 복사는 됨)
```
읽기 = PC 시세 DB · 공식 기준정보 · 판단 근거 DB(읽기 전용) · 쓰기 = state/ml/research/poc7_04/ 만 · 외부 조회 0.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.candidate_compare import current as CU  # noqa: E402
from app.entry_timing.protocol import new_id, real_root, write_once  # noqa: E402
from app.weekly_decision import evidence as E  # noqa: E402
from app.weekly_decision import history as H  # noqa: E402
from app.weekly_decision import page_live as PL  # noqa: E402
from app.weekly_decision import server as SV  # noqa: E402
from app.weekly_decision import store as ST  # noqa: E402

MARKET_DB = REPO / "state" / "market" / "market_data.sqlite"
DECISION_DB = REPO / "state" / "decision" / "decision_evidence.sqlite"
ROOT = REPO / "state" / "ml" / "research" / "poc7_04"
WEEKLY_FILTERS = {
    "exclude_inverse": True,
    "exclude_leveraged": True,
    "exclude_synthetic": True,
    "exclude_futures": True,
}
DEFAULT_PORT = 8770


def _sources() -> tuple:
    from app import api_etf_compare as AE

    official, state = AE._official()
    dictionary, _ = AE._dictionary()
    # 공식 기준정보를 못 읽으면 None — 빈 목록을 넘기면 '이 ETF 가 공식 기준정보에 없다'로 판정돼 버림
    return (official if state.get("status") == "ok" else None), dictionary


def _app(end: str | None) -> SV.App:
    return SV.App(
        db=MARKET_DB,
        decision_db=DECISION_DB,
        root=real_root(ROOT),
        end=end,
        filters=WEEKLY_FILTERS,
        sources=_sources,
        reader=CU.default_reader(MARKET_DB),
    )


def cmd_serve(port: int, end: str | None, open_browser: bool) -> int:
    app = _app(end)
    print("자료 준비 중 — 이번 주 후보와 지난 네 주 복원(약 15초)", flush=True)
    ctx = app.context()
    httpd = SV.serve(app, port)
    url = f"http://127.0.0.1:{port}/"
    print(
        f"검토 기준일 {ctx.end} · 지난 네 주 {', '.join(ctx.rows) or '없음'}",
        flush=True,
    )
    print(f"열기: {url}  (끄기: Ctrl+C)", flush=True)
    print(
        "저장하지 않은 입력은 쓰던 창에만 임시로 남습니다 — 서버를 다시 켰다면 쓰던 창에서 새로 고치세요"
        "(새로 열리는 창에는 그 입력이 없음).",
        flush=True,
    )
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("연구 서버를 껐습니다.", flush=True)
    finally:
        httpd.server_close()
    return 0


def cmd_page(ticker: str, end: str | None) -> int:
    official, dictionary = _sources()
    ctx = H.load_context(
        MARKET_DB, end, filters=WEEKLY_FILTERS, official=official, dictionary=dictionary
    )
    root = real_root(ROOT)
    listing = ST.list_reviews(root)
    rv = E.compose(
        ctx,
        ticker,
        sessions=H.read_sessions(DECISION_DB),
        reviews=listing["items"],
        reader=CU.default_reader(MARKET_DB),
        cutoff=H.cutoff_of(end, ctx.end, CU.now_kst()),
        reviews_broken=len(listing["broken"]),
    )
    html = PL.render_live(rv, build_id=None, candidates=[], reviews=[])
    path = root / "pages" / f"{ctx.end}_{ticker}_{new_id(CU.now_kst())}.html"
    write_once(root, path, html.encode("utf-8"))
    print(f"한 장: {path}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--end", default=None)
    s.add_argument("--no-open", action="store_true")
    p = sub.add_parser("page")
    p.add_argument("--ticker", required=True)
    p.add_argument("--end", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "serve":
        return cmd_serve(a.port, a.end, not a.no_open)
    return cmd_page(a.ticker, a.end)


if __name__ == "__main__":
    raise SystemExit(main())
