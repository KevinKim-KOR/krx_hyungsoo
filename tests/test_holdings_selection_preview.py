"""POC3-OPS-01A — 미발송 preview 계약 test (T-17).

검증자 r1 지적: preview 자동검증이 없었다. 시점 모순·발송 여부·저장 위치를
테스트로 고정한다. 합성 SQLite + tmp_path 만 사용한다.
"""

from __future__ import annotations

import json
import sqlite3

from scripts.build_holdings_selection_preview import BASIS, build_preview, main


def _make_db(path, tickers, *, base=100.0, last=85.0, n=30):
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE etf_daily_price (ticker TEXT, date TEXT, close REAL,"
        " PRIMARY KEY (ticker, date))"
    )
    for t in tickers:
        for i in range(n):
            close = last if i == n - 1 else base
            con.execute(
                "INSERT INTO etf_daily_price VALUES (?,?,?)",
                (t, f"2026-06-{i + 1:02d}", close),
            )
    con.commit()
    con.close()


def _make_holdings(path, rows):
    path.write_text(json.dumps({"holdings": rows}, ensure_ascii=False), "utf-8")


def _setup(tmp_path):
    db = tmp_path / "market.sqlite"
    hold = tmp_path / "holdings.json"
    _make_db(db, ["AAA", "BBB"])
    _make_holdings(
        hold,
        [
            {"ticker": "AAA", "name": "가나다", "account_group": "일반"},
            {"ticker": "AAA", "name": "가나다", "account_group": "ISA"},
            {"ticker": "BBB", "name": "라마바", "account_group": "일반"},
        ],
    )
    return db, hold


def test_t17_preview_declares_close_proxy_and_is_not_sent(tmp_path):
    db, hold = _setup(tmp_path)
    p = build_preview(basis_date="2026-06-30", db_path=db, holdings_path=hold)
    assert p["basis"] == BASIS == "EOD_CLOSE_PROXY"
    assert p["telegram_sent"] is False
    assert p["basis_date"] == "2026-06-30"


def test_t17_preview_header_has_no_execution_time(tmp_path):
    """`09:14` 같은 실행시각을 쓰면 과거 OPEN 재현이라고 주장하는 셈이다."""
    db, hold = _setup(tmp_path)
    body = build_preview(basis_date="2026-06-30", db_path=db, holdings_path=hold)[
        "message_text"
    ]
    assert "형식 미리보기" in body
    assert "과거 종가 기준: 2026-06-30" in body
    for token in ("09:14", "09:15", "12:30", "15:40"):
        assert token not in body, f"실행시각 {token} 노출"


def test_t17_preview_does_not_claim_run_time_before_basis_date(tmp_path):
    """실행시각이 데이터 기준일보다 이르다고 주장하지 않는다."""
    db, hold = _setup(tmp_path)
    p = build_preview(basis_date="2026-06-30", db_path=db, holdings_path=hold)
    assert p["generated_at_kst"][:10] >= p["basis_date"]


def test_t17_preview_has_no_disclaimer_copy(tmp_path):
    db, hold = _setup(tmp_path)
    body = build_preview(basis_date="2026-06-30", db_path=db, holdings_path=hold)[
        "message_text"
    ]
    for phrase in ("매도·교체·비중 조절", "매매 지시", "이 알림은"):
        assert phrase not in body


def test_t17_preview_dedups_accounts_and_keeps_all_selected(tmp_path):
    db, hold = _setup(tmp_path)
    p = build_preview(basis_date="2026-06-30", db_path=db, holdings_path=hold)
    assert p["holdings_record_count"] == 3
    assert p["unique_ticker_count"] == 2
    assert p["selected_count"] == 2
    assert p["message_text"].count("가나다") == 1
    assert "(2개 계좌)" in p["message_text"]


def test_t17_preview_writes_only_under_previews_dir(tmp_path):
    """운영 상태와 디렉터리를 분리한다."""
    db, hold = _setup(tmp_path)
    out = tmp_path / "previews"
    rc = main(
        [
            "--basis-date",
            "2026-06-30",
            "--db",
            str(db),
            "--holdings",
            str(hold),
            "--out-dir",
            str(out),
        ]
    )
    assert rc == 0
    written = list(out.glob("*.json"))
    assert len(written) == 1
    assert written[0].name == "holdings_selection_preview_latest.json"
    saved = json.loads(written[0].read_text(encoding="utf-8"))
    assert saved["telegram_sent"] is False
    assert saved["basis"] == "EOD_CLOSE_PROXY"
