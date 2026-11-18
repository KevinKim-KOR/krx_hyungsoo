"""POC6-32 V2 — 공통 시장 근거(`GET /market/evidence`) · 공식 기준정보 경로(`GET /market/etf-official`) 시험.

PLAN §4-1 · §4-2 · §6 · §9 I-16 · I-23 · I-24 확인:
1. 화면 이식(사건 문장 · 아침/당일 같은 근거 한 번) = 화면과 같은 고정 자료(`fixtures/poc6_32_evidence_cases.json`).
2. 임시 시장 DB(합성 값)로 실제 시장 흐름 조립을 돌려 일일 글 순서 · 첫머리 · 근거 줄 = 일일 글 줄 · 코스피 시작 종가
   출처 · 기대 거래일 확인 불가 · VIX 두 날짜 · 60거래일 다섯 분류(기관계 세부 중복 합산 없음 · 국가 따로 적지 않음).
3. ok · partial · unavailable · 읽기 실패 격리 · 오늘 시세 있음 · 없음 · 마지막 시도 실패 · 다른 날.
4. 읽기 전용(표를 만들지 않음 · 파일을 만들지 않음) · 경로 422.
라이브 DB · 라이브 상태 파일은 열지 않는다(임시 DB · 합성 응답 · 빠른 시세는 conftest 가 임시 경로로 격리).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import market_evidence as ME
from app import market_evidence_reads as R
from app import market_evidence_text as T
from app.market_benchmark_store import KOSPI_SOURCE, MARKET_BENCHMARK_DAILY_PRICE_DDL
from app.supply_fx_oil_calc import won
from app.supply_fx_oil_store import FLOW_DDL, MACRO_DDL, USDKRW, WTI

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "poc6_32_evidence_cases.json").read_text(
        encoding="utf-8"
    )
)
NOW = datetime(2026, 11, 17, 0, 0, tzinfo=timezone.utc)  # 11/17 09:00 KST
# 재설계 판정 V2 §3 인용 문단(판정 문서 원문 그대로 — 굵게 표시만 뺌)
DECISION_PARAGRAPH = (
    "답변 전에 판단에 사용하는 항목의 최신 공개 자료를 확인해 주세요. 공식 출처를 우선하고, 국내 종가·수급과 "
    "해외 지표는 각 자료의 거래일과 공표 시점을 기준으로 확인해 주세요. 확인 결과에는 값·기준일·출처 링크를 "
    "적어 주세요. 저장값과 같으면 그 사실을, 더 최신 값이나 같은 날짜의 정정값이 있으면 어느 해석이 달라지는지 "
    "적어 주세요. 최신 공개 자료를 확인할 수 없으면 ‘최신 자료 확인 불가’라고 쓰고 제공된 저장 자료의 기준일을 "
    "밝혀 설명해 주세요."
)
MOCKUP_ANSWER = (
    "다섯 줄로 답해 주세요. ① 최신 확인 결과와 시장 판정 ② 코스피 방향 ③ 외국인 매도·매수 방향과 속도 "
    "④ 환율·유가·VIX 관측 ⑤ 다음 확인 한 가지. 줄마다 근거와 실제 날짜를 쓰고, 비교 기간이 다르면 따로 써 "
    "주세요. 못 읽은 자료는 '확인 불가'. 해석에 추가 자료가 필요하면 그 항목을 마지막 줄에 적어 주세요."
)
INST = (
    "inst_securities",
    "inst_insurance",
    "inst_trust",
    "inst_bank",
    "inst_other_finance",
    "inst_pension",
    "inst_private_fund",
)
EOK = 100_000_000


# ── 1. 화면 이식 = 같은 고정 자료 ─────────────────────────────────────────────
@pytest.mark.parametrize("case", CASES["events"], ids=lambda c: c["note"])
def test_event_sentence_matches_frontend_fixture(case):
    assert T.event_sentence(case["input"]) == case["expected_sentence"]


def _query_data(q: dict):
    """화면 QueryState → 서버 입력(성공 · 새 응답만 · 실패 · 이전 응답은 None)."""
    return q.get("data") if q["phase"] == "success" and not q.get("stale") else None


@pytest.mark.parametrize("case", CASES["common_rows"], ids=lambda c: c["note"])
def test_common_row_matches_frontend_fixture(case):
    assert T.common_row(_query_data(case["input"])) == case["expected"]


def test_fixture_covers_rounding_and_josa_edges():
    notes = " ".join(c["note"] for c in CASES["events"])
    for word in ("1.15 → 1.1", "1.15 → 1.2", "1.005 → 1.01", "2.5 → 3", "옛 응답"):
        assert word in notes
    assert len(CASES["common_rows"]) >= 15


# ── 2. 임시 시장 DB(합성 값) ─────────────────────────────────────────────────
def _weekdays(a: str, b: str) -> list[str]:
    d, end, out = date.fromisoformat(a), date.fromisoformat(b), []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


KDATES = _weekdays(
    "2026-03-02", "2026-11-13"
)  # 코스피 · 수급(국내) — 11/16 없음(1거래일 늦음)
UDATES = _weekdays("2026-03-02", "2026-11-16")  # 원/달러 · WTI · VIX — 11/16 까지


def _flow_value(inv: str, i: int) -> int:
    base = {
        "foreign": -(300 + i % 7) * EOK,
        "individual": (120 + i % 5) * EOK,
        "other_corp": (90 + i % 3) * EOK,
        "native_foreign": -(1 + i % 2) * EOK,
        "nation": 0,
    }
    if inv in base:
        return base[inv]
    k = INST.index(inv)
    return (k + 1) * (10 + i % 4) * EOK  # 기관 세부 7


def make_db(
    path: Path,
    *,
    flows: bool = True,
    kospi_last_source: str = KOSPI_SOURCE,
    skip_native: tuple[str, ...] = (),
    nation: int = 0,
    stray: bool = False,
) -> Path:
    con = sqlite3.connect(str(path))
    con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
    con.execute(MACRO_DDL)
    con.execute(FLOW_DDL)
    rows = []
    for i, d in enumerate(KDATES):
        src = KOSPI_SOURCE if d >= "2026-09-17" else "FinanceDataReader/KS11"
        if d == KDATES[-1]:
            src = kospi_last_source
        rows.append(("KOSPI", "코스피", d, 5000.0 + i, src, "2026-11-14T00:10:00Z"))
    for i, d in enumerate(UDATES):
        rows.append(("VIX", "VIX", d, 15.0 + (i % 9), "FDR", "2026-11-17T00:20:00Z"))
    con.executemany(
        "INSERT INTO market_benchmark_daily_price VALUES (?, ?, ?, ?, ?, ?)", rows
    )
    macro = []
    for i, d in enumerate(UDATES):
        macro.append(
            (USDKRW, d, 1400.0 - i * 0.5, "KRW/USD", "y", "b", "2026-11-17T00:30:00Z")
        )
        macro.append(
            (WTI, d, 90.0 - (i % 11), "USD/bbl", "y", "b", "2026-11-17T00:30:00Z")
        )
    con.executemany(
        "INSERT INTO market_macro_daily VALUES (?, ?, ?, ?, ?, ?, ?)", macro
    )
    if flows:
        frows = []
        for i, d in enumerate(KDATES):
            for inv in ("foreign", "individual", "other_corp", "native_foreign", *INST):
                if inv == "native_foreign" and d in skip_native:
                    continue
                frows.append((d, inv, _flow_value(inv, i)))
            frows.append((d, "nation", nation if d == KDATES[-1] else 0))
            frows.append((d, "institution", sum(_flow_value(k, i) for k in INST)))
        if (
            stray
        ):  # 코스피 저장 거래일이 아닌 날(일요일)의 수급 행 — 읽기 전용 합에 더하지 않음
            frows.append(("2026-11-15", "foreign", -999 * EOK))
        con.executemany(
            "INSERT INTO market_investor_flow_daily VALUES ('KOSPI', ?, ?, NULL, NULL, ?, "
            "'KIWOOM_KA10051_KRX_VIA_OCI', '2026-11-14T00:40:00Z')",
            frows,
        )
    con.commit()
    con.close()
    return path


CTX = {
    "status": "ok",
    "regime_label": "하락장",
    "regime_code": "bear",
    "regime_score": -4,
    "kodex200": {
        "status": "ok",
        "return_20d_pct": -11.03,
        "return_60d_pct": -26.29,
        "ma20": 86000.0,
        "ma60": 99000.0,
        "ma20_position": "below",
        "ma60_position": "below",
        "ma20_distance_pct": -7.78,
        "ma60_distance_pct": -19.7,
        "return_1m_start_date": "2026-10-19",
        "return_3m_start_date": "2026-08-18",
        "return_end_date": "2026-11-16",
    },
    "regime_streak": {"regime_code": "bear", "streak_days": 27, "at_least": False},
}
SAVED = "2026-11-16T16:05:00+09:00"


def morning(today_row=None, today_ctx=None, status="ok") -> dict:
    row = today_row or {
        "date": "2026-11-16",
        "close": 80000.0,
        "state": "after_close",
        "fetched_at_kst": SAVED,
    }
    return {
        "status": status,
        "message": None if status == "ok" else "아침 요약 기준을 읽지 못했습니다",
        "expected_date": "2026-11-16",
        "items": [
            {"key": "kospi", "stored_date": "2026-11-13"},
            {
                "key": "kodex200",
                "received_at": SAVED,
                "basis_row": {
                    "date": "2026-11-16",
                    "close": 80000.0,
                    "state": "after_close",
                },
            },
        ],
        "morning_regime": {
            "status": "ok",
            "basis_date": "2026-11-16",
            "reason": None,
            "context": CTX,
        },
        "today_regime": {
            "status": "ok",
            "basis_date": row["date"],
            "reason": None,
            "context": today_ctx or CTX,
            "basis_row": row,
        },
    }


def quick(
    status="ok", trade="2026-11-17", attempts=("updated", "updated", "updated")
) -> dict:
    names = (
        ("KOSPI", "코스피", "index", 5300.12),
        ("KOSDAQ", "코스닥", "index", 900.5),
        ("069500", "KODEX 200", "stock", 78070.0),
    )
    items = []
    for (code, name, kind, v), att in zip(names, attempts):
        items.append(
            {
                "code": code,
                "name": name,
                "kind": kind,
                "quote": {
                    "value": v,
                    "change": None,
                    "change_pct": None,
                    "source_time": f"{trade}T14:13:00+09:00",
                    "trade_date": trade,
                    "market_status": "OPEN",
                    "fetched_at": f"{trade}T14:14:00+09:00",
                },
                "last_attempt": {
                    "at": "2026-11-17T14:14:00+09:00",
                    "status": att,
                    "reason": "timeout" if att == "failed" else None,
                },
            }
        )
    return {"status": status, "message": None, "items": items}


@pytest.fixture
def db(tmp_path):
    return make_db(tmp_path / "market.sqlite")


def build(monkeypatch, db_path, mb=None, q=None):
    monkeypatch.setattr(ME, "build_morning_basis", lambda **kw: mb or morning())
    if q is not None:
        monkeypatch.setattr(ME, "read_quick_quotes", lambda: q)
    return ME.build_market_evidence(now=NOW, db_path=db_path)


def lines(out: dict) -> list[str]:
    return out["daily_text"].split("\n\n", 2)[2].splitlines()


def line(out: dict, head: str) -> str:
    got = [x for x in lines(out) if x.startswith(head)]
    assert len(got) == 1, (head, lines(out))
    return got[0]


def last60(inv: str) -> int:
    idx = range(len(KDATES) - 60, len(KDATES))
    if inv == "institution":
        return sum(sum(_flow_value(k, i) for k in INST) for i in idx)
    return sum(_flow_value(inv, i) for i in idx)


# ── 3. 일일 글 · 근거 줄 ─────────────────────────────────────────────────────
def test_daily_text_head_order_and_items_equal_lines(monkeypatch, db):
    out = build(monkeypatch, db, q=quick())
    assert out["status"] == "ok"
    p1, p2, _ = out["daily_text"].split("\n\n", 2)
    assert p1 == DECISION_PARAGRAPH == T.LATEST_CHECK
    assert p2 == MOCKUP_ANSWER == T.DAILY_ANSWER
    assert lines(out) == [i["text"] for i in out["evidence_items"]]
    heads = [
        "[시장 판정]",
        "[코스피 공식 종가]",
        "[코스피 1개월]",
        "[코스피 3개월]",
        "[코스피 6개월]",
        "[외국인 6개월]",
        "[외국인 20거래일]",
        "[60거래일 수급]",
        "[원/달러]",
        "[WTI]",
        "[VIX]",
        "[가능한 해석(6개월",
        "[오늘 시세 참고]",
        "[최근 큰 변화",
        "[자료 상태]",
    ]
    pos = [next(i for i, x in enumerate(lines(out)) if x.startswith(h)) for h in heads]
    assert pos == sorted(pos)
    assert out["review_date"] == "2026-11-17"
    assert out["generated_at"] == "2026-11-17T09:00:00+09:00"
    assert out["basis"] == {
        "regime_label": "하락장",
        "regime_price_date": "2026-11-16",
        "regime_price_state": "after_close",
        "kospi_date": "2026-11-13",
        "flow_date": "2026-11-13",
        "common_end_date": "2026-11-13",
    }


def test_regime_same_basis_printed_once_with_returns_and_ma(monkeypatch, db):
    out = build(monkeypatch, db)
    assert [i["key"] for i in out["evidence_items"]].count("regime") == 1
    assert line(out, "[시장 판정]") == (
        "[시장 판정] KODEX 200 하락장 · 27거래일째 · 판정 가격 11/16(16:05 마감 뒤 저장) · 아침 · 당일 같은 근거"
        " · 20거래일 -11.03%(10/19 → 11/16) · 60거래일 -26.29%(8/18 → 11/16) · 20일선 아래(거리 -7.78%)"
        " · 60일선 아래(거리 -19.70%)"
    )


def test_regime_morning_and_today_differ_printed_each(monkeypatch, db):
    ctx = json.loads(json.dumps(CTX))
    ctx["regime_streak"]["streak_days"] = 28
    ctx["kodex200"].update(
        return_20d_pct=-9.88,
        return_1m_start_date="2026-10-20",
        return_end_date="2026-11-17",
    )
    row = {
        "date": "2026-11-17",
        "close": 78070.0,
        "state": "intraday",
        "fetched_at_kst": "2026-11-17T14:14:00+09:00",
    }
    out = build(monkeypatch, db, mb=morning(today_row=row, today_ctx=ctx))
    keys = [i["key"] for i in out["evidence_items"]]
    assert "regime" not in keys and keys[:2] == ["regime_morning", "regime_today"]
    assert line(out, "[시장 판정 · 아침]").startswith(
        "[시장 판정 · 아침] KODEX 200 하락장 · 27거래일째 · 판정 가격 11/16(16:05 마감 뒤 저장) · 20거래일"
    )
    today = line(out, "[시장 판정 · 당일]")
    assert (
        "28거래일째 · 판정 가격 11/17(14:14 장중 저장) · 20거래일 -9.88%(10/20 → 11/17)"
        in today
    )
    assert "같은 근거" not in today
    assert out["basis"]["regime_price_date"] == "2026-11-17"
    assert out["basis"]["regime_price_state"] == "intraday"


def test_kospi_actual_periods_start_source_and_expected_day(monkeypatch, db):
    out = build(monkeypatch, db)
    head = line(out, "[코스피 공식 종가]")
    n = len(KDATES) - 1
    assert head.startswith(
        f"[코스피 공식 종가] {5000 + n:,.2f} · 11/13 · 11/12 대비 +1.00pt("
    )
    assert head.endswith("기대 거래일 11/16 종가 확인 불가")
    one = line(out, "[코스피 1개월]")
    assert (
        "(10/13 " in one and "→ 11/13 " in one and "출처" not in one
    )  # 시작 · 끝 모두 KRX 공식
    six = line(out, "[코스피 6개월]")
    assert "(5/13 " in six and "· 시작 종가 출처 FDR(KRX 공식 아님)" in six
    assert "끝 종가 출처" not in six
    k = out["fields"]["kospi"]
    assert (
        k["periods"]["6M"]["start_official"],
        k["periods"]["1M"]["start_official"],
    ) == (False, True)


def test_kospi_latest_not_official_names_source(monkeypatch, tmp_path):
    out = build(
        monkeypatch, make_db(tmp_path / "m.sqlite", kospi_last_source="NAVER_FDR")
    )
    head = line(out, "[코스피 종가]")
    assert "· 출처 네이버(FDR 경유)(KRX 공식 아님)" in head
    assert not any(x.startswith("[코스피 공식 종가]") for x in lines(out))
    assert "끝 종가 출처 네이버(FDR 경유)(KRX 공식 아님)" in line(out, "[코스피 1개월]")


def test_flows_six_twenty_and_q10_five_categories_without_double_count(monkeypatch, db):
    out = build(monkeypatch, db)
    six = line(out, "[외국인 6개월]")
    assert six.startswith("[외국인 6개월] 누적 순매도 ") and "/" in six and "일)" in six
    assert line(out, "[외국인 20거래일]").startswith("[외국인 20거래일] 직전 ")
    r60 = line(out, "[60거래일 수급]")
    start = KDATES[-60]
    assert r60.startswith(
        f"[60거래일 수급] {T.md(start)} ~ 11/13(코스피 저장 거래일 60일 · 순매수 합) "
    )
    for inv, label in ME.FLOW60:
        assert f"{label} {won(last60(inv))}" in r60
    # 기관계 = 원천 기관계 칸 그대로 · 세부 7 을 다시 더하지 않음(두 배가 아님)
    assert won(2 * last60("institution")) not in r60
    assert "국가 · 지자체는 따로 적지 않음(이 기간 0)" in r60
    assert "기관계 = 금융투자 등 세부 7 합 · 세부는 따로 더하지 않음" in r60
    assert "외국인 = 내국인대우외국인 제외" in r60
    f = out["fields"]["flows"]["r60"]
    assert [i["key"] for i in f["investors"]] == [k for k, _ in ME.FLOW60]
    assert f["investors"][0]["value"] == last60("foreign")


def test_flows_partial_native_and_nonzero_nation(monkeypatch, tmp_path):
    path = make_db(tmp_path / "m.sqlite", skip_native=(KDATES[-3],), nation=5 * EOK)
    r60 = line(build(monkeypatch, path), "[60거래일 수급]")
    assert "내국인대우외국인 " in r60 and "(부분 집계 59/60일)" in r60
    assert f"국가 · 지자체는 따로 적지 않음(이 기간 합 {won(5 * EOK)})" in r60


def test_flows_sixty_mismatch_with_flow_response_is_unconfirmed(monkeypatch, db):
    real = R.investor_sums

    def changed(*a, **kw):
        got = real(*a, **kw)
        got["investors"]["foreign"]["sum"] += EOK
        return got

    monkeypatch.setattr(R, "investor_sums", changed)
    out = build(monkeypatch, db)
    assert line(out, "[60거래일 수급]").startswith(
        "[60거래일 수급] 확인 불가 — 시장 흐름 응답과 다시 읽은"
    )
    assert out["status"] == "partial"


def test_macro_and_vix_latest_date_and_six_month_dates(monkeypatch, db):
    out = build(monkeypatch, db)
    fx = line(out, "[원/달러]")
    assert "· 11/16(런던 날짜) · 직전 관측 11/13 대비 -0.50원(" in fx
    assert "· 5개 관측 -2.50원(" in fx and "11/9부터)" in fx
    assert fx.endswith(
        "· 5/13 → 11/13)"
    )  # 해석에 쓴 6개월 끝(≤ 국내 끝일) · 최신 값 날짜와 따로
    assert "· 11/16(뉴욕 날짜 · 근월물 선물)" in line(out, "[WTI]")
    vix = line(out, "[VIX]")
    assert vix.startswith("[VIX] ") and "· 11/16(미국 날짜) · 직전 관측 11/13 " in vix
    assert "· 5개 관측 " in vix and "(11/9 " in vix
    assert vix.endswith("· 5/13 → 11/13 미국 날짜)")
    assert out["fields"]["vix"]["freshness"]["state"] in ("fresh", "one_weekday_behind")


def test_data_status_late_items_and_quick_missing(monkeypatch, db):
    out = build(monkeypatch, db)  # 빠른 시세 파일 없음(conftest 임시 경로)
    st = line(out, "[자료 상태]")
    assert st.startswith("[자료 상태] 11/17 확인 · ")
    assert "코스피 11/13까지(기대 11/16 · 1거래일 늦음)" in st
    assert "외국인 수급 11/13까지(기대 11/16 · 1거래일 늦음)" in st
    assert "시장 판정" not in st and "원/달러" not in st  # 11/16 · 최신
    assert st.endswith("1거래일 늦음) · 지연 원인 확인 전 · 오늘 시세 미확보")
    assert not any(x.startswith("[오늘 시세 참고]") for x in lines(out))
    assert "오늘 시세 미확보" in out["data_status"]


def test_data_status_all_fresh_sentence(monkeypatch, db):
    sat = datetime(
        2026, 11, 14, 1, 0, tzinfo=timezone.utc
    )  # 11/14(토) KST — 기대 거래일 11/13
    monkeypatch.setattr(ME, "build_morning_basis", lambda **kw: morning())
    monkeypatch.setattr(ME, "read_quick_quotes", lambda: quick(trade="2026-11-14"))
    out = ME.build_market_evidence(now=sat, db_path=db)
    assert (
        line(out, "[자료 상태]")
        == "[자료 상태] 11/14 확인 · 확인한 자료 모두 기대 기준일 기준 최신"
    )
    assert out["data_status"] == []


def test_daily_text_has_no_raw_codes(monkeypatch, tmp_path):
    out = build(
        monkeypatch,
        make_db(tmp_path / "m.sqlite", kospi_last_source="NAVER_FDR"),
        q=quick(),
    )
    raw = (
        "after_close",
        "intraday",
        "unknown",
        "OPEN",
        "CLOSE",
        "bear",
        "None",
        "KS11",
    )
    raw += (
        "NAVER_FDR",
        "KRX_OPEN_API",
        "FinanceDataReader",
        "updated",
        "failed",
        "nan",
    )
    for code in raw:
        assert code not in out["daily_text"], code


@pytest.mark.parametrize(
    "q, shown, missing",
    [
        (quick(), 3, None),
        (
            quick(attempts=("updated", "failed", "unchanged")),
            2,
            "오늘 시세 미확보(코스닥)",
        ),
        (quick(attempts=("failed", "failed", "failed")), 0, "오늘 시세 미확보"),
        (quick(trade="2026-11-16"), 0, "오늘 시세 미확보"),
        (
            {"status": "invalid", "message": "x", "items": []},
            0,
            "오늘 시세 미확보(저장 파일을 읽지 못함)",
        ),
    ],
    ids=[
        "오늘 · 성공",
        "한 항목 마지막 시도 실패",
        "모두 실패",
        "다른 날 시세",
        "저장 파일 깨짐",
    ],
)
def test_quick_quote_reference_only_today_and_success(
    monkeypatch, db, q, shown, missing
):
    out = build(monkeypatch, db, q=q)
    got = [x for x in lines(out) if x.startswith("[오늘 시세 참고]")]
    assert len(out["fields"]["quick"]["shown"]) == shown
    if shown:
        assert got[0].startswith(
            "[오늘 시세 참고] 11/17 네이버 시세(공식 종가 · 수급 통계 아님) · 코스피 5,300.12(장중 · 원천 시각 14:13)"
        )
        if shown == 3:
            assert got[0].endswith("KODEX 200 78,070원(장중 · 원천 시각 14:13)")
    else:
        assert got == []
    if missing:
        assert missing in out["data_status"]
    else:
        assert not any("오늘 시세 미확보" in p for p in out["data_status"])


def test_events_all_listed_and_close_based_tag(monkeypatch, db):
    out = build(monkeypatch, db)
    flow = {  # 실제 조립은 공통 비교일(D)이 있을 때만 큰 변화를 확인한다(D 없음 = 확인 안 함 · BE-1)
        "D": "2026-11-16",
        "events": [c["input"] for c in CASES["events"][:9]],
        "event_check": {},
    }
    items = T._event_items(ME.events_block(flow))
    assert len(items) == 9
    for (key, text), case in zip(items, CASES["events"][:9]):
        tail = "(종가 기준)" if case["input"]["key"] in T.PRICE_KEYS else ""
        assert text.endswith(case["expected_sentence"] + tail), text
    assert (
        items[7][1]
        == "[최근 큰 변화 8] 11/5 외국인 순매도 3.4조원 · 직전 20거래일 평균 규모의 2.1배"
    )
    assert any(x.startswith("[최근 큰 변화") for x in lines(out))


# ── 4. 상태 · 읽기 실패 격리 ───────────────────────────────────────────────────
def test_partial_when_no_flows_says_unconfirmed_not_zero(monkeypatch, tmp_path):
    out = build(monkeypatch, make_db(tmp_path / "m.sqlite", flows=False))
    assert out["status"] == "partial"
    assert (
        line(out, "[외국인 6개월]")
        == "[외국인 6개월] 확인 불가 — 투자자별 수급 자료 없음"
    )
    assert (
        line(out, "[60거래일 수급]")
        == "[60거래일 수급] 확인 불가 — 투자자별 수급 자료 없음"
    )
    assert line(out, "[코스피 공식 종가]")  # 다른 칸은 그대로


def test_flows_without_common_day_keep_latest_flow_date_for_basis(
    monkeypatch, tmp_path
):
    """시장 흐름 D(공통 비교일)가 없어도 수급 최신 날짜(series.flows.E)가 있으면 basis.flow_date 로 남긴다 —
    화면 대조(시장 흐름 응답 series.flows.E)가 늘 '근거 다름'으로 멈추지 않게(통합 I9)."""
    flow = {
        "D": None,
        "series": {"flows": {"E": "2026-11-13", "collected_at": "2026-11-14T08:00"}},
    }
    blk = ME.flows_block(flow, None)
    assert blk["status"] == "unavailable" and blk["latest_date"] == "2026-11-13"
    assert ME._basis({"flows": blk}, flow)["flow_date"] == "2026-11-13"
    why = "코스피 저장 자료가 없어 계산하지 않음"
    assert all(
        blk[k] == {"status": "unavailable", "reason": why}
        for k in ("six", "w20", "r60")
    )
    assert T._flow_items(blk)[0][1] == f"[외국인 6개월] 확인 불가 — {why}"
    # 시장 흐름을 못 읽었으면 날짜를 지어내지 않음
    assert ME.flows_block(None, None).get("latest_date") is None
    # 실제 경로(코스피 저장 자료 없음): 시장 흐름 응답도 series 가 비어 화면 · 서버 수급 기준일이 함께 없음(같음)
    db = make_db(tmp_path / "m.sqlite")
    con = sqlite3.connect(str(db))
    con.execute("DELETE FROM market_benchmark_daily_price WHERE benchmark_id='KOSPI'")
    con.commit()
    con.close()
    out = build(monkeypatch, db)
    screen = ME.build_market_flow_context(db_path=db, now=NOW)
    assert screen["D"] is None
    assert out["basis"]["flow_date"] == (screen["series"].get("flows") or {}).get("E")


def test_unavailable_when_regime_kospi_flows_all_unreadable(monkeypatch, tmp_path):
    def boom(**kw):
        raise sqlite3.OperationalError("x")

    monkeypatch.setattr(ME, "build_market_flow_context", boom)
    # 있는 빈 DB 파일(r1 F3 — 파일이 없으면 빌더가 읽기 없이 'DB 없음'으로 끝나 이 경로를 보지 못함)
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(str(empty)).close()
    out = build(monkeypatch, empty, mb=morning(status="invalid"))
    assert out["status"] == "unavailable"
    assert out["daily_text"] is None and out["evidence_items"] == []
    assert "시장 흐름 자료 읽기 실패" in out["data_status"]
    assert set(out["basis"]) == {
        "regime_label",
        "regime_price_date",
        "regime_price_state",
        "kospi_date",
        "flow_date",
        "common_end_date",
    }


def test_read_failure_isolated_to_that_field(monkeypatch, db):
    def boom(**kw):
        raise sqlite3.OperationalError("x")

    monkeypatch.setattr(ME, "_build_vix_card", boom)
    out = build(monkeypatch, db)
    assert out["status"] == "partial"
    assert line(out, "[VIX]") == "[VIX] 확인 불가 — VIX 저장 자료를 읽지 못함"
    assert "VIX 읽기 실패" in line(out, "[자료 상태]")
    assert line(out, "[원/달러]").startswith("[원/달러] ")
    assert line(out, "[시장 판정]").startswith("[시장 판정] KODEX 200 하락장")


def test_kospi_missing_early_return_is_not_written_as_none(monkeypatch, tmp_path):
    """검토 BE-1 — 시장 흐름 조립이 코스피 저장 자료가 없어 일찍 끝나면(D 없음) 원/달러 · WTI · 최근 큰 변화 ·
    VIX 6개월 · 해석은 '계산하지 않음'(자료가 있어도 '저장 자료 없음' · 큰 변화 '없음'으로 쓰지 않음)."""
    db = make_db(tmp_path / "m.sqlite")
    con = sqlite3.connect(str(db))
    con.execute("DELETE FROM market_benchmark_daily_price WHERE benchmark_id='KOSPI'")
    con.commit()
    con.close()
    out = build(monkeypatch, db)
    why = "코스피 저장 자료가 없어 계산하지 않음"
    assert out["status"] == "partial" and out["daily_text"]
    assert line(out, "[원/달러]") == f"[원/달러] 확인 불가 — {why}"
    assert line(out, "[WTI]") == f"[WTI] 확인 불가 — {why}"
    assert line(out, "[최근 큰 변화]") == f"[최근 큰 변화] 확인 불가 — {why}"
    assert line(out, "[VIX]").endswith(f" · 6개월 확인 불가({why})")
    head = "[가능한 해석(6개월 · 확정 아님)]"
    assert line(out, "[가능한 해석") == f"{head} 확인 불가 — {why}"
    assert "[최근 큰 변화] 없음" not in lines(out)
    assert not any(
        "저장 자료 없음" in x for x in lines(out) if x[:5] in ("[원/달러", "[WTI]")
    )


def test_event_none_only_when_event_check_ran():
    """검토 BE-1 — '[최근 큰 변화] 없음' 류는 확인 결과 글이 있을 때만(확인 안 한 빈 목록 = 확인 불가)."""
    ran = {
        "status": "ok",
        "items": [],
        "unchecked_text": None,
        "empty_text": "큰 변화 없음",
    }
    assert T._event_items(ran) == [("events", "[최근 큰 변화] 큰 변화 없음")]
    assert T._event_items({**ran, "empty_text": None}) == [
        ("events", "[최근 큰 변화] 확인 불가 — 큰 변화를 확인하지 않음")
    ]
    early = {"D": None, "events": [], "event_check": {"empty_text": None}}
    assert ME.events_block(early) == {
        "status": "unavailable",
        "reason": "코스피 저장 자료가 없어 계산하지 않음",
        "items": [],
    }


def test_flow_read_failure_is_not_written_as_missing(monkeypatch, db):
    """검토 BE-2 — 시장 흐름 읽기 실패(None) = VIX 6개월 · [자료 상태] 코스피 행도 '시장 흐름 자료를 읽지 못함'
    (읽기 실패를 '기간을 덮는 저장 값 없음' · '자료 없음'으로 바꿔 쓰지 않음 · 수급 · 원/달러 행과 같은 사유)."""

    def boom(**kw):
        raise sqlite3.OperationalError("x")

    monkeypatch.setattr(ME, "build_market_flow_context", boom)
    out = build(monkeypatch, db)
    assert out["status"] == "partial"
    vix = line(out, "[VIX]")
    assert vix.startswith("[VIX] ") and vix.endswith(
        " · 6개월 확인 불가(시장 흐름 자료를 읽지 못함)"
    )
    st = line(out, "[자료 상태]")
    assert "코스피 기준 확인 필요(시장 흐름 자료를 읽지 못함)" in st
    assert "코스피 기준 확인 필요(자료 없음)" not in st


def test_morning_invalid_keeps_other_evidence(monkeypatch, db):
    out = build(monkeypatch, db, mb=morning(status="invalid"))
    assert out["status"] == "partial"
    assert (
        line(out, "[시장 판정]")
        == "[시장 판정] 확인 불가 — 아침 요약 기준을 읽지 못했습니다"
    )
    assert out["basis"]["regime_label"] is None
    assert (
        "시장 판정(KODEX 200) 기준 확인 필요(아침 요약 기준을 읽지 못했습니다)"
        in out["data_status"]
    )


def test_same_now_passed_to_morning_and_flow(monkeypatch, db):
    seen = {}

    def mb(**kw):
        seen["morning"] = kw
        return morning()

    real = ME.build_market_flow_context

    def fc(**kw):
        seen["flow"] = kw
        return real(**kw)

    monkeypatch.setattr(ME, "build_morning_basis", mb)
    monkeypatch.setattr(ME, "build_market_flow_context", fc)
    ME.build_market_evidence(now=NOW, db_path=db)
    assert seen["morning"]["now"] is NOW and seen["flow"]["now"] is NOW
    assert seen["morning"]["db_path"] == seen["flow"]["db_path"] == db


# ── 5. 읽기 전용 조회 ─────────────────────────────────────────────────────────
def test_reads_do_not_create_file_or_tables(tmp_path):
    missing = tmp_path / "nothing.sqlite"
    assert (
        R.investor_sums("2026-01-01", "2026-12-31", ("foreign",), db_path=missing)
        is None
    )
    assert R.kospi_sources(["2026-11-13"], db_path=missing) == {}
    assert not missing.exists()
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(str(empty)).close()
    before = empty.read_bytes()
    assert (
        R.investor_sums("2026-01-01", "2026-12-31", ("foreign",), db_path=empty) is None
    )
    assert R.kospi_sources(["2026-11-13"], db_path=empty) == {}
    con = sqlite3.connect(str(empty))
    assert con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0
    con.close()
    assert empty.read_bytes() == before


def test_reads_sums_only_kospi_dates_and_marks_partial(tmp_path):
    db = make_db(tmp_path / "m.sqlite", stray=True)
    got = R.investor_sums(
        "2026-11-10", "2026-11-16", ("foreign", "native_foreign", "nation"), db_path=db
    )
    assert (
        got["expected"] == 4
    )  # 11/10 ~ 11/13(11/15 · 11/16 은 코스피 저장 거래일 아님)
    n = len(KDATES)
    assert got["investors"]["foreign"] == {
        "sum": sum(_flow_value("foreign", i) for i in range(n - 4, n)),
        "days": 4,
        "partial": False,
    }
    src = R.kospi_sources(["2026-05-13", "2026-11-13", "2026-11-16"], db_path=db)
    assert src == {"2026-05-13": "FinanceDataReader/KS11", "2026-11-13": KOSPI_SOURCE}


# ── 6. 경로 ──────────────────────────────────────────────────────────────────
def test_route_market_evidence_returns_builder_output(client, monkeypatch):
    monkeypatch.setattr(
        ME, "build_market_evidence", lambda: {"status": "ok", "daily_text": "글"}
    )
    r = client.get("/market/evidence")
    assert r.status_code == 200 and r.json() == {"status": "ok", "daily_text": "글"}


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?tickers=",
        "?tickers=,",
        "?tickers=ABC",
        "?tickers=1234567",
        "?tickers=0091c0",
        "?tickers=069500,12345",
    ]
    + ["?tickers=" + ",".join(f"{i:06d}" for i in range(1, 12))],
    ids=[
        "칸 없음",
        "빈 값",
        "쉼표만",
        "짧은 코드",
        "긴 코드",
        "소문자",
        "하나만 틀림",
        "11개",
    ],
)
def test_route_etf_official_rejects_bad_tickers(client, query):
    assert client.get(f"/market/etf-official{query}").status_code == 422


def test_route_etf_official_pair_only_for_exactly_two(client, monkeypatch):
    calls = []
    fake = types.ModuleType("app.etf_official_info")

    def lookup_official(tickers):
        calls.append(list(tickers))
        return {
            "csv": {"date": "2026-09-27"},
            "items": {t: {"ticker": t} for t in tickers},
        }

    fake.lookup_official = lookup_official
    fake.pair_state = lambda a, b: {"a": a["ticker"], "b": b["ticker"]}
    monkeypatch.setitem(sys.modules, "app.etf_official_info", fake)
    r = client.get("/market/etf-official?tickers= 069500, 0091C0 ,069500")
    assert r.status_code == 200
    assert calls[-1] == ["069500", "0091C0"]
    assert r.json()["pair"] == {"a": "069500", "b": "0091C0"}
    assert r.json()["csv"] == {"date": "2026-09-27"}
    one = client.get("/market/etf-official?tickers=069500,069500").json()
    assert "pair" not in one and calls[-1] == ["069500"]
    three = client.get("/market/etf-official?tickers=069500,102110,0091C0").json()
    assert "pair" not in three and len(three["items"]) == 3


@pytest.mark.parametrize(
    "sources, day, expected",
    [
        (None, "2026-11-13", ("확인 불가", None)),  # 출처를 읽지 못함
        ({}, "2026-11-13", ("확인 불가", None)),  # 그날 행 없음
        ({"2026-11-13": KOSPI_SOURCE}, None, ("확인 불가", None)),  # 날짜 없음
        ({"2026-11-13": KOSPI_SOURCE}, "2026-11-13", ("KRX 공식", True)),
        ({"2026-11-13": "FinanceDataReader/KS11"}, "2026-11-13", ("FDR", False)),
        ({"2026-11-13": "UNKNOWN_PIPE"}, "2026-11-13", ("기타 수집 경로", False)),
    ],
)
def test_source_label_unread_is_unconfirmed_not_other(sources, day, expected):
    """r1 정정 변이 G4-M3 — 출처를 못 읽은 날을 '기타 수집 경로'로 바꿔 적지 않는다(확인 불가 · 공식 여부 모름)."""
    assert R.source_label(sources, day) == expected
