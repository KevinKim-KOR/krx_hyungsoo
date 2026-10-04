"""POC5-01A 러너 기계 분리 동등성 검증 — 검증 전용 (PLAN §3-1 · 운영 경로 import 0 · OCI 실행 금지).

분리 전 러너(git blob 고정)와 작업 트리 러너를 한 프로세스에 올려 시나리오마다 같은 대역 ·
새 tmp 로 따로 돌려 비교한다(본문 · 조립 인자 · stdout · 종료 코드 · 예외 · JSONL · DB 행 ·
상태 파일 · 로그). 정규화 = 실제 시계 키 4개 · tmp 경로 · 러너 모듈 이름. 라이브 가드 ·
외부 연결 차단 · 가짜 Telegram 토큰. `--self-check` = 기준 대 기준(도구 검증).
종료 코드: 0 = 다름 0 · 1 = 다름 있음 · 2 = 기준점 · 정적 검사 · 라이브 차단 문제
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib
import importlib.util
import io
import json
import logging
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from functools import partial
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASELINE_BLOB = "f256677020232600627d207c54baf5081c70c6e2"
NEW_MODULES = tuple(
    f"app/three_push_runtime/runner_{n}.py" for n in ("record", "preflight", "dispatch")
)
# 테스트가 러너 모듈에 쓰는 이름 14개(PLAN 1-8 · 전체 테스트 런타임 전수 기록). 새 모듈은 직접 import 금지.
PATCHED_NAMES = tuple(
    """telegram_send _collect_target_tickers _HISTORY_PATH HOLDINGS_SELECTION_STATE_PATH
    kst_today_date kst_now_iso build_runtime_message insert_status_from_record
    param_from_dict read_active_param_dict HOLDINGS_RISK_STATE_PATH kst_today
    mark_sent is_already_sent""".split()
)
# 바뀌면 안 되는 기존 모듈 20개(PLAN 1-0 표) = PLAN 실측 커밋의 blob.
PIN_COMMIT = "7d507951abf8acea2a1218e2612be5d60bc448da"
PINNED_PATHS = """app/three_push_runtime/ app/three_push_runner_common.py
app/three_push_runtime_message_builder.py app/runtime_evidence/holdings_risk_flow.py
app/runtime_evidence/holdings_selection_flow.py app/runtime_execution_status_store.py
app/runtime_sent_registry_store.py tests/conftest.py""".split()
LOGGER_RE = re.compile(r"logger\s*[:=]|getLogger\(|setup_logging\(")
STATE_FILE_NAMES = tuple(
    "oci_runtime_history.jsonl holdings_selection_state_latest.json "
    "holdings_risk_state_latest.json".split()
)
KINDS = tuple(
    "market_briefing holdings_briefing spike_or_falling_alert holdings_risk_alert".split()
)
PUSH_FLAG = {k: f"PUSH_AUTOSEND_{k.upper()}_ENABLED" for k in KINDS}
RUNNER_MODULE_NAMES = tuple(
    "scripts.run_three_push_runtime_oci poc5_01a_runner_baseline poc5_01a_runner_base2".split()
)
# 실제 시계를 쓰는 키(PLAN §3-1 ④ 3개 + DB `inserted_at`)만 가린다.
CLOCK_KEYS = ("started_at", "finished_at", "sent_at_utc", "inserted_at")
CLOCK_RE = re.compile(r'"(%s)": "[^"]*"' % "|".join(CLOCK_KEYS))
TODAY = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
NOW_ISO = f"{TODAY}T09:30:00+09:00"
# 러너 `kst_today` 대역과 원래 모듈 대역을 서로 다른 날짜로 — 러너 전역을 거치지 않으면
# (별칭 import · 모듈 속성 · 값 미리 계산 모두) 조립 인자가 달라진다.
KST_TODAY_SENTINEL, HSS_TODAY = "2099-01-02", "2099-01-03"
PASSTHROUGH = ("build_runtime_message", "insert_status_from_record", "mark_sent")
PASSTHROUGH += (
    "param_from_dict",
    "is_already_sent",
)  # 실제 함수를 기록 대역으로만 감싼다
CUR: dict[str, Any] = {}  # 현재 시나리오 — 대역이 호출 때 읽는다


def git_blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True
    ).stdout


def baseline_bytes() -> bytes:
    data = _git("cat-file", "blob", BASELINE_BLOB)
    if git_blob_hash(data) != BASELINE_BLOB:
        print("기준 blob 해시 불일치")
        raise SystemExit(2)
    return data


def _module_problems(tree: ast.AST, origins: set[tuple[str, str]]) -> list[str]:
    bad, aliases, mods = [], {}, {m for m, _ in origins}
    imp = (ast.Import, ast.ImportFrom)
    for n, a in [(n, a) for n in ast.walk(tree) if isinstance(n, imp) for a in n.names]:
        full = f"{n.module}.{a.name}" if isinstance(n, ast.ImportFrom) else a.name
        if isinstance(n, ast.ImportFrom) and ((n.module, a.name) in origins):
            bad.append(f"고정 이름의 원래 이름 import {full}")
        if (a.asname or a.name) in PATCHED_NAMES:
            bad.append(f"고정 이름 import {full}")
        if full in mods:
            aliases[a.asname or a.name.split(".")[-1]] = full
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            if (aliases.get(n.value.id), n.attr) in origins:
                bad.append(f"고정 이름 모듈 속성 {n.value.id}.{n.attr}")
        if isinstance(n, ast.Constant) and str(n.value).endswith(STATE_FILE_NAMES):
            bad.append(f"상태 파일 경로 상수 {n.value}")
    for n in tree.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and LOGGER_RE.search(
            ast.unparse(n)
        ):
            bad.append("모듈 전역 logger")
    return bad


def static_checks(self_check: bool) -> list[str]:
    tree = _git("ls-tree", "-r", PIN_COMMIT, "--", *PINNED_PATHS).decode()
    pins = {ln.split("\t")[1]: ln.split()[2] for ln in tree.splitlines()}
    problems = [] if len(pins) == 20 else [f"기준 blob 수 {len(pins)} != 20"]
    problems += [
        f"기존 모듈 blob 변경: {r}"
        for r, b in pins.items()
        if git_blob_hash((ROOT / r).read_bytes()) != b
    ]
    # 14개 이름의 원래 (모듈, 이름) — 분리 전 러너의 import 문에서 읽는다.
    origins = {
        (n.module, a.name)
        for n in ast.walk(ast.parse(baseline_bytes()))
        if isinstance(n, ast.ImportFrom) and n.module
        for a in n.names
        if (a.asname or a.name) in PATCHED_NAMES
    }
    for rel in () if self_check else NEW_MODULES:
        if not (ROOT / rel).exists():
            problems.append(f"새 모듈 없음: {rel}")
            continue
        tree_ = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        problems += [f"{rel}: {b}" for b in _module_problems(tree_, origins)]
    return problems


def _shape(v: Any) -> Any:
    """조립 함수 인자를 비교 가능한 값으로."""
    if isinstance(v, logging.Logger):
        return f"logger:{v.name}"
    if callable(v) and hasattr(v, "__qualname__"):
        module = getattr(v, "__module__", "") or ""
        module = "<RUNNER>" if module in RUNNER_MODULE_NAMES else module
        return f"callable:{module}.{v.__qualname__}"
    if isinstance(v, dict):
        return {str(k): _shape(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_shape(x) for x in v]
    return v if isinstance(v, (str, int, float, bool, type(None))) else repr(v)


def _rec(name: str, fn: Any) -> Any:
    def wrapped(*a: Any, **k: Any) -> Any:
        CUR["calls"].append({"fn": f"runner.{name}"})
        return fn(*a, **k)

    return wrapped


def _call(name: str, kwargs: dict) -> None:
    CUR["calls"].append({"fn": name, "kwargs": _shape(kwargs)})


def fake_holdings_assemble(**kwargs: Any) -> Any:
    from app.runtime_evidence import holdings_selection_flow as hsf

    _call("assemble_holdings_push", kwargs)
    cfg = CUR.get("holdings", {})
    if cfg.get("raise"):
        raise RuntimeError("fake holdings assembly error")
    text, fail, oc = cfg.get("text", ""), cfg.get("fail"), cfg.get("outcome", {})
    out = hsf.HoldingsSelectionOutcome(message_text=text, diagnostics={"h": 1}, **oc)
    kw = dict(outcome=None if fail else out, fail=fail, message_text=text)
    kw.update(skip_non_trading_day=cfg.get("skip_ntd", False))
    return hsf.HoldingsAssembly(diagnostics={"fake": "h"}, **kw)


def fake_risk_assemble(**kwargs: Any) -> Any:
    from app.runtime_evidence import holdings_risk_flow as hrf

    _call("assemble_holdings_risk_push", kwargs)
    cfg = CUR.get("risk", {})
    text, sector = cfg.get("text", ""), CUR["tmp"] / "three_push" / "sector_state.json"
    intraday = pending = None
    if cfg.get("intraday"):
        intraday = SimpleNamespace(message_text=text, state_path=sector)
        intraday.sent_signals, intraday.observed, intraday.unevaluable = [], [], set()
    if cfg.get("pending"):
        pending = dict(sector_state_path=sector, observed=[], today_kst=TODAY)
        pending.update(unevaluable=[], tick_outcome="no_signal", entry_omitted=False)
        pending.update(tally_path=CUR["tmp"] / "tally.json", runtime_kst=NOW_ISO)
    out = hrf.HoldingsRiskOutcome(message_text=text, save_entries={}, today_kst=TODAY)
    out.skip_reason = cfg.get("skip_reason")
    kw = dict(intraday=intraday, outcome=out, fail=cfg.get("fail"), message_text=text)
    kw.update(skip_non_trading_day=cfg.get("skip_ntd", False), intraday_records=pending)
    return hrf.RiskAssembly(diagnostics={"fake": "r"}, **kw)


def fake_market_assemble(record: dict, *, push_kind: str, **kwargs: Any) -> Any:
    from app.market_briefing import flow

    if push_kind != "market_briefing":
        return None
    _call("market_assemble", dict(kwargs, push_kind=push_kind))
    cfg = CUR.get("market", {})
    if cfg.get("raise"):
        raise RuntimeError("fake market assembly error")
    text = cfg.get("text", "")
    record.update({"index_status": "ok", "fake": "m", "message_text_length": len(text)})
    kw = dict(skip_reason=cfg.get("skip_reason"), fail=cfg.get("fail"))
    return flow.BriefingOutcome(message_text=text, fingerprint="UP#NONE", **kw)


def fake_compose(push_kind: str, **kwargs: Any) -> Any:
    _call("compose_runtime_evidence", dict(kwargs, push_kind=push_kind))
    cfg = CUR.get("spike", {})
    if cfg.get("raise"):
        raise RuntimeError("fake compose error")
    fps = cfg.get("fps", [])
    return SimpleNamespace(
        available_sources={"universe_momentum_snapshot": "available"},
        extra_notes=[f"note {fp}" for fp in fps],
        diagnostics=dict(cfg.get("diag", {"reevaluate_status": "ok"})),
        spike_signal_fingerprints=fps,
    )


def fake_fetch_many(tickers: list) -> list:
    bad = set(CUR.get("bad_quotes", ()))
    return [SimpleNamespace(ticker=t, quote=None if t in bad else "Q") for t in tickers]


class _ListHandler(logging.Handler):
    def emit(self, rec: logging.LogRecord) -> None:
        CUR.setdefault("logs", []).append([rec.name, rec.levelname, rec.getMessage()])


def _norm(s: str, tmp: Path) -> str:
    for t in {str(tmp), str(tmp.resolve())}:
        s = s.replace(t, "<TMP>")
    return s


def _clock(s: Any) -> Any:
    return CLOCK_RE.sub(r'"\1": "<CLOCK>"', s) if isinstance(s, str) else s


def _db_rows(path: Path) -> dict[str, list]:
    if not path.exists():
        return {}
    con, out = sqlite3.connect(path), {}
    for table in ("runtime_execution_status", "runtime_sent_registry"):
        try:
            cur = con.execute(f"SELECT * FROM {table} ORDER BY rowid")
        except sqlite3.OperationalError:
            continue
        cols = [d[0] for d in cur.description]
        out[table] = [dict(zip(cols, r)) for r in cur]
        for r in out[table]:
            r.update({k: "<CLOCK>" for k in CLOCK_KEYS if k in r})
    con.close()
    return out


def _isolation(tmp: Path, sc: dict, base: dict) -> list[tuple]:
    """(모듈, 이름, 값) — 앱 모듈 경로 · 조립 대역. 러너 모듈 쪽은 run_once 가 따로."""
    import app.runtime_evidence_composer as rec
    import app.runtime_state_db as rdb
    import app.three_push_runner_common as common
    from app import draft_three_push as dtp, market_naver
    from app.runtime_evidence import holdings_price_basis as hpb
    from app.runtime_evidence import holdings_risk_flow as hrf
    from app.runtime_evidence import holdings_selection_state as hss
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime import runner_market_briefing as mb

    tp, art = tmp / "three_push", sc.get("artifact")
    return [
        (rdb, "DEFAULT_DB_PATH", tmp / "runtime_state.sqlite"),
        # 보유 선정 상태 저장은 자기 모듈 시계(초 단위)를 쓴다 — 고정값으로.
        (hss, "kst_now_iso", lambda: f"{TODAY}T09:31:00+09:00"),
        (hss, "kst_today", lambda: HSS_TODAY),
        (common, "STATE_DIR", tp),
        (common, "LOG_DIR", tmp / "logs"),
        (mb, "STATE_DIR", tp),
        (mb, "MARKET_META_DIR", tmp / "meta"),
        (hpb, "DEFAULT_META_DIR", tmp / "meta"),
        (hrf, "DEFAULT_SECTOR_STATE_PATH", tp / "ss.json"),
        (hrf, "DEFAULT_TALLY_PATH", tp / "tally.json"),
        (mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp / "batch_state.json"),
        (hrf, "assemble_holdings_risk_push", fake_risk_assemble),
        (mb, "assemble", fake_market_assemble),
        (rec, "compose_runtime_evidence", fake_compose),
        (market_naver, "fetch_many", fake_fetch_many),
        (dtp, "_load_universe_artifact_for_spike", lambda: copy.deepcopy(art)),
    ]


def _invoke(mod: Any, sc: dict, mp: Any) -> dict:
    out, res = io.StringIO(), {}
    try:
        with redirect_stdout(out):
            if sc.get("entry") == "run":
                rv = mod.run(sc["kind"], sc["mode"], sc.get("slot"))
                res["return"] = json.dumps(rv, ensure_ascii=False)
            else:
                argv = ["runner", "--push-kind", sc["kind"], "--mode", sc["mode"]]
                argv += ["--slot-id", sc["slot"]] if sc.get("slot") else []
                mp.setattr(sys, "argv", argv)
                mod.main()
    except SystemExit as e:
        res["exit"] = e.code
    # 예외 종류 · 전파 여부 자체가 비교 대상이다.
    except Exception as e:  # noqa: BLE001
        res["exception"] = f"{type(e).__name__}: {e}"
    res["stdout"] = out.getvalue()
    return {k: _clock(v) for k, v in res.items()}


def run_once(mod: Any, sc: dict, base: dict) -> dict:
    import pytest

    from app.three_push_runtime import market_data_batch as mdb

    tmp = Path(tempfile.mkdtemp(prefix="poc5_01a_eq_"))
    (tmp / "three_push").mkdir()
    CUR.clear()
    CUR.update(sc.get("cfg", {}), tmp=tmp, calls=[], sent=[], logs=[])
    mp, trace = pytest.MonkeyPatch(), {}
    try:
        for target, name, value in _isolation(tmp, sc, base):
            mp.setattr(target, name, value)
        if sc.get("batch_state"):
            g = base["gen"]
            bs = dict(status="success", price_data_as_of=TODAY, refresh_date_kst=TODAY)
            bs.update(artifact_generated_at=g, refresh_completed_at=g)
            mdb.write_batch_state(state_path=tmp / "batch_state.json", **bs)
        pd = sc.get("param_dict", base["param_dict"])
        tickers = sc.get("tickers", ["AAA", "BBB"])

        def _send(text: str) -> tuple:
            CUR["sent"].append(text)
            return tuple(sc.get("send_result", (True, None, False)))

        # 테스트가 러너에서 바꿔 끼우는 이름들 — 러너 모듈 전역에 둔다(PLAN 1-8).
        rp_ = {
            "_HISTORY_PATH": tmp / "history.jsonl",
            "HOLDINGS_SELECTION_STATE_PATH": tmp / "three_push" / "hs.json",
            "HOLDINGS_RISK_STATE_PATH": tmp / "three_push" / "hr.json",
            "kst_now_iso": lambda: NOW_ISO,
            "kst_today_date": lambda: TODAY,
            "kst_today": lambda: KST_TODAY_SENTINEL,
            "read_active_param_dict": lambda: copy.deepcopy(pd),
            "_collect_target_tickers": lambda pk: list(tickers),
            "telegram_send": _send,
        }
        rp_ |= {n: getattr(mod, n) for n in PASSTHROUGH}
        # 14개 모두 호출 기록 대역 — 새 모듈이 러너 전역을 거치지 않으면 기록이 달라진다.
        rp_ = {k: _rec(k, v) if callable(v) else v for k, v in rp_.items()}
        rp_.update({k: f(mod) for k, f in sc.get("rp", {}).items()})
        for name, value in rp_.items():
            mp.setattr(mod, name, value, raising=name != "kst_today")
        envs = {PUSH_FLAG[k]: "true" for k in KINDS} | {"PUSH_AUTOSEND_ENABLED": "true"}
        for key, val in (envs | sc.get("env", {})).items():
            mp.setenv(key, val)
        results = [_invoke(mod, sc, mp) for _ in range(sc.get("repeat", 1))]
        hist = tmp / "history.jsonl"
        files = {
            str(p.relative_to(tmp)): _clock(p.read_text(encoding="utf-8"))
            for p in sorted(tmp.rglob("*"))
            if p.is_file()
            and not p.name.startswith(("runtime_state.sqlite", "history"))
        }
        db = _db_rows(tmp / "runtime_state.sqlite")
        jsonl = _clock(hist.read_text(encoding="utf-8")) if hist.exists() else None
        trace = dict(
            results=results, sent=CUR["sent"], calls=CUR["calls"], logs=CUR["logs"]
        )
        trace.update(jsonl=jsonl, db=db, files=files)
    finally:
        mp.undo()
        text = json.dumps(trace, ensure_ascii=False, default=str)
        shutil.rmtree(tmp, ignore_errors=True)
    return json.loads(_norm(text, tmp))


def err(name: str, msg: str) -> dict:
    """러너 전역 `name` 을 예외를 내는 대역으로."""

    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError(msg)

    return {name: lambda m: boom}


def scenarios(base: dict) -> list[dict]:
    """종료 27곳 · 부분 전송 · 미포착 예외 3종(조립 · mark_sent · insert_status)."""
    from app.three_push_runner_common import FORBIDDEN_PHRASES

    pd = base["param_dict"]
    no_mkt = dict(pd, enabled_push_kinds=[k for k in KINDS if k != KINDS[0]])
    secret = SimpleNamespace(param_id="p-secret", param_source="fake")
    secret.to_dict, secret.is_push_kind_enabled = lambda: {"x": {"token": "t"}}, bool
    sec = {"param_from_dict": lambda m: (lambda d: secret)}
    summary = dict(refresh_status="ok", falling_threshold_pct=-10.0)
    summary.update(spike_trigger_type="falling", spike_direction="down")
    summary.update(evidence_as_of=TODAY, artifact_generated_at=base["gen"])
    fresh = {"mode": "universe", "asof": TODAY, "summary": summary, "candidates": []}
    M, H, S, R = KINDS
    body, hold, risk = "[시장 흐름 브리핑] 08:30\n본문", "[보유] 본문", "[장중] 본문"
    fail, rfail = ("failed", "x_fail", "d"), ("failed", "holdings_risk_error", "e")
    tg_fail, part = (False, "HTTP 500", False), (False, "partial_at_2_of_2", True)
    nosel = {"skip_reason": "no_selection", "save_empty_state": True}
    nosig = {"reevaluate_status": "ok", "no_signal": True}
    bad, half = {"bad_quotes": ["AAA", "BBB"]}, {"bad_quotes": ["BBB"]}
    off, raise_ = {"PUSH_AUTOSEND_ENABLED": "false"}, {"raise": True}

    dflt = {"market": {"text": body}, "holdings": {"text": hold}, "spike": {}}
    dflt["risk"] = {"text": risk, "intraday": True, "pending": True}

    def kc(key: str, **c: Any) -> dict:
        return {key: dict(dflt[key], **c)}

    mk, hk, rk, sk = (partial(kc, x) for x in ("market", "holdings", "risk", "spike"))

    def sc(name: str, kind: str, mode: str = "send", **kw: Any) -> dict:
        if kind == S:
            kw = dict({"artifact": fresh, "batch_state": True, "tickers": []}, **kw)
        return dict(name=name, kind=kind, mode=mode, **kw)

    return [
        sc("M01 market sent", M, cfg=mk()),
        sc("M02 market dry-run", M, "dry-run", cfg=mk()),
        sc("M03 forbidden", M, cfg=mk(text=body + FORBIDDEN_PHRASES[0])),
        sc("M04 raw ident", M, cfg=mk(text=body + " param_id")),
        sc("M05 autosend off", M, cfg=mk(), env=off),
        sc("M06 kind off", M, cfg=mk(), env={PUSH_FLAG[M]: "false"}),
        sc("M07 mb skip", M, cfg=mk(skip_reason="non_trading_day")),
        sc("M08 mb fail", M, cfg=mk(text="", fail=fail)),
        sc("M09 mb no text", M, cfg=mk(text="")),
        sc("M10 tg fail", M, cfg=mk(), send_result=tg_fail),
        sc("M11 tg partial", M, cfg=mk(), send_result=part),
        sc("M12 duplicate", M, cfg=mk(), repeat=2),
        sc("M13 registry error", M, cfg=mk(), rp=err("is_already_sent", "locked")),
        sc("M14 assemble raises", M, cfg=mk(**raise_)),
        sc("M15 insert raises", M, cfg=mk(), rp=err("insert_status_from_record", "x")),
        sc("M16 mark_sent raises", M, cfg=mk(), rp=err("mark_sent", "mark fail")),
        sc("M17 param load error", M, cfg=mk(), rp=err("read_active_param_dict", "x")),
        sc("M18 param secret", M, cfg=mk(), rp=sec),
        sc("M19 kind not in param", M, cfg=mk(), param_dict=no_mkt),
        sc("M20 slot ignored", M, cfg=mk(), entry="run", slot="OPEN"),
        sc("H01 sent OPEN", H, slot="OPEN", cfg=hk()),
        sc("H02 sent MIDDAY", H, slot="MIDDAY", cfg=hk()),
        sc("H03 slot required", H, cfg=hk()),
        sc("H04 slot invalid", H, slot="XYZ", entry="run", cfg=hk()),
        sc("H05 refresh error", H, slot="OPEN", rp=err("_collect_target_tickers", "x")),
        sc("H06 price all failed", H, slot="OPEN", cfg=dict(hk(), **bad)),
        sc("H07 price partial ok", H, slot="CLOSE", cfg=dict(hk(), **half)),
        sc("H08 dry-run fail", H, "dry-run", slot="OPEN", cfg=hk(fail=fail)),
        sc("H09 send fail", H, slot="OPEN", cfg=hk(fail=fail)),
        sc("H10 non trading day", H, slot="OPEN", cfg=hk(skip_ntd=True)),
        sc("H11 no selection", H, slot="OPEN", cfg=hk(outcome=nosel)),
        sc(
            "H12 off+ntd",
            H,
            slot="OPEN",
            cfg=hk(skip_ntd=True),
            env={PUSH_FLAG[H]: "false"},
        ),
        sc("H13 assemble raises", H, slot="OPEN", cfg=hk(**raise_)),
        sc("R01 sent intraday", R, cfg=rk()),
        sc("R02 sent plain", R, cfg=rk(intraday=False, pending=False)),
        sc("R03 skip", R, cfg=rk(text="", skip_reason="no_new_or_worsened")),
        sc("R04 tg fail", R, cfg=rk(), send_result=tg_fail),
        sc("R05 partial", R, cfg=rk(), send_result=part),
        sc("R06 dry-run", R, "dry-run", cfg=rk(intraday=False)),
        sc("R07 fail", R, cfg=rk(fail=rfail)),
        sc("R08 non trading day", R, cfg=rk(skip_ntd=True)),
        sc("S01 stale", S, artifact=dict(fresh, asof="2026-01-02"), batch_state=False),
        sc("S02 compose raises", S, cfg=sk(**raise_)),
        sc("S03 reeval failed", S, cfg=sk(diag={"reevaluate_status": "failed"})),
        sc("S04 no_signal diag", S, cfg=sk(diag=nosig)),
        sc("S05 no new fps", S, cfg=sk(fps=[])),
        sc("S06 sent", S, cfg=sk(fps=["fp1", "fp2"])),
        sc("S07 duplicate", S, cfg=sk(fps=["fp1"]), repeat=2),
        sc("S08 dry-run", S, "dry-run", cfg=sk(fps=["fp1"])),
    ]


def _load_module(name: str, data: bytes, tmpdir: Path) -> Any:
    path = tmpdir / f"{name}.py"
    path.write_bytes(data)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _first_diff(a: Any, b: Any, path: str = "") -> str:
    while isinstance(a, (dict, list)) and isinstance(b, type(a)) and len(a) == len(b):
        keys = list(a) if isinstance(a, dict) else range(len(a))
        if isinstance(a, dict) and keys != list(b):
            break
        k = next(k for k in keys if a[k] != b[k])
        a, b, path = a[k], b[k], f"{path}.{k}"
    return f"{path}: {str(a)[:160]!r} != {str(b)[:160]!r}"


def _prepare() -> None:
    # Telegram 실제 토큰이 .env 에서 올라오지 않게 먼저 가짜 값을 둔다(덮어쓰지 않는 로더).
    os.environ["TELEGRAM_BOT_TOKEN"] = "poc5-01a-equivalence-dummy-token"
    os.environ["TELEGRAM_CHAT_ID"] = "0"

    def _no_net(*a: Any, **k: Any) -> Any:
        raise OSError("poc5_01a: 외부 연결 금지")

    socket.socket.connect = _no_net  # type: ignore[method-assign]
    socket.create_connection = _no_net  # type: ignore[assignment]
    from app.runtime_evidence import holdings_selection_flow as hsf

    # 러너가 import 때 이 이름을 묶으므로 두 러너를 올리기 전에 바꿔 둔다.
    hsf.assemble_holdings_push = fake_holdings_assemble
    for kind in KINDS:
        lg = logging.getLogger(f"three_push_runtime_runner.{kind}")
        lg.addHandler(_ListHandler())  # setup_logging 이 파일 handler 를 붙이지 않게
        lg.propagate = False


def main() -> int:
    ap = argparse.ArgumentParser(description="POC5-01A 러너 분리 동등성 검증")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    from tests import _live_guard

    _live_guard.install()
    problems = static_checks(args.self_check)
    data = baseline_bytes()
    _prepare()
    modtmp = Path(tempfile.mkdtemp(prefix="poc5_01a_mod_"))
    base_mod = _load_module(RUNNER_MODULE_NAMES[1], data, modtmp)
    if args.self_check:
        cand_mod = _load_module(RUNNER_MODULE_NAMES[2], data, modtmp)
    else:
        cand_mod = importlib.import_module(RUNNER_MODULE_NAMES[0])
        problems += [
            f"러너 전역에 {n} 없음" for n in PATCHED_NAMES if not hasattr(cand_mod, n)
        ]
    from app.three_push_runtime_param import build_manual_seed_param

    gen = datetime.now(timezone.utc).isoformat()
    base = {"param_dict": build_manual_seed_param().to_dict(), "gen": gen}
    total = diffs = 0
    for sc in scenarios(base):
        if args.only and args.only not in sc["name"]:
            continue
        a, b = run_once(base_mod, sc, base), run_once(cand_mod, sc, base)
        total, diffs = total + 1, diffs + (a != b)
        last = a["results"][-1]
        rv = json.loads(last["stdout"] or last.get("return") or "{}")
        shown = last.get("exception") or f"{rv.get('status')}/{rv.get('reason')}"
        print(f"{'SAME' if a == b else 'DIFF'}  {sc['name']:<24} {shown}")
        if a != b:
            print("      " + _first_diff(a, b))
    blocks = _live_guard.take_blocks()
    _live_guard.uninstall()
    shutil.rmtree(modtmp, ignore_errors=True)
    mode = "self-check" if args.self_check else "baseline-vs-worktree"
    print(f"scenarios={total} diff={diffs} static_problems={len(problems)}", end=" ")
    print(f"live_blocks={len(blocks)} mode={mode}")
    for line in problems + [f"LIVE_BLOCK {b}" for b in blocks]:
        print("PROBLEM", line)
    if problems or blocks:
        return 2
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
