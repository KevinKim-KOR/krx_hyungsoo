"""POC5-05 개정 2 — 이동평균 · 보유 기간 계산(app/holdings_book · 순수 함수 · 파일 0).

설계 §3 계산 예 · §11-2 날짜 순서 예 · §11-1 Q-E 입력 정정 · §6 기간 충돌.
"""

from __future__ import annotations

import ast
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from app import holdings_book as book

_N = 0


def _rec(kind, payload, *, cycle="C1", position="P1", supersedes=None):
    global _N
    _N += 1
    return {
        "record_id": f"R{_N}",
        "kind": kind,
        "position_id": position,
        "cycle_id": cycle,
        "supersedes_id": supersedes,
        "recorded_at": f"2026-10-08T10:{_N:02d}:00+09:00",
        "payload": payload,
    }


def _trade_payload(day, price, qty, seq):
    return {
        "trade_date": day,
        "trade_time": None,
        "price": price,
        "quantity": qty,
        "amount": book.exact_product(price, qty),
        "memo": None,
        "seq": seq,
    }


def buy(day, price, qty, seq=0, **kw):
    return _rec("BUY", _trade_payload(day, price, qty, seq), **kw)


def sell(day, price, qty, seq=0, **kw):
    return _rec("SELL", _trade_payload(day, price, qty, seq), **kw)


def adj(day, seq=99, **payload):
    cycle = payload.pop("cycle", "C1")
    return _rec(
        "ADJUSTMENT", {"effective_date": day, "seq": seq, **payload}, cycle=cycle
    )


def baseline(qty, avg, **kw):
    return _rec("BASELINE", {"quantity": qty, "avg_buy_price": avg}, **kw)


def doc(records, positions=None):
    return {
        "schema_version": 2,
        "revision": 1,
        "holdings": [],
        "personal_trade_history": {
            "positions": positions
            or [
                {
                    "position_id": "P1",
                    "ticker": "069500",
                    "account_group": "ISA",
                    "name": "KODEX 200",
                }
            ],
            "records": records,
        },
    }


def D(x):
    return Decimal(x)


def test_design_section3_example_exact():
    rs = [
        baseline("10", "10000"),
        buy("2026-10-06", "12000", "5"),
        sell("2026-10-07", "13000", "6"),
        sell("2026-10-08", "10000", "9"),
    ]
    cy = book.replay_cycle(rs)
    ev = cy["events"]
    assert (ev[1]["q_after"], ev[1]["c_after"]) == (D(15), D(160000))
    assert str(ev[1]["avg_after"]).startswith("10666.66666666")
    assert (ev[2]["cost_of_sold"], ev[2]["realized_pnl"], ev[2]["realized_rate"]) == (
        D(64000),
        D(14000),
        D("21.875"),
    )
    assert (ev[2]["q_after"], ev[2]["c_after"], ev[2]["avg_after"]) == (
        D(9),
        D(96000),
        ev[1]["avg_after"],
    )
    assert ev[3]["realized_pnl"] == D(-6000) and ev[3]["c_after"] == 0
    assert cy["status"] == "CLOSED" and cy["closed_by"] == "SELL"
    assert (cy["realized"], cy["sold_cost"]) == (D(8000), D(160000))
    assert cy["realized"] / cy["sold_cost"] * 100 == D(
        5
    )  # 합/합 — 개별 수익률 평균 아님


def test_section11_2_real_date_order_for_buy_started_cycle():
    first = buy("2026-10-08", "10000", "10")  # 먼저 입력했지만 날짜가 늦다
    rs = [
        first,
        buy("2026-10-07", "20000", "5", seq=0),
        sell("2026-10-07", "30000", "2", seq=1),
    ]
    cy = book.replay_cycle(rs)
    s = next(e for e in cy["events"] if e["record"]["kind"] == "SELL")
    assert (s["cost_of_sold"], s["realized_pnl"]) == (D(40000), D(20000))
    assert (cy["q"], cy["c"]) == (D(13), D(160000))
    assert cy["opened_by"] == "BUY" and cy["start_date"] == "2026-10-07"


def test_first_buy_date_correction_and_void_recompute():
    first = buy("2026-10-08", "10000", "10")
    later = [buy("2026-10-07", "20000", "5"), sell("2026-10-07", "30000", "2", seq=1)]
    moved = buy("2026-10-06", "10000", "10", supersedes=first["record_id"])
    eff = book.effective_records([first, *later, moved])
    cy = book.replay_cycle(eff)
    s = next(e for e in cy["events"] if e["record"]["kind"] == "SELL")
    with localcontext() as ctx:  # 계산과 같은 정밀도(40)
        ctx.prec = book.PREC
        expected = D(2) * D(200000) / D(15)
    assert s["cost_of_sold"] == expected  # 이제 10-06 매수가 먼저
    void = _rec("VOID", {}, supersedes=first["record_id"])
    cy2 = book.replay_cycle(book.effective_records([first, *later, void]))
    assert (cy2["q"], cy2["c"]) == (D(3), D(60000))


def test_oversell_and_closed_mid_cycle_are_refused():
    with pytest.raises(book.BookError, match="잔량"):
        book.replay_cycle(
            [buy("2026-10-01", "100", "1"), sell("2026-10-02", "100", "2")]
        )
    with pytest.raises(book.BookError, match="보유가 0"):
        book.replay_cycle(
            [
                buy("2026-10-01", "100", "1"),
                sell("2026-10-02", "100", "1"),
                buy("2026-10-03", "100", "1"),
            ]
        )
    with pytest.raises(book.BookError):
        book.replay_cycle([sell("2026-10-01", "100", "1")])


def test_adjustment_sets_balance_and_backdated_trade_does_not_change_it():
    rs = [
        baseline("10", "10000"),
        adj("2026-10-08", quantity="12", avg_buy_price="9500"),
    ]
    cy = book.replay_cycle(rs)
    assert (cy["q"], cy["c"], cy["has_adjustment"]) == (D(12), D(114000), True)
    rs.append(buy("2026-10-07", "20000", "5"))  # 정정보다 앞 날짜로 나중에 넣은 매수
    cy = book.replay_cycle(rs)
    assert (cy["q"], cy["c"]) == (D(12), D(114000))  # 정정 뒤 잔고는 확정값
    assert cy["events"][1]["record"]["kind"] == "BUY"  # 정정 전 경로에는 반영


def test_zero_adjustment_closes_without_sell_or_pnl():
    rs = [
        baseline("10", "10000"),
        sell("2026-10-06", "12000", "4"),
        adj("2026-10-08", quantity="0", avg_buy_price="10000"),
    ]
    cy = book.replay_cycle(rs)
    assert cy["status"] == "CLOSED" and cy["closed_by"] == "ADJUSTMENT"
    assert cy["realized"] == D(8000)  # 이미 발생한 매도 계산은 그대로
    assert "realized_pnl" not in cy["events"][-1]  # 정정 자체는 손익 대상 아님
    assert cy["sold_cost"] == D(40000)  # SELL 집계에 정정 없음


def test_name_only_adjustment_changes_display_only():
    rs = [
        baseline("3", "71200"),
        adj("2026-10-08", name="삼성전자우", before={"name": "삼성전자"}),
    ]
    d = doc(rs)
    cy = book.replay_cycle(rs)
    assert (cy["q"], cy["c"], cy["has_adjustment"]) == (D(3), D(213600), False)
    out = book.compute(d)
    assert out["holdings"][0]["name"] == "삼성전자우"
    assert out["holdings"][0]["avg_buy_price"] == 71200.0


def test_rebuy_cycle_does_not_carry_cost_and_boundary_checks():
    c1 = [
        buy("2026-09-01", "10000", "10", cycle="C1"),
        sell("2026-09-10", "11000", "10", cycle="C1"),
    ]
    c2 = [buy("2026-10-01", "20000", "1", cycle="C2")]
    out = book.compute(doc(c1 + c2))
    pos = out["positions"][0]
    assert [c["status"] for c in pos["cycles"]] == ["CLOSED", "OPEN"]
    assert (
        out["holdings"][0]["avg_buy_price"] == 20000.0
        and out["holdings"][0]["cycle_id"] == "C2"
    )
    early = buy("2026-09-05", "20000", "1", cycle="C2")
    with pytest.raises(book.BookError, match="이전 보유 기간 종료일"):
        book.compute(doc(c1 + [early]))
    reopened = c1[:1] + c2  # C1 의 매도가 빠져 다시 열림 + 뒤 기간 존재
    with pytest.raises(book.BookError, match="다시 열려"):
        book.compute(doc(reopened))


def test_fractional_and_loss_and_float_baseline_precision():
    cy = book.replay_cycle(
        [
            buy("2026-10-01", "100.5", "0.5"),
            buy("2026-10-02", "99.25", "0.25"),
            sell("2026-10-03", "90", "0.75"),
        ]
    )
    assert (
        cy["q"] == 0
        and cy["realized"] < 0
        and cy["realized"] == D("67.5") - D("75.0625")
    )
    b = book.replay_cycle([baseline("0.1234567", "35000.123456789")])
    assert b["q"] == D("0.1234567")  # 기준잔고는 새 입력 자릿수 한도를 소급하지 않는다
    out = book.compute(doc([baseline(repr(0.1 + 0.2), repr(1 / 3))]))
    assert out["holdings"][0]["quantity"] == 0.1 + 0.2
    assert (
        out["holdings"][0]["avg_buy_price"] == 1 / 3
    )  # C/Q 가 입력 평단을 그대로 되돌린다


def test_next_seq_after_and_before():
    rs = [buy("2026-10-07", "1", "1", seq=0), buy("2026-10-07", "1", "1", seq=3)]
    assert book.next_seq(rs, "C1", "2026-10-07", before=False) == 4
    assert book.next_seq(rs, "C1", "2026-10-07", before=True) == -1
    assert book.next_seq(rs, "C1", "2026-10-06", before=False) == 0


def test_module_is_pure():
    tree = ast.parse(Path(book.__file__).read_text(encoding="utf-8"))
    mods = {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    mods |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {
        "__future__",
        "decimal",
        "typing",
        "re",
        "datetime",
        "math",
    }  # 표준 라이브러리만


def test_same_day_seq_decides_order_not_input_order():
    # 같은 날 매도를 먼저 입력하고 그 앞(seq 작음)에 매수를 끼워 넣은 경우
    s = sell("2026-10-07", "13000", "2", seq=1)
    b = buy("2026-10-07", "10000", "5", seq=0)
    cy = book.replay_cycle([s, b])
    assert [e["record"]["kind"] for e in cy["events"]] == ["BUY", "SELL"]
    assert cy["events"][1]["realized_pnl"] == D(6000)


def test_fmt_and_exact_product_never_round():
    big = Decimal("15241578753238767078092381604.29703552")
    assert (
        book.fmt(big) == "15241578753238767078092381604.29703552"
    )  # 기본 문맥(28)에서도
    assert book.exact_product("123456789012345.67", "123456789012345.123456") == (
        "15241578753238767078092381604.29703552"
    )
    # 자릿수가 많아도(전량매도 = 기존 기준잔고 정밀도 그대로) 곱은 정확하다 — 독립 계산과 같다.
    with localcontext() as ctx:
        ctx.prec = 200
        expected = Decimal("1" * 30) * Decimal("0." + "7" * 40)
    assert book.exact_product("1" * 30, "0." + "7" * 40) == format(expected, "f")


def test_cycle_boundary_uses_latest_end_of_all_earlier_cycles():
    # 종료일 없는 기간이 끼어도 경계를 건너뛰지 않는다(앞선 모든 기간의 가장 늦은 종료일).
    def cy(cid, status, first, end):
        ev = {"record": {"record_id": f"r-{cid}"}}
        return {
            "cycle_id": cid,
            "status": status,
            "first_date": first,
            "end_date": end,
            "events": [ev],
        }

    cycles = [
        cy("A", "CLOSED", "2026-10-01", "2026-10-05"),
        cy("B", "CLOSED", None, None),
        cy("C", "OPEN", "2026-10-02", None),
    ]
    with pytest.raises(book.BookError, match="2026-10-05"):
        book._check_cycles(cycles)
    cycles[2]["first_date"] = "2026-10-05"  # 같은 날은 허용
    book._check_cycles(cycles)
