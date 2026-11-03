"""POC6-19 — 과거 시장 자료 연구 사본(가짜 전송 · tmp DB · 라이브 DB · 실제 키움 / Yahoo 호출 0).

PLAN §3-5 대응: 날짜 무시 응답 · 반복 값 오탐 방지(판정 보완 1) · 부호 · 단위 · 빈 값 · 미완료 페이지 · 호출 제한 ·
인증 거절 · 연속 실패 중단 · 5xx 재시도 · 서머타임 창 앞뒤 · WTI 음수 보존 · 원/달러 0 이하 · Yahoo 날짜 집합
차이(판정 보완 2) · 중간 중단 뒤 원시 · 종료 이유 · 실행 폴더 밖 쓰기 0 · verify 의 변조 검출.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import requests

from app import kiwoom_investor_flow as KW
from app.market_history import fetch as FT
from app.market_history import normalize as N
from app.market_history import verify as VR
from app.supply_fx_oil_store import USDKRW, WTI

KOSPI_DATES = [
    "2022-01-03",
    "2022-01-04",
    "2022-06-01",
    "2023-01-02",
    "2023-01-03",
    "2023-06-01",
    "2024-01-02",
    "2024-01-30",
    "2024-02-01",
    "2024-02-02",
]
CLOSES = {d: round(2000 + i * 11.11, 2) for i, d in enumerate(KOSPI_DATES)}
PLAN = FT.Plan(
    flow_samples=("2024-02-02", "2024-02-01", "2023-01-02", "2022-01-03"),
    macro_windows=(
        ("R", "2024-01-30", "2024-02-02"),
        ("P1", "2023-04-04", "2023-04-06"),
        ("P2", "2022-01-04", "2022-01-07"),
    ),
    target_end="2024-02-02",
    macro_target_start="2022-01-04",
)
B_DATES = [
    "2024-01-30",
    "2024-01-02",
    "2023-06-01",
    "2023-01-03",
    "2022-06-01",
    "2022-01-04",
]
NOW = datetime(2026, 11, 3, 3, 0, tzinfo=timezone.utc)  # 12:00 KST
FIELDS = list(KW.FIELD_TO_INVESTOR)
KEY, SECRET = "APPKEY-SECRET-1", "APPSECRET-SECRET-2"
TOKEN = "TOKEN-SECRET-3"


class Resp:
    def __init__(self, status: int, payload=None, text=None, headers=None):
        self.status_code = status
        self.text = (
            text if text is not None else json.dumps(payload, ensure_ascii=False)
        )
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _nets(d: str) -> list[str]:
    base = int(d.replace("-", "")) % 997
    return [f"{'-' if i % 2 else '+'}{base + i}" for i in range(len(FIELDS))]


def kiwoom_body(d: str, *, close=None, nets=None, rc=0, row_extra=None, with_001=True):
    row = {"inds_cd": "001", "inds_nm": "종합(KOSPI)"}
    row["cur_prc"] = f"+{round((CLOSES[d] if close is None else close) * 100)}"
    row.update(dict(zip(FIELDS, nets or _nets(d))))
    row.update(row_extra or {})
    rows = [{"inds_cd": "002", "inds_nm": "대형주", "cur_prc": "+100"}]
    rows += [row] if with_001 else []
    return {"return_code": rc, "return_msg": "정상", "inds_netprps": rows}


class FakeKiwoom:
    """날짜마다 동작 목록을 차례로 쓴다: ok · 503 · conn · 1700 · nodata · mismatch · ('nets', …)."""

    def __init__(self, plan=None, auth_code=0):
        self.plan, self.auth_code, self.calls = dict(plan or {}), auth_code, []

    def __call__(self, url, json=None, headers=None, timeout=None):
        if url.endswith(KW.TOKEN_PATH):
            self.calls.append("TOKEN")
            if self.auth_code:
                msg = f"[{self.auth_code}:지정단말기 인증에 실패했습니다] IP 1.2.3.4"
                return Resp(200, {"return_code": 3, "return_msg": msg})
            return Resp(
                200, {"return_code": 0, "token": TOKEN, "expires_dt": "29991231235959"}
            )
        d = N.iso(json["base_dt"])
        self.calls.append(d)
        steps = self.plan.get(d) or ["ok"]
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        if step == "conn":
            raise requests.ConnectionError("down")
        if step == "503":
            return Resp(503, text="busy")
        if step == "1700":
            return Resp(200, {"return_code": 1700, "return_msg": "요청 개수 초과"})
        if step == "rl_msg":
            msg = "[1700:허용된 요청 개수를 초과하였습니다]"
            return Resp(200, {"return_code": 5, "return_msg": msg})
        if step == "auth_msg":
            msg = "[8005:토큰이 유효하지 않습니다] IP 1.2.3.4"
            return Resp(200, {"return_code": 3, "return_msg": msg})
        if step == "weird":
            return Resp(200, {"return_code": 0, "inds_netprps": [None]})
        if step == "kbi":
            raise KeyboardInterrupt
        if step == "big":
            return Resp(200, kiwoom_body(d, row_extra={"pad": "x" * 2_000_000}))
        if step == "nodata":
            return Resp(200, {"return_code": 1, "return_msg": "조회 자료 없음"})
        if step == "mismatch":
            return Resp(200, kiwoom_body(d, close=CLOSES["2024-02-02"] + 50))
        if step == "nopage":
            return Resp(200, kiwoom_body(d, with_001=False), headers={"cont-yn": "Y"})
        if isinstance(step, tuple) and step[0] == "nets":
            return Resp(200, kiwoom_body(d, nets=step[1]))
        if isinstance(step, tuple) and step[0] == "dt":
            return Resp(200, kiwoom_body(d, row_extra={"dt": step[1]}))
        return Resp(200, kiwoom_body(d))

    def data_calls(self):
        return [c for c in self.calls if c != "TOKEN"]


def _weekday_series(first, last, base, skip=(), override=None):
    out, d = {}, date.fromisoformat(first)
    while d <= date.fromisoformat(last):
        k = d.isoformat()
        if d.weekday() < 5 and k not in skip:
            out[k] = round(base + (d.toordinal() % 50) * 0.37, 4)
        d += timedelta(days=1)
    out.update(override or {})
    return out


class FakeYahoo:
    TZ = {"KRW=X": "Europe/London", "CL=F": "America/New_York"}

    def __init__(
        self,
        fx_override=None,
        status=None,
        b_override=None,
        drop=None,
        fail_calls=None,
        pad=None,
        on_call=None,
        odd=None,
    ):
        self.series = {
            "KRW=X": _weekday_series(
                "2022-01-03",
                "2024-02-09",
                1200,
                skip={"2024-01-31"},
                override=fx_override,
            ),
            "CL=F": _weekday_series(
                "2022-01-03", "2024-02-09", 70, override={"2023-04-05": -37.63}
            ),
        }
        self.status, self.calls = dict(status or {}), []
        # fail_calls = {심볼: {그 심볼의 몇 번째 호출}} → HTTP 404
        # b_override = {심볼: {날짜: 값}} — 긴 구간 요청(장기 창)에만
        # pad = {심볼: 바이트} — 장기 창 응답에 상관없는 칸을 덧붙여 크게
        self.fail_calls, self.b_override = fail_calls or {}, b_override or {}
        self.pad, self.on_call = pad or {}, on_call
        self.odd = odd or {}  # {심볼: {날짜: "HH:MM"(자정 아닌 봉) 또는 None(빈 종가)}}
        for sym, dates in (drop or {}).items():
            for d in dates:
                self.series[sym].pop(d, None)

    def __call__(self, url, params=None, headers=None, timeout=None):
        sym = url.rsplit("/", 1)[1]
        self.calls.append(sym)
        if self.on_call:
            self.on_call(sym)
        if self.status.get(sym):
            return Resp(self.status[sym], text="limit")
        if self.calls.count(sym) in self.fail_calls.get(sym, ()):
            return Resp(404, text="not found")
        tz = ZoneInfo(self.TZ[sym])
        stamps, closes = [], []
        series = dict(self.series[sym])
        if params["period2"] - params["period1"] > 90 * 86400:
            series.update(self.b_override.get(sym, {}))
        for d, c in sorted(series.items()):
            when = time(0)
            odd = self.odd.get(sym, {})
            if d in odd and odd[d]:
                when = time(*map(int, odd[d].split(":")))
            ts = int(datetime.combine(date.fromisoformat(d), when, tz).timestamp())
            if params["period1"] <= ts < params["period2"]:
                stamps.append(ts)
                closes.append(None if d in odd and odd[d] is None else c)
        today = int(datetime(2026, 11, 3, tzinfo=tz).timestamp())
        meta = {
            "exchangeTimezoneName": self.TZ[sym],
            "currentTradingPeriod": {"regular": {"start": today}},
        }
        if self.pad.get(sym) and params["period2"] - params["period1"] > 90 * 86400:
            meta["padding"] = "x" * self.pad[sym]
        body = {
            "chart": {
                "result": [
                    {
                        "meta": meta,
                        "timestamp": stamps,
                        "indicators": {"quote": [{"close": closes}]},
                    }
                ]
            }
        }
        return Resp(200, body)


class Clock:
    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def mono(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture()
def env(tmp_path):
    market = tmp_path / "market.sqlite"
    con = sqlite3.connect(market)
    con.executescript(
        "CREATE TABLE market_benchmark_daily_price(benchmark_id TEXT, benchmark_name TEXT,"
        " date TEXT, close REAL, source TEXT, created_at TEXT);"
        "CREATE TABLE market_investor_flow_daily(market TEXT, trade_date TEXT, investor TEXT,"
        " buy_value INTEGER, sell_value INTEGER, net_value INTEGER, source TEXT,"
        " collected_at TEXT);"
        "CREATE TABLE market_macro_daily(series_id TEXT, obs_date TEXT, value REAL, unit TEXT,"
        " provider TEXT, basis TEXT, collected_at TEXT);"
    )
    for d in KOSPI_DATES:
        con.execute(
            "INSERT INTO market_benchmark_daily_price VALUES('KOSPI','KOSPI',?,?,'NAVER_FDR','t')",
            (d, CLOSES[d]),
        )
    for i, field in enumerate(FIELDS):  # 2024-02-01 저장본 · foreign 하나만 값이 다름
        won = int(_nets("2024-02-01")[i]) * KW.EOK_TO_WON
        inv = KW.FIELD_TO_INVESTOR[field]
        won += 1 if inv == "foreign" else 0
        con.execute(
            "INSERT INTO market_investor_flow_daily"
            " VALUES('KOSPI','2024-02-01',?,NULL,NULL,?,'s','t')",
            (inv, won),
        )
    fx = FakeYahoo().series["KRW=X"]
    for d, v in (
        ("2024-01-30", fx["2024-01-30"]),
        ("2024-01-31", 1300.0),
        ("2024-02-01", 9.0),
    ):
        con.execute(
            "INSERT INTO market_macro_daily VALUES(?,?,?,'KRW/USD','p','b','t')",
            (USDKRW, d, v),
        )
    con.commit()
    con.close()
    sealed = tmp_path / "sealed.sqlite"
    con = sqlite3.connect(sealed)
    con.executescript(
        "CREATE TABLE krx_dataset_version(version_id TEXT, status TEXT);"
        "CREATE TABLE krx_dataset_member(version_id TEXT, bas_dd TEXT, response_id INTEGER);"
    )
    con.execute(
        "INSERT INTO krx_dataset_version VALUES(?, 'SEALED')", (FT.SEALED_VERSION,)
    )
    for d in ["2021-12-30", *KOSPI_DATES]:
        con.execute(
            "INSERT INTO krx_dataset_member VALUES(?,?,1)",
            (FT.SEALED_VERSION, d.replace("-", "")),
        )
    con.commit()
    con.close()
    repo = tmp_path / "repo"
    repo.mkdir()
    return {"tmp": tmp_path, "market": market, "sealed": sealed, "repo": repo}


def _run(
    env,
    kiwoom=None,
    yahoo=None,
    limits=FT.Limits(),
    plan=PLAN,
    now=NOW,
    creds=(KEY, SECRET),
):
    clock = Clock()
    kiwoom = kiwoom or FakeKiwoom()
    yahoo = yahoo or FakeYahoo()
    summary = FT.run(
        repo_root=env["repo"],
        out_root=env["tmp"] / "runs",
        plan=plan,
        limits=limits,
        market_db=env["market"],
        sealed_db=env["sealed"],
        credentials=creds,
        kiwoom_post=kiwoom,
        yahoo_get=yahoo,
        sleep=clock.sleep,
        monotonic=clock.mono,
        now_utc=lambda: now,
        code=lambda root: {"git_head": "TEST"},
    )
    run_dir = env["tmp"] / "runs" / summary["run_id"] if "run_id" in summary else None
    return summary, run_dir, kiwoom, yahoo, clock


def _report(run_dir):
    return json.loads((run_dir / "report.json").read_text(encoding="utf-8"))


def _flow_rows(run_dir):
    text = (run_dir / N.FLOW_DATES_CSV).read_text(encoding="utf-8").splitlines()
    head = text[0].split(",")
    return {r.split(",")[0]: dict(zip(head, r.split(","))) for r in text[1:]}


# --- 전체 흐름 -----------------------------------------------------------------


def test_full_run_archive_ready_verify_ok_and_isolation(env):
    market_before, sealed_before = _sha(env["market"]), _sha(env["sealed"])
    summary, run_dir, kw, yh, clock = _run(env)
    assert summary["status"] == "OK", summary
    assert summary["sources"] == {
        "kospi_flow": "ARCHIVE_READY",
        USDKRW: "ARCHIVE_READY",
        WTI: "ARCHIVE_READY",
    }
    # A 표본 = 최근 → 과거 · B = 최신부터 · A 날짜는 다시 부르지 않음
    assert kw.data_calls() == list(PLAN.flow_samples) + B_DATES
    assert kw.calls.count("TOKEN") == 1
    assert yh.calls == ["KRW=X"] * 3 + ["CL=F"] * 3 + ["KRW=X", "CL=F"]
    assert (
        all(s <= 1.0 for s in clock.sleeps) and len(clock.sleeps) >= 10
    )  # 공급자 시작 간격
    rep = _report(run_dir)
    flow = rep["sources"]["kospi_flow"]
    assert flow["actual"]["valid_dates"] == len(KOSPI_DATES)
    assert flow["date_check"] == {
        "direct": 0,
        "indirect": len(KOSPI_DATES),
        "fields_seen": [],
    }
    assert (
        flow["not_requested_before_kospi_start"]["count"] == 1
    )  # 2021-12-30 = 결측 아님
    assert (
        flow["stored_overlap"]["different"]["count"] == 1
    )  # foreign 만 다름 · 고치지 않음
    assert flow["stored_overlap"]["equal"] == 12
    # 판정 보완 2 — 저장본에만 있는 01-31 · 값이 다른 02-01 이 있어도 B 진행 · 기록만
    fx = rep["sources"][USDKRW]
    assert fx["windows"]["B_FULL"]["status"] == "VALID"
    assert fx["stored_overlap"]["only_stored"]["items"] == [
        {"key": "2024-01-31", "reason": "새 응답에 없음(사유 미확인)"}
    ]
    assert flow["stored_overlap"]["compared_pairs"] == 13
    assert flow["stored_overlap"]["only_new"]["items"] == [
        {"key": "2024-02-02", "reason": "저장본에 없음(사유 미확인)"}
    ]
    assert {w: c["different"]["count"] for w, c in fx["sample_vs_full"].items()} == {
        "P1": 0,
        "P2": 0,
        "R": 0,
    }
    assert fx["weekday_gaps"]["longest_run"] == 1 and fx["duplicate_windows"] == []
    assert fx["stored_overlap"]["different"]["count"] == 1
    assert {
        "date": "2024-01-31",
        "kind": "봉 없음(휴장 가능 · 기대 거래일 미확정)",
    } in fx["weekday_gaps"]["items"]
    # 서머타임(런던 4월) 창 = 시작일 봉이 남고 앞뒤 하루 여유로 들어온 봉은 잘림
    p1 = fx["windows"]["P1"]
    assert p1["counts"]["in_window"] == 3 and p1["counts"]["outside_window"] == 1
    macro = (run_dir / N.MACRO_CSV).read_text(encoding="utf-8")
    assert f"{USDKRW},KRW=X,A,P1,2023-04-04," in macro
    oil = rep["sources"][WTI]
    assert oil["nonpositive"]["kept_flagged"] == [
        "2023-04-05"
    ]  # WTI 음수 = 보존 · 표시
    assert rep["three_common"]["weeks"] > 0
    assert VR.verify_run(run_dir)["status"] == "OK"
    # 키 · 토큰 · 접속 IP 가 어떤 파일에도 없다
    for p in run_dir.rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            assert "SECRET" not in text and "1.2.3.4" not in text, p
    # 운영 DB · 봉인 판 불변 · 실행 폴더 밖 새 파일 0
    assert _sha(env["market"]) == market_before and _sha(env["sealed"]) == sealed_before
    outside = [
        p
        for p in env["tmp"].rglob("*")
        if p.is_file()
        and run_dir not in p.parents
        and p not in (env["market"], env["sealed"])
    ]
    assert outside == []
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["end_reason"] == "COMPLETED" and end["sealed_unchanged"] is True


def test_repeat_values_are_flagged_not_failed(env):
    same = ("nets", ["+5"] * 13)
    kw = FakeKiwoom({"2024-01-30": [same], "2024-01-02": [same], "2023-06-01": [same]})
    summary, run_dir, *_ = _run(env, kiwoom=kw)
    rows = _flow_rows(run_dir)
    for d in ("2024-01-30", "2024-01-02", "2023-06-01"):
        assert rows[d]["status"] == "VALID" and rows[d]["repeat_suspect"] == "1"
    assert rows["2022-01-04"]["repeat_suspect"] == "0"
    assert (
        summary["sources"]["kospi_flow"] == "ARCHIVE_READY"
    )  # 연속 실패로 세지 않아 B 끝까지


def test_three_consecutive_failures_stop_kiwoom_b(env):
    kw = FakeKiwoom({d: ["nodata"] for d in B_DATES[:3]})
    summary, run_dir, kw, *_ = _run(env, kiwoom=kw)
    assert kw.data_calls() == list(PLAN.flow_samples) + B_DATES[:3]
    rep = _report(run_dir)
    assert rep["sources"]["kospi_flow"]["status"] == "PARTIAL"
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert "연속 실패 3회" in end["providers"]["kiwoom"]["b"]["stop"]
    assert VR.verify_run(run_dir)["status"] == "OK"


def test_recent_sample_failure_blocks_kiwoom_b(env):
    kw = FakeKiwoom({"2024-02-02": ["mismatch"]})
    summary, run_dir, kw, yh, _ = _run(env, kiwoom=kw)
    assert kw.data_calls() == list(PLAN.flow_samples)  # 장기 조회 없음
    flow = _report(run_dir)["sources"]["kospi_flow"]
    assert flow["status"] == "PARTIAL"
    assert any("장기 조회 안 함" in c for c in flow["causes"])
    assert (
        _flow_rows(run_dir)["2024-02-02"]["reason"] == "지수값 ≠ 그날 저장 코스피 종가"
    )
    assert summary["sources"][USDKRW] == "ARCHIVE_READY"  # 다른 공급자는 계속


@pytest.mark.parametrize(
    "step", ["1700", "rl_msg"]
)  # 응답 코드 · 문구 안 사유 코드 두 꼴
def test_rate_limit_stops_kiwoom_only(env, step):
    kw = FakeKiwoom({"2024-02-02": [step]})
    summary, run_dir, kw, yh, _ = _run(env, kiwoom=kw)
    assert kw.data_calls() == ["2024-02-02"]
    assert summary["sources"]["kospi_flow"] == "FETCH_FAILED"
    assert summary["sources"][USDKRW] == "ARCHIVE_READY"
    assert "호출 제한" in summary["end_reason"]


def test_auth_rejection_is_access_blocked_without_message(env):
    summary, run_dir, kw, *_ = _run(env, kiwoom=FakeKiwoom(auth_code=8050))
    assert kw.data_calls() == []
    assert summary["sources"]["kospi_flow"] == "ACCESS_BLOCKED"
    auth = N.read_jsonl(run_dir / N.KIWOOM_AUTH_RAW)
    assert [(a["return_code"], a["msg_code"]) for a in auth] == [(3, 8050)]
    assert "return_msg" not in auth[0] and "body" not in auth[0]
    assert "8050" in summary["end_reason"]
    assert summary["sources"][WTI] == "ARCHIVE_READY"


def test_missing_credentials_is_access_blocked(env):
    summary, _, kw, *_ = _run(env, creds=(None, None))
    assert kw.calls == [] and summary["sources"]["kospi_flow"] == "ACCESS_BLOCKED"


def test_5xx_and_connection_errors_retry_once(env):
    kw = FakeKiwoom({"2024-01-30": ["503", "ok"], "2024-01-02": ["conn", "conn"]})
    summary, run_dir, kw, _, _clock = _run(env, kiwoom=kw)
    lines = N.read_jsonl(run_dir / N.KIWOOM_RAW)
    by = [(ln["base_dt"], ln["attempt"]) for ln in lines]
    assert ("20240130", 2) in by and ("20240102", 2) in by
    rows = _flow_rows(run_dir)
    assert (
        rows["2024-01-30"]["status"] == "VALID"
        and rows["2024-01-30"]["attempts"] == "2"
    )
    assert rows["2024-01-02"]["reason"] == "통신 오류(ConnectionError)"
    assert kw.data_calls()[-1] == B_DATES[-1]  # 짧은 끊김 뒤에도 B 를 끝까지 받는다
    assert _clock.sleeps.count(FT.Limits().comm_backoff_seconds) == 1
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["requests"]["data"]["kiwoom"]["B"]["retries"] == 2
    assert VR.verify_run(run_dir)["status"] == "OK"


def test_fx_nonpositive_marks_partial(env):
    summary, run_dir, *_ = _run(env, yahoo=FakeYahoo(fx_override={"2023-05-02": 0.0}))
    fx = _report(run_dir)["sources"][USDKRW]
    assert fx["status"] == "PARTIAL" and fx["nonpositive"]["invalid"] == ["2023-05-02"]


def test_yahoo_rate_limit_stops_yahoo_only(env):
    summary, run_dir, _, yh, _ = _run(env, yahoo=FakeYahoo(status={"KRW=X": 429}))
    assert yh.calls == ["KRW=X"]
    assert summary["sources"][USDKRW] == "FETCH_FAILED"
    assert summary["sources"]["kospi_flow"] == "ARCHIVE_READY"


def test_phase_budget_stop_keeps_raw_and_reason(env):
    summary, run_dir, kw, *_ = _run(env, limits=FT.Limits(b_requests=3))
    assert summary["status"] == "OK"
    assert len(kw.data_calls()) == len(PLAN.flow_samples) + 1  # B = Yahoo 2 + 키움 1
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert "B 요청 상한 3회" in end["end_reason"]
    assert summary["sources"]["kospi_flow"] == "PARTIAL"
    assert (run_dir / "files.json").is_file() and VR.verify_run(run_dir)[
        "status"
    ] == "OK"


# --- 판정 단위 -----------------------------------------------------------------


def _line(d, body, http=200, cont_yn=None, error=None):
    return {
        "seq": 1,
        "phase": "A",
        "base_dt": d.replace("-", ""),
        "attempt": 1,
        "http_status": http,
        "cont_yn": cont_yn,
        "body": json.dumps(body, ensure_ascii=False),
        "error": error,
    }


KOSPI_MAP = {d: (c, "NAVER_FDR") for d, c in CLOSES.items()}


def test_sign_unit_minus_zero_and_blank_not_zero():
    nets = ["-0", "+12", "-5"] + ["+0"] * 10
    ev = N.evaluate_flow_line(
        _line("2024-02-01", kiwoom_body("2024-02-01", nets=nets)), KOSPI_MAP
    )
    got = {inv: won for inv, _, _, won in ev["values"]}
    assert ev["status"] == "VALID"
    assert (got["individual"], got["foreign"], got["institution"]) == (
        0,
        12 * 10**8,
        -5 * 10**8,
    )
    blank = ["" if i == 1 else "+1" for i in range(13)]
    ev = N.evaluate_flow_line(
        _line("2024-02-01", kiwoom_body("2024-02-01", nets=blank)), KOSPI_MAP
    )
    assert ev["status"] == "FAILED" and ev["values"] is None  # 0 으로 바꾸지 않는다


def test_response_date_field_decides_date_check():
    ok = kiwoom_body("2024-02-01", row_extra={"dt": "20240201"})
    ev = N.evaluate_flow_line(_line("2024-02-01", ok), KOSPI_MAP)
    assert ev["status"] == "VALID" and ev["date_check"] == "DIRECT"
    bad = kiwoom_body("2024-02-01", row_extra={"dt": "20240202"})
    ev = N.evaluate_flow_line(_line("2024-02-01", bad), KOSPI_MAP)
    assert ev["status"] == "FAILED" and ev["reason"] == "응답 날짜 ≠ 요청일"


def test_latest_value_for_old_date_fails_by_index():
    latest = kiwoom_body("2022-01-04", close=CLOSES["2024-02-02"])
    ev = N.evaluate_flow_line(_line("2022-01-04", latest), KOSPI_MAP)
    assert ev["status"] == "FAILED" and ev["index_diff"] > 0.005


def test_incomplete_page_and_missing_row():
    body = kiwoom_body("2024-02-01", with_001=False)
    ev = N.evaluate_flow_line(_line("2024-02-01", body, cont_yn="Y"), KOSPI_MAP)
    assert ev["reason"].startswith("미완료 페이지")
    ev = N.evaluate_flow_line(_line("2024-02-01", body), KOSPI_MAP)
    assert ev["reason"] == "코스피 종합 행(001) 없음"
    weird = {"return_code": 0, "inds_netprps": ["x"]}
    assert (
        N.evaluate_flow_line(_line("2024-02-01", weird), KOSPI_MAP)["status"]
        == "FAILED"
    )


def test_repeat_marking_keeps_status():
    evs = [
        N.evaluate_flow_line(_line(d, kiwoom_body(d, nets=["+1"] * 13)), KOSPI_MAP)
        for d in ("2024-02-01", "2024-02-02")
    ]
    N.mark_repeats(evs)
    assert [(e["status"], e["repeat_suspect"]) for e in evs] == [("VALID", 1)] * 2


# --- 거부 · 검산 ----------------------------------------------------------------


def test_plan_mismatch_refused_before_any_request(env):
    bad = FT.Plan(
        flow_samples=("2024-02-02", "2024-02-01", "2023-01-03", "2022-01-03"),
        macro_windows=PLAN.macro_windows,
        target_end=PLAN.target_end,
        macro_target_start=PLAN.macro_target_start,
    )
    summary, run_dir, kw, yh, _ = _run(env, plan=bad)
    assert summary["status"] == "REFUSED"
    assert kw.calls == [] and yh.calls == []
    start = json.loads((run_dir / "run_start.json").read_text(encoding="utf-8"))
    assert "2023-01-02" in start["refused"]


def test_start_window_refused_without_folder(env):
    summary, run_dir, kw, *_ = _run(
        env, now=datetime(2026, 11, 3, 0, 40, tzinfo=timezone.utc)
    )
    assert summary["status"] == "REFUSED" and run_dir is None
    assert not (env["tmp"] / "runs").exists() and kw.calls == []


def _reindex(run_dir):
    idx = run_dir / "files.json"
    doc = json.loads(idx.read_text(encoding="utf-8"))
    for f in doc["files"]:
        p = run_dir / f["path"]
        f["bytes"], f["sha256"] = p.stat().st_size, _sha(p)
    idx.write_text(json.dumps(doc), encoding="utf-8")


def test_verify_detects_tampered_normalized_and_raw(env):
    _, run_dir, *_ = _run(env)
    csv_path = run_dir / N.FLOW_VALUES_CSV
    text = csv_path.read_text(encoding="utf-8")
    rows = text.splitlines()
    head, won = rows[-1].rsplit(",", 1)
    rows[-1] = f"{head},{int(won) + 1}"
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    res = VR.verify_run(run_dir)
    assert res["status"] == "MISMATCH"
    assert f"파일 바이트 · sha256 다름: {N.FLOW_VALUES_CSV}" in res["problems"]
    # 파일 목록 해시까지 맞춘 변조도 원시에서 다시 계산해 잡는다(요약끼리만 비교하지 않음)
    for rel in (N.FLOW_VALUES_CSV, "report.md"):
        if rel == "report.md":
            md = run_dir / rel
            md.write_text(md.read_text(encoding="utf-8") + "x\n", encoding="utf-8")
        _reindex(run_dir)
        res = VR.verify_run(run_dir)
        assert not any("파일 바이트" in p for p in res["problems"])
        label = "정규화" if rel != "report.md" else "보고"
        assert f"{label} 다시 계산 결과가 다름: {rel}" in res["problems"], res
    csv_path.write_text(text, encoding="utf-8")
    raw = run_dir / N.KIWOOM_RAW
    lines = raw.read_text(encoding="utf-8").splitlines()
    doc = json.loads(lines[0])
    doc["body"] = doc["body"].replace('"+', '"-', 1)
    raw.write_text(
        "\n".join([json.dumps(doc, ensure_ascii=False), *lines[1:]]) + "\n",
        encoding="utf-8",
    )
    res = VR.verify_run(run_dir)
    assert any("본문 sha256" in p for p in res["problems"])


# --- 독립 검토 반영 시험 ---------------------------------------------------------


def test_data_request_auth_rejection_stops_kiwoom_as_access_blocked(env):
    kw = FakeKiwoom({"2024-01-02": ["auth_msg"]})
    summary, run_dir, kw, *_ = _run(env, kiwoom=kw)
    assert kw.data_calls() == list(PLAN.flow_samples) + ["2024-01-30", "2024-01-02"]
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["providers"]["kiwoom"]["stop"]["status"] == "ACCESS_BLOCKED"
    assert "8005" in end["providers"]["kiwoom"]["stop"]["reason"]
    assert _flow_rows(run_dir)["2024-01-02"]["reason"].endswith("(인증 거절)")
    assert "1.2.3.4" not in (run_dir / N.KIWOOM_RAW).read_text(encoding="utf-8")


def test_keyboard_interrupt_records_interrupted_and_keeps_files(env):
    kw = FakeKiwoom({B_DATES[2]: ["kbi"]})
    with pytest.raises(KeyboardInterrupt):
        _run(env, kiwoom=kw)
    (run_dir,) = list((env["tmp"] / "runs").iterdir())
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["error"]["type"] == "INTERRUPTED"
    assert end["end_reason"] == "ERROR(INTERRUPTED)"
    assert (run_dir / "report.json").is_file() and (run_dir / "files.json").is_file()
    assert VR.verify_run(run_dir)["status"] == "OK"
    _assert_report_faulted(run_dir, "실행 중단: INTERRUPTED")


def test_communication_failures_wait_then_stop_separately(env):
    kw = FakeKiwoom({d: ["conn", "conn"] for d in B_DATES[:3]})
    summary, run_dir, kw, _, clock = _run(env, kiwoom=kw)
    assert kw.data_calls() == list(PLAN.flow_samples) + [
        d for d in B_DATES[:3] for _ in (1, 2)
    ]
    assert clock.sleeps.count(FT.Limits().comm_backoff_seconds) == 2
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["providers"]["kiwoom"]["b"]["stop"].startswith("통신 연속 실패 3회")


def test_structure_and_communication_counts_are_separate(env):
    kw = FakeKiwoom(
        {
            B_DATES[0]: ["nodata"],
            B_DATES[1]: ["conn", "conn"],
            B_DATES[2]: ["nodata"],
            B_DATES[3]: ["conn", "conn"],
        }
    )
    summary, run_dir, kw, *_ = _run(env, kiwoom=kw)
    assert kw.data_calls()[-1] == B_DATES[-1]  # 두 종류가 번갈아 와도 3회에 닿지 않음


def test_unexpected_shape_fails_that_date_only(env):
    kw = FakeKiwoom({"2023-06-01": ["weird"]})
    summary, run_dir, kw, yh, _ = _run(env, kiwoom=kw)
    assert summary["status"] == "OK" and kw.data_calls()[-1] == B_DATES[-1]
    assert _flow_rows(run_dir)["2023-06-01"]["status"] == "FAILED"
    assert yh.calls.count("CL=F") == 4


def test_yahoo_failures_are_counted_per_symbol(env):
    summary, run_dir, _, yh, _ = _run(env, yahoo=FakeYahoo(status={"KRW=X": 404}))
    assert yh.calls == ["KRW=X"] * 3 + ["CL=F"] * 3 + ["CL=F"]
    assert summary["sources"][USDKRW] == "FETCH_FAILED"
    assert summary["sources"][WTI] == "ARCHIVE_READY"
    fx = _report(run_dir)["sources"][USDKRW]
    assert any(c.startswith("조회 중단: 연속 실패 3회") for c in fx["causes"])


def test_b_skipped_by_estimate_is_recorded(env, monkeypatch):
    real = FT._b_estimate

    def capped(*a, **k):
        return {**real(*a, **k), "skipped_reason": "예상 용량 시험"}

    monkeypatch.setattr(FT, "_b_estimate", capped)
    summary, run_dir, kw, *_ = _run(env)
    assert kw.data_calls() == list(PLAN.flow_samples)
    assert "장기 조회 생략" in summary["end_reason"]
    rep = _report(run_dir)
    assert any("장기 조회 생략" in c for c in rep["sources"][USDKRW]["causes"])
    assert rep["sources"][USDKRW]["status"] == "PARTIAL"
    assert rep["sources"]["kospi_flow"]["not_requested_in_target"]["count"] == len(
        B_DATES
    )


def test_sample_and_full_window_values_are_compared(env):
    yh = FakeYahoo(b_override={"KRW=X": {"2024-01-30": 1.5}})
    summary, run_dir, *_ = _run(env, yahoo=yh)
    fx = _report(run_dir)["sources"][USDKRW]
    diff = fx["sample_vs_full"]["R"]["different"]
    assert diff["count"] == 1 and diff["items"][0]["key"] == "2024-01-30"


def test_long_internal_gap_is_partial(env):
    hole = [f"2023-01-{d:02d}" for d in range(2, 32)]
    summary, run_dir, *_ = _run(env, yahoo=FakeYahoo(drop={"CL=F": hole}))
    oil = _report(run_dir)["sources"][WTI]
    assert oil["status"] == "PARTIAL"
    assert any(c.startswith("중간 공백 최장 연속 평일 22일") for c in oil["causes"])


def _session(tmp_path, wall):
    from app.market_history.transport import Recorder, Session

    clock = Clock()
    rec = Recorder(tmp_path / "run", 10**9)
    return Session(rec, FT.Limits(), clock.sleep, clock.mono, wall), clock


def test_session_stops_when_quiet_window_starts(tmp_path):
    now = {"t": NOW}
    session, _ = _session(tmp_path, lambda: now["t"])
    session.begin_phase("B")
    session.before_data("kiwoom", retry=False)  # 12:00 KST = 통과
    now["t"] = datetime(2026, 11, 3, 0, 31, tzinfo=timezone.utc)  # 09:31 KST
    with pytest.raises(FT.PhaseStop, match="운영 작업 시간대"):
        session.before_data("kiwoom", retry=False)


def test_session_time_cap_uses_wall_clock(tmp_path):
    now = {"t": NOW}
    session, _ = _session(tmp_path, lambda: now["t"])
    session.begin_phase("B")
    now["t"] = NOW + timedelta(seconds=7300)  # 맥북이 잠들어 단조 시계는 멈췄던 경우
    with pytest.raises(FT.PhaseStop, match="시간 상한"):
        session.before_data("kiwoom", retry=False)


def test_redact_ipv4_and_ipv6_keeps_times():
    text = "from 1.2.3.4 and 2001:db8::1 at 12:30:45"
    assert N.redact(text) == "from [IP] and [IP] at 12:30:45"


def test_yahoo_counts_do_not_mix_between_symbols(env):
    yh = FakeYahoo(status={"KRW=X": 404}, fail_calls={"CL=F": {1}})
    summary, run_dir, _, yh, _ = _run(env, yahoo=yh)
    # KRW=X 3회 실패 뒤에도 CL=F 는 자기 실패 1회만 센다 → 나머지 두 창도 조회
    assert yh.calls == ["KRW=X"] * 3 + ["CL=F"] * 3
    assert _report(run_dir)["sources"][WTI]["windows"]["P1"]["status"] == "VALID"


# --- 검증자 r1 정정(F1 입력 전제 · F2 상한) -------------------------------------


def _sealed_sql(env, sql, *args):
    con = sqlite3.connect(env["sealed"])
    con.execute(sql, args)
    con.commit()
    con.close()


@pytest.mark.parametrize(
    "case, reason",
    [
        ("draft", "봉인되지 않은 판"),
        ("no_version", "봉인 판 기록이 없다"),
        ("no_dates", "날짜 목록이 비어 있다"),
        ("no_sealed_file", "봉인 판 파일이 없다"),
        ("no_market_db", "운영 시장 DB 파일이 없다"),
        ("no_kospi", "코스피 종가가 없다"),
    ],
)
def test_input_premise_refused_before_any_request(env, case, reason):
    if case == "draft":
        _sealed_sql(env, "UPDATE krx_dataset_version SET status = 'DRAFT'")
    elif case == "no_version":
        _sealed_sql(env, "DELETE FROM krx_dataset_version")
    elif case == "no_dates":
        _sealed_sql(env, "DELETE FROM krx_dataset_member")
    elif case == "no_sealed_file":
        env["sealed"].unlink()
    elif case == "no_market_db":
        env["market"].unlink()
    else:
        con = sqlite3.connect(env["market"])
        con.execute("DELETE FROM market_benchmark_daily_price")
        con.commit()
        con.close()
    summary, run_dir, kw, yh, _ = _run(env)
    assert summary["status"] == "REFUSED" and reason in summary["reason"]
    assert kw.calls == [] and yh.calls == [] and run_dir is None
    assert not (env["tmp"] / "runs").exists()


def test_sealed_status_rechecked_on_input_copy(env, monkeypatch):
    _sealed_sql(env, "UPDATE krx_dataset_version SET status = 'DRAFT'")
    # 앞 검사를 지나도 입력 사본에서 다시 막는다
    monkeypatch.setattr(FT, "precheck", lambda *a: None)
    summary, run_dir, kw, yh, _ = _run(env)
    assert summary["status"] == "REFUSED" and kw.calls == [] and yh.calls == []
    start = json.loads((run_dir / "run_start.json").read_text(encoding="utf-8"))
    assert "봉인되지 않은 판" in start["refused"]


def test_sealed_change_during_run_is_error(env):
    def touch(sym):
        with open(env["sealed"], "ab") as fh:
            fh.write(b"x")

    summary, run_dir, *_ = _run(env, yahoo=FakeYahoo(on_call=touch))
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ERROR" and end["error"]["type"] == "INPUT_CHANGED"
    assert "ARCHIVE_READY" not in summary["sources"].values()
    problems = VR.verify_run(run_dir)["problems"]
    assert "실행 중 봉인 판 파일이 바뀌었거나 확인 기록이 없음" in problems


def test_last_yahoo_response_over_byte_limit_is_recorded(env):
    yh = FakeYahoo(pad={"KRW=X": 3_000_000})
    limits = FT.Limits(max_bytes=1_000_000)
    summary, run_dir, kw, yh, _ = _run(env, yahoo=yh, creds=(None, None), limits=limits)
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    # KRW=X 장기 응답이 상한을 넘김 → 그 자리에서 멈춰 CL=F 장기 창은 요청하지 않는다
    assert yh.calls == ["KRW=X"] * 3 + ["CL=F"] * 3 + ["KRW=X"]
    assert end["error"]["type"] == "RunStop"
    assert "파일 용량 상한 초과" in end["error"]["message"]
    assert summary["status"] == "ERROR"
    # 장기 창을 다 받았어도 실행 오류가 기록된 실행 = ARCHIVE_READY 아님
    fx = _report(run_dir)["sources"][USDKRW]
    assert fx["status"] == "PARTIAL" and any(
        "파일 용량 상한" in c for c in fx["causes"]
    )
    assert VR.verify_run(run_dir)["status"] == "OK"  # 초과가 기록됐으므로 검산 일치


def test_kiwoom_data_response_over_byte_limit_stops_run(env):
    kw = FakeKiwoom({"2024-01-02": ["big"]})
    limits = FT.Limits(max_bytes=1_500_000)
    summary, run_dir, kw, *_ = _run(env, kiwoom=kw, limits=limits)
    assert kw.data_calls()[-1] == "2024-01-02"
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["error"]["type"] == "RunStop"
    assert "파일 용량 상한 초과" in end["error"]["message"]
    assert summary["status"] == "ERROR"


def _bytes(run_dir, *names):
    return sum((run_dir / n).stat().st_size for n in names)


def test_auth_response_over_byte_limit_stops_run(env):
    _, first, *_ = _run(env)
    names = (N.INPUT_KOSPI, N.INPUT_STORED, N.INPUT_SEALED, "run_start.json")
    before_auth = _bytes(first, *names)
    limits = FT.Limits(max_bytes=before_auth + 40)
    summary, run_dir, kw, yh, _ = _run(env, limits=limits)
    assert kw.calls == ["TOKEN"] and yh.calls == []
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["error"]["type"] == "RunStop"
    assert "파일 용량 상한 초과" in end["error"]["message"]


def _assert_report_faulted(run_dir, phrase):
    """실패한 실행의 최종 보고 = 어느 자료도 ARCHIVE_READY 아님 · 사유가 report.json / md 에 있음."""
    rep = _report(run_dir)
    assert all(s["status"] != "ARCHIVE_READY" for s in rep["sources"].values())
    for sec in rep["sources"].values():
        assert any(phrase in c for c in sec["causes"]), (sec["label"], sec["causes"])
    assert phrase in (run_dir / "report.md").read_text(encoding="utf-8")


def test_postprocess_over_byte_limit_is_recorded(env, monkeypatch):
    real = FT._b_estimate

    def no_skip(*a, **k):  # 예상 용량으로 B 를 건너뛰지 않게 — 후처리 뒤 검사만 본다
        est = real(*a, **k)
        est.pop("skipped_reason", None)
        return est

    monkeypatch.setattr(FT, "_b_estimate", no_skip)
    _, first, *_ = _run(env)
    files = json.loads((first / "files.json").read_text(encoding="utf-8"))["files"]
    total = sum(f["bytes"] for f in files if f["path"] != "postprocess.json")
    fetched = json.loads((first / "run_end.json").read_text(encoding="utf-8"))
    cap = total - 200
    assert fetched["resources"]["bytes_written"] < cap - 5_000  # 조회 중에는 상한 안
    summary, run_dir, *_ = _run(env, limits=FT.Limits(max_bytes=cap))
    post = json.loads((run_dir / "postprocess.json").read_text(encoding="utf-8"))
    assert post["error"]["type"] == "LIMIT"
    assert "파일 용량 상한 초과" in post["error"]["message"]
    assert summary["status"] == "ERROR" and VR.verify_run(run_dir)["status"] == "OK"
    _assert_report_faulted(run_dir, "후처리 상한")  # 검증자 r2 F3
    assert "후처리 상한 초과" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_memory_limit_after_fetch_is_recorded(env, monkeypatch):
    monkeypatch.setattr(FT, "peak_rss_bytes", lambda: 5 * 1024**3)
    summary, run_dir, *_ = _run(env)
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    post = json.loads((run_dir / "postprocess.json").read_text(encoding="utf-8"))
    assert "메모리 상한 초과" in end["error"]["message"]
    assert post["error"]["type"] == "LIMIT" and summary["status"] == "ERROR"
    assert VR.verify_run(run_dir)["status"] == "OK"
    _assert_report_faulted(run_dir, "후처리 상한")


def test_verify_flags_unrecorded_limit_and_unsealed_input(env):
    _, run_dir, *_ = _run(env)
    edits = {
        "run_start.json": lambda d: d["limits"].update(max_bytes=1000, max_rss_bytes=1),
        N.INPUT_SEALED: lambda d: d.update(status="DRAFT"),
        "postprocess.json": lambda d: d.update(limit_seconds=1e-9),
    }
    for rel, edit in edits.items():
        path = run_dir / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        edit(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    _reindex(run_dir)
    problems = VR.verify_run(run_dir)["problems"]
    assert any(p.startswith("파일 용량 상한 초과가 기록되지 않음") for p in problems)
    assert "입력 봉인 판 상태가 SEALED 가 아님: DRAFT" in problems
    assert any(p.startswith("메모리 상한 초과가 기록되지 않음") for p in problems)
    assert any(p.startswith("후처리 시간 상한 초과가 기록되지 않음") for p in problems)


def test_postprocess_time_limit_is_recorded(env, monkeypatch):
    monkeypatch.setattr(FT, "POSTPROCESS_LIMIT_SECONDS", -1)
    summary, run_dir, *_ = _run(env)
    post = json.loads((run_dir / "postprocess.json").read_text(encoding="utf-8"))
    assert post["error"]["type"] == "LIMIT"
    assert "후처리 시간 상한 초과" in post["error"]["message"]
    assert summary["status"] == "ERROR"
    _assert_report_faulted(run_dir, "후처리 시간 상한 초과")  # 검증자 r2 F3
    assert VR.verify_run(run_dir)["status"] == "OK"


# --- 설계자 RESULT 판정(PARTIAL) 정정 — A 연속 실패 = 공급자 중단 · 공백 구분 ---------------

PLAN5 = FT.Plan(
    flow_samples=("2024-02-02", "2024-02-01", "2024-01-02", "2023-01-02", "2022-01-03"),
    macro_windows=PLAN.macro_windows,
    target_end=PLAN.target_end,
    macro_target_start=PLAN.macro_target_start,
)


@pytest.mark.parametrize("step", [["nodata"], ["conn", "conn"]])  # 날짜 · 구조 / 통신
def test_a_consecutive_failures_stop_kiwoom_so_b_is_zero(env, step):
    old = ("2024-01-02", "2023-01-02", "2022-01-03")
    kw = FakeKiwoom({d: list(step) for d in old})
    summary, run_dir, kw, yh, _ = _run(env, kiwoom=kw, plan=PLAN5)
    assert sorted(set(kw.data_calls())) == sorted(PLAN5.flow_samples)  # B 요청 0회
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    kiwoom = end["providers"]["kiwoom"]
    assert (
        kiwoom["gate"]["passed"] is True
    )  # 최근 두 표본은 성공 — 그래도 같은 실행의 B 는 없다
    assert "연속 실패 3회" in kiwoom["stop"]["reason"] and kiwoom["b"]["planned"] == 0
    assert yh.calls[-2:] == ["KRW=X", "CL=F"]  # 다른 공급자는 계속
    flow = _report(run_dir)["sources"]["kospi_flow"]
    assert flow["status"] == "PARTIAL"
    assert any(c.startswith("공급자 중단:") for c in flow["causes"])


def test_yahoo_symbol_stopped_in_a_gets_no_b(env):
    windows = (
        ("R", "2024-01-30", "2024-02-02"),
        ("P0", "2023-06-05", "2023-06-09"),
        ("P1", "2023-04-04", "2023-04-06"),
        ("P2", "2022-06-06", "2022-06-10"),
        ("P3", "2022-01-04", "2022-01-07"),
    )
    plan = FT.Plan(
        flow_samples=PLAN.flow_samples,
        macro_windows=windows,
        target_end=PLAN.target_end,
        macro_target_start=PLAN.macro_target_start,
    )
    yh = FakeYahoo(fail_calls={"KRW=X": {3, 4, 5}})
    summary, run_dir, _, yh, _ = _run(env, yahoo=yh, plan=plan)
    end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    assert end["providers"]["yahoo"]["gates"][USDKRW]["passed"] is True
    assert "KRW=X" in end["providers"]["yahoo"]["symbol_stop"]
    assert yh.calls == ["KRW=X"] * 5 + ["CL=F"] * 5 + ["CL=F"]  # KRW=X 장기 창 0회
    assert (
        end["b_estimate"]["requests"] == len(B_DATES) + 1
    )  # 장기 조회 예상에도 KRW=X 없음
    assert summary["sources"][WTI] == "ARCHIVE_READY"
    assert summary["sources"][USDKRW] == "PARTIAL"


def test_gap_kinds_separate_rule_excluded_and_null_close(env):
    yh = FakeYahoo(odd={"CL=F": {"2023-07-03": "09:30", "2023-11-23": None}})
    summary, run_dir, *_ = _run(env, yahoo=yh)
    oil = _report(run_dir)["sources"][WTI]
    kinds = {x["date"]: x["kind"] for x in oil["weekday_gaps"]["items"]}
    assert kinds["2023-07-03"].startswith("자정 아닌 봉(원시에 있음")
    assert kinds["2023-11-23"] == "빈 종가(원시에 봉 있음)"
    excluded = (run_dir / N.MACRO_EXCLUDED_CSV).read_text(encoding="utf-8")
    assert "2023-07-03,09:30" in excluded and N.EXCLUDED_NOT_MIDNIGHT in excluded
    assert N.EXCLUDED_NULL_CLOSE in excluded
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "자정 아닌 봉(원시에 있음 · 현행 어댑터 규칙으로 정규화에서 제외) 1개" in md
    assert VR.verify_run(run_dir)["status"] == "OK"


def test_hole_cause_states_weekday_limit(env):
    hole = [f"2023-01-{d:02d}" for d in range(2, 32)]
    summary, run_dir, *_ = _run(env, yahoo=FakeYahoo(drop={"CL=F": hole}))
    oil = _report(run_dir)["sources"][WTI]
    cause = next(c for c in oil["causes"] if c.startswith("중간 공백"))
    assert "평일 기준 공백 · 기대 거래일 미확정" in cause
