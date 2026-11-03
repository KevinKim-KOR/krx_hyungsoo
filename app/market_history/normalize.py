"""POC6-19 — 원시 응답 → 정규화(외부 조회 0 · 기존 어댑터에 저장 본문을 다시 넣어 같은 파싱을 쓴다).

수집(`fetch`)이 실행 중에 쓰는 판정과 검산(`verify`)이 원시에서 다시 계산하는 판정은 이 파일의 같은
함수다 — 둘이 갈리지 않게.

- 수급(날짜마다 마지막 시도 줄): `KiwoomClient` 에 저장 본문을 다시 넣어 13분류 · 지수값을 읽는다.
  날짜 근거 = 응답 날짜 칸(있으면 요청일과 같아야 함) + 그날 저장 코스피 종가 대조(허용 0.005).
  13분류 값이 다른 날짜와 통째로 같아도 '반복 응답 의심' 표시만 한다(PLAN 판정 보완 1).
- 원/달러 · WTI(창마다 마지막 시도): `fetch_completed_daily` 에 저장 본문을 다시 넣어 완료 일봉을 얻고,
  현지 날짜 [시작일, 끝일] 만 남긴다. 원시 timestamp · 시간대를 함께 둔다.
  WTI 0 이하 = 원본 그대로 두고 표시 · 원/달러 0 이하 = 손상 표시(유효 개수에서 뺀다).
- 빈 날짜를 0 · 직전 값 · 보간으로 채우지 않는다. 기관계와 세부 분류를 다시 더하지 않는다.
"""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import requests

from app import kiwoom_investor_flow as KW
from app import yahoo_daily_series as YH
from app.supply_fx_oil_refresh import CLOSE_TOLERANCE
from app.supply_fx_oil_store import MACRO_SERIES, USDKRW, WTI

VALID = "VALID"
FAILED = "FAILED"

KIWOOM_RAW = "raw/kiwoom_ka10051.jsonl"
KIWOOM_AUTH_RAW = "raw/kiwoom_auth.jsonl"
YAHOO_RAW_DIR = "raw/yahoo"
INPUT_KOSPI = "inputs/kospi_close.json"
INPUT_STORED = "inputs/stored_overlap.json"
INPUT_SEALED = "inputs/sealed_calendar.json"
FLOW_DATES_CSV = "normalized/investor_flow_dates.csv"
FLOW_VALUES_CSV = "normalized/investor_flow.csv"
MACRO_CSV = "normalized/macro.csv"
MACRO_EXCLUDED_CSV = "normalized/macro_excluded.csv"
EXCLUDED_NOT_MIDNIGHT = "NOT_MIDNIGHT_EXCLUDED"  # 원시에 봉이 있으나 기존 어댑터 규칙(현지 자정 봉만)으로 제외
EXCLUDED_NULL_CLOSE = "NULL_CLOSE"  # 원시에 봉이 있으나 종가가 비어 있음

SERIES_BY_SYMBOL = {"KRW=X": USDKRW, "CL=F": WTI}
FULL_WINDOW = "B_FULL"
FLAG_OK = "OK"
FLAG_WTI_NONPOSITIVE = (
    "NONPOSITIVE_KEPT"  # WTI 선물 음수 거래 사례 — 손상으로 지우지 않는다
)
FLAG_FX_NONPOSITIVE = "NONPOSITIVE_INVALID"  # 원/달러는 양수여야 한다

FLOW_DATE_COLUMNS = tuple(
    (
        "date phase status reason index_value kospi_close kospi_source "
        "index_diff date_check date_fields repeat_suspect raw_seq attempts"
    ).split()
)
FLOW_VALUE_COLUMNS = ("date", "investor", "source_field", "raw_eok", "net_won")
MACRO_EXCLUDED_COLUMNS = tuple(
    (
        "series_id symbol phase window obs_date local_time timezone "
        "raw_timestamp_utc close reason canonical raw_file"
    ).split()
)
MACRO_COLUMNS = tuple(
    (
        "series_id symbol phase window obs_date timezone raw_timestamp_utc "
        "close unit flag canonical raw_file"
    ).split()
)

_DATE_KEY = re.compile(r"(^dt$|_dt$|date)", re.IGNORECASE)
_YYYYMMDD = re.compile(r"^\d{8}$")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_CANDIDATE = re.compile(r"[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}")
_MSG_CODE = re.compile(r"\[(\d{4}):")
RATE_LIMIT_CODES = (1700, 1701)
COMM = "COMM"  # 통신 · 서버 오류(재시도 뒤) — 날짜 · 구조 실패와 따로 센다
STRUCT = "STRUCT"  # 날짜 · 구조 실패(지수 · 날짜 불일치 · 행 없음 · 값 못 읽음 · 미완료 페이지 · 응답 코드)
_COUNT_KEYS = (
    "raw",
    "null_close",
    "not_midnight",
    "in_progress",
    "before_request",
    "weekend",
    "outside_window",
    "in_window",
)


def iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _ipv6(match: re.Match) -> str:
    token = match.group(0)
    try:
        ipaddress.IPv6Address(token)
    except ValueError:
        return token
    return "[IP]"


def redact(text: Optional[str]) -> Optional[str]:
    """IP 주소처럼 보이는 글자(IPv4 · 검증된 IPv6)를 가린다(인증 · 오류 문구에 접속 IP 가 실릴 수 있음)."""
    if text is None:
        return None
    return _IPV6_CANDIDATE.sub(_ipv6, _IPV4.sub("[IP]", text))


def message_code(body: Any) -> Optional[int]:
    """키움 응답 문구의 네 자리 사유 코드(`[8050:…]` 꼴) — 문구 자체는 남기지 않는다."""
    msg = body.get("return_msg") if isinstance(body, dict) else None
    m = _MSG_CODE.search(msg) if isinstance(msg, str) else None
    return int(m.group(1)) if m else None


def code_kind(return_code: Any, msg_code: Optional[int]) -> str:
    """응답 코드 분류: 호출 제한 · 인증 거절(8xxx) · 그 밖(해당 요청일 미확보)."""
    codes = {c for c in (return_code, msg_code) if isinstance(c, int)}
    if codes & set(RATE_LIMIT_CODES):
        return "호출 제한 응답"
    if any(8000 <= c < 9000 for c in codes):
        return "인증 거절"
    return "해당 요청일 미확보"


class ReplayResponse:
    """저장 본문을 기존 어댑터에 다시 넣기 위한 응답(외부 호출 없음)."""

    def __init__(self, status_code: int, text: str, headers: Optional[dict] = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self) -> Any:
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def final_by(items: list[dict], key: Callable[[dict], str]) -> dict[str, dict]:
    """같은 요청의 여러 시도 중 마지막 시도(순번이 가장 큰 것)."""
    out: dict[str, dict] = {}
    for item in sorted(items, key=lambda x: x["seq"]):
        out[key(item)] = item
    return out


# --- 수급 ---------------------------------------------------------------------


def _replay_client(line: dict) -> KW.KiwoomClient:
    def post(
        url, json=None, headers=None, timeout=None
    ):  # noqa: A002 — 어댑터 호출 형태
        if url.endswith(KW.TOKEN_PATH):
            body = {"return_code": 0, "token": "replay", "expires_dt": "29991231235959"}
            return ReplayResponse(200, _dumps_line(body))
        return ReplayResponse(line["http_status"], line["body"])

    return KW.KiwoomClient("replay", "replay", http_post=post)


def _date_fields(body: dict, row: dict) -> list[tuple[str, str]]:
    """응답 · 001 행에서 날짜처럼 보이는 칸(이름에 dt · date · 값 YYYYMMDD)."""
    found = []
    for scope, src in (("body", body), ("row", row)):
        for k, v in src.items():
            if k == "inds_netprps" or not isinstance(v, str):
                continue
            if _DATE_KEY.search(k) and _YYYYMMDD.match(v.strip()):
                found.append((f"{scope}.{k}", v.strip()))
    return sorted(found)


def evaluate_flow_line(line: dict, kospi: dict[str, tuple[float, str]]) -> dict:
    """한 날짜의 마지막 시도 줄 → 판정. 값의 반복은 여기서 보지 않는다(`mark_repeats`)."""
    d = iso(line["base_dt"])
    close, source = kospi.get(d, (None, None))
    out: dict = {
        "date": d,
        "phase": line["phase"],
        "status": FAILED,
        "reason": "",
        "index_value": None,
        "kospi_close": close,
        "kospi_source": source,
        "index_diff": None,
        "date_check": "",
        "date_fields": "",
        "repeat_suspect": 0,
        "raw_seq": line["seq"],
        "attempts": line["attempt"],
        "values": None,
        "failure_kind": STRUCT,
    }
    if line.get("error") or (line.get("http_status") or 0) >= 500:
        out["failure_kind"] = COMM
    if line.get("error"):
        out["reason"] = f"통신 오류({line['error']})"
        return out
    if line.get("http_status") != 200:
        out["reason"] = f"HTTP {line.get('http_status')}"
        return out
    try:
        body = json.loads(line.get("body") or "")
    except ValueError:
        out["reason"] = "응답 형식 오류(JSON 아님)"
        return out
    if not isinstance(body, dict):
        out["reason"] = "응답 형식 오류(객체 아님)"
        return out
    if body.get("return_code") != 0:
        rc, mc = body.get("return_code"), message_code(body)
        out["reason"] = f"응답 코드 {rc} · 사유 {mc}({code_kind(rc, mc)})"
        return out
    rows = body.get("inds_netprps")
    if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
        out["reason"] = "응답 구조 오류(행 목록)"
        return out
    row = next((x for x in rows if x.get("inds_cd") == KW.KOSPI_ROW), None)
    if row is None:
        out["reason"] = (
            "미완료 페이지(연속 조회 있음 · 001 없음)"
            if line.get("cont_yn") == "Y"
            else "코스피 종합 행(001) 없음"
        )
        return out
    try:
        nets, index_value = _replay_client(line).kospi_net_by_investor(d)
    except (KW.KiwoomFlowError, AttributeError, TypeError, ValueError) as e:
        out["reason"] = f"값을 읽을 수 없음({type(e).__name__}: {str(e)[:80]})"
        return out
    out["index_value"] = index_value
    fields = _date_fields(body, row)
    out["date_fields"] = ";".join(f"{k}={v}" for k, v in fields)
    if fields and any(v != line["base_dt"] for _, v in fields):
        out["date_check"] = "MISMATCH"
        out["reason"] = "응답 날짜 ≠ 요청일"
        return out
    out["date_check"] = "DIRECT" if fields else "INDIRECT"
    if close is None:
        out["reason"] = "저장 코스피 종가 없음(대조 불가)"
        return out
    diff = abs(index_value - close)
    out["index_diff"] = round(diff, 6)
    if diff > CLOSE_TOLERANCE:
        out["reason"] = "지수값 ≠ 그날 저장 코스피 종가"
        return out
    out["values"] = [
        (inv, field, row.get(field), nets[inv])
        for field, inv in KW.FIELD_TO_INVESTOR.items()
    ]
    out["status"] = VALID
    return out


def mark_repeats(evals: list[dict]) -> None:
    """유효 날짜 중 13분류 값이 통째로 같은 날짜들 = 반복 응답 의심(표시만 · 유효 그대로)."""
    groups: dict[tuple, list[dict]] = {}
    for ev in evals:
        if ev["status"] == VALID:
            groups.setdefault(tuple(v[3] for v in ev["values"]), []).append(ev)
    for group in groups.values():
        if len(group) > 1:
            for ev in group:
                ev["repeat_suspect"] = 1


def flow_evaluations(lines: list[dict], kospi: dict) -> list[dict]:
    finals = final_by(lines, lambda x: x["base_dt"])
    evals = [evaluate_flow_line(finals[k], kospi) for k in sorted(finals)]
    mark_repeats(evals)
    return evals


# --- 원/달러 · WTI ------------------------------------------------------------


def _classify(body: dict, adapter_start: date, start: str, end: str) -> tuple:
    """원시 봉을 기존 어댑터 규칙대로 나눠 센다(보고 · 원시 timestamp 용 · 어댑터 결과와 대조)."""
    res = body["chart"]["result"][0]
    meta = res["meta"]
    tz_name = meta["exchangeTimezoneName"]
    tz = ZoneInfo(tz_name)
    today = (
        datetime.fromtimestamp(
            meta["currentTradingPeriod"]["regular"]["start"], timezone.utc
        )
        .astimezone(tz)
        .date()
    )
    stamps = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0]["close"]
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    kept: dict[str, tuple[float, int]] = {}
    excluded: list[tuple] = (
        []
    )  # 요청 창 안 · 원시에 있으나 정규화에서 빠진 봉(종류별 · 공급자 미제공 아님)
    for ts, c in zip(stamps, closes):
        counts["raw"] += 1
        loc = datetime.fromtimestamp(ts, timezone.utc).astimezone(tz)
        key = loc.date().isoformat()
        in_window = start <= key <= end
        if c is None:
            counts["null_close"] += 1
            if in_window:
                excluded.append(
                    (key, loc.strftime("%H:%M"), ts, None, EXCLUDED_NULL_CLOSE)
                )
        elif (loc.hour, loc.minute, loc.second) != (0, 0, 0):
            counts["not_midnight"] += 1
            if in_window:
                excluded.append(
                    (key, loc.strftime("%H:%M"), ts, float(c), EXCLUDED_NOT_MIDNIGHT)
                )
        elif loc.date() >= today:
            counts["in_progress"] += 1
        elif loc.date() < adapter_start:
            counts["before_request"] += 1
        elif loc.weekday() >= 5:
            counts["weekend"] += 1
        elif not start <= key <= end:
            counts["outside_window"] += 1
        else:
            counts["in_window"] += 1
            kept[key] = (float(c), ts)
    return counts, kept, tz_name, excluded


def evaluate_yahoo_doc(doc: dict) -> dict:
    """한 창의 마지막 시도 → 판정 · 현지 날짜 [시작, 끝] 완료 일봉."""
    sid = SERIES_BY_SYMBOL[doc["symbol"]]
    out: dict = {
        "series_id": sid,
        "symbol": doc["symbol"],
        "window": doc["window"],
        "phase": doc["phase"],
        "start": doc["start"],
        "end": doc["end"],
        "raw_file": doc["file"],
        "status": FAILED,
        "reason": "",
        "timezone": None,
        "counts": {},
        "rows": [],
        "excluded": [],
        "failure_kind": STRUCT,
    }
    if doc.get("error") or (doc.get("http_status") or 0) >= 500:
        out["failure_kind"] = COMM
    if doc.get("error"):
        out["reason"] = f"통신 오류({doc['error']})"
        return out
    if doc.get("http_status") != 200:
        out["reason"] = f"HTTP {doc.get('http_status')}"
        return out
    adapter_start = date.fromisoformat(doc["adapter_start"])
    try:
        body = json.loads(doc["body"])
        counts, kept, tz_name, excluded = _classify(
            body, adapter_start, doc["start"], doc["end"]
        )
    except (ValueError, KeyError, IndexError, TypeError) as e:
        out["reason"] = f"응답 형식 · 시간대 확인 불가({type(e).__name__})"
        return out
    out["counts"], out["timezone"], out["excluded"] = counts, tz_name, excluded
    try:
        rows = YH.fetch_completed_daily(
            doc["symbol"],
            adapter_start,
            now_utc=datetime.fromisoformat(doc["period2_utc"]),
            http_get=lambda *a, **k: ReplayResponse(200, doc["body"]),
        )
    except (YH.YahooSeriesError, ValueError, requests.HTTPError) as e:
        out["reason"] = f"어댑터 판정 실패({type(e).__name__}: {str(e)[:80]})"
        return out
    in_window = {d: c for d, c in rows if doc["start"] <= d <= doc["end"]}
    if in_window != {d: v[0] for d, v in kept.items()}:
        out["reason"] = "어댑터 결과와 원시 분류가 다름"
        return out
    if not in_window:
        out["reason"] = "요청 범위 안 완료 일봉 없음(해당 기간 미확보)"
        return out
    for d in sorted(kept):
        close, ts = kept[d]
        flag = FLAG_OK
        if close <= 0:
            flag = FLAG_WTI_NONPOSITIVE if sid == WTI else FLAG_FX_NONPOSITIVE
        out["rows"].append((d, close, ts, flag))
    out["status"] = VALID
    return out


def macro_evaluations(docs: list[dict]) -> dict[str, dict[str, dict]]:
    """{계열: {창: 판정}} — 같은 창의 여러 시도 중 마지막."""
    finals = final_by(docs, lambda x: f"{x['symbol']}|{x['window']}")
    out: dict[str, dict[str, dict]] = {sid: {} for sid in SERIES_BY_SYMBOL.values()}
    for doc in finals.values():
        ev = evaluate_yahoo_doc(doc)
        out[ev["series_id"]][ev["window"]] = ev
    return out


def canonical_window(evals: dict[str, dict]) -> list[str]:
    """정규 계열 = 장기(B) 창이 유효하면 그것 하나, 아니면 유효한 표본 창들."""
    if evals.get(FULL_WINDOW, {}).get("status") == VALID:
        return [FULL_WINDOW]
    return sorted(w for w, ev in evals.items() if ev["status"] == VALID)


# --- 표 만들기 · 쓰기 --------------------------------------------------------


def load_inputs(run_dir: Path) -> dict:
    kospi = json.loads((run_dir / INPUT_KOSPI).read_text(encoding="utf-8"))
    stored = json.loads((run_dir / INPUT_STORED).read_text(encoding="utf-8"))
    sealed = json.loads((run_dir / INPUT_SEALED).read_text(encoding="utf-8"))
    return {"kospi": kospi, "stored": stored, "sealed": sealed}


def kospi_map(kospi_doc: dict) -> dict[str, tuple[float, str]]:
    return {d: (float(c), s) for d, c, s in kospi_doc["rows"]}


def load_yahoo_docs(run_dir: Path) -> list[dict]:
    folder = run_dir / YAHOO_RAW_DIR
    if not folder.is_dir():
        return []
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))
    ]


def build_tables(run_dir: Path) -> dict:
    """원시 + 입력 사본 → 정규화 표(쓰지 않음 · 수집 뒤 처리와 검산이 같이 쓴다)."""
    inputs = load_inputs(run_dir)
    flow_evals = flow_evaluations(
        read_jsonl(run_dir / KIWOOM_RAW), kospi_map(inputs["kospi"])
    )
    macro_evals = macro_evaluations(load_yahoo_docs(run_dir))
    flow_dates, flow_values, macro, macro_excluded = [], [], [], []
    for ev in flow_evals:
        flow_dates.append({k: ev[k] for k in FLOW_DATE_COLUMNS})
        for inv, field, raw, won in ev["values"] or []:
            flow_values.append(
                {
                    "date": ev["date"],
                    "investor": inv,
                    "source_field": field,
                    "raw_eok": raw,
                    "net_won": won,
                }
            )
    for sid, by_window in macro_evals.items():
        unit = MACRO_SERIES[sid][0]
        canon = set(canonical_window(by_window))
        for window in sorted(by_window):
            ev = by_window[window]
            for d, hm, ts, close, reason in ev["excluded"]:
                macro_excluded.append(
                    {
                        "series_id": sid,
                        "symbol": ev["symbol"],
                        "phase": ev["phase"],
                        "window": window,
                        "obs_date": d,
                        "local_time": hm,
                        "timezone": ev["timezone"],
                        "raw_timestamp_utc": _utc(ts),
                        "close": close,
                        "reason": reason,
                        "canonical": 1 if window in canon else 0,
                        "raw_file": ev["raw_file"],
                    }
                )
            for d, close, ts, flag in ev["rows"]:
                macro.append(
                    {
                        "series_id": sid,
                        "symbol": ev["symbol"],
                        "phase": ev["phase"],
                        "window": window,
                        "obs_date": d,
                        "timezone": ev["timezone"],
                        "raw_timestamp_utc": _utc(ts),
                        "close": close,
                        "unit": unit,
                        "flag": flag,
                        "canonical": 1 if window in canon else 0,
                        "raw_file": ev["raw_file"],
                    }
                )
    return {
        "inputs": inputs,
        "flow_evals": flow_evals,
        "macro_evals": macro_evals,
        "flow_dates": flow_dates,
        "flow_values": flow_values,
        "macro": macro,
        "macro_excluded": macro_excluded,
    }


def _utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    return str(v).replace(",", ";").replace("\n", " ")


def render_csv(rows: list[dict], columns: tuple[str, ...]) -> str:
    lines = [",".join(columns)]
    lines += [",".join(_cell(r[c]) for c in columns) for r in rows]
    return "\n".join(lines) + "\n"


def rendered_files(tables: dict) -> dict[str, str]:
    return {
        FLOW_DATES_CSV: render_csv(tables["flow_dates"], FLOW_DATE_COLUMNS),
        FLOW_VALUES_CSV: render_csv(tables["flow_values"], FLOW_VALUE_COLUMNS),
        MACRO_CSV: render_csv(tables["macro"], MACRO_COLUMNS),
        MACRO_EXCLUDED_CSV: render_csv(
            tables["macro_excluded"], MACRO_EXCLUDED_COLUMNS
        ),
    }


def _dumps_line(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


# --- 날짜 도우미(보고용) ------------------------------------------------------


def weekdays(first: str, last: str) -> list[str]:
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def longest_run(gaps: list[str]) -> int:
    """연속 평일 빈 날 최장 길이(주말을 건너 이어지면 같은 공백으로 본다)."""
    best = run = 0
    prev = None
    for d in gaps:
        cur = date.fromisoformat(d)
        nxt = prev and next_weekday(prev)
        run = run + 1 if prev and nxt == cur else 1
        best, prev = max(best, run), cur
    return best


def next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d
