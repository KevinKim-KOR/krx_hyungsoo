"""POC5-21 — PC 후보 수익률 · KODEX200 비교의 실제 계산 기간(사용한 저장 행 날짜).

설계 V1 §2 · §5-3 · PLAN 판정(2026-10-17 · Q1 (b) · Q2 (a) · Q3 (b) · §2 시험 보충).
격리 DB(tmp)만 쓴다. 날짜는 이미 읽은 행에서만 오고(추가 조회 0), 기본 호출 출력은 예전 그대로다.

종목(ETF):
- 111111 장기 — 2023-06-01 ~ 2026-10-14 매일
- 222222 늦게 상장 — 2026-08-01 ~ 2026-10-14 (3개월 이상은 첫 저장 행부터)
- 333333 끝이 이름 — 2026-07-01 ~ 2026-10-13 (시장 저장 최신일보다 하루 앞)
- 444444 행 1개 — 수익률 계산 불가(기존 제외 사유)
- 069500 KODEX200 — 2026-05-01 ~ 2026-10-14
"""

from __future__ import annotations

import copy
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, market_data_store, market_refresh_service
from app import market_topn as market_topn_module
from app.holdings_market_evidence import _build_short_term_payload
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    fetch_price_history,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_regime import compute_kodex200_metrics, kodex200_return_dates
from app.market_topn import _compute_period, compute_topn
from app.short_term_momentum import (
    compute_daily_return_check,
    compute_short_term_momentum,
    compute_short_term_momentum_batch,
)

END = date(2026, 10, 14)
PERIODS = (
    "daily",
    "one_month",
    "three_month",
    "six_month",
    "twelve_month",
    "three_year",
)
NEW_KEYS = {"price_start_date", "price_end_date"}
KODEX_KEYS = {"return_1m_start_date", "return_3m_start_date", "return_end_date"}


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _rows(
    ticker: str, start: date, end: date, base: float, step: float, gap: int = 0
) -> list:
    out = []
    for i, d in enumerate(_days(start, end)):
        if gap and i % gap == gap - 1 and d != end:
            continue  # 저장 안 된 날(후보와 KODEX200 의 행 날짜가 갈리게)
        c = round(base + step * i + (i % 7) * 0.3, 4)
        out.append(EtfDailyPriceRow(ticker, d.isoformat(), c, c, c, c, 1000 + i, 0))
    return out


def _seed(db: Path) -> None:
    upsert_etf_master(
        [
            EtfMasterRow("111111", "장기 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("222222", "늦게 상장 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("333333", "끝이 이른 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("444444", "행 하나 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1, 1.0),
        ],
        source="Test",
        db_path=db,
    )
    rows = (
        _rows("111111", date(2023, 6, 1), END, 100.0, 0.05)
        + _rows("222222", date(2026, 8, 1), END, 50.0, 0.4)
        + _rows("333333", date(2026, 7, 1), END - timedelta(days=1), 80.0, -0.1)
        + _rows("444444", END, END, 10.0, 0.0)
        + _rows("069500", date(2026, 5, 1), END, 300.0, 0.7, gap=6)
    )
    upsert_daily_prices(rows, source="Test", db_path=db)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "m.sqlite"
    _seed(p)
    return p


def _topn(db: Path, **kw) -> dict:
    kw.setdefault("n", 10)
    return compute_topn(
        db_path=db,
        exclude_inverse=False,
        exclude_leveraged=False,
        exclude_synthetic=False,
        exclude_futures=False,
        **kw,
    )


def _by_ticker(payload: dict) -> dict:
    return {c["ticker"]: c for c in payload["candidates"]}


def _closes(db: Path, ticker: str) -> dict[str, float]:
    return dict(fetch_price_history(ticker, db_path=db))


# ── 실제 선택 행 ↔ 수익률 ───────────────────────────────────────────────


def test_price_dates_are_the_rows_that_make_each_return(db: Path) -> None:
    pc = _topn(db, actual_price_dates=True)
    seen = 0
    for tk, c in _by_ticker(pc).items():
        closes = _closes(db, tk)
        last = max(closes)
        for label in PERIODS:
            r = c["returns"][label]
            if r is None:
                continue
            s, e = r["price_start_date"], r["price_end_date"]
            assert s in closes and e in closes
            # 그 두 종가로 같은 수익률이 다시 나온다.
            assert round((closes[e] / closes[s] - 1.0) * 100.0, 4) == r["return_pct"]
            assert e == last  # 끝 = 그 종목 마지막 저장 행
            assert r["basis_start_date"] == s
            assert (
                r["basis_end_date"] == pc["asof"]
            )  # 기존 필드 뜻(시장 저장 최신일) 그대로
            seen += 1
    assert seen >= 15


def test_daily_start_is_the_previous_stored_row(db: Path) -> None:
    pc = _by_ticker(_topn(db, actual_price_dates=True))
    for tk in ("111111", "222222", "333333"):
        dates = sorted(_closes(db, tk))
        d = pc[tk]["returns"]["daily"]
        assert (d["price_start_date"], d["price_end_date"]) == (dates[-2], dates[-1])


def test_same_end_different_start_for_late_listed_ticker(db: Path) -> None:
    pc = _by_ticker(_topn(db, actual_price_dates=True))
    late, longer = pc["222222"]["returns"], pc["111111"]["returns"]
    for label in ("three_month", "six_month", "twelve_month", "three_year"):
        assert late[label]["price_start_date"] == "2026-08-01"  # 첫 저장 행
        assert (
            late[label]["price_end_date"]
            == longer[label]["price_end_date"]
            == END.isoformat()
        )
        assert late[label]["price_start_date"] != longer[label]["price_start_date"]
    # 짧은 이력이면 기간이 달라도 같은 행 → 같은 값(기존 계산 그대로 · 새 판정 없음).
    assert late["six_month"]["return_pct"] == late["three_year"]["return_pct"]


def test_end_date_follows_the_end_row_not_market_latest(db: Path) -> None:
    pc = _topn(db, actual_price_dates=True)
    stale = _by_ticker(pc)["333333"]["returns"]["one_month"]
    assert pc["asof"] == END.isoformat()
    assert stale["price_end_date"] == (END - timedelta(days=1)).isoformat()
    assert stale["basis_end_date"] == END.isoformat()  # 예전 필드는 시장 저장 최신일


def test_end_date_unchanged_while_end_row_same_start_follows_selected_row(
    db: Path,
) -> None:
    """판정 §2 — 실제 끝 가격 행이 같으면 끝일 불변 · 시작일은 바뀐 선택 행을 따른다."""
    before = _by_ticker(_topn(db, actual_price_dates=True))
    newer = END + timedelta(days=3)
    upsert_daily_prices(
        _rows("222222", END + timedelta(days=1), newer, 90.0, 0.1),
        source="Test",
        db_path=db,
    )
    after_payload = _topn(db, actual_price_dates=True)
    after = _by_ticker(after_payload)
    assert after_payload["asof"] == newer.isoformat()
    for tk in ("111111", "333333"):
        b, a = before[tk]["returns"]["one_month"], after[tk]["returns"]["one_month"]
        assert a["price_end_date"] == b["price_end_date"]  # 같은 끝 행
        target = (newer - timedelta(days=30)).isoformat()
        first_on_or_after = min(d for d in _closes(db, tk) if d >= target)
        assert a["price_start_date"] == first_on_or_after  # 시작은 새 목표일의 행
        assert a["price_start_date"] != b["price_start_date"]


def test_missing_returns_keep_reasons_and_carry_no_dates(db: Path) -> None:
    pc = _topn(db, actual_price_dates=True)
    default = _topn(db)
    # 행 1개 종목은 예전처럼 계산 불가 → 후보에서 빠지고 제외 사유 수는 같다.
    assert "444444" not in _by_ticker(pc)
    assert pc["period_exclusions"] == default["period_exclusions"]
    assert pc["period_exclusions"]["one_month"]["insufficient_history"] >= 1
    # 계산 함수는 실패 시 끝일을 만들지 않는다(값 없음 = 날짜 없음).
    one_row = fetch_price_history("444444", db_path=db)
    r = _compute_period(one_row, END.isoformat(), 30)
    assert r.return_pct is None and r.end_date is None and r.base_date is None


# ── 기본 호출 불변 · 추가 조회 0 ─────────────────────────────────────────


def _strip_new(payload: dict) -> dict:
    out = copy.deepcopy(payload)
    out.pop("runtime_seconds", None)
    for c in out["candidates"]:
        for r in c["returns"].values():
            if r is not None:
                for k in NEW_KEYS:
                    r.pop(k, None)
    k200 = out["market_context"].get("kodex200") or {}
    for k in KODEX_KEYS:
        k200.pop(k, None)
    return out


def _has_new_key(obj) -> bool:
    if isinstance(obj, dict):
        return bool((NEW_KEYS | KODEX_KEYS) & set(obj)) or any(
            _has_new_key(v) for v in obj.values()
        )
    if isinstance(obj, list):
        return any(_has_new_key(v) for v in obj)
    return False


@pytest.mark.parametrize("basis", ["daily", "one_month", "three_month"])
@pytest.mark.parametrize("order", ["desc", "asc"])
def test_flag_off_is_unchanged_and_flag_only_adds_dates(
    db: Path, basis: str, order: str
) -> None:
    default = _topn(db, basis=basis, order=order)
    pc = _topn(db, basis=basis, order=order, actual_price_dates=True)
    assert not _has_new_key(default)  # 다른 호출 7곳이 받는 출력에 새 키 없음
    assert _has_new_key(pc)
    d = copy.deepcopy(default)
    d.pop("runtime_seconds", None)
    assert _strip_new(pc) == d  # 수익률 · 순서 · 선정 · 필터 · 나머지 전부 같음


def test_flag_adds_no_reads(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = market_topn_module.fetch_price_history

    def counting(ticker, *a, **kw):
        calls.append(ticker)
        return real(ticker, *a, **kw)

    monkeypatch.setattr(market_topn_module, "fetch_price_history", counting)
    _topn(db)
    off = list(calls)
    calls.clear()
    _topn(db, actual_price_dates=True)
    assert calls == off


def test_only_pc_screen_api_turns_the_flag_on() -> None:
    # 추적 여부와 무관하게 app · scripts 의 모든 .py 를 읽는다(띄어쓰기 변형 포함).
    root = Path(__file__).resolve().parents[1]
    pattern = re.compile(r"actual_price_dates\s*=\s*True")
    hits = sorted(
        str(f.relative_to(root))
        for d in ("app", "scripts")
        for f in (root / d).rglob("*.py")
        if pattern.search(f.read_text(encoding="utf-8"))
    )
    assert hits == ["app/api_market_topn.py"]


# ── KODEX200 비교 기간 ───────────────────────────────────────────────────


def test_kodex200_dates_are_the_rows_of_its_1m_3m_returns(db: Path) -> None:
    pc = _topn(db, actual_price_dates=True)
    k = pc["market_context"]["kodex200"]
    closes = _closes(db, "069500")
    assert k["return_end_date"] == max(closes)
    for key, start in (
        ("return_1m_pct", "return_1m_start_date"),
        ("return_3m_pct", "return_3m_start_date"),
    ):
        recomputed = round(
            (closes[k["return_end_date"]] / closes[k[start]] - 1.0) * 100.0, 2
        )
        assert recomputed == k[key]
    # 후보 1개월(달력 30일)과 KODEX200 1M(20행)은 이 자료에서 기간이 다르다(매일 저장).
    cand = _by_ticker(pc)["111111"]["returns"]["one_month"]
    assert cand["price_start_date"] != k["return_1m_start_date"]
    assert not KODEX_KEYS & set(_topn(db)["market_context"]["kodex200"])


def test_kodex200_dates_none_when_history_too_short() -> None:
    short = [
        ((date(2026, 9, 1) + timedelta(days=i)).isoformat(), 100.0 + i)
        for i in range(30)
    ]
    assert compute_kodex200_metrics(short)["status"] == "unavailable"
    assert kodex200_return_dates(short) == {k: None for k in KODEX_KEYS}
    # 0 이하 · 빈 종가는 그 함수와 같이 거른다.
    rows = [
        ((date(2026, 5, 1) + timedelta(days=i)).isoformat(), 100.0 + i)
        for i in range(70)
    ]
    rows.insert(-5, ("2026-07-07x", 0.0))
    dates = kodex200_return_dates(rows)
    good = [d for d, c in rows if c > 0]
    assert dates["return_1m_start_date"] == good[-21]
    assert dates["return_3m_start_date"] == good[-61]


# ── 단기 흐름 · 일간 점검 ────────────────────────────────────────────────


def test_short_term_kodex_dates_match_the_rows_used(db: Path) -> None:
    batch = compute_short_term_momentum_batch(
        ["111111", "222222", "333333"], db_path=db
    )
    bench = fetch_price_history("069500", db_path=db)
    for tk, m in batch.items():
        assert m.status == "ok"
        assert m.kodex200_end_date == bench[-1][0]
        for w, s, ks, got in (
            (
                5,
                m.start_date_5d,
                m.kodex200_start_date_5d,
                m.excess_vs_kodex200_5d_pctp,
            ),
            (
                10,
                m.start_date_10d,
                m.kodex200_start_date_10d,
                m.excess_vs_kodex200_10d_pctp,
            ),
            (
                20,
                m.start_date_20d,
                m.kodex200_start_date_20d,
                m.excess_vs_kodex200_20d_pctp,
            ),
        ):
            assert ks == bench[-(w + 1)][0]
            series = dict(fetch_price_history(tk, db_path=db))
            b = dict(bench)
            r = (series[m.end_date] / series[s] - 1.0) * 100.0
            br = (b[m.kodex200_end_date] / b[ks] - 1.0) * 100.0
            assert got == pytest.approx(r - br)
    # 끝이 이른 종목도 KODEX200 끝일은 KODEX200 마지막 행(후보 끝일로 바꾸지 않음).
    assert batch["333333"].end_date != batch["333333"].kodex200_end_date
    # 이 자료에서는 KODEX200 에 빠진 날이 있어 같은 '20행 앞'이라도 날짜가 다르다.
    assert batch["111111"].kodex200_start_date_20d != batch["111111"].start_date_20d
    single = compute_short_term_momentum("111111", db_path=db)
    assert single.kodex200_start_date_20d == batch["111111"].kodex200_start_date_20d
    assert single.kodex200_end_date == batch["111111"].kodex200_end_date


def test_holdings_evidence_short_term_payload_unchanged(db: Path) -> None:
    """보유 근거 API 는 필드를 하나씩 옮겨 담는다 — 새 KODEX200 날짜가 그 출력에 나가지 않는다."""
    m = compute_short_term_momentum_batch(["111111"], db_path=db)["111111"]
    payload = _build_short_term_payload(m)
    assert not any("kodex200_start" in k or k == "kodex200_end_date" for k in payload)


def test_daily_return_check_dates_are_last_two_rows(db: Path) -> None:
    d = compute_daily_return_check("111111", db_path=db)
    series = fetch_price_history("111111", db_path=db)
    assert (d.price_start_date, d.price_end_date) == (series[-2][0], series[-1][0])
    assert d.daily_return_pct == pytest.approx(
        (series[-1][1] - series[-2][1]) / series[-2][1] * 100.0
    )
    one = compute_daily_return_check("444444", db_path=db)
    assert one.status == "unavailable" and one.price_start_date is None


@pytest.mark.parametrize(
    "last_close, flag",
    [(115.0, "daily_surge_check_needed"), (85.0, "daily_drop_check_needed")],
)
def test_daily_return_check_warning_paths_carry_dates(
    tmp_path: Path, last_close: float, flag: str
) -> None:
    db = tmp_path / "w.sqlite"
    upsert_daily_prices(
        [
            EtfDailyPriceRow("555555", "2026-10-12", 90.0, 90.0, 90.0, 90.0, 1, 0),
            EtfDailyPriceRow("555555", "2026-10-13", 100.0, 100.0, 100.0, 100.0, 1, 0),
            EtfDailyPriceRow(
                "555555",
                "2026-10-14",
                last_close,
                last_close,
                last_close,
                last_close,
                1,
                0,
            ),
        ],
        source="Test",
        db_path=db,
    )
    d = compute_daily_return_check("555555", db_path=db)
    assert (d.status, d.flag) == ("warning", flag)
    assert (d.price_start_date, d.price_end_date) == ("2026-10-13", "2026-10-14")


# ── 시장 저장 최신일 = 가격 표 전체(보유 개별주 포함) ──────────────────


def test_stock_only_newer_moves_market_latest_not_candidate_end(db: Path) -> None:
    newer = (END + timedelta(days=1)).isoformat()
    upsert_daily_prices(
        [EtfDailyPriceRow("005930", newer, 1.0, 1.0, 1.0, 1.0, 1, 0)],
        source="Test",
        db_path=db,
    )
    pc = _topn(db, actual_price_dates=True)
    assert pc["asof"] == newer  # 보유 개별주 행이 시장 저장 최신일을 정한다
    tickers = {c["ticker"] for c in pc["candidates"]}
    assert "005930" not in tickers  # 후보는 ETF 목록에서만
    ends = {
        c["returns"]["one_month"]["price_end_date"]
        for c in pc["candidates"]
        if c["returns"]["one_month"]
    }
    assert (
        newer not in ends
    )  # 후보 끝일은 각자 마지막 행(시장 저장 최신일로 채우지 않음)


# ── PC 화면 API ──────────────────────────────────────────────────────────


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing(db_path=fake_db)
    return TestClient(api_module.app)


def test_pc_screen_api_carries_all_period_dates(api_client: TestClient) -> None:
    _seed(api_market_topn.DEFAULT_DB_PATH)
    p = api_client.get(
        "/market/topn/latest",
        params={
            "exclude_inverse": False,
            "exclude_leveraged": False,
            "exclude_synthetic": False,
            "exclude_futures": False,
        },
    ).json()
    c = {x["ticker"]: x for x in p["candidates"]}["111111"]
    assert c["returns"]["one_month"]["price_start_date"]
    assert c["returns"]["one_month"]["price_end_date"] == END.isoformat()
    assert c["returns"]["one_month"]["basis_end_date"] == p["asof"]
    k = p["market_context"]["kodex200"]
    assert (
        k["return_1m_start_date"] and k["return_3m_start_date"] and k["return_end_date"]
    )
    stm = c["short_term_momentum"]
    bench = fetch_price_history("069500", db_path=api_market_topn.DEFAULT_DB_PATH)
    assert stm["kodex200_start_dates"] == {
        "five_d": bench[-6][0],
        "ten_d": bench[-11][0],
        "twenty_d": bench[-21][0],
    }
    assert stm["kodex200_end_date"] == END.isoformat()
    drc = c["data_quality"]["daily_return_check"]
    assert (drc["price_start_date"], drc["price_end_date"]) == (
        (END - timedelta(days=1)).isoformat(),
        END.isoformat(),
    )
