"""POC6-32 V2 — 새 모듈 단위 시험: ③ R1 「어떤 상품인가」 · [비교 상세] D2 · D3(공식 기준정보 · 지수 상태 · 구성 요약) ·
R2 국내시장 대비 문구 · ② 행 자료 부족 · 보유 겹침 카드 기간(`holdings_overlap_period`).

계약 문장(PLAN V2 §3-1 R1 · §3-2 D2 · D3 · §9 I-6 · I-9 · I-10 · I-19 · I-21) → 시험:
- 공식 기준정보 = CSV 글자 그대로 · 파일 날짜 · CSV 에 없으면 '공식 기준정보에 없음' · ETF 목록에도 없으면 개별 주식 ·
  ETF 목록을 못 읽으면 종류 미확인 · 같은 파일이면 정리한 표를 다시 씀.
- 지수 상태 = 같은 공식 기초지수(이름이 같을 때만 · 구조가 달라도 같음 + 구조 차이) / 다른 지수 · 같은 계열 / 다른 지수 /
  기준 미확인(공식 기준정보 없음 · 개별 주식 · 파일 못 읽음 · 고르지 않음) · 판정 순서(미확인이 먼저).
- 구성 요약 = 원천일이 확인된 최신 구성(없으면 저장 최신 + 원천 기준일 미확인) · 상태 넷 · 주식 상위 3개와 합(주식만) ·
  집중 Top 1 · 3 · 5 · 10(기존 정의) · 보유와 무관 · `GET /market/constituents/summary`.
합성 종목 이름 · 임시 폴더 · 임시 DB 만 쓴다(라이브 DB · 실제 보유 없음).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn
from app import etf_constituents_store
from app import etf_official_info as eoi
from app import weekly_candidate_reads as CR
from app import weekly_candidate_review as wcr
from app import weekly_review as wr
from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE
from app.etf_constituents_status import LOG_OK
from app.etf_constituents_store import (
    ConstituentRow,
    replace_constituents_snapshot,
    upsert_constituents,
)
from app.holdings_overlap_period import topn_basis
from app.market_briefing.official_csv import EXPECTED_HEADER
from app.market_data_store import EtfMasterRow, upsert_etf_master
from tests.test_api_holdings_market_evidence import (  # noqa: F401 — fixture
    _seed_history,
    api_client,
)

A = {
    "단축코드": "A00001",
    "한글종목약명": "가상 지수 하나",
    "기초지수명": "가상 대표 200",
    "지수산출기관": "가상거래소",
    "추적배수": "일반",
    "복제방법": "실물(패시브)",
    "기초시장분류": "국내",
    "기초자산분류": "주식",
    "총보수": "0.150000",
    "과세유형": "비과세",
    "상장일": "2002/10/14",
}
LEV = {
    **A,
    "단축코드": "A00002",
    "한글종목약명": "가상 지수 둘 레버리지",
    "추적배수": "2X 레버리지",
    "복제방법": "실물(액티브)",
}
FEE = {**A, "단축코드": "A00003", "한글종목약명": "가상 셋", "총보수": "0.15"}
OTHER = {
    **A,
    "단축코드": "B00001",
    "한글종목약명": "가상 해외",
    "기초지수명": "가상 해외 지수",
}
DJ1 = {
    **A,
    "단축코드": "D00001",
    "기초지수명": "Dow Jones U.S. Dividend 100 Price Return Index",
}
DJ2 = {
    **A,
    "단축코드": "D00002",
    "기초지수명": "DowJones U.S. Dividend 100 7% Premium Covered Call 지수 (TR)",
}
ROWS = [A, LEV, FEE, OTHER, DJ1, DJ2]
NAMES = {r["단축코드"]: r["한글종목약명"] for r in ROWS} | {
    "E00009": "목록에만 있는 ETF"
}


def write_csv(meta: Path, rows=ROWS, day="20260927") -> Path:
    meta.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPECTED_HEADER)
    for r in rows:
        vals = {h: "x" for h in EXPECTED_HEADER}
        vals.update(r)
        w.writerow([vals[h] for h in EXPECTED_HEADER])
    p = meta / f"krx_etf_basic_{day}.csv"
    p.write_bytes(buf.getvalue().encode("cp949"))
    return p


@pytest.fixture
def meta(tmp_path):
    write_csv(tmp_path / "meta")
    return tmp_path / "meta"


def look(meta, tickers, names=NAMES):
    # names=None 이면 ETF 목록을 읽음 — 없는 임시 경로를 줘서 라이브 DB 를 열지 않음(= ETF 목록 확인 불가)
    return eoi.lookup_official(
        tickers, meta_dir=meta, db_path=meta / "no_market.sqlite", etf_names=names
    )


# ── 공식 기준정보 조회 ────────────────────────────────────────────────────────


def test_lookup_values_verbatim_and_file_date(meta):
    r = look(meta, ["A00001", " A00001 ", ""])
    assert r["csv"] == {
        "name": "krx_etf_basic_20260927.csv",
        "asof": "2026-09-27",
        "ok": True,
        "error": None,
    }
    assert list(r["items"]) == ["A00001"]
    it = r["items"]["A00001"]
    assert (it["found"], it["kind"], it["missing_reason"]) == (True, "etf", None)
    assert {k: it[k] for k in ("name", "index_name", "index_provider")} == {
        "name": "가상 지수 하나",
        "index_name": "가상 대표 200",
        "index_provider": "가상거래소",
    }
    assert (it["market"], it["asset"], it["multiple"], it["replication"]) == (
        "국내",
        "주식",
        "일반",
        "실물(패시브)",
    )
    # 총보수 · 상장일 = 글자 그대로(숫자 · 날짜로 바꾸지 않음)
    assert (it["fee_pct"], it["tax"], it["listed"]) == (
        "0.150000",
        "비과세",
        "2002/10/14",
    )


@pytest.mark.parametrize(
    "ticker, names, kind, why",
    [
        (
            "E00009",
            NAMES,
            "etf",
            "공식 기준정보에 없음",
        ),  # ETF 목록에는 있으나 CSV 에 없음
        ("005930", NAMES, "stock", "개별 주식 · 기초지수 해당 없음"),
        (
            "Z99999",
            None,
            "unknown",
            "공식 기준정보에 없음",
        ),  # ETF 목록 못 읽음 — 주식이라 하지 않음
    ],
)
def test_lookup_missing_ticker_kinds(meta, ticker, names, kind, why):
    it = look(meta, [ticker], names)["items"][ticker]
    assert (it["found"], it["kind"], it["missing_reason"]) == (False, kind, why)
    assert it["index_name"] is None and it["fee_pct"] is None
    assert it["name"] == (names or {}).get(ticker)


def test_lookup_without_csv_says_unreadable_not_missing(tmp_path):
    r = look(tmp_path / "empty", ["A00001", "005930"])
    assert r["csv"]["ok"] is False and r["csv"]["asof"] is None
    assert r["csv"]["error"].startswith("공식 기준정보 파일을 읽지 못함")
    assert r["items"]["A00001"]["missing_reason"] == "공식 기준정보 파일을 읽지 못함"
    assert r["items"]["005930"]["missing_reason"] == "개별 주식 · 기초지수 해당 없음"


def test_lookup_reads_etf_master_when_names_not_given(meta, tmp_path):
    db = tmp_path / "m.sqlite"
    upsert_etf_master(
        [EtfMasterRow("E00009", "목록에만 있는 ETF", "1", 1.0, 1, 1.0)],
        source="TestSource",
        db_path=db,
    )
    r = eoi.lookup_official(["E00009", "005930"], meta_dir=meta, db_path=db)
    assert r["items"]["E00009"]["kind"] == "etf"
    assert r["items"]["005930"]["kind"] == "stock"
    # DB 가 없으면 ETF 목록 확인 불가 → 종류 미확인
    r = eoi.lookup_official(["005930"], meta_dir=meta, db_path=tmp_path / "no.sqlite")
    assert r["items"]["005930"]["kind"] == "unknown"


def test_lookup_cache_is_per_file(meta, tmp_path):
    eoi._CACHE.clear()
    look(meta, ["A00001"])
    first = dict(eoi._CACHE)
    look(meta, ["B00001"])
    assert eoi._CACHE == first and len(first) == 1  # 같은 파일 = 같은 표
    write_csv(meta, rows=[{**A, "기초지수명": "바뀐 지수"}], day="20261001")
    assert look(meta, ["A00001"])["items"]["A00001"]["index_name"] == "바뀐 지수"
    assert len(eoi._CACHE) == 1 and eoi._CACHE != first


def test_from_official_uses_given_rows_and_meta():
    rows = {"A00001": A}
    meta = {
        "status": "ok",
        "name": "krx_etf_basic_20260927.csv",
        "csv_asof": "2026-09-27",
    }
    r = eoi.from_official(rows, meta, ["A00001", "005930"], {"A00001": "x"})
    assert r["csv"]["asof"] == "2026-09-27" and r["items"]["A00001"]["found"]
    assert r["items"]["005930"]["kind"] == "stock"
    bad = eoi.from_official({}, {"status": "unavailable"}, ["A00001"], None)
    assert bad["csv"]["ok"] is False
    assert bad["items"]["A00001"]["missing_reason"] == "공식 기준정보 파일을 읽지 못함"


# ── 지수 상태(D3 · I-6 · I-19) ────────────────────────────────────────────────


def _items(meta, *tickers, names=NAMES):
    got = look(meta, list(tickers), names)["items"]
    return [got[t] for t in tickers]


def test_pair_same_index_same_structure(meta):
    a, b = _items(meta, "A00001", "A00003")
    p = eoi.pair_state(a, b)
    assert (p["state"], p["label"]) == ("same", "같은 공식 기초지수")
    # 총보수 '0.150000' ↔ '0.15' = 같은 숫자(표기만 다름) → 구조 차이 아님
    assert p["structure_diffs"] == []
    assert p["reason"] == "두 상품 모두 공식 기초지수 '가상 대표 200'"


def test_pair_same_index_different_structure_keeps_same_and_lists_diffs(meta):
    a, b = _items(meta, "A00001", "A00002")
    p = eoi.pair_state(a, b)
    assert p["state"] == "same" and p["reason"].endswith(" · 상품 구조 다름")
    assert p["structure_diffs"] == [
        {"field": "추적배수", "a": "일반", "b": "2X 레버리지"},
        {"field": "복제방법", "a": "실물(패시브)", "b": "실물(액티브)"},
    ]


# r1 F2 — 빈 값은 차이가 아니다: 두 값이 모두 확인된 칸만 '구조 다름' · 빈 칸은 '확인 안 된 구조 항목'(빈 쪽)
FEE45 = {"field": "총보수", "a": "0.150000", "b": "0.45"}


@pytest.mark.parametrize(
    "a_over, b_over, diffs, unconfirmed, tail",
    [
        (
            {},
            {"총보수": ""},
            [],
            [{"field": "총보수", "side": "b"}],
            " · 상품 구조 일부 확인 안 됨",
        ),
        (
            {"총보수": ""},
            {},
            [],
            [{"field": "총보수", "side": "a"}],
            " · 상품 구조 일부 확인 안 됨",
        ),
        (
            {"과세유형": ""},
            {"과세유형": "   "},
            [],
            [{"field": "과세유형", "side": "both"}],
            " · 상품 구조 일부 확인 안 됨",
        ),
        ({}, {"총보수": "0.45"}, [FEE45], [], " · 상품 구조 다름"),
        (
            {"추적배수": ""},
            {"총보수": "0.45"},
            [FEE45],
            [{"field": "추적배수", "side": "a"}],
            " · 상품 구조 다름 · 상품 구조 일부 확인 안 됨",
        ),
    ],
    ids=["후보 쪽 빔", "보유 쪽 빔", "두 쪽 모두 빔", "두 쪽 확인 · 다름", "다름 + 빔"],
)
def test_pair_empty_structure_value_is_unconfirmed_not_diff(
    tmp_path, a_over, b_over, diffs, unconfirmed, tail
):
    b = {**A, "단축코드": "A00009", "한글종목약명": "가상 아홉"}
    write_csv(tmp_path / "meta", rows=[{**A, **a_over}, {**b, **b_over}])
    x, y = _items(tmp_path / "meta", "A00001", "A00009")
    p = eoi.pair_state(x, y)
    # 같은 공식 지수는 그대로 '같은 공식 기초지수'(차이 요약 허용) · 빈 칸은 차이 목록에 없음
    assert (p["state"], p["structure_diffs"], p["structure_unconfirmed"]) == (
        "same",
        diffs,
        unconfirmed,
    )
    assert p["reason"] == "두 상품 모두 공식 기초지수 '가상 대표 200'" + tail


def test_route_etf_official_empty_fee_is_not_structure_diff(tmp_path, monkeypatch):
    """검증자 r1 F2 재현 — 같은 공식 지수 두 ETF 중 한쪽 총보수만 빈 값(임시 CSV · 임시 DB)."""
    meta = tmp_path / "meta"
    b = {**A, "단축코드": "A00009", "한글종목약명": "가상 아홉", "총보수": ""}
    write_csv(meta, rows=[A, b])
    db = tmp_path / "market.sqlite"
    upsert_etf_master(
        [EtfMasterRow(t, t, "1", 1.0, 1, 1.0) for t in ("A00001", "A00009")],
        source="TestSource",
        db_path=db,
    )
    monkeypatch.setattr(eoi, "META_DIR", meta)
    monkeypatch.setattr(eoi.market_data_store, "DEFAULT_DB_PATH", db)
    eoi._CACHE.clear()
    got = TestClient(api_module.app).get(
        "/market/etf-official", params={"tickers": "A00001,A00009"}
    )
    p = got.json()["pair"]
    assert got.status_code == 200 and p["state"] == "same"
    assert p["structure_diffs"] == [] and "상품 구조 다름" not in p["reason"]
    assert p["structure_unconfirmed"] == [{"field": "총보수", "side": "b"}]
    assert got.json()["items"]["A00009"]["fee_pct"] is None


# r1 G3 — 빈칸 대신 적힌 자리 표시('-' · '—' · '–' · '－')와 공백뿐인 값 = 빈 값과 똑같이 '확인 안 된 구조 항목'
# (차이 목록 · '상품 구조 다름'에 넣지 않음). 실제 CSV(krx_etf_basic_20260927.csv 1,175행)에는 지금 이런 값이 없다.
PLACEHOLDER = ["-", "—", "–", "－", " ", "　", "\t", " - ", "　－　"]
STRUCT = {
    "multiple": "일반",
    "replication": "실물(패시브)",
    "fee_pct": "0.150000",
    "tax": "비과세",
}
SAME_TAIL = "두 상품 모두 공식 기초지수 '가상 대표 200' · 상품 구조 일부 확인 안 됨"


def _it(**over):
    return {
        "found": True,
        "kind": "etf",
        "index_name": "가상 대표 200",
        **STRUCT,
        **over,
    }


def _pair(key, side, value):
    a = _it(**({key: value} if side in ("a", "both") else {}))
    b = _it(**({key: value} if side in ("b", "both") else {}))
    return a, b


@pytest.mark.parametrize("side", ["a", "b", "both"])
@pytest.mark.parametrize("ph", PLACEHOLDER, ids=[repr(v) for v in PLACEHOLDER])
def test_placeholder_structure_value_is_unconfirmed_like_empty(ph, side):
    p = eoi.pair_state(*_pair("fee_pct", side, ph))
    empty = eoi.pair_state(*_pair("fee_pct", side, ""))
    want = [{"field": "총보수", "side": side}]
    # 빈 값과 결과가 똑같다(상태 · 사유 · 차이 없음 · 빈 쪽)
    assert p == empty
    assert (p["state"], p["structure_diffs"], p["structure_unconfirmed"]) == (
        "same",
        [],
        want,
    )
    assert p["reason"] == SAME_TAIL and "상품 구조 다름" not in p["reason"]
    assert eoi.structure_diffs(*_pair("fee_pct", side, ph)) == []


@pytest.mark.parametrize("key, label", list(eoi._STRUCTURE))
def test_placeholder_in_every_structure_field_and_mixed_marks(key, label):
    # 두 쪽에 서로 다른 자리 표시('-' ↔ '—') — 글자는 다르지만 차이가 아니라 두 쪽 모두 확인 안 됨
    a, b = _it(**{key: "-"}), _it(**{key: "—"})
    p = eoi.pair_state(a, b)
    assert p["structure_diffs"] == []
    assert p["structure_unconfirmed"] == [{"field": label, "side": "both"}]
    # 한쪽만 자리 표시 · 다른 칸은 확인됐고 다름 = 그 칸만 차이(자리 표시 칸은 확인 안 됨)
    other = "fee_pct" if key != "fee_pct" else "tax"
    p = eoi.pair_state(_it(**{key: "－"}), _it(**{other: "0.45"}))
    assert [d["field"] for d in p["structure_diffs"]] == [dict(eoi._STRUCTURE)[other]]
    assert p["structure_unconfirmed"] == [{"field": label, "side": "a"}]


def test_value_with_dash_inside_is_confirmed_value():
    """자리 표시 = 값 전체가 그 글자 하나일 때만(앞뒤 공백 제외) — 값 안에 줄표가 있으면 확인된 값."""
    p = eoi.pair_state(_it(multiple="1X-인버스"), _it(multiple="일반"))
    assert p["structure_diffs"] == [
        {"field": "추적배수", "a": "1X-인버스", "b": "일반"}
    ]
    assert p["structure_unconfirmed"] == []
    assert "상품 구조 다름" in p["reason"]


def test_route_etf_official_placeholder_values_are_not_structure_diff(
    tmp_path, monkeypatch
):
    """임시 KRX 형식 CSV(cp949 — '—' · '–' 는 이 파일 형식에 담을 수 없어 위 칸 시험에서 확인) · 임시 DB."""
    meta = tmp_path / "meta"
    hold = {**A, "총보수": "－", "복제방법": "　"}
    cand = {
        **A,
        "단축코드": "A00009",
        "한글종목약명": "가상 아홉",
        "과세유형": "-",
        "추적배수": " - ",
    }
    write_csv(meta, rows=[hold, cand])
    db = tmp_path / "market.sqlite"
    upsert_etf_master(
        [EtfMasterRow(t, t, "1", 1.0, 1, 1.0) for t in ("A00001", "A00009")],
        source="TestSource",
        db_path=db,
    )
    monkeypatch.setattr(eoi, "META_DIR", meta)
    monkeypatch.setattr(eoi.market_data_store, "DEFAULT_DB_PATH", db)
    eoi._CACHE.clear()
    got = TestClient(api_module.app).get(
        "/market/etf-official", params={"tickers": "A00001,A00009"}
    )
    assert got.status_code == 200
    p, items = got.json()["pair"], got.json()["items"]
    assert (p["state"], p["structure_diffs"], p["reason"]) == ("same", [], SAME_TAIL)
    assert p["structure_unconfirmed"] == [
        {"field": "추적배수", "side": "b"},
        {"field": "복제방법", "side": "a"},
        {"field": "총보수", "side": "a"},
        {"field": "과세유형", "side": "b"},
    ]
    # 응답 값 글자는 그대로(분류만 바뀜 · 공백뿐인 값은 기존대로 빈 값 = null)
    assert (items["A00001"]["fee_pct"], items["A00001"]["replication"]) == ("－", None)
    assert (items["A00009"]["tax"], items["A00009"]["multiple"]) == ("-", "-")


def test_pair_same_family_and_different(meta):
    a, b = _items(meta, "D00001", "D00002")
    p = eoi.pair_state(a, b)
    assert (p["state"], p["label"]) == ("same_family", "다른 지수 · 같은 계열")
    assert "Dow Jones U.S. Dividend 100 계열" in p["reason"]
    a, b = _items(meta, "A00001", "B00001")
    p = eoi.pair_state(a, b)
    assert (p["state"], p["label"]) == ("different", "다른 지수")
    assert p["reason"] == "공식 기초지수가 다름('가상 대표 200' ↔ '가상 해외 지수')"


@pytest.mark.parametrize(
    "pick, why",
    [
        (("A00001", "E00009"), "공식 기준정보에 없음"),
        (("005930", "A00001"), "개별 주식 · 기초지수 해당 없음"),
        (
            ("005930", "E00009"),
            "개별 주식 · 기초지수 해당 없음 / 공식 기준정보에 없음",
        ),
    ],
)
def test_pair_unconfirmed_reasons(meta, pick, why):
    a, b = _items(meta, *pick)
    p = eoi.pair_state(a, b)
    assert (p["state"], p["label"], p["reason"]) == ("unconfirmed", "기준 미확인", why)
    assert p["structure_diffs"] == []


def test_pair_unconfirmed_when_one_side_not_picked_or_csv_unreadable(meta, tmp_path):
    (a,) = _items(meta, "A00001")
    p = eoi.pair_state(a, None)
    assert (p["state"], p["reason"]) == ("unconfirmed", "고른 상품 없음")
    (x,) = _items(tmp_path / "none", "A00001")
    p = eoi.pair_state(x, a)
    assert (p["state"], p["reason"]) == (
        "unconfirmed",
        "공식 기준정보 파일을 읽지 못함",
    )


def test_pair_order_unconfirmed_wins_over_same_name():
    # 판정 순서 변이 — 한쪽이 공식 기준정보 없음이면 지수명이 같아 보여도 '같은 공식 기초지수'가 아님
    a = {"found": True, "kind": "etf", "index_name": "X"}
    b = {"found": False, "kind": "etf", "index_name": "X", "missing_reason": None}
    assert eoi.pair_state(a, b)["state"] == "unconfirmed"
    assert eoi.pair_state({**b, "found": True}, a)["state"] == "same"


# ── 구성 요약(보유와 무관 · 상태 넷 · I-9 · I-10) ─────────────────────────────


def kr(etf, asof, rank, code, name, w):
    return ConstituentRow(
        etf_ticker=etf,
        asof=asof,
        source=NAVER_STOCK_SOURCE,
        rank=rank,
        constituent_ticker=code,
        constituent_name=name,
        weight_pct=w,
        constituent_key=code,
        constituent_isin=f"KR7{code}003",
        market_type="0",
    )


def cash(etf, asof, rank, w):
    return ConstituentRow(
        etf_ticker=etf,
        asof=asof,
        source=NAVER_STOCK_SOURCE,
        rank=rank,
        constituent_ticker=None,
        constituent_name="원화현금",
        weight_pct=w,
        constituent_key=None,
        constituent_isin="KRD010010001",
        market_type=None,
    )


def rows_11(etf="C00001", asof="2026-11-16"):
    ws = [30.07, 20.90, 6.88, 6.0, 5.0, 4.0, 3.0, 3.0, 2.0, 1.0]
    out = [
        kr(etf, asof, i + 1, f"1{i:05d}", f"가상주식{i + 1}", w)
        for i, w in enumerate(ws)
    ]
    return out + [cash(etf, asof, 11, 0.15)]


ETFS = {"C00001", "100003"}  # 100003 = 구성 안의 국내 ETF(주식이 아님)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "market.sqlite"


def cons(db, etfs=ETFS):
    """구성 요약 — 한 읽기(`weekly_candidate_reads.read_candidate`)로.

    ETF 목록 = 그 DB 의 `etf_master`(etfs=None = 목록 없음)."""
    if etfs:
        upsert_etf_master(
            [EtfMasterRow(t, t, "1", 1.0, 1, 1.0) for t in sorted(etfs)],
            source="TestSource",
            db_path=db,
        )
    return CR.read_candidate("C00001", db_path=db)["constituents"]


def save(rows, db, *, complete):
    replace_constituents_snapshot(
        rows, log_status=LOG_OK, confirm=True, complete=complete, db_path=db
    )


def test_constituents_full_state_top3_and_concentration(db):
    save(rows_11(), db, complete=True)
    d = cons(db)
    assert (d["state"], d["state_label"], d["asof"]) == (
        "full",
        "전체 확인",
        "2026-11-16",
    )
    assert (d["stored_rows"], d["top_n"]) == (11, 11)
    # 100003 은 ETF 목록에 있는 국내 ETF → 주식 아님
    assert d["stock_rows"] == 9 and d["other_rows"] == [
        {"label": "국내 ETF", "count": 1},
        {"label": "원화현금", "count": 1},
    ]
    assert d["top_stocks"] == [
        {"name": "가상주식1", "weight_pct": 30.07},
        {"name": "가상주식2", "weight_pct": 20.9},
        {"name": "가상주식3", "weight_pct": 6.88},
    ]
    assert d["top3_sum_pct"] == 57.85  # 정확한 소수 합(30.07 + 20.90 + 6.88)
    assert d["concentration"]["top1_weight_pct"] == 30.07
    assert d["concentration"]["top10_weight_pct"] == round(
        sum([30.07, 20.90, 6.88, 6.0, 5.0, 4.0, 3.0, 3.0, 2.0, 1.0]), 2
    )
    assert [r["is_stock"] for r in d["rows"]].count(True) == 9
    assert d["line"] == (
        "구성 기준일 11/16 · 저장 11행(주식 9 · 국내 ETF 1 · 원화현금 1) · 전체 확인(원천 항목 11개를 모두 받음)"
    )
    assert "rows" not in wcr.summary_of(d) and "concentration" not in wcr.summary_of(d)


def test_constituents_top_rows_state(db):
    save(rows_11()[:10], db, complete=False)
    d = cons(db)
    assert (d["state"], d["state_label"], d["top_n"]) == (
        "top_rows",
        "상위 10행만 확인",
        10,
    )
    assert d["line"].endswith("상위 10행만 확인(그 밖 구성은 미확인)")


def test_constituents_unconfirmed_shows_latest_stored_with_label(db):
    upsert_constituents(rows_11(), db_path=db)  # 확인 기록 없음(예전 수집 경로)
    d = cons(db)
    assert (d["state"], d["state_label"], d["asof"]) == (
        "source_unconfirmed",
        "원천 기준일 미확인",
        "2026-11-16",
    )
    assert d["top_n"] is None and d["stored_rows"] == 11
    assert d["top_stocks"][0] == {"name": "가상주식1", "weight_pct": 30.07}


def test_constituents_confirmed_older_beats_newer_unconfirmed(db):
    save(rows_11(asof="2026-11-13"), db, complete=True)
    upsert_constituents(rows_11(asof="2026-11-16")[:3], db_path=db)
    d = cons(db)
    assert (d["state"], d["asof"], d["stored_rows"]) == ("full", "2026-11-13", 11)


def test_constituents_not_collected_and_unknown_stock_list(db):
    d = cons(db)
    assert (d["state"], d["state_label"], d["stored_rows"]) == (
        "not_collected",
        "미수집",
        0,
    )
    assert d["top_stocks"] == [] and d["top3_sum_pct"] is None
    assert d["line"] == "구성 자료 없음(미수집) — [구성종목 보기]에서 수집"
    save(rows_11(), db.with_name("no_list.sqlite"), complete=True)
    d = cons(db.with_name("no_list.sqlite"), etfs=None)
    # ETF 목록을 못 읽으면 주식 행을 가르지 않음(0 · 빈 목록과 구분)
    assert d["stocks_known"] is False and d["stock_rows"] is None
    assert d["top_stocks"] == [] and d["top3_sum_pct"] is None
    assert "ETF 목록을 읽지 못해 주식 행을 가를 수 없음" in d["line"]


def test_top3_sum_is_none_when_a_weight_is_unreadable(db):
    rows = rows_11()
    rows[1] = kr("C00001", "2026-11-16", 2, "100001", "가상주식2", None)
    save(rows, db, complete=True)
    d = cons(db)
    assert d["top3_sum_pct"] is None  # 0 으로 채우지 않음


@pytest.fixture
def client(monkeypatch, db):
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", db)
    return TestClient(api_module.app)


def test_summary_endpoint_returns_rows_and_name(client, db, monkeypatch):
    save(rows_11(), db, complete=True)
    upsert_etf_master(
        [EtfMasterRow("C00001", "가상 구성 ETF", "1", 1.0, 1, 1.0)],
        source="TestSource",
        db_path=db,
    )
    r = client.get("/market/constituents/summary", params={"ticker": " C00001 "}).json()
    assert (r["status"], r["ticker"], r["name"], r["state"]) == (
        "ok",
        "C00001",
        "가상 구성 ETF",
        "full",
    )
    assert len(r["rows"]) == 11 and r["rows"][-1]["kind_label"] == "원화현금"
    assert set(r["rows"][0]) == {"rank", "name", "weight_pct", "is_stock", "kind_label"}
    assert set(r["concentration"]) == {
        "top1_weight_pct",
        "top3_weight_pct",
        "top5_weight_pct",
        "top10_weight_pct",
    }
    # 화면을 열어도 수집하지 않음(GET = 읽기만 · 행 수 그대로)
    again = client.get(
        "/market/constituents/summary", params={"ticker": "C00001"}
    ).json()
    assert again["stored_rows"] == 11


def test_summary_endpoint_bad_ticker_missing_db_and_read_failure(
    client, db, monkeypatch
):
    assert (
        client.get("/market/constituents/summary", params={"ticker": "a b"}).status_code
        == 422
    )
    assert client.get("/market/constituents/summary").status_code == 422
    r = client.get("/market/constituents/summary", params={"ticker": "C00001"}).json()
    assert (r["status"], r["name"]) == ("missing", None)
    save(rows_11(), db, complete=True)

    def boom(*a, **k):
        import sqlite3

        raise sqlite3.OperationalError("locked")

    real = CR.snapshots_in
    monkeypatch.setattr(CR, "snapshots_in", boom)
    r = client.get("/market/constituents/summary", params={"ticker": "C00001"}).json()
    assert (r["status"], r["state"], r["name"]) == ("error", "error", None)
    assert r["message"].startswith("구성 자료를 읽지 못함")
    # ETF 목록만 못 읽음(표 없음 · 잠김 = None) → 이름 없음 · 구성은 그대로(주식 행을 가르지 않음)
    monkeypatch.setattr(CR, "snapshots_in", real)
    monkeypatch.setattr(CR, "master_in", lambda con: None)
    r = client.get("/market/constituents/summary", params={"ticker": "C00001"}).json()
    assert (r["status"], r["state"], r["name"], r["stocks_known"]) == (
        "ok",
        "full",
        None,
        False,
    )


# ── R2 국내시장 대비 문구(I-7) · ② 행 자료 부족(I-11) ─────────────────────────────

AFTER = {"date": "2026-11-16", "state": "after_close", "fetched_at_kst": None}
UNK = {"date": "2026-11-16", "state": "unknown", "fetched_at_kst": None}


@pytest.mark.parametrize(
    "etf, diff, kodex, prov, want",
    [
        (5.0, 3.0, 2.0, False, "올랐고 국내시장보다 3.00%p 높음"),
        (1.0, -2.0, 3.0, False, "올랐지만 국내시장보다 2.00%p 낮음"),
        (1.0, 0.004, 0.996, False, "올랐음 · 국내시장과 같음"),
        (-2.0, 3.0, -5.0, False, "내렸지만 국내시장보다 3.00%p 덜 내림"),
        (-5.0, -2.0, -3.0, False, "내렸고 국내시장보다 2.00%p 더 내림"),
        (-2.0, -3.0, 1.0, False, "내렸고 국내시장보다 3.00%p 낮음"),
        (-2.0, 0.0, -2.0, False, "내렸음 · 국내시장과 같음"),
        (0.004, 1.0, -1.0, False, "변화 없음 · 국내시장보다 1.00%p 높음"),
        (0.0, -1.0, 1.0, False, "변화 없음 · 국내시장보다 1.00%p 낮음"),
        (-0.001, 0.0, 0.0, False, "변화 없음 · 국내시장과 같음"),
        (5.0, 3.0, 2.0, True, "올랐고 국내시장보다 3.00%p 높음 · 잠정 비교"),
    ],
)
def test_v2_market_phrase_table(etf, diff, kodex, prov, want):
    assert wcr.market_phrase(wcr.direction_of(etf), diff, kodex, prov) == want


@pytest.mark.parametrize(
    "crit, end_price, index_name, official_ok, want",
    [
        ({}, AFTER, "지수 X", True, []),
        (
            {"three_month": {"status": "period_differs"}},
            AFTER,
            "지수 X",
            True,
            ["3개월 기간 다름"],
        ),
        (
            {"one_month": {"status": "missing", "value": None}},
            UNK,
            None,
            True,
            ["1개월 수익률 없음", "가격 끝일 상태 모름", "공식 기준정보 없음"],
        ),
        (
            {},
            None,
            None,
            False,
            ["가격 끝일 상태 모름", "공식 기준정보 파일 읽기 실패"],
        ),
    ],
)
def test_v2_row_lack_reasons(crit, end_price, index_name, official_ok, want):
    ok = {"status": "ok", "value": 1.0, "start": "s", "end": "e"}
    row = {
        "criteria": {
            "one_month": {**ok, **crit.get("one_month", {})},
            "three_month": {**ok, **crit.get("three_month", {})},
        },
        "classification": {"index_name": index_name},
    }
    if end_price is not None:
        row["end_price"] = end_price
    assert wcr.lack_of(row, official_ok) == want


# ── 보유 겹침 카드 기간(I-22) ──────────────────────────────────────────────────


def test_v2_topn_basis_period_range_and_empty():
    payload = {
        "status": "ok",
        "asof": "2026-11-16",
        "basis": "one_month",
        "n": 10,
        "filters": dict(wr.FILTERS),
        "candidates": [
            {
                "selected_basis_start_date": "2026-10-19",
                "selected_basis_end_date": "2026-11-16",
            },
            {
                "selected_basis_start_date": "2026-10-20",
                "selected_basis_end_date": "2026-11-16",
            },
            {"selected_basis_start_date": None, "selected_basis_end_date": None},
        ],
    }
    assert topn_basis(payload) == {
        "basis": "one_month",
        "n": 10,
        "count": 3,
        "filters": dict(wr.FILTERS),
        "start_min": "2026-10-19",
        "start_max": "2026-10-20",
        "end": "2026-11-16",
    }
    empty = topn_basis(
        {
            "status": "empty",
            "asof": None,
            "basis": "one_month",
            "n": 10,
            "candidates": [],
        }
    )
    assert (empty["count"], empty["start_min"], empty["end"]) == (0, None, None)


def test_topn_basis_reaches_holdings_evidence_response(api_client):  # noqa: F811
    # 응답 모델에 칸이 있어야 직렬화에서 빠지지 않음(실제 GET · 임시 DB · 시작일이 ETF 마다 다른 사례)
    db = api_market_topn.DEFAULT_DB_PATH
    end = date(2026, 5, 30)
    _seed_history(db, "A00001", "가상 하나", end, [100.0 + i for i in range(25)])
    _seed_history(db, "A00002", "가상 둘", end, [100.0 + i * 2 for i in range(20)])
    tb = api_client.get("/holdings/market-evidence/latest").json()["topn_basis"]
    assert (tb["basis"], tb["n"], tb["count"]) == ("one_month", 10, 2)
    assert (tb["start_min"], tb["start_max"], tb["end"]) == (
        "2026-05-06",
        "2026-05-11",
        "2026-05-30",
    )
