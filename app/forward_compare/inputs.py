"""POC6-06 — 05 PC 보관본에서 연구 축 · 입력 창 · 목표 창 고르기(판정 §2 Q2 (a) · 설계 §8).

```text
대상 묶음  DAILY_COLLECTION · 상태 OK · PARTIAL · SKIPPED_NO_NEW(FAILED · 미완료 · 손상 제외)
           OCI 공개(published_at) · PC 수신(receipt.copied_at_pc) 둘 다 cutoff 이하(실제 시각 해석 비교)
창 원본    object 가 처음 실린 '대상 묶음'(공개 · run_id 순) = 원래 공개 판 · reused_from 은 참조로 남김
연구 축    그 묶음이 보관한 KOSPI 저장일 object + 거래일 파일 object(06 `research_axis` 그대로)
입력       기준일 D 묶음의 창 중 축 D-60..D 가 06 가격 · 연결 검사를 통과한 가장 이른 원래 공개 판
목표       D..D+20(21 종가)이 한 창 · 한 축에서 통과한 가장 이른 원래 공개 판 · 첫 평가 고정
           읽는 묶음 = 기준일이 D+20 이상 · D+120일 이하(수신 창 120일이 D 를 담을 수 있는 범위)
```

종목 안에서 다른 수신 판을 이어 붙이지 않는다. 상태 글자 OK 만으로 쓰지 않는다(창을 실제로 검사).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

from app import market_data_fdr as fdr_mod
from app import trading_day_lag as tdl
from app.forward_compare import protocol as P
from app.ml_evidence import store
from app.reentry_review import model as m06
from app.reentry_review import prices as px

USABLE = ("OK", "PARTIAL", "SKIPPED_NO_NEW")
WINDOW_ROLES = ("naver_windows", "naver_windows_target_day")
LB, H = m06.LB, m06.H
SPAN_DAYS = (
    fdr_mod.DEFAULT_LOOKBACK_DAYS
)  # 05 수신 창 = 수집일 전 120일 → D 를 담을 수 있는 묶음 범위
_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, EOFError, store.EvidenceError)


@dataclass(frozen=True)
class Run05:
    run_id: str
    published: datetime
    copied: datetime
    target_day: Optional[str]
    manifest: dict


class Evidence:
    """cutoff 시점에 PC 가 가진 05 정상 묶음(읽기 전용). 거래일 파일은 임시 폴더에 object 로 복원해 쓴다."""

    def __init__(
        self, ev_root: Path, cutoff: datetime, tickers: Optional[set] = None
    ) -> None:
        self.root = Path(ev_root)
        self.cutoff = cutoff
        self.tickers = (
            tickers  # 주면 그 종목 줄만 기억(1,000여 종목 창 전체를 쌓지 않음)
        )
        self.excluded: list[dict] = []
        self._tmp = tempfile.TemporaryDirectory(prefix="poc6_06_cal_")
        self._cal: dict[tuple, Path] = {}
        self._json: dict[str, Any] = {}
        self._lines: dict[str, dict[str, dict]] = {}
        runs, problems = store.list_runs(self.root)
        self.excluded += [{"run": p, "reason": "manifest 문제"} for p in problems]
        self.runs: list[Run05] = []
        for r in runs:
            m = r.manifest
            if m["kind"] != "DAILY_COLLECTION":
                continue
            why = self._why_not(r)
            if why:
                self.excluded.append({"run_id": r.run_id, "reason": why})
                continue
            nav = m.get("sources", {}).get("naver_etf_windows", {})
            self.runs.append(
                Run05(
                    r.run_id,
                    store.parse_iso(m["published_at"]),
                    store.parse_iso(r.receipt["copied_at_pc"]),
                    nav.get("target_day"),
                    m,
                )
            )
        self.runs.sort(key=lambda x: (x.published, x.run_id))
        self.origin: dict[str, Run05] = {}  # 창 object → 처음 실린 대상 묶음
        for run in self.runs:
            for sha in self.window_objects(run):
                self.origin.setdefault(sha, run)

    def close(self) -> None:
        self._tmp.cleanup()

    def _why_not(self, r: store.RunRef) -> Optional[str]:
        if r.manifest["status"] not in USABLE:
            return f"상태 {r.manifest['status']}"
        try:
            copied = store.parse_iso((r.receipt or {}).get("copied_at_pc"))
        except ValueError:
            return "PC 수신 시각 없음 · 형식 아님"
        if store.parse_iso(r.manifest["published_at"]) > self.cutoff:
            return "OCI 공개가 cutoff 뒤"
        if copied > self.cutoff:
            return "PC 수신이 cutoff 뒤"
        return None

    def inventory(self) -> list[dict]:
        return [
            {
                "run_id": r.run_id,
                "published_at": store.iso(r.published),
                "copied_at_pc": store.iso(r.copied),
                "target_day": r.target_day,
                "status": r.manifest["status"],
            }
            for r in self.runs
        ]

    # ── 자료 읽기 ───────────────────────────────────────────────────────────

    @staticmethod
    def window_objects(run: Run05) -> list[str]:
        nav = run.manifest.get("sources", {}).get("naver_etf_windows", {})
        listed = nav.get("objects_for_target_day") or []
        roles = {o["sha256"]: o.get("role") for o in run.manifest["objects"]}
        return [s for s in listed if roles.get(s) in WINDOW_ROLES]

    def json_object(self, sha: str) -> Any:
        if sha not in self._json:
            self._json[sha] = json.loads(store.read_object(self.root, sha))
        return self._json[sha]

    def lines(self, sha: str) -> dict[str, dict]:
        """창 object → {ticker: 줄}(손상이면 EvidenceError)."""
        if sha not in self._lines:
            self._lines[sha] = {
                ln["ticker"]: ln
                for ln in store.read_jsonl_gz(self.root, sha)
                if self.tickers is None or ln["ticker"] in self.tickers
            }
        return self._lines[sha]

    def axis_inputs(self, run: Run05) -> tuple[list[str], Path, dict]:
        """그 묶음의 KOSPI 저장일 · 거래일 파일(object 복원) · 참조."""
        da = run.manifest["sources"]["date_axis"]
        kospi_sha = da["kospi_stored_dates"]["object"]
        dates = self.json_object(kospi_sha)["dates"]
        files = tuple((f["name"], f["sha256"]) for f in da.get("calendar_files") or [])
        if files not in self._cal:
            d = Path(self._tmp.name) / f"c{len(self._cal)}"
            d.mkdir()
            for name, sha in files:
                if "/" in name or not name.startswith("krx_trading_days_"):
                    raise store.EvidenceError(f"거래일 파일 이름 이상: {name[:40]}")
                (d / name).write_bytes(store.read_object(self.root, sha))
            self._cal[files] = d
        ref = {"kospi_object": kospi_sha, "calendar_files": [list(f) for f in files]}
        return dates, self._cal[files], ref

    def calendar_dir(self, run: Run05) -> Path:
        return self.axis_inputs(run)[1]

    def latest(self) -> Optional[Run05]:
        return self.runs[-1] if self.runs else None

    # ── 창 검사 ─────────────────────────────────────────────────────────────

    def _candidates(self, ticker: str, ok_run) -> Iterator[tuple[Run05, str, dict]]:
        """원래 공개 순(공개 · run_id) · object 는 차례가 왔을 때만 읽는다(첫 통과에서 멈춤)."""
        shas: dict[str, Run05] = {}
        for run in self.runs:
            if ok_run(run):
                for sha in self.window_objects(run):
                    shas.setdefault(sha, self.origin[sha])
        order = sorted(
            shas.items(), key=lambda kv: (kv[1].published, kv[1].run_id, kv[0])
        )
        for sha, origin in order:
            try:
                line = self.lines(sha).get(ticker)
            except _READ_ERRORS as e:
                yield origin, sha, {"_damaged": f"{type(e).__name__}"}
                continue
            if line is not None:
                yield origin, sha, line

    def _series(self, run: Run05, t: str, first: str, line: dict):
        dates, cal_dir, ref = self.axis_inputs(run)
        axis = px.research_axis(t, first, dates, calendar_dir=cal_dir)
        rows = [
            px.PriceRow(r[0], r[4], P.SOURCE, line.get("observed_at"), r[6])
            for r in line.get("rows") or []
        ]
        return axis, px.AxisSeries(axis["dates"], rows), ref

    def _source_ref(self, run: Run05, sha: str, line: dict, axis_ref: dict) -> dict:
        reused = next(
            (
                o.get("reused_from")
                for o in run.manifest["objects"]
                if o["sha256"] == sha
            ),
            None,
        )
        return {
            "run_id": run.run_id,
            "reused_from": reused,
            "object": sha,
            "observed_at": line.get("observed_at"),
            "available_at": store.iso(run.published),
            "copied_at_pc": store.iso(run.copied),
            "axis": axis_ref,
        }

    def select_input(self, ticker: str, D: str) -> dict[str, Any]:
        """기준일 D 입력 — 가장 이른 원래 공개 판 중 축 D-60..D 를 통과한 창(Q2 (a))."""
        tried = []
        for run, sha, line in self._candidates(ticker, lambda r: r.target_day == D):
            if "_damaged" in line:
                tried.append({"object": sha, "reason": "OBJECT_DAMAGED"})
                continue
            if not line.get("rows"):  # 상태 글자가 아니라 창 내용으로 판단(판정 §2-2)
                tried.append({"object": sha, "reason": f"LINE_{line.get('status')}"})
                continue
            try:
                axis, s, ref = self._series(run, D, line["rows"][0][0], line)
            except _READ_ERRORS as e:
                tried.append(
                    {
                        "object": sha,
                        "reason": "AXIS_OBJECT_DAMAGED",
                        "detail": type(e).__name__,
                    }
                )
                continue
            problem = px.axis_problem(D, axis)
            if problem:
                tried.append(
                    {"object": sha, "reason": "AXIS_UNCERTAIN", "detail": problem}
                )
                continue
            iD = len(s.dates) - 1
            reasons = s.window_reasons(iD - LB, iD) if iD >= LB else ["DATA_SHORT"]
            if reasons:
                tried.append({"object": sha, "reason": "WINDOW", "detail": reasons})
                continue
            lo, hi = iD - LB, iD + 1
            return {
                "status": "OK",
                "source": self._source_ref(run, sha, line, ref),
                "window": [[d, c] for d, c in zip(s.dates[lo:hi], s.closes[lo:hi])],
                "features": m06.features_at(s.closes, iD),
                "base_close": s.closes[iD],
                "tried": tried,
            }
        status = "INPUT_CHECK_REQUIRED" if tried else "INPUT_MISSING"
        return {"status": status, "tried": tried}

    def select_target(self, ticker: str, D: str) -> dict[str, Any]:
        """D20 성숙 목표 — 한 창 · 한 축에 D..D+20 21 종가(설계 §8). 상태 4종 구분."""
        latest = self.latest()
        if latest is None or latest.target_day is None:
            return {
                "status": "PENDING_CALENDAR",
                "detail": "05 정상 묶음 · 기준일 없음",
            }
        try:
            dates, cal_dir, _ = self.axis_inputs(latest)
        except _READ_ERRORS as e:
            return {
                "status": "DATA_CHECK_REQUIRED",
                "detail": f"최신 묶음 축 자료 손상 {type(e).__name__}",
            }
        axis = px.research_axis(latest.target_day, D, dates, calendar_dir=cal_dir)
        if (
            px.axis_problem(latest.target_day, axis)
            or not axis["dates"]
            or axis["dates"][0] != D
        ):
            return {
                "status": "PENDING_CALENDAR",
                "detail": "D · 최신 기준일이 연구 축에서 확정되지 않음",
            }
        if len(axis["dates"]) < H + 1:
            return {"status": "PENDING_NOT_DUE", "axis_after_D": len(axis["dates"]) - 1}
        tried = []

        last = (date.fromisoformat(D) + timedelta(days=SPAN_DAYS)).isoformat()

        def due(run: Run05) -> bool:
            """D+20 이 지났고 · 수신 창(120일)이 아직 D 를 담을 수 있는 묶음만."""
            return (
                run.target_day is not None
                and axis["dates"][H] <= run.target_day <= last
            )

        for run, sha, line in self._candidates(ticker, due):
            if "_damaged" in line:
                tried.append({"object": sha, "reason": "OBJECT_DAMAGED"})
                continue
            if not line.get("rows"):
                tried.append({"object": sha, "reason": f"LINE_{line.get('status')}"})
                continue
            try:
                ax, s, ref = self._series(run, run.target_day, D, line)
            except _READ_ERRORS as e:
                tried.append(
                    {
                        "object": sha,
                        "reason": "AXIS_OBJECT_DAMAGED",
                        "detail": type(e).__name__,
                    }
                )
                continue
            if (
                px.axis_problem(run.target_day, ax)
                or len(s.dates) < H + 1
                or s.dates[0] != D
            ):
                tried.append({"object": sha, "reason": "AXIS_UNCERTAIN"})
                continue
            reasons = s.window_reasons(0, H)
            if reasons:
                tried.append({"object": sha, "reason": "WINDOW", "detail": reasons})
                continue
            return {
                "status": "MATURED",
                "source": self._source_ref(run, sha, line, ref),
                "closes": [[d, c] for d, c in zip(s.dates[: H + 1], s.closes[: H + 1])],
                "target": m06.target_at(s.closes, 0),
                "target_end": s.dates[H],
                "tried": tried,
            }

        def only_missing(t: dict) -> bool:
            """받은 값이 없을 뿐(줄 없음 · 축 날짜 종가 없음)인 시도."""
            if t["reason"].startswith("LINE_"):
                return True
            return t["reason"] == "WINDOW" and t.get("detail") == [px.MISSING_PRICE]

        bad = [t for t in tried if not only_missing(t)]
        return {
            "status": "DATA_CHECK_REQUIRED" if bad else "DUE_DATA_MISSING",
            "tried": tried,
        }


def next_trading_day(D: str, cal_dir: Path) -> Optional[str]:
    """D 다음 거래일(운영 축 · 14일 안 · 못 찾으면 None = 판정 안 함)."""
    d = date.fromisoformat(D)
    for i in range(1, 15):
        cand = (d + timedelta(days=i)).isoformat()
        if tdl.is_trading_day(cand, calendar_dir=cal_dir):
            return cand
    return None
