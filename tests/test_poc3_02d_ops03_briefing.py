"""POC3-02D-OPS-03 — 08:30 시장 흐름 브리핑 · 국내 T-1 정확 일치 · 배치 실패 고지.

설계자 PLAN 판정(2026-09-29) 확정 계약 1 · 5 · 6 · 13 · PLAN STEP 3-7~9 · STEP 7-3.
검증 시나리오 4(T-2 만) · 9(한국 휴장일) · 10(하루 가격 누락) · 12(재실행 중복 발송 없음).

**외부 조회 0건 · 라이브 DB · state · logs 미접근** — 전부 `tmp_path` 다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import trading_day_lag
from app.market_briefing import flow, krx_store, meta_gate, render
from app.three_push_runtime import runner_market_briefing as mb

TODAY = "2026-09-18"  # 금요일
T1 = "2026-09-17"
T2 = "2026-09-16"
AXIS = (
    [f"2026-08-{d:02d}" for d in (3, 4, 5, 6, 7, 10, 11, 12, 13, 14)]
    + [f"2026-08-{d:02d}" for d in (18, 19, 20, 21, 24, 25, 26, 27, 28, 31)]
    + [f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)]
)
TICKERS = ("069500", "102110")
DESIGNER_LINE = "국내 기초지수는 직전 거래일 자료를 확인하지 못해 제외했습니다."
STALE_LINE = render.INDEX_NOTICE["stale"]


def _axis_before(day: str) -> list[str]:
    return [d for d in AXIS if d <= day]


def _setup(
    tmp_path: Path,
    *,
    stored: list[str],
    judged_for: str | None = T1,
    closes: dict[str, float] | None = None,
    **verdict,
) -> Path:
    """`stored` 날짜를 적재하고, `judged_for` 창(거래일 날짜 창)의 판정을 남긴다."""
    db = tmp_path / "krx.sqlite"
    closes = closes or {}
    for d in stored:
        bas = d.replace("-", "")
        px = str(closes.get(d, 11000.0 if d >= "2026-09-11" else 10000.0))
        rows = [{"ISU_CD": t, "BAS_DD": bas, "TDD_CLSPRC": px} for t in TICKERS]
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(rows, expected_date=bas), db_path=db
        )
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(AXIS) + "\n", encoding="utf-8"
    )
    (tmp_path / "official.csv").write_bytes(
        (
            "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법,"
            "한글종목약명\n"
            "069500,코스피200,KRX,주식,일반,실물(패시브),KODEX 200\n"
            "102110,코스피200,KRX,주식,일반,실물(패시브),TIGER 200\n"
        ).encode("cp949")
    )
    if judged_for is not None:
        window = krx_store.resolve_calendar_window(
            judged_for, calendar_dir=tmp_path, db_path=db
        )
        fields = dict(
            status=meta_gate.STATUS_OK,
            api_ticker_count=2,
            csv_ticker_count=2,
            exact_match_count=2,
            join_coverage=1.0,
            evaluated_api_basis_date=judged_for.replace("-", ""),
            evaluated_window_d20_date=window.d20,
            evaluated_at_kst=f"{TODAY}T08:10:40+09:00",
        )
        fields.update(verdict)
        meta_gate.save_consistency(
            meta_gate.ConsistencyResult(**fields), tmp_path / "c.json"
        )
    return db


def _assemble(
    tmp_path: Path,
    *,
    today: str = TODAY,
    sp500: float | None = 1.2,
    fresh: bool = True,
    batch_failure=(),
) -> flow.BriefingOutcome:
    return flow.assemble_market_briefing(
        today_kst=today,
        runtime_kst=f"{today}T08:30:00+09:00",
        state_path=tmp_path / "state.json",
        consistency_path=tmp_path / "c.json",
        official_csv_path=tmp_path / "official.csv",
        sp500_return_pct=sp500,
        sp500_asof=T1,
        sp500_fresh=fresh,
        calendar_dir=tmp_path,
        db_path=tmp_path / "krx.sqlite",
        batch_failure=batch_failure,
    )


# ── 머리 · T-1 정확 일치 (확정 계약 1 · 6) ─────────────────────────────────────


def test_header_is_0830():
    assert render.HEADER == "[시장 흐름 브리핑] 08:30"


def test_t1_present_shows_index_with_t1_basis(tmp_path):
    _setup(tmp_path, stored=_axis_before(T1))
    out = _assemble(tmp_path)
    assert out.diagnostics["index_status"] == "ok", out.diagnostics
    body = out.message_text
    assert body.splitlines()[0] == "[시장 흐름 브리핑] 08:30"
    assert "오늘 볼 기초지수" in body
    assert f"국내 {T1} 종가" in body
    assert DESIGNER_LINE not in body


def test_t2_only_omits_index_with_designer_line_and_no_t2_leak(tmp_path):
    """시나리오 4 — T-2 만 있다. 옛 lag ≤ 1 은 통과시켰다(아래 첫 assert)."""
    assert (
        trading_day_lag.window_lag_trading_days(
            T2, today_kst=TODAY, calendar_dir=_write_axis(tmp_path)
        )
        == 1
    ), "옛 관문이 T-2 를 통과시켰다는 전제가 깨졌다"
    _setup(tmp_path, stored=_axis_before(T2), judged_for=T2)
    out = _assemble(tmp_path)
    assert out.diagnostics["index_status"] == render.STATUS_PREV_DAY_MISSING
    d = out.diagnostics["index_diagnostics"]
    assert d == {
        "reason": "basis_date_not_expected",
        "expected_previous_trading_day": T1,
        "actual_basis_date": T2,
    }
    body = out.message_text
    assert out.should_send
    assert render.SENTENCE_UP in body, "미국 전망은 정상 조건이면 발송한다"
    assert DESIGNER_LINE in body
    assert f"미국 {T1} 종가" in body
    for leak in (T2, "국내 20", "오늘 볼 기초지수", "5일", "20일", "코스피200"):
        assert leak not in body, (leak, body)
    assert out.fingerprint == "UP#NONE"


def _write_axis(tmp_path: Path) -> Path:
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(AXIS) + "\n", encoding="utf-8"
    )
    return tmp_path


def test_basis_later_than_expected_is_not_fresh(tmp_path):
    """정확 일치다 — 기대 T-1 보다 뒤 날짜(당일 행)도 정상이 아니다."""
    _setup(tmp_path, stored=_axis_before(TODAY), judged_for=TODAY)
    out = _assemble(tmp_path)
    assert out.diagnostics["index_status"] == render.STATUS_PREV_DAY_MISSING
    assert out.diagnostics["index_diagnostics"]["actual_basis_date"] == TODAY


def test_korean_holiday_expected_day_skips_the_holiday(tmp_path):
    """시나리오 9 — 달력의 휴장일(08-17 대체공휴일)은 건너뛴다: 08-18 의 T-1 = 08-14."""
    _write_axis(tmp_path)
    assert (
        trading_day_lag.expected_previous_trading_day(
            "2026-08-18", calendar_dir=tmp_path
        )
        == "2026-08-14"
    )


def test_t1_missing_wins_over_unusable_csv(tmp_path):
    """T-1 부재를 CSV 갱신 필요로 잘못 안내하지 않는다(국내 기준일 확인이 맨 앞)."""
    _setup(tmp_path, stored=_axis_before(T2), judged_for=T2)
    (tmp_path / "meta").mkdir()
    out = flow.assemble_market_briefing(
        today_kst=TODAY,
        runtime_kst=None,
        state_path=tmp_path / "state.json",
        consistency_path=tmp_path / "c.json",
        meta_dir=tmp_path / "meta",  # 유효 CSV 없음
        sp500_return_pct=1.0,
        sp500_asof=T1,
        sp500_fresh=True,
        calendar_dir=tmp_path,
        db_path=tmp_path / "krx.sqlite",
    )
    assert out.diagnostics["index_status"] == render.STATUS_PREV_DAY_MISSING
    assert render.INDEX_NOTICE[meta_gate.STATUS_CSV_REFRESH_REQUIRED] not in (
        out.message_text
    )


def test_no_t1_verdict_is_not_used_and_csv_notice_not_appended(tmp_path):
    """T-2 판정의 `refresh_due` 를 T-1 없는 날에 쓰지 않는다(R2 Q24 · Q27 과 같은 취지)."""
    _setup(
        tmp_path,
        stored=_axis_before(T2),
        judged_for=T2,
        refresh_due=True,
        refresh_due_reason=meta_gate.REFRESH_REASON_PENDING,
        refresh_due_cycle_id="20260916",
    )
    out = _assemble(tmp_path)
    assert render.CSV_REFRESH_NOTICE not in out.message_text
    assert out.refresh_notice_cycle_id is None


# ── 거래일 날짜 창 (확정 계약 5 · 시나리오 10) ──────────────────────────────────


def _window_dates(tmp_path: Path) -> tuple[str, str, str]:
    return trading_day_lag.trading_window_dates(T1, calendar_dir=_write_axis(tmp_path))


def test_missing_d5_date_fails_closed_instead_of_shifting(tmp_path):
    latest, d5, d20 = _window_dates(tmp_path)
    stored = [d for d in _axis_before(T1) if d != d5]
    _setup(tmp_path, stored=stored)
    # 옛 행 위치 창이면 d5 가 하루 더 앞(6거래일 전)으로 밀린다.
    old = krx_store.resolve_window(db_path=tmp_path / "krx.sqlite")
    assert old is not None and old.d5 != d5
    out = _assemble(tmp_path)
    assert out.diagnostics["index_status"] == "stale"
    diag = out.diagnostics["index_diagnostics"]
    assert diag["reason"] == "window_missing_days"
    assert diag["missing_required"] == [d5] and diag["usable"] is False
    assert STALE_LINE in out.message_text
    assert "오늘 볼 기초지수" not in out.message_text
    assert "국내 20" not in out.message_text


def test_missing_non_required_day_keeps_calendar_d20_value(tmp_path):
    """계산에 안 쓰는 날이 빠져도 d5 · d20 은 **날짜로** 정해진다(값이 밀리지 않는다)."""
    latest, d5, d20 = _window_dates(tmp_path)
    gap = "2026-09-02"
    assert gap not in (latest, d5, d20) and d20 < gap < d5
    closes = {d: 10500.0 for d in AXIS}
    closes.update({latest: 11000.0, d5: 10000.0, d20: 9000.0})
    stored = [d for d in _axis_before(T1) if d != gap]
    _setup(tmp_path, stored=stored, closes=closes)
    out = _assemble(tmp_path)
    assert out.diagnostics["index_status"] == "ok", out.diagnostics
    body = out.message_text
    # 11000 / 10000 = +10.0% · 11000 / 9000 = +22.2% (행 위치로 밀렸으면 20일 = +4.8%).
    assert "5일 +10.0% · 20일 +22.2%" in body, body


def test_verdict_for_row_position_window_is_meta_gate_stale(tmp_path):
    """판정 창 d20 이 거래일 날짜 d20 과 다르면 저장 판정을 쓰지 않는다(08:10 과 같은 창)."""
    _latest, _d5, d20 = _window_dates(tmp_path)
    _setup(tmp_path, stored=_axis_before(T1), evaluated_window_d20_date="2026-08-12")
    assert d20 != "2026-08-12"
    out = _assemble(tmp_path)
    assert out.diagnostics["index_status"] == meta_gate.STATUS_META_GATE_STALE
    assert out.diagnostics["index_diagnostics"]["reason"] == "window_d20_mismatch"


# ── 배치 실패 고지 (확정 계약 13 · PLAN STEP 7-3) ──────────────────────────────


@pytest.mark.parametrize(
    "state,reasons",
    [
        (None, ["batch_state_missing"]),
        ({"refresh_date_kst": "2026-09-17", "status": "success"}, ["batch_not_today"]),
        (
            {"refresh_date_kst": TODAY, "status": "failed", "stage_status": {}},
            ["batch_failed"],
        ),
        # POC3-02D-OPS-04 Q2 a — FDR 가격 단계 실패 · 건너뜀은 고지하지 않는다(기록만).
        (
            {"refresh_date_kst": TODAY, "stage_status": {"fdr_price": "failed"}},
            [],
        ),
        (
            {
                "refresh_date_kst": TODAY,
                "status": "failed",
                "stage_status": {"fdr_price": "skipped", "collect": "failed"},
            },
            [],
        ),
        # 넣지 않는 것 — KOSPI · VIX · IXIC · SOX · US500 · KRX 실패(자기 줄 · PC 전용).
        (
            {
                "refresh_date_kst": TODAY,
                "status": "success_with_benchmark_failure",
                "benchmark_status": "failed",
                "benchmark_failed": ["KOSPI", "VIX", "IXIC", "SOX", "US500"],
                "stage_status": {"fdr_price": "ok", "benchmark": "failed"},
                "krx_sync_status": "target_not_obtained",
            },
            [],
        ),
        (
            {
                "refresh_date_kst": TODAY,
                "status": "success",
                "stage_status": {"fdr_price": "ok", "krx": "pending"},
            },
            [],
        ),
        ({"refresh_date_kst": TODAY, "status": "success"}, []),  # 옛 상태 파일
    ],
)
def test_batch_failure_reasons_inputs_are_limited(state, reasons):
    assert mb.batch_failure_reasons(state, TODAY) == reasons


def test_batch_failure_state_file_is_read(tmp_path):
    p = tmp_path / "bs.json"
    assert mb._batch_failure(TODAY, p) == ["batch_state_missing"]
    p.write_text(
        json.dumps({"refresh_date_kst": TODAY, "stage_status": {"fdr_price": "ok"}}),
        encoding="utf-8",
    )
    assert mb._batch_failure(TODAY, p) == []
    p.write_text("{not json", encoding="utf-8")
    assert mb._batch_failure(TODAY, p) == ["batch_state_missing"]


def test_batch_notice_is_appended_last_before_csv_notice(tmp_path):
    _setup(
        tmp_path,
        stored=_axis_before(T1),
        refresh_due=True,
        refresh_due_reason=meta_gate.REFRESH_REASON_PENDING,
        refresh_due_cycle_id="20260917",
    )
    plain = _assemble(tmp_path)
    failed = _assemble(tmp_path, batch_failure=["batch_not_today"])
    assert failed.message_text.endswith(
        f"\n\n{render.BATCH_FAILURE_NOTICE}\n\n{render.CSV_REFRESH_NOTICE}"
    )
    core = plain.message_text[: -len(render.CSV_REFRESH_NOTICE) - 2]
    assert failed.message_text.startswith(core)
    assert failed.fingerprint == plain.fingerprint, "고지가 fingerprint 를 바꿨다"
    assert failed.diagnostics["batch_failure_notice"] == {
        "reasons": ["batch_not_today"],
        "appended": True,
        "notice_only": False,
    }
    assert failed.message_text.count(render.BATCH_FAILURE_NOTICE) == 1


def test_notice_only_body_when_nothing_else_to_send(tmp_path):
    """전망 불가 + T-1 없음 → 예전에는 미발송. 배치 실패면 고지 1줄만 담아 보낸다."""
    _setup(
        tmp_path,
        stored=_axis_before(T2),
        judged_for=T2,
        refresh_due=True,
        refresh_due_cycle_id="20260916",
    )
    out = _assemble(
        tmp_path, sp500=None, fresh=False, batch_failure=["batch_not_today"]
    )
    assert out.should_send
    assert out.message_text == f"{render.HEADER}\n\n{render.BATCH_FAILURE_NOTICE}"
    assert DESIGNER_LINE not in out.message_text
    assert render.CSV_REFRESH_NOTICE not in out.message_text
    assert out.diagnostics["would_skip_reason"] == flow.REASON_ALL_STALE
    assert out.diagnostics["batch_failure_notice"]["notice_only"] is True
    assert out.fingerprint == "NONE#NONE"


def test_notice_only_body_has_no_csv_notice_while_refresh_cycle_is_live(tmp_path):
    """T-1 있음 · d5 빠짐(구역 `stale`) · 판정 `refresh_due` · 전망 불가 · 배치 실패.

    위 T-2 경우는 `PREV_DAY_MISSING` 이 CSV 안내 주기를 먼저 막는다. 여기서는 주기가
    살아 있다 — 고지만 담은 본문에는 그래도 붙이지 않는다(PLAN STEP 7-3 · 다음 실제
    본문에 붙는다 · 안내 주기를 소진하지 않는다).
    """
    _latest, d5, _d20 = _window_dates(tmp_path)
    _setup(
        tmp_path,
        stored=[d for d in _axis_before(T1) if d != d5],
        refresh_due=True,
        refresh_due_reason=meta_gate.REFRESH_REASON_PENDING,
        refresh_due_cycle_id="20260917",
    )
    out = _assemble(
        tmp_path, sp500=None, fresh=False, batch_failure=["batch_not_today"]
    )
    assert out.diagnostics["index_status"] == "stale"
    assert out.diagnostics["batch_failure_notice"]["notice_only"] is True
    assert out.message_text == f"{render.HEADER}\n\n{render.BATCH_FAILURE_NOTICE}"
    assert out.diagnostics["refresh_notice"]["appended"] is False
    assert out.refresh_notice_cycle_id is None


def test_fdr_failure_alone_no_longer_sends_notice_only_body(tmp_path):
    """POC3-02D-OPS-04 Q2 a — 전망 불가 + T-1 없음인 날 FDR 단계만 실패했으면 예전에는
    고지만 담은 본문을 보냈다. 이제 고지 사유가 아니라서 보내지 않는다(발송 1건 → 0건)."""
    _setup(tmp_path, stored=_axis_before(T2), judged_for=T2)
    reasons = mb.batch_failure_reasons(
        {
            "refresh_date_kst": TODAY,
            "status": "failed",
            "stage_status": {"fdr_price": "failed", "krx": "ok"},
        },
        TODAY,
    )
    assert reasons == []
    out = _assemble(tmp_path, sp500=None, fresh=False, batch_failure=reasons)
    assert out.skip_reason == flow.REASON_ALL_STALE
    assert out.message_text == "" and not out.should_send
    assert out.diagnostics["batch_failure_notice"]["notice_only"] is False


def test_nothing_to_send_without_batch_failure_still_skips(tmp_path):
    _setup(tmp_path, stored=_axis_before(T2), judged_for=T2)
    out = _assemble(tmp_path, sp500=None, fresh=False)
    assert out.skip_reason == flow.REASON_ALL_STALE
    assert out.message_text == "" and out.fingerprint == ""


def test_batch_notice_once_per_day_through_runner(tmp_path, monkeypatch):
    """시나리오 12 — 같은 날 재실행은 registry 가 막는다 → 고지는 하루 1번."""
    from tests.test_market_briefing_flow_through import NEXT_TRADING, _install

    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    monkeypatch.setattr(mb, "_batch_failure", lambda *_a, **_k: ["batch_not_today"])
    first = runner.run("market_briefing", "send")
    again = runner.run("market_briefing", "send")
    assert first["status"] == "sent", first
    assert first["batch_failure_notice"]["reasons"] == ["batch_not_today"]
    assert again["reason"] == "duplicate_runtime"
    assert len(sent) == 1 and sent[0].count(render.BATCH_FAILURE_NOTICE) == 1

    # 다음 거래일 · 배치 정상 → 고지 없음(같은 원인을 끌고 가지 않는다).
    from tests.test_market_briefing_flow_through import _advance_window

    monkeypatch.setattr(runner, "kst_today_date", lambda: NEXT_TRADING)
    _advance_window(tmp_path, state_dir)
    monkeypatch.setattr(mb, "_batch_failure", lambda *_a, **_k: [])
    assert runner.run("market_briefing", "send")["status"] == "sent"
    assert render.BATCH_FAILURE_NOTICE not in sent[1]


@pytest.mark.parametrize(
    "state,reasons",
    [
        # POC3-02D-OPS-04 Q2 a — FDR 단계만 실패한 날은 고지가 붙지 않는다.
        (
            {
                "refresh_date_kst": TODAY,
                "status": "failed",
                "stage_status": {"fdr_price": "failed", "krx": "ok"},
            },
            [],
        ),
        # 배치가 안 돈 날(오늘 기록 아님)은 그대로 고지한다.
        ({"refresh_date_kst": "2026-09-17", "status": "success"}, ["batch_not_today"]),
    ],
    ids=["fdr_failed_no_notice", "batch_not_today_notice"],
)
def test_runner_assemble_reads_batch_state_path(tmp_path, monkeypatch, state, reasons):
    """`assemble(batch_state_path=…)` → 실제 파일 판정이 본문까지 이어진다."""
    _setup(tmp_path, stored=_axis_before(T1))
    monkeypatch.setattr(mb, "_sp500_input", lambda _t, **_k: (1.0, T1, True))
    real_flow = flow.assemble_market_briefing
    monkeypatch.setattr(
        flow,
        "assemble_market_briefing",
        lambda **kw: real_flow(**{**kw, "calendar_dir": tmp_path}),
    )
    meta = tmp_path / "meta"
    meta.mkdir()
    bs = tmp_path / "bs.json"
    bs.write_text(json.dumps(state), encoding="utf-8")
    record: dict = {}
    out = mb.assemble(
        record,
        push_kind=mb.PUSH_KIND,
        today_kst=TODAY,
        runtime_kst=f"{TODAY}T08:30:00+09:00",
        state_dir=tmp_path,
        meta_dir=meta,
        db_path=tmp_path / "krx.sqlite",
        batch_state_path=bs,
    )
    assert record["batch_failure_notice"]["reasons"] == reasons
    assert out.message_text.endswith(render.BATCH_FAILURE_NOTICE) is bool(reasons)
