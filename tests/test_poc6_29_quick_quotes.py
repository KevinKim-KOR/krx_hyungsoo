"""POC6-29 보완 — 빠른 시세(네이버 코스피 · 코스닥 · KODEX 200)(PLAN §9-2 ⓪ · 보완 판정 Q-R1 · 확인 1).

- 응답 해석: `tests/fixtures/poc6_29_quick_quotes/` = 개발자가 2026-11-12 받은 **네이버 공개 응답 사본**(칸만 줄임 ·
  README.txt). 장중(OPEN) · 손상 응답은 이 파일 안에서 만든 **합성** 자료다(이름 · 주석에 '합성').
- 시도 상태: 원천 시각만 바뀜 = unchanged(마지막 성공 그대로) · 장 상태 · 값 · 등락 · 등락률 · 거래일 변화 = updated ·
  첫 성공 = updated. 일부 실패 = partial(실패 항목은 마지막 성공 유지) · 전부 실패 = failed · 저장 실패 = failed.
- 읽기(`GET /market/quick-quotes`): 저장값만(조회 함수 · 실제 HTTP 를 부르지 않음) · 파일 없음 = empty · 손상 = invalid.
네트워크는 부르지 않는다 — 가짜 조회 함수 · `httpx.MockTransport` 만 쓰고, 실제 HTTP 전송은 시도만 해도 실패.
저장 파일은 임시 폴더(`STORE_FILE` 바꿔 끼움 · 라이브 `state/` 안 씀).
"""

from __future__ import annotations

import copy
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app import market_naver
from app import pc_quick_quotes as qq

FIXTURES = Path(__file__).parent / "fixtures" / "poc6_29_quick_quotes"
URL_KOSPI = "https://m.stock.naver.com/api/index/KOSPI/basic"
URL_KOSDAQ = "https://m.stock.naver.com/api/index/KOSDAQ/basic"
URL_KODEX = "https://m.stock.naver.com/api/stock/069500/basic"
URLS = [URL_KOSPI, URL_KOSDAQ, URL_KODEX]
CODES = ["KOSPI", "KOSDAQ", "069500"]
UPDATED = {"status": "updated", "reason": None}
UNCHANGED = {"status": "unchanged", "reason": None}


def _fx(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _kospi(**changes: Any) -> dict[str, Any]:
    """합성 — 코스피 15:36 사본에서 칸만 바꾼 응답."""
    p = _fx("kospi_1536")
    p.update(changes)
    return p


def _without(name: str, key: str) -> dict[str, Any]:
    p = _fx(name)
    del p[key]
    return p


def _closed(kospi: str = "kospi_1536") -> dict[str, Any]:
    return {
        URL_KOSPI: _fx(kospi),
        URL_KOSDAQ: _fx("kosdaq_1536"),
        URL_KODEX: _fx("kodex200_1535"),
    }


class FakeFetch:
    """주소 → 응답(예외면 던짐) · 부른 주소 기록."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url: str) -> object:
        self.calls.append(url)
        r = self.responses[url]
        if isinstance(r, BaseException):
            raise r
        return copy.deepcopy(r)


def _at(h: int, m: int, s: int = 0) -> Callable[[], datetime]:
    return lambda: datetime(2026, 11, 12, h, m, s, tzinfo=qq.KST)


def _quote(name: str, fetched_at: str, **over: Any) -> dict[str, Any]:
    q, reason = qq.parse_quote(_fx(name), fetched_at)
    assert reason is None and q is not None
    return {**q, **over}


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qq, "STORE_FILE", tmp_path / "market_cache" / "quick_quotes_latest.json"
    )


@pytest.fixture(autouse=True)
def _no_real_http(monkeypatch: pytest.MonkeyPatch) -> Any:
    attempts: list[str] = []

    def blocked(self: Any, request: httpx.Request) -> Any:
        attempts.append(str(request.url))
        raise RuntimeError("실제 HTTP 전송 금지(시험)")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    yield
    assert attempts == [], f"실제 HTTP 전송 시도: {attempts}"


# ── 응답 해석(네이버 사본) ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name, value, change, pct, source_time",
    [
        ("kospi_1536", 5342.73, -32.63, -0.61, "2026-11-12T15:36:00+09:00"),
        ("kospi_1558", 5342.73, -32.63, -0.61, "2026-11-12T15:58:00+09:00"),
        ("kosdaq_1536", 696.53, -8.57, -1.22, "2026-11-12T15:36:00+09:00"),
        ("kodex200_1535", 84240.0, -300.0, -0.35, "2026-11-12T15:35:18+09:00"),
    ],
)
def test_naver_copies_parse_to_contract_fields(
    name: str, value: float, change: float, pct: float, source_time: str
) -> None:
    quote, reason = qq.parse_quote(_fx(name), "2026-11-12T15:36:05+09:00")
    assert reason is None
    assert quote == {
        "value": value,
        "change": change,
        "change_pct": pct,
        "source_time": source_time,
        "trade_date": "2026-11-12",
        "market_status": "CLOSE",
        "fetched_at": "2026-11-12T15:36:05+09:00",
    }


@pytest.mark.parametrize(
    "changes, change, pct, status",
    [
        (
            {"compareToPreviousClosePrice": None, "fluctuationsRatio": None},
            None,
            None,
            "CLOSE",
        ),
        # 합성 — 부호가 빠진 금액(market_naver 466920 사례)은 등락률과 어긋나 비운다
        ({"compareToPreviousClosePrice": "32.63"}, None, -0.61, "CLOSE"),
        (
            {"compareToPreviousClosePrice": "0", "fluctuationsRatio": "0.00"},
            0.0,
            0.0,
            "CLOSE",
        ),
        ({"fluctuationsRatio": "250"}, -32.63, None, "CLOSE"),  # 등락률 범위 밖 = 없음
        ({"marketStatus": None}, -32.63, -0.61, None),
    ],
)
def test_optional_fields_never_fail_the_item(
    changes: dict[str, Any], change: Any, pct: Any, status: Any
) -> None:
    quote, reason = qq.parse_quote(_kospi(**changes), "2026-11-12T15:36:05+09:00")
    assert reason is None and quote is not None
    assert (quote["value"], quote["change"], quote["change_pct"]) == (
        5342.73,
        change,
        pct,
    )
    assert quote["market_status"] == status


# ── 받기 · 저장 ───────────────────────────────────────────────────────────


def test_first_refresh_fetches_three_fixed_urls_and_stores_them() -> None:
    fetch = FakeFetch(_closed())
    out = qq.refresh_quick_quotes(fetch=fetch, now=_at(15, 36, 5))
    assert fetch.calls == URLS
    assert out == {
        "status": "done",
        "fetched_at": "2026-11-12T15:36:05+09:00",
        "items": {c: UPDATED for c in CODES},
        "message": None,
    }
    stored = json.loads(qq.STORE_FILE.read_text(encoding="utf-8"))
    assert stored["updated_at"] == "2026-11-12T15:36:05+09:00"
    assert list(stored["items"]) == CODES
    assert stored["items"]["069500"] == {
        "last_success": _quote("kodex200_1535", "2026-11-12T15:36:05+09:00"),
        "last_attempt": {
            "at": "2026-11-12T15:36:05+09:00",
            "status": "updated",
            "reason": None,
        },
    }
    assert [p.name for p in qq.STORE_FILE.parent.iterdir()] == [qq.STORE_FILE.name]
    body = qq.read_quick_quotes()
    assert body["status"] == "ok" and body["message"] is None
    assert [(i["code"], i["name"], i["kind"]) for i in body["items"]] == [
        ("KOSPI", "코스피", "index"),
        ("KOSDAQ", "코스닥", "index"),
        ("069500", "KODEX 200", "stock"),
    ]
    assert [i["quote"]["value"] for i in body["items"]] == [5342.73, 696.53, 84240.0]


def test_index_time_ticking_after_close_with_same_values_is_unchanged() -> None:
    """확인 1 — 실측: 코스피 15:36 · 15:58 같은 값. 원천 시각만 다르면 '조회 성공 · 시세 변동 없음'."""
    qq.refresh_quick_quotes(fetch=FakeFetch(_closed("kospi_1536")), now=_at(15, 36, 5))
    out = qq.refresh_quick_quotes(
        fetch=FakeFetch(_closed("kospi_1558")), now=_at(15, 58, 10)
    )
    assert out["status"] == "done" and out["message"] is None
    assert out["items"] == {c: UNCHANGED for c in CODES}
    kospi = qq.read_quick_quotes()["items"][0]
    # 마지막 성공은 그대로 — 화면은 '원천 시각 15:36 그대로(새 시세 없음)'를 보인다
    assert kospi["quote"] == _quote("kospi_1536", "2026-11-12T15:36:05+09:00")
    assert kospi["last_attempt"] == {
        "at": "2026-11-12T15:58:10+09:00",
        "status": "unchanged",
        "reason": None,
    }


@pytest.mark.parametrize(
    "first, second",
    [
        # 합성 장중 10:05 → 실제 마감 15:36(값 · 등락 · 장 상태 모두 다름)
        (
            _kospi(
                closePrice="5,360.10",
                compareToPreviousClosePrice="-15.26",
                fluctuationsRatio="-0.28",
                localTradedAt="2026-11-12T10:05:00+09:00",
                marketStatus="OPEN",
            ),
            _fx("kospi_1536"),
        ),
        (_kospi(marketStatus="OPEN"), _fx("kospi_1536")),  # 합성 — 장 상태만 다름
        (_kospi(closePrice="5,342.74"), _fx("kospi_1536")),  # 합성 — 값만 다름
        (
            _kospi(compareToPreviousClosePrice="-32.64"),
            _fx("kospi_1536"),
        ),  # 합성 — 등락만
        (_kospi(fluctuationsRatio="-0.62"), _fx("kospi_1536")),  # 합성 — 등락률만
        (
            _fx("kospi_1536"),
            _kospi(localTradedAt="2026-11-13T15:36:00+09:00"),
        ),  # 합성 — 다음 거래일
    ],
    ids=["open_to_close", "status", "value", "change", "change_pct", "trade_date"],
)
def test_any_change_besides_source_time_is_updated(
    first: dict[str, Any], second: dict[str, Any]
) -> None:
    qq.refresh_quick_quotes(
        fetch=FakeFetch({**_closed(), URL_KOSPI: first}), now=_at(15, 0)
    )
    out = qq.refresh_quick_quotes(
        fetch=FakeFetch({**_closed(), URL_KOSPI: second}), now=_at(16, 0)
    )
    assert out["items"]["KOSPI"] == UPDATED
    expected, _ = qq.parse_quote(second, "2026-11-12T16:00:00+09:00")
    assert qq.read_quick_quotes()["items"][0]["quote"] == expected


def test_partial_failure_keeps_the_failed_items_last_success() -> None:
    qq.refresh_quick_quotes(fetch=FakeFetch(_closed()), now=_at(15, 36, 5))
    second = {
        **_closed(),
        URL_KOSPI: _kospi(
            closePrice="5,350.00", localTradedAt="2026-11-12T15:40:00+09:00"
        ),
        URL_KOSDAQ: httpx.ConnectTimeout("slow"),
    }
    out = qq.refresh_quick_quotes(fetch=FakeFetch(second), now=_at(15, 40, 2))
    assert out["status"] == "partial"
    assert out["items"] == {
        "KOSPI": UPDATED,
        "KOSDAQ": {"status": "failed", "reason": "timeout"},
        "069500": UNCHANGED,
    }
    assert out["message"].startswith("코스닥 시세를 받지 못했습니다.")
    kospi, kosdaq, _ = qq.read_quick_quotes()["items"]
    assert kospi["quote"]["value"] == 5350.0
    assert kosdaq["quote"] == _quote("kosdaq_1536", "2026-11-12T15:36:05+09:00")
    assert kosdaq["last_attempt"] == {
        "at": "2026-11-12T15:40:02+09:00",
        "status": "failed",
        "reason": "timeout",
    }


def test_all_failed_keeps_previous_and_never_succeeded_reads_as_no_quote() -> None:
    failing = FakeFetch(
        {
            URL_KOSPI: httpx.ConnectError("down"),
            URL_KOSDAQ: _without("kosdaq_1536", "closePrice"),  # 합성
            URL_KODEX: _without("kodex200_1535", "localTradedAt"),  # 합성
        }
    )
    out = qq.refresh_quick_quotes(fetch=failing, now=_at(9, 1))
    assert out["status"] == "failed" and out["message"] == qq.ALL_FAILED_TEXT
    reasons = ["http_error", "bad_value", "missing_time"]
    assert out["items"] == {
        c: {"status": "failed", "reason": r} for c, r in zip(CODES, reasons)
    }
    body = qq.read_quick_quotes()
    assert body["status"] == "ok"
    assert [i["quote"] for i in body["items"]] == [None, None, None]  # '시세 미확인'
    assert [i["last_attempt"]["reason"] for i in body["items"]] == reasons
    # 성공한 뒤 전부 실패 — 세 항목 모두 마지막 성공을 그대로 둔다
    qq.refresh_quick_quotes(fetch=FakeFetch(_closed()), now=_at(15, 36, 5))
    before = [i["quote"] for i in qq.read_quick_quotes()["items"]]
    assert qq.refresh_quick_quotes(fetch=failing, now=_at(16, 0))["status"] == "failed"
    after = qq.read_quick_quotes()["items"]
    assert [i["quote"] for i in after] == before and None not in before
    assert {i["last_attempt"]["status"] for i in after} == {"failed"}


@pytest.mark.parametrize(
    "response, reason",
    [
        (httpx.ReadTimeout("slow"), "timeout"),
        (httpx.ConnectError("down"), "http_error"),
        (qq.QuickFetchError("http_error"), "http_error"),
        (ValueError("Expecting value"), "bad_value"),  # JSON 해석 실패
        (RuntimeError("unexpected"), "http_error"),
        (["not", "a", "dict"], "bad_value"),
        # 합성 손상 응답
        (_without("kospi_1536", "closePrice"), "bad_value"),
        (_kospi(closePrice=""), "bad_value"),
        (_kospi(closePrice="abc"), "bad_value"),
        (_kospi(closePrice="0"), "bad_value"),
        (_kospi(closePrice="-5"), "bad_value"),
        (_kospi(closePrice="nan"), "bad_value"),
        (_kospi(closePrice=True), "bad_value"),
        (_without("kospi_1536", "localTradedAt"), "missing_time"),
        (_kospi(localTradedAt=""), "missing_time"),
        (_kospi(localTradedAt="15:36"), "missing_time"),
        (_kospi(localTradedAt="2026-11-12T15:36:00"), "missing_time"),  # 시간대 없음
        (_kospi(localTradedAt=20261112), "missing_time"),
    ],
)
def test_failure_reasons(response: Any, reason: str) -> None:
    out = qq.refresh_quick_quotes(
        fetch=FakeFetch({**_closed(), URL_KOSPI: response}), now=_at(15, 36)
    )
    assert out["status"] == "partial"
    assert out["items"]["KOSPI"] == {"status": "failed", "reason": reason}
    assert out["items"]["KOSDAQ"] == UPDATED


def test_default_fetch_uses_naver_client_conventions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """기본 조회 = market_naver 와 같은 시간 제한 · 머리글 · 주소(MockTransport · 네트워크 없음)."""
    real_client = httpx.Client
    made: list[dict[str, Any]] = []
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if url == URL_KOSPI:
            return httpx.Response(200, json=_fx("kospi_1536"))
        if url == URL_KOSDAQ:
            return httpx.Response(503)
        return httpx.Response(200, content=b"<html>not json</html>")

    def factory(**kw: Any) -> httpx.Client:
        made.append(kw)
        return real_client(transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(httpx, "Client", factory)
    assert qq.http_fetch(URL_KOSPI) == _fx("kospi_1536")
    assert made == [
        {
            "timeout": market_naver.DEFAULT_TIMEOUT_SEC,
            "headers": market_naver.DEFAULT_HEADERS,
        }
    ]
    assert seen[0].headers["Referer"] == "https://m.stock.naver.com/"
    assert seen[0].headers["User-Agent"] == market_naver.DEFAULT_HEADERS["User-Agent"]
    out = qq.refresh_quick_quotes(now=_at(15, 36))  # 기본 조회 함수
    assert [str(r.url) for r in seen[1:]] == URLS
    assert out["items"] == {
        "KOSPI": UPDATED,
        "KOSDAQ": {"status": "failed", "reason": "http_error"},
        "069500": {"status": "failed", "reason": "bad_value"},
    }

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with real_client(transport=httpx.MockTransport(slow)) as c:
        with pytest.raises(httpx.TimeoutException):
            qq.http_fetch(URL_KOSPI, client=c)


# ── 손상 · 저장 실패 · 예외 ────────────────────────────────────────────────


def _store_ok() -> dict[str, Any]:
    qq.refresh_quick_quotes(fetch=FakeFetch(_closed()), now=_at(15, 36, 5))
    return json.loads(qq.STORE_FILE.read_text(encoding="utf-8"))


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], Any]:
    def apply(d: dict[str, Any]) -> Any:
        *keys, last = path.split(".")
        node = d
        for k in keys:
            node = node[k]
        if value is _DEL:
            del node[last]
        else:
            node[last] = value
        return d

    return apply


_DEL = object()
_S = "items.KOSPI.last_success"
_A = "items.KOSPI.last_attempt"


@pytest.mark.parametrize(
    "damage",
    [
        lambda d: "{not json",
        lambda d: b"\xff\xfe\x00broken",
        lambda d: [],
        lambda d: {"updated_at": d["updated_at"]},
        _set("items", []),
        _set("items.KOSPI", "x"),
        _set(f"{_S}.value", "5342.73"),
        _set(f"{_S}.value", 0),
        _set(f"{_S}.value", True),
        _set(f"{_S}.change", "-32.63"),
        _set(f"{_S}.source_time", "15:36"),
        _set(f"{_S}.trade_date", "2026-11-11"),  # 원천 시각과 어긋남
        _set(f"{_S}.trade_date", "2026/11/12"),
        _set(f"{_S}.market_status", 1),
        _set(f"{_S}.fetched_at", _DEL),
        _set(f"{_A}.status", "ok"),
        _set(f"{_A}.reason", "x"),  # 받음인데 사유
        _set(f"{_A}.at", "yesterday"),
        _set(_S, None),  # 성공 기록 없이 '받음'
        _set(
            "items.069500.last_attempt",
            {"at": "2026-11-12T15:36:05+09:00", "status": "failed", "reason": None},
        ),
    ],
)
def test_damaged_store_reads_as_invalid(damage: Callable[[Any], Any]) -> None:
    damaged = damage(_store_ok())
    if isinstance(damaged, bytes):
        qq.STORE_FILE.write_bytes(damaged)
    elif isinstance(damaged, str):
        qq.STORE_FILE.write_text(damaged, encoding="utf-8")
    else:
        qq.STORE_FILE.write_text(json.dumps(damaged), encoding="utf-8")
    body = qq.read_quick_quotes()
    assert body["status"] == "invalid" and body["message"] == qq.INVALID_TEXT
    assert [(i["quote"], i["last_attempt"]) for i in body["items"]] == [
        (None, None)
    ] * 3


def test_store_path_is_a_folder_reads_as_invalid() -> None:
    qq.STORE_FILE.mkdir(parents=True)
    assert qq.read_quick_quotes()["status"] == "invalid"


def test_random_damage_never_raises() -> None:
    _store_ok()
    good = qq.STORE_FILE.read_bytes()
    rng = random.Random(20261112)
    seen: set[str] = set()
    for _ in range(300):
        data = bytearray(good)
        if rng.random() < 0.5:
            data = data[: rng.randrange(len(data))]
        else:
            for _ in range(rng.randint(1, 4)):
                data[rng.randrange(len(data))] = rng.randrange(256)
        qq.STORE_FILE.write_bytes(bytes(data))
        body = qq.read_quick_quotes()
        seen.add(body["status"])
        assert body["status"] in ("ok", "invalid")
        assert all(
            i["quote"] is None or qq._valid_success(i["quote"]) for i in body["items"]
        )
    assert "invalid" in seen


def test_refresh_over_unreadable_store_rewrites_it_and_says_so() -> None:
    qq.STORE_FILE.parent.mkdir(parents=True)
    qq.STORE_FILE.write_text("{broken", encoding="utf-8")
    out = qq.refresh_quick_quotes(fetch=FakeFetch(_closed()), now=_at(15, 36, 5))
    assert out["status"] == "done" and out["message"] == qq.PREVIOUS_INVALID_TEXT
    assert qq.read_quick_quotes()["status"] == "ok"


def test_store_write_failure_is_failed_and_keeps_the_previous_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store_ok()
    before = qq.STORE_FILE.read_bytes()

    def broken_replace(src: Any, dst: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(qq.os, "replace", broken_replace)
    second = {**_closed("kospi_1558"), URL_KOSDAQ: httpx.ConnectError("down")}
    out = qq.refresh_quick_quotes(fetch=FakeFetch(second), now=_at(15, 58, 10))
    assert out == {
        "status": "failed",
        "fetched_at": "2026-11-12T15:58:10+09:00",
        "items": {
            "KOSPI": {"status": "failed", "reason": "store_error"},
            "KOSDAQ": {"status": "failed", "reason": "http_error"},
            "069500": {"status": "failed", "reason": "store_error"},
        },
        "message": qq.STORE_FAILED_TEXT,
    }
    assert qq.STORE_FILE.read_bytes() == before
    assert [p.name for p in qq.STORE_FILE.parent.iterdir()] == [qq.STORE_FILE.name]


def test_unexpected_error_inside_refresh_is_returned_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> Any:
        raise RuntimeError("x")

    monkeypatch.setattr(qq, "_load", boom)
    out = qq.refresh_quick_quotes(fetch=FakeFetch(_closed()), now=_at(15, 36))
    assert (out["status"], out["items"], out["message"]) == (
        "failed",
        {},
        qq.ERROR_TEXT,
    )
    assert qq._parse_time(out["fetched_at"]) is not None


# ── 읽기 endpoint(저장값만) ────────────────────────────────────────────────


def test_endpoint_reads_stored_values_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = client.get("/market/quick-quotes")
    assert empty.status_code == 200
    assert empty.json() == {
        "status": "empty",
        "message": None,
        "items": [
            {"code": c, "name": n, "kind": k, "quote": None, "last_attempt": None}
            for c, n, k in [
                ("KOSPI", "코스피", "index"),
                ("KOSDAQ", "코스닥", "index"),
                ("069500", "KODEX 200", "stock"),
            ]
        ],
    }
    qq.refresh_quick_quotes(fetch=FakeFetch(_closed()), now=_at(15, 36, 5))

    def forbidden(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("화면 읽기가 조회 함수를 불렀다")

    for name in ("http_fetch", "refresh_quick_quotes", "_fetch_item", "_write"):
        monkeypatch.setattr(qq, name, forbidden)
    res = client.get("/market/quick-quotes")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["message"] is None
    assert body["items"][0] == {
        "code": "KOSPI",
        "name": "코스피",
        "kind": "index",
        "quote": _quote("kospi_1536", "2026-11-12T15:36:05+09:00"),
        "last_attempt": {
            "at": "2026-11-12T15:36:05+09:00",
            "status": "updated",
            "reason": None,
        },
    }
    assert [i["quote"]["source_time"] for i in body["items"]] == [
        "2026-11-12T15:36:00+09:00",
        "2026-11-12T15:36:00+09:00",
        "2026-11-12T15:35:18+09:00",
    ]
    qq.STORE_FILE.write_text("{", encoding="utf-8")
    bad = client.get("/market/quick-quotes").json()
    assert bad["status"] == "invalid"
    assert bad["message"] == "빠른 시세 저장 파일을 읽지 못했습니다."
    assert [(i["quote"], i["last_attempt"]) for i in bad["items"]] == [(None, None)] * 3
