"""POC6-26 — KODEX200 2025 1주 검산 도구의 순수 함수 시험(가상 숫자 · 라이브 DB · 네트워크 0).

통합설계 V1.1 · 재개 판정 V1.2 §2: 권리 = T+2 결제일 < 지급기준일(같으면 경계 확인) · 실지급일 ≤ D1(미확인 · 넘김 = 자료 미충족)
· A · B 공통 원가 상쇄 뒤 원 단위 정확 검산 · 입력 형식 미충족이면 계산하지 않음.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts import run_kodex200_distribution_check as M

SETTLE = "2025-01-06"
D1 = "2025-12-30"


def _row(basic, pay, amount=100):
    return {"basic_date": basic, "pay_date": pay, "amount_krw": amount}


CLASSIFY = [
    ("결제일보다 앞선 기준일", _row("2024-10-31", "2024-11-04"), M.NOT_ENTITLED_BEFORE),
    (
        "매입일 다음 · 결제일 앞",
        _row("2025-01-03", "2025-01-07"),
        M.NOT_ENTITLED_BEFORE,
    ),
    ("결제일 = 기준일", _row("2025-01-06", "2025-01-08"), M.BOUNDARY_CHECK),
    ("결제일 < 기준일 · 지급 ≤ D1", _row("2025-01-31", "2025-02-04"), M.INCLUDED),
    ("기준일 = D1 · 지급 미확인", _row("2025-12-30", None), M.PAY_UNKNOWN),
    ("기준일 ≤ D1 · 지급 > D1", _row("2025-12-29", "2026-01-02"), M.PAY_AFTER_D1),
    ("지급 = D1", _row("2025-12-26", "2025-12-30"), M.INCLUDED),
    ("기준일 > D1", _row("2026-01-30", "2026-02-03"), M.AFTER_PERIOD),
]


@pytest.mark.parametrize("label,row,want", CLASSIFY, ids=[c[0] for c in CLASSIFY])
def test_classify_rights_and_payment_boundaries(label, row, want) -> None:
    assert M.classify(row, SETTLE, D1) == want


def test_settlement_date_counts_trading_days_on_calendar() -> None:
    cal = ["2024-12-30", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    assert M.settlement_date(cal, "2025-01-02") == "2025-01-06"  # 주말 건너뜀
    with pytest.raises(M.InputError):
        M.settlement_date(cal, "2025-01-06")  # 달력 밖


def test_ledger_exact_check_and_returns() -> None:
    book = M.ledger(Decimal(10000), Decimal(11000), 1.0, 1.12, cash=300, recount=300)
    e = Decimal(10000) * Decimal("1.002")
    assert Decimal(book["start_cost_e"]) == e == Decimal("10020.000")
    assert book["amount_gap_krw"] == "300"
    assert book["exact_check"] is True
    assert Decimal(book["A"]) == Decimal(11000) / e - 1
    assert Decimal(book["B"]) == Decimal(11300) / e - 1
    assert Decimal(book["C"]) == Decimal(repr(1.12)) / Decimal("1.002") - 1
    assert abs(Decimal(book["B_minus_A_pp"]) - Decimal(300) / e * 100) < Decimal(
        "1e-30"
    )
    assert abs(Decimal(book["b_minus_a_vs_cash_over_e"])) < Decimal("1e-30")
    bad = M.ledger(Decimal(10000), Decimal(11000), 1.0, 1.12, cash=300, recount=299)
    assert bad["exact_check"] is False


def _doc(rows=None, **over):
    doc = {
        "schema": M.SCHEMA,
        "product": {"code": "069500", "fid": "2ETF01", "name": "KODEX 200"},
        "source": {
            "page_url": "https://example.invalid/page",
            "download_url": "https://example.invalid/file",
            "downloaded_at": "2026-11-08T00:00:00+00:00",
            "http_status": 200,
            "file_sha256": "a" * 64,
            "file_type": "가상",
            "read_method": "가상",
        },
        "rows": rows
        or [
            _row("2024-10-31", "2024-11-04", 10),
            _row("2025-01-31", "2025-02-04", 11),
            _row("2025-04-30", "2025-05-07", 12),
            _row("2025-07-31", "2025-08-04", 13),
            _row("2025-10-31", "2025-11-04", 14),
            _row("2026-01-30", "2026-02-03", 15),
        ],
        "coverage": {"file_year_rows": 4},
        "factsheet": {
            "url": "https://example.invalid/fs.pdf",
            "fetched_at": "2026-11-08T00:00:00+00:00",
            "file_sha256": "b" * 64,
            "page": 2,
            "rows_2025": 4,
            "match": True,
        },
    }
    for k, v in over.items():
        doc[k] = v
    return doc


def _write(tmp_path: Path, doc) -> Path:
    p = tmp_path / "official_rows.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def test_load_official_accepts_six_rows_and_recount_matches_classify(
    tmp_path: Path,
) -> None:
    p = _write(tmp_path, _doc())
    inp = M.load_official(p)
    assert len(inp["rows"]) == 6
    cash = sum(
        r["amount_krw"] for r in inp["rows"] if M.classify(r, SETTLE, D1) == M.INCLUDED
    )
    assert cash == 11 + 12 + 13 + 14
    assert M.recount_cash(p, SETTLE, D1) == cash


def _bad(mut):
    doc = _doc()
    mut(doc)
    return doc


BAD = [
    ("schema", lambda d: d.update(schema="x")),
    ("종목 코드", lambda d: d["product"].update(code="069660")),
    ("상품 id", lambda d: d["product"].update(fid="2ETF02")),
    ("금액 소수", lambda d: d["rows"][1].update(amount_krw=11.0)),
    ("금액 불", lambda d: d["rows"][1].update(amount_krw=True)),
    ("금액 음수", lambda d: d["rows"][1].update(amount_krw=-1)),
    ("날짜 형식", lambda d: d["rows"][1].update(basic_date="2025-1-31")),
    ("없는 날짜", lambda d: d["rows"][1].update(pay_date="2025-02-30")),
    ("정렬", lambda d: d["rows"].reverse()),
    ("중복", lambda d: d["rows"].insert(2, dict(d["rows"][1]))),
    ("연간 전체 아님", lambda d: d["coverage"].update(file_year_rows=5)),
    ("인접 회차 없음", lambda d: d["rows"].pop(0)),
    ("팩트시트 쪽", lambda d: d["factsheet"].update(page="2")),
    ("팩트시트 일치 칸", lambda d: d["factsheet"].update(match="yes")),
    ("해시 형식", lambda d: d["source"].update(file_sha256="xyz")),
    ("출처 없음", lambda d: d["source"].pop("download_url")),
]


@pytest.mark.parametrize("label,mut", BAD, ids=[b[0] for b in BAD])
def test_load_official_rejects_bad_input(tmp_path: Path, label, mut) -> None:
    with pytest.raises(M.InputError):
        M.load_official(_write(tmp_path, _bad(mut)))


def _raw(day, close, cmpprev, shrs=1000.0):
    return {
        "date": day,
        "code": "069500",
        "close": Decimal(close),
        "cmpprev": Decimal(cmpprev),
        "list_shrs": shrs,
    }


def test_unit_checks_explains_gap_before_record_date_only() -> None:
    cal = ["2025-01-23", "2025-01-24", "2025-01-31", "2025-02-03"]
    raw = [
        _raw("2025-01-23", 100, 0),
        _raw(
            "2025-01-24", 99, 0
        ),  # 기준가 99 ≠ 전일 100 → 다음 거래일 01-31 = 지급기준일 → 설명됨
        _raw("2025-01-31", 99, 0),
        _raw(
            "2025-02-03", 98, 0
        ),  # 기준가 98 ≠ 전일 99 → 다음 거래일 없음 → 설명 안 됨
    ]
    out = M.unit_checks(raw, [_row("2025-01-31", "2025-02-04")], cal)
    assert [g["date"] for g in out["base_price_gap_days"]] == [
        "2025-01-24",
        "2025-02-03",
    ]
    assert out["unexplained_gap_days"] == ["2025-02-03"]
    assert out["list_shrs_split_suspicious_days"] == 0


def test_unit_checks_flags_share_count_jump() -> None:
    cal = ["2025-01-02", "2025-01-03"]
    raw = [_raw("2025-01-02", 100, 0, 1000.0), _raw("2025-01-03", 100, 0, 2500.0)]
    out = M.unit_checks(raw, [], cal)
    assert out["list_shrs_split_suspicious_days"] == 1
    assert out["unexplained_gap_days"] == []


def test_run_stops_without_reading_sealed_db_on_bad_input(tmp_path: Path) -> None:
    _write(tmp_path, _bad(lambda d: d["product"].update(code="069660")))
    rep = M.run(tmp_path, db_path=tmp_path / "없는_봉인판.sqlite")
    assert rep["status"] == M.INSUFFICIENT
    assert rep["reasons"][0].startswith("입력:")
    assert (tmp_path / "report.json").exists() and (tmp_path / "report.md").exists()
    assert (
        json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))["status"]
        == M.INSUFFICIENT
    )
    with pytest.raises(SystemExit):
        M.run(tmp_path, db_path=tmp_path / "없는_봉인판.sqlite")  # 한 번만
