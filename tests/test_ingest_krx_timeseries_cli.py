"""scripts/ingest_krx_timeseries.py CLI 자동 테스트 (2026-06-30).

외부 네트워크 / 실제 KRX 자료 없이 fixture CSV 로 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.market_data_store import (
    EtfMasterRow,
    fetch_price_history,
    init_db,
    upsert_etf_master,
)
from app.market_timeseries_ingestion_store import (
    STATUS_NORMAL,
    STATUS_SOURCE_MISSING,
    read_state,
)
from scripts.ingest_krx_timeseries import main as cli_main


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def _seed_universe(db: Path, tickers: list[str]) -> None:
    upsert_etf_master(
        [
            EtfMasterRow(
                ticker=tk,
                name=f"NAME_{tk}",
                category="1",
                price=None,
                volume=None,
                market_cap=None,
            )
            for tk in tickers
        ],
        source="TEST",
        db_path=db,
    )


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("종목코드,일자,종가\n", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(r[h] for h in headers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_cli_benchmark_kodex200(fake_db: Path, tmp_path: Path) -> None:
    csv_path = tmp_path / "kodex200.csv"
    _write_csv(
        csv_path,
        [
            {"종목코드": "069500", "일자": "20241029", "종가": "100"},
            {"종목코드": "069500", "일자": "20241030", "종가": "101"},
            {"종목코드": "069500", "일자": "20241031", "종가": "102"},
        ],
    )
    rc = cli_main(
        [
            "benchmark",
            "--csv",
            str(csv_path),
            "--benchmark-id",
            "069500",
            "--benchmark-name",
            "KODEX 200",
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc == 0
    series = fetch_price_history("069500", db_path=fake_db)
    assert len(series) == 3
    state = read_state("069500", db_path=fake_db)
    assert state is not None
    assert state.ingestion_status == STATUS_NORMAL
    assert state.price_basis == "raw_close"


def test_cli_etf_skips_already_normal(fake_db: Path, tmp_path: Path) -> None:
    """두 번 실행해도 (ticker, date) PK 로 중복 0건 (재개)."""
    _seed_universe(fake_db, ["069500", "379800"])
    # 먼저 KODEX200 benchmark 적재 (벤치마크 달력 확보) — 그래야 ETF normal 가능.
    bench_csv = tmp_path / "kodex.csv"
    _write_csv(
        bench_csv,
        [
            {"종목코드": "069500", "일자": "2024-10-29", "종가": "100.5"},
            {"종목코드": "069500", "일자": "2024-10-30", "종가": "101.5"},
        ],
    )
    cli_main(
        [
            "benchmark",
            "--csv",
            str(bench_csv),
            "--benchmark-id",
            "069500",
            "--benchmark-name",
            "KODEX 200",
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    csv_path = tmp_path / "etf.csv"
    _write_csv(
        csv_path,
        [
            {"종목코드": "069500", "일자": "2024-10-29", "종가": "100.5"},
            {"종목코드": "069500", "일자": "2024-10-30", "종가": "101.5"},
            {"종목코드": "379800", "일자": "2024-10-29", "종가": "200"},
            {"종목코드": "379800", "일자": "2024-10-30", "종가": "210"},
        ],
    )
    rc = cli_main(
        [
            "etf",
            "--csv",
            str(csv_path),
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc == 0
    rc2 = cli_main(
        [
            "etf",
            "--csv",
            str(csv_path),
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc2 == 0
    # 두 번째 실행 후 데이터 중복 없음 (동일 값 ON CONFLICT 흡수).
    series = fetch_price_history("069500", db_path=fake_db)
    assert len(series) == 2


def test_cli_etf_source_missing_when_ticker_absent_from_csv(
    fake_db: Path, tmp_path: Path
) -> None:
    """SQLite universe 에는 있지만 CSV 에는 없는 ticker → source_missing."""
    _seed_universe(fake_db, ["069500", "999999"])
    csv_path = tmp_path / "etf.csv"
    _write_csv(
        csv_path,
        [{"종목코드": "069500", "일자": "2024-10-29", "종가": "100"}],
    )
    rc = cli_main(
        [
            "etf",
            "--csv",
            str(csv_path),
            "--price-basis",
            "raw_close",
            "--ticker",
            "999999",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc == 0
    state = read_state("999999", db_path=fake_db)
    assert state is not None
    assert state.ingestion_status == STATUS_SOURCE_MISSING


def test_cli_etf_rejects_ticker_not_in_universe(fake_db: Path, tmp_path: Path) -> None:
    """SQLite universe 에 없는 ticker 는 --ticker 로 지정해도 거부."""
    _seed_universe(fake_db, ["069500"])
    csv_path = tmp_path / "etf.csv"
    _write_csv(
        csv_path,
        [{"종목코드": "888888", "일자": "2024-10-29", "종가": "100"}],
    )
    rc = cli_main(
        [
            "etf",
            "--csv",
            str(csv_path),
            "--price-basis",
            "raw_close",
            "--ticker",
            "888888",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc == 2
    state = read_state("888888", db_path=fake_db)
    assert state is None


def test_cli_etf_rejects_when_universe_empty(fake_db: Path, tmp_path: Path) -> None:
    """SQLite etf_master 가 비어 있으면 CLI 가 즉시 거부 (지시문 §7)."""
    csv_path = tmp_path / "etf.csv"
    _write_csv(
        csv_path,
        [{"종목코드": "069500", "일자": "2024-10-29", "종가": "100"}],
    )
    rc = cli_main(
        [
            "etf",
            "--csv",
            str(csv_path),
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc == 2


def test_cli_etf_rejects_ticker_when_universe_empty(
    fake_db: Path, tmp_path: Path
) -> None:
    """FIX r2 — --ticker 경로도 universe 비어있을 때 거부 (가드 일관)."""
    csv_path = tmp_path / "etf.csv"
    _write_csv(
        csv_path,
        [{"종목코드": "069500", "일자": "2024-10-29", "종가": "100"}],
    )
    rc = cli_main(
        [
            "etf",
            "--csv",
            str(csv_path),
            "--price-basis",
            "raw_close",
            "--ticker",
            "069500",
            "--db-path",
            str(fake_db),
        ]
    )
    assert rc == 2
    state = read_state("069500", db_path=fake_db)
    assert state is None  # 적재 시작 안 됨


def test_cli_status_command(fake_db: Path, tmp_path: Path, capsys) -> None:
    rc = cli_main(["status", "--db-path", str(fake_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ingestion_status counts" in out
    assert "normal: 0" in out


def test_cli_output_is_ascii_safe(fake_db: Path, tmp_path: Path, capsys) -> None:
    """FIX r2 — Windows 콘솔 (cp949 등) 에서 CLI 출력이 인코딩 가능해야 한다.

    em dash / 화살표 같은 비ASCII 문자가 출력 메시지에 섞이면 Windows 기본
    콘솔에서 UnicodeEncodeError 로 종료된다. 모든 stdout / stderr 출력이
    ASCII 만 사용해야 한다.
    """
    _seed_universe(fake_db, ["069500"])
    # KODEX200 benchmark CSV + etf CSV 로 전체 출력 경로를 한 번 돌린다.
    bench_csv = tmp_path / "kodex.csv"
    _write_csv(
        bench_csv,
        [
            {"종목코드": "069500", "일자": "2024-10-29", "종가": "100"},
            {"종목코드": "069500", "일자": "2024-10-30", "종가": "101"},
        ],
    )
    cli_main(
        [
            "benchmark",
            "--csv",
            str(bench_csv),
            "--benchmark-id",
            "069500",
            "--benchmark-name",
            "KODEX 200",
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    etf_csv = tmp_path / "etf.csv"
    _write_csv(
        etf_csv,
        [
            {"종목코드": "069500", "일자": "2024-10-29", "종가": "100"},
            {"종목코드": "069500", "일자": "2024-10-30", "종가": "101"},
        ],
    )
    cli_main(
        [
            "etf",
            "--csv",
            str(etf_csv),
            "--price-basis",
            "raw_close",
            "--db-path",
            str(fake_db),
        ]
    )
    cli_main(["status", "--db-path", str(fake_db)])
    captured = capsys.readouterr()
    # stdout / stderr 모두 ASCII 만 사용 — Windows cp949 등으로 인코딩 가능.
    captured.out.encode("ascii")
    captured.err.encode("ascii")
