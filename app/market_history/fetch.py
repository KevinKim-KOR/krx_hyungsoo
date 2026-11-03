"""POC6-19 — 입력 사본 · A 표본 조회 → 조건부 B 장기 조회 · 원시 응답 보관(맥북 1회성 연구 명령).

- 기존 어댑터를 그대로 쓴다: 키움 `KiwoomClient(http_post=…)` · Yahoo `fetch_completed_daily(http_get=…)`.
  주입한 전송이 요청 수 · 간격(같은 공급자 시작 간격 1초) · 일시 오류 1회 재시도 · 중단 규칙을 지키고,
  응답을 받을 때마다 원시를 디스크에 쓴다(중간에 멈춰도 받은 것이 남는다). 공유 코드는 바꾸지 않는다.
- 키 · 토큰은 어디에도 쓰지 않는다: 토큰 요청은 HTTP 상태 · 응답 코드만 남기고, 요청 헤더는 남기지 않는다.
  IP 처럼 보이는 글자는 가린다.
- 판정은 `normalize` 의 함수를 그대로 쓴다(실행 중 판정 = 검산 판정).
- 운영 DB 는 `mode=ro` 로만 연다 · 봉인 판은 `immutable` 로만 연다 · 모든 쓰기는 실행 폴더 안인지 검사한다.
  운영 파일 지문이 실행 전후로 달라도 '변경 감지'로만 적는다(연구 코드의 쓰기로 단정하지 않음 · 되돌리지 않음).
- 실행 시각: 08:20 ~ 10:30 KST 시작 금지(OCI 05 수집 09:40 · 맥북 06 자동 실행 10:00 과 겹치지 않게).
"""

from __future__ import annotations

import json
import secrets
import time
import traceback
from dataclasses import asdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

from app import kiwoom_investor_flow as KW
from app import yahoo_daily_series as YH
from app.config import optional_env
from app.krx_sealed_reader import DEFAULT_SEALED_DB
from app.market_data_store import DEFAULT_DB_PATH
from app.market_history import normalize as N
from app.market_history.inputs import (  # noqa: F401 — Plan 등은 CLI · 시험이 fetch 에서 쓴다
    FLOW_SAMPLES,
    MACRO_WINDOWS,
    SEALED_VERSION,
    Plan,
    check_plan,
    code_info,
    precheck,
    prepare_inputs,
    sealed_refusal,
)
from app.market_history import report as R
from app.market_history.transport import (
    KiwoomTransport,
    Limits,
    PhaseStop,
    ProviderStop,
    Recorder,
    RunStop,
    Session,
    YahooTransport,
)
from app.ml_baseline_snapshot import file_sha256, new_run_dir
from app.research_run_guard import (
    LEGACY_ROOT_REL,
    check_out_dir,
    is_under,
    live_changes,
    live_fingerprint,
    peak_rss_bytes,
)
from app.supply_fx_oil_store import USDKRW, WTI

REPO = Path(__file__).resolve().parents[2]
ROOT_REL = Path("state/ml/research/poc6_19")
KST = timezone(timedelta(hours=9))
NO_START_KST = (dtime(8, 20), dtime(10, 30))
SYMBOLS = (("KRW=X", USDKRW), ("CL=F", WTI))
SPEC_RECORD = {
    "kiwoom_ka10051": (
        "키움 공식 REST ka10051 — POC5-28 PLAN §9-6 명세 확인(2026-10-20) · 설계 [1] 공식 예제 "
        "https://github.com/Kiwoom-Securities/Kiwoom-REST-API (2026-11-03 설계자 열람 · 날짜 인자 존재만) · "
        "이번 실행의 공개 명세 조회 0회"
    ),
    "yahoo_chart": "기존 어댑터 app/yahoo_daily_series.py(POC6-01) · 공개 명세 조회 0회",
}
KIWOOM_BODY = {"mrkt_tp": "0", "amt_qty_tp": "0", "stex_tp": "1"}


# --- 조회 ----------------------------------------------------------------------


_PARSE_ERRORS = (AttributeError, TypeError, KeyError, ValueError, OverflowError)


def _after_failure(ev: dict, counts: dict, session, limits) -> Optional[str]:
    """실패 1건 뒤: 날짜 · 구조 실패와 통신 실패를 따로 센다. 통신 실패 뒤에는 기다린다(망이 돌아올 시간).

    돌려주는 값 = 그 구간을 멈출 사유(없으면 None). 성공하면 두 횟수 모두 0 으로 돌린다.
    """
    if ev["status"] == N.VALID:
        counts.update(struct=0, comm=0)
        return None
    key = "comm" if ev["failure_kind"] == N.COMM else "struct"
    counts[key] += 1
    if counts[key] >= limits.max_consecutive_failures:
        label = "통신 연속 실패" if key == "comm" else "연속 실패"
        return f"{label} {counts[key]}회"
    if key == "comm":
        session.sleep(limits.comm_backoff_seconds)
    return None


def _flow_loop(client, kt, dates, phase, kospi, state, session, limits) -> list[dict]:
    """날짜를 차례로 조회 · 판정. 인증 · 호출 제한 · 연속 실패(날짜 · 구조 또는 통신 3회) = state['stop'] =
    키움 공급자 중단 — 같은 실행에서 그 뒤 요청 0회(A 에서 멈추면 B 도 없음 · 설계자 RESULT 판정 §3 · §4-1).

    응답 모양이 예상 밖이라 어댑터가 해석 중 멈추면(AttributeError 등) 저장한 원시 줄로 그날을 실패 판정하고
    계속한다 — 그 호출에서 원시가 하나도 남지 않았으면(이 코드의 결함) 그대로 올린다.
    """
    evals, counts = [], {"struct": 0, "comm": 0}
    for d in dates:
        seq_before = kt.seq
        try:
            client.kospi_net_by_investor(d)
        except ProviderStop as e:
            state["stop"] = e.as_dict()
        except KW.KiwoomAuthError:
            state["stop"] = {
                "status": R.ACCESS_BLOCKED,
                "reason": f"키움 인증 거절(응답 코드 {kt.last_auth_code})",
            }
        except (KW.KiwoomFlowError, requests.RequestException):
            pass  # 판정은 저장한 마지막 시도 줄로 한다
        except _PARSE_ERRORS:
            if kt.seq == seq_before:
                raise
        line = kt.final.get(d) if kt.seq > seq_before else None
        stop = None
        if line is not None:
            ev = N.evaluate_flow_line(line, kospi)
            evals.append(ev)
            state["attempted"].append(d)
            stop = (
                None if state["stop"] else _after_failure(ev, counts, session, limits)
            )
        if state["stop"]:
            break
        if stop:
            state["phase_stop"][phase] = f"{stop}(마지막 {d})"
            state["stop"] = {"status": R.FETCH_FAILED, "reason": f"{stop}(마지막 {d})"}
            break
    return evals


def _macro_loop(yt, jobs, state, session, limits) -> None:
    """창을 차례로 조회 · 판정. 연속 실패는 심볼마다 따로 센다(한 심볼이 막혀도 다른 심볼은 조회).

    연속 실패로 멈춘 심볼은 state['symbol_stop'] 에 남아 같은 실행의 뒤 구간(B)에서도 요청 0회다.
    """
    counts: dict[str, dict] = {}
    halted = state.setdefault("symbol_stop", {})
    for symbol, window, start, end, phase in jobs:
        if symbol in halted:
            continue
        s, e = date.fromisoformat(start), date.fromisoformat(end)
        adapter_start = s - timedelta(days=1)
        period2 = datetime(e.year, e.month, e.day, tzinfo=timezone.utc) + timedelta(
            days=2
        )
        yt.current = {
            "symbol": symbol,
            "window": window,
            "phase": phase,
            "start": start,
            "end": end,
            "adapter_start": adapter_start.isoformat(),
            "period2_utc": period2.isoformat(),
        }
        seq_before = yt.seq
        try:
            YH.fetch_completed_daily(
                symbol, adapter_start, now_utc=period2, http_get=yt
            )
        except ProviderStop as ex:
            state["stop"] = ex.as_dict()
        except (YH.YahooSeriesError, requests.RequestException):
            pass
        except _PARSE_ERRORS:
            if yt.seq == seq_before:
                raise
        doc = yt.final.get(f"{symbol}|{window}") if yt.seq > seq_before else None
        stop = None
        if doc is not None and not state["stop"]:
            ev = N.evaluate_yahoo_doc(doc)
            c = counts.setdefault(symbol, {"struct": 0, "comm": 0})
            stop = _after_failure(ev, c, session, limits)
        if state["stop"]:
            break
        if stop:
            halted[symbol] = f"{stop}(마지막 {symbol} {window})"
            state["phase_stop"][f"{phase}:{symbol}"] = halted[symbol]


def _flow_gate(evals: list[dict], plan: Plan) -> dict:
    by = {e["date"]: e for e in evals}
    bad = [
        f"{d} {by[d]['reason'] if d in by else '조회 안 됨'}"
        for d in plan.flow_samples[:2]
        if by.get(d, {}).get("status") != N.VALID
    ]
    if bad:
        return {"passed": False, "reason": " · ".join(bad), "b_start": None}
    good = [d for d, e in by.items() if e["status"] == N.VALID]
    return {"passed": True, "reason": "", "b_start": min(good)}


def _macro_gate(yt: YahooTransport, symbol: str, plan: Plan) -> dict:
    def ok(window: str) -> tuple[bool, str]:
        doc = yt.final.get(f"{symbol}|{window}")
        if doc is None:
            return False, f"{window} 조회 안 됨"
        ev = N.evaluate_yahoo_doc(doc)
        return ev["status"] == N.VALID, f"{window} {ev['reason']}"

    recent, *past = [w for w, _, _ in plan.macro_windows]
    r_ok, r_msg = ok(recent)
    past_ok = [ok(w) for w in past]
    if not r_ok:
        return {"passed": False, "reason": r_msg}
    if not any(x for x, _ in past_ok):
        return {"passed": False, "reason": " · ".join(m for _, m in past_ok)}
    return {"passed": True, "reason": ""}


def _b_estimate(kt, yt, b_dates, macro_symbols, plan, limits, rec) -> dict:
    per_line = kt.data_bytes / kt.data_lines if kt.data_lines else 0
    span = (
        date.fromisoformat(plan.target_end)
        - date.fromisoformat(plan.macro_target_start)
    ).days
    yahoo = 0.0
    for symbol in macro_symbols:
        sizes = days = 0
        for window, start, end in plan.macro_windows:
            sizes += yt.bytes_by_window.get(f"{symbol}|{window}", 0)
            days += (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        yahoo += sizes / days * span if days else 0
    latency = kt.latency_total / kt.data_lines if kt.data_lines else 0
    est = {
        "kiwoom_bytes": int(per_line * len(b_dates)),
        "yahoo_bytes": int(yahoo),
        "kiwoom_seconds": round(len(b_dates) * max(limits.gap_seconds, latency), 1),
        "requests": len(b_dates) + len(macro_symbols),
    }
    est["total_bytes_after"] = rec.bytes + est["kiwoom_bytes"] + est["yahoo_bytes"]
    if est["total_bytes_after"] > limits.max_bytes:
        est["skipped_reason"] = (
            f"예상 용량 {est['total_bytes_after']} > 상한 {limits.max_bytes}"
        )
    return est


def _fetch(ctx: dict, run_end: dict) -> None:
    plan, limits, inputs = ctx["plan"], ctx["limits"], ctx["inputs"]
    session = Session(
        ctx["rec"], limits, ctx["sleep"], ctx["monotonic"], ctx["now_utc"]
    )
    ctx["session"] = session
    kt = KiwoomTransport(session, ctx["rec"], ctx["kiwoom_post"])
    yt = YahooTransport(session, ctx["rec"], ctx["yahoo_get"])
    kospi = N.kospi_map(inputs["kospi"])
    kospi_dates = [r[0] for r in inputs["kospi"]["rows"]]
    kw = run_end["providers"]["kiwoom"]
    yh = run_end["providers"]["yahoo"]
    key, secret = ctx["credentials"]
    client = KW.KiwoomClient(key, secret, http_post=kt) if key and secret else None
    if client is None:
        kw["stop"] = {"status": R.ACCESS_BLOCKED, "reason": "키움 앱키 없음(.env)"}

    session.begin_phase("A")
    flow_a: list[dict] = []
    try:
        if client is not None:
            flow_a = _flow_loop(
                client, kt, plan.flow_samples, "A", kospi, kw, session, limits
            )
    except PhaseStop as e:
        run_end["phases"]["A"]["stop"] = e.reason
    try:
        jobs = [
            (sym, w, s, e, "A") for sym, _ in SYMBOLS for w, s, e in plan.macro_windows
        ]
        _macro_loop(yt, jobs, yh, session, limits)
    except PhaseStop as e:
        run_end["phases"]["A"]["stop"] = e.reason
    run_end["phases"]["A"]["elapsed_seconds"] = round(session.elapsed(), 3)

    kw["gate"] = _flow_gate(flow_a, plan)
    yh["gates"] = {sid: _macro_gate(yt, sym, plan) for sym, sid in SYMBOLS}
    b_dates: list[str] = []
    if kw["gate"]["passed"] and not kw["stop"]:
        b_dates = sorted(
            (
                d
                for d in kospi_dates
                if kw["gate"]["b_start"] <= d <= plan.target_end
                and d not in kw["attempted"]
            ),
            reverse=True,
        )
    macro_b = [
        sym
        for sym, sid in SYMBOLS
        if yh["gates"][sid]["passed"]
        and not yh["stop"]
        and sym not in yh.get("symbol_stop", {})
    ]
    est = _b_estimate(kt, yt, b_dates, macro_b, plan, limits, ctx["rec"])
    run_end["b_estimate"] = est
    kw["b"] = {"start": kw["gate"]["b_start"], "planned": len(b_dates), "requested": 0}
    if est.get("skipped_reason"):
        kw["b"]["skipped_reason"] = est["skipped_reason"]
        yh["b_skipped_reason"] = est["skipped_reason"]
        run_end["phases"]["B"]["stop"] = f"장기 조회 생략: {est['skipped_reason']}"
        return

    session.begin_phase("B")
    try:
        _macro_loop(
            yt,
            [
                (sym, N.FULL_WINDOW, plan.macro_target_start, plan.target_end, "B")
                for sym in macro_b
            ],
            yh,
            session,
            limits,
        )
    except PhaseStop as e:
        run_end["phases"]["B"]["stop"] = e.reason
    try:
        if b_dates and client is not None and not kw["stop"]:
            _flow_loop(client, kt, b_dates, "B", kospi, kw, session, limits)
    except PhaseStop as e:
        run_end["phases"]["B"]["stop"] = e.reason
    finally:
        planned = set(b_dates)
        kw["b"]["requested"] = sum(1 for d in kw["attempted"] if d in planned)
        kw["b"]["stop"] = kw["phase_stop"].get("B") or run_end["phases"]["B"].get(
            "stop"
        )
        run_end["phases"]["B"]["elapsed_seconds"] = round(session.elapsed(), 3)


# --- 실행 ----------------------------------------------------------------------


def start_refusal(now_utc: datetime) -> Optional[str]:
    t = now_utc.astimezone(KST).time()
    lo, hi = NO_START_KST
    if lo <= t < hi:
        return (
            f"지금 {t:%H:%M} KST — {lo:%H:%M} ~ {hi:%H:%M} 에는 시작하지 않는다"
            "(OCI 05 수집 09:40 · 06 자동 실행 10:00 과 겹침)"
        )
    return None


def _new_run_end(run_id: str) -> dict:
    def provider() -> dict:
        return {"stop": None, "attempted": [], "phase_stop": {}}

    return {
        "schema": "poc6_19_run_end.v1",
        "run_id": run_id,
        "phases": {"A": {"stop": None}, "B": {"stop": None}},
        "providers": {"kiwoom": provider(), "yahoo": provider()},
        "error": None,
    }


def _end_reason(run_end: dict) -> str:
    if run_end["error"]:
        return f"ERROR({run_end['error']['type']})"
    stops = [
        run_end["phases"]["A"].get("stop"),
        run_end["phases"]["B"].get("stop"),
        *[p.get("stop") and p["stop"]["reason"] for p in run_end["providers"].values()],
        *[v for p in run_end["providers"].values() for v in p["phase_stop"].values()],
    ]
    unique = list(
        dict.fromkeys(s for s in stops if s)
    )  # 같은 사유가 공급자 · 구간에 함께 남은 경우 한 번만
    return "STOPPED: " + " · ".join(unique) if unique else "COMPLETED"


POSTPROCESS_LIMIT_SECONDS = 900  # 설계 §5 후처리 15분


def limit_breach(total_bytes: int, limits: Limits) -> Optional[str]:
    """새 원시 · 파생 파일 합계 · 메모리 상한을 넘었는가(넘었으면 사유 문장 · 정리하지 않는다)."""
    if total_bytes > limits.max_bytes:
        return f"파일 용량 상한 초과({total_bytes} > {limits.max_bytes} 바이트)"
    rss = peak_rss_bytes()
    if rss >= limits.max_rss_bytes:
        return f"메모리 상한 초과({rss} ≥ {limits.max_rss_bytes} 바이트)"
    return None


def _report_texts(tables, run_start, run_end, post_error) -> dict[str, str]:
    report = R.build_report(tables, run_start, run_end, post_error)
    return {"report.json": R.render_json(report), "report.md": R.render_md(report)}


def postprocess(run_dir: Path, rec: Recorder, limits: Limits) -> dict:
    """원시 → 정규화 CSV · report.json · report.md(외부 조회 0).

    상한(파일 합계 · 메모리 · 후처리 15분)은 보고를 쓰기 **전에** 판단한다(검증자 r2 F3): 보고를 메모리에서
    만들어 그것까지 쓴 합계로 보고, 넘으면 그 사유를 넣은 보고(ARCHIVE_READY 아님)를 다시 만들어 쓴다.
    사유를 넣은 보고는 더 크므로 '넘음' 판단은 그대로 맞다.
    """
    t0 = time.monotonic()
    tables = N.build_tables(run_dir)
    for rel, text in N.rendered_files(tables).items():
        rec.new_text(rel, text)
    run_start = json.loads((run_dir / "run_start.json").read_text(encoding="utf-8"))
    run_end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    texts = _report_texts(tables, run_start, run_end, None)
    projected = rec.bytes + sum(len(x.encode("utf-8")) for x in texts.values())
    out = {
        "elapsed_seconds": round(time.monotonic() - t0, 3),
        "limit_seconds": POSTPROCESS_LIMIT_SECONDS,
        "max_bytes": limits.max_bytes,
        "peak_rss_bytes": peak_rss_bytes(),
    }
    breach = limit_breach(projected, limits)
    if not breach and out["elapsed_seconds"] > POSTPROCESS_LIMIT_SECONDS:
        breach = f"후처리 시간 상한 초과({out['elapsed_seconds']} > {POSTPROCESS_LIMIT_SECONDS}초)"
    if breach:
        out["error"] = {"type": "LIMIT", "message": breach}
        texts = _report_texts(tables, run_start, run_end, out["error"])
    for rel, text in texts.items():
        rec.new_text(rel, text)
    out["bytes"] = rec.bytes
    return out


def write_files_index(run_dir: Path, rec) -> None:
    items = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and p.name != "files.json":
            rel = str(p.relative_to(run_dir))
            kind = rel.split("/", 1)[0] if "/" in rel else "meta"
            items.append(
                {
                    "path": rel,
                    "bytes": p.stat().st_size,
                    "sha256": file_sha256(p),
                    "kind": kind,
                }
            )
    rec.new_json("files.json", {"files": items})


def run(
    *,
    repo_root: Path = REPO,
    out_root: Optional[Path] = None,
    plan: Plan = Plan(),
    limits: Limits = Limits(),
    market_db: Path = DEFAULT_DB_PATH,
    sealed_db: Path = DEFAULT_SEALED_DB,
    credentials: Optional[tuple] = None,
    kiwoom_post: Optional[Callable] = None,
    yahoo_get: Optional[Callable] = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now_utc: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    code: Optional[Callable[[Path], dict]] = None,
) -> dict:
    """A → 조건부 B → 정규화 · 보고. 돌려주는 값 = 요약(CLI 의 RESULT)."""
    now = now_utc()
    refusal = start_refusal(now)
    refusal = refusal or precheck(Path(market_db), Path(sealed_db))
    if refusal:
        return {"status": "REFUSED", "reason": refusal}
    run_id = f"{now:%Y%m%dT%H%M%SZ}_{secrets.token_hex(4)}"
    run_dir = (out_root or repo_root / ROOT_REL) / run_id
    check_out_dir(run_dir, repo_root)
    new_run_dir(run_dir, forbidden_root=repo_root / LEGACY_ROOT_REL).mkdir(parents=True)
    rec = Recorder(run_dir, limits.max_bytes)
    live_before = live_fingerprint(repo_root)
    inputs = prepare_inputs(rec, Path(market_db), Path(sealed_db))
    if credentials is None:
        credentials = (
            optional_env("KIWOOM_APP_KEY", None),
            optional_env("KIWOOM_APP_SECRET", None),
        )
    run_start = {
        "schema": "poc6_19_run_start.v1",
        "run_id": run_id,
        "started_at": now.isoformat(),
        "plan": asdict(plan),
        "limits": asdict(limits),
        "public_params": {
            "kiwoom": {
                "url": KW.HOST + KW.SECT_PATH,
                "api_id": "ka10051",
                "body": KIWOOM_BODY,
            },
            "yahoo": {"url": YH.CHART_URL, "interval": "1d", "symbols": dict(SYMBOLS)},
        },
        "spec": SPEC_RECORD,
        "code": (code or code_info)(repo_root),
        "inputs": inputs["summary"],
        "credentials_present": bool(credentials[0] and credentials[1]),
        "start_rule": f"{NO_START_KST[0]:%H:%M} ~ {NO_START_KST[1]:%H:%M} KST 시작 금지",
    }
    refused = sealed_refusal(inputs["sealed"]) or check_plan(
        plan, [r[0] for r in inputs["kospi"]["rows"]]
    )
    if refused:
        run_start["refused"] = refused
    rec.new_json("run_start.json", run_start)
    run_end = _new_run_end(run_id)
    ctx = {
        "plan": plan,
        "limits": limits,
        "inputs": inputs,
        "rec": rec,
        "credentials": credentials,
        "kiwoom_post": kiwoom_post,
        "yahoo_get": yahoo_get,
        "sleep": sleep,
        "monotonic": monotonic,
        "now_utc": now_utc,
    }
    interrupted: Optional[BaseException] = None
    try:
        if refused:
            run_end["error"] = {"type": "REFUSED", "message": refused}
        else:
            _fetch(ctx, run_end)
    except RunStop as e:
        run_end["error"] = {"type": "RunStop", "message": e.reason}
    except Exception as e:  # noqa: BLE001 — 원시 · 종료 이유 · 오류 위치를 남기고 ERROR
        run_end["error"] = {
            "type": type(e).__name__,
            "message": N.redact(str(e))[:300],
            "traceback": N.redact(traceback.format_exc())[-4000:],
        }
    # Ctrl-C · 종료 신호 — 받은 원시 · 보고 · 파일 목록을 남긴 뒤 다시 올린다
    except BaseException as e:
        run_end["error"] = {"type": "INTERRUPTED", "message": type(e).__name__}
        interrupted = e
    finally:
        session = ctx.get("session")
        run_end["finished_at"] = datetime.now(timezone.utc).isoformat()
        run_end["requests"] = {
            "data": session.counts if session else {},
            "auth": session.auth_requests if session else 0,
        }
        run_end["live_changes"] = live_changes(live_fingerprint(repo_root), live_before)
        run_end["sealed_unchanged"] = (
            file_sha256(Path(sealed_db)) == inputs["sealed"]["file_sha256_before"]
        )
        breach = limit_breach(rec.bytes, limits)
        if not run_end["error"] and not run_end["sealed_unchanged"]:
            run_end["error"] = {
                "type": "INPUT_CHANGED",
                "message": "실행 중 봉인 판 파일이 바뀌었다(sha256 전후 다름 · 이 실행은 판정에 쓰지 않음)",
            }
        elif not run_end["error"] and breach:
            run_end["error"] = {"type": "RunStop", "message": breach}
        run_end["end_reason"] = _end_reason(run_end)
        run_end["resources"] = {
            "peak_rss_bytes": peak_rss_bytes(),
            "bytes_written": rec.bytes,
        }
        rec.new_json("run_end.json", run_end)
    post: dict = {}
    try:
        post = postprocess(run_dir, rec, limits)
    except Exception as e:  # noqa: BLE001 — 후처리 실패도 원시는 남긴다
        post = {"error": {"type": type(e).__name__, "message": N.redact(str(e))[:300]}}
    rec.new_json("postprocess.json", post)
    write_files_index(run_dir, rec)
    if interrupted is not None:
        raise interrupted
    failed = post.get("error") or (
        run_end["error"] and run_end["error"]["type"] != "REFUSED"
    )
    summary = {"status": "ERROR" if failed else "OK", "run_id": run_id}
    if refused:
        summary["status"] = "REFUSED"
    summary["run_dir"] = (
        str(run_dir.relative_to(repo_root))
        if is_under(run_dir, repo_root)
        else str(run_dir)
    )
    summary["end_reason"] = run_end["end_reason"]
    if not post.get("error"):
        rep = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        summary["sources"] = {k: v["status"] for k, v in rep["sources"].items()}
    return summary
