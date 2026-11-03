"""POC6-19 — 정규화 표 + 실행 기록 → report.json / report.md(외부 조회 0 · 계산은 범위 · 개수 · 값 대조만).

자료별 상태(설계 §8): ARCHIVE_READY(사본 확보 · 정의/검산 확인) · PARTIAL(일부 범위만) ·
SOURCE_UNAVAILABLE(공급자의 명시 응답이 있을 때만 · 자동으로 주지 않음) · ACCESS_BLOCKED(인증 · IP) ·
FETCH_FAILED(통신 · 구조 · 예산 중단). HTTP 200 만으로 상태를 주지 않는다.

ARCHIVE_READY 는 수집 사본의 상태다 — ML 효용 · 표본 충분성 · 당시 공개 판 일치 · 새 미사용 시험을 뜻하지 않는다.
시장 공통 입력의 독립 시간 표본은 날짜 · ISO 주로 센다(ETF 수로 늘리지 않음). 달력이 다른 자료(런던 · 뉴욕
날짜)는 날짜 문자열로 붙이지 않고 ISO 주가 겹치는지만 센다. 상관 · 모델 · 수익은 계산하지 않는다.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Iterable, Optional

from app.market_history import normalize as N
from app.market_history.normalize import (
    FAILED,
    FLAG_FX_NONPOSITIVE,
    FULL_WINDOW,
    SERIES_BY_SYMBOL,
    VALID,
)
from app.supply_fx_oil_store import USDKRW, WTI

ARCHIVE_READY = "ARCHIVE_READY"
PARTIAL = "PARTIAL"
ACCESS_BLOCKED = "ACCESS_BLOCKED"
FETCH_FAILED = "FETCH_FAILED"
REPORT_SCHEMA = "poc6_19_market_history_report.v1"
SERIES_LABEL = {"kospi_flow": "코스피 수급", USDKRW: "원/달러", WTI: "WTI"}
TIME_MEANING = {
    "kospi_flow": (
        "KRX 코스피 종합(001) 그날 마감 집계 · 억원 → 정수 원 · 날짜 근거 = 응답 날짜 칸(있으면) + 그날 "
        "저장 코스피 종가 대조 · 당시 공개 시각 미확인 · 수신 시각은 이번 실행(과거로 소급 안 함)"
    ),
    USDKRW: (
        "Yahoo KRW=X 일봉 종가 · 공급자 시간대(런던) 현지 날짜 · 한국 15:30 값 아님 · 당시 공개 시각 미확인"
    ),
    WTI: (
        "Yahoo CL=F 근월물 선물 일봉 종가 · 뉴욕 현지 날짜 · 현물 · 총수익 아님 · 월물 교체 조정 없음 · "
        "당시 공개 시각 미확인"
    ),
}
LIST_LIMIT = 60
MAX_HOLE_WEEKDAYS = (
    5  # 휴장(성탄 · 부활절 등)보다 긴 연속 평일 공백 = 장기 창의 부분 확보로 본다
)
GAP_NO_BAR = "봉 없음(휴장 가능 · 기대 거래일 미확정)"
GAP_KIND = {  # 정규화에 없는 평일의 종류 — 원시에 있는 봉을 '공급자 미제공'으로 부르지 않는다
    N.EXCLUDED_NOT_MIDNIGHT: "자정 아닌 봉(원시에 있음 · 현행 어댑터 규칙으로 정규화에서 제외)",
    N.EXCLUDED_NULL_CLOSE: "빈 종가(원시에 봉 있음)",
}


def sid_symbol(sid: str) -> str:
    return next(sym for sym, s in SERIES_BY_SYMBOL.items() if s == sid)


def _iso_week(d: str) -> tuple[int, int]:
    y, w, _ = date.fromisoformat(d).isocalendar()
    return (y, w)


def _week_label(w: tuple[int, int]) -> str:
    return f"{w[0]}-W{w[1]:02d}"


def _weeks(dates: Iterable[str]) -> set[tuple[int, int]]:
    return {_iso_week(d) for d in dates}


def _week_summary(weeks: set) -> dict:
    s = sorted(weeks)
    return {
        "weeks": len(s),
        "first_week": _week_label(s[0]) if s else None,
        "last_week": _week_label(s[-1]) if s else None,
    }


def _short_list(items: list) -> dict:
    return {
        "count": len(items),
        "items": items[:LIST_LIMIT],
        "truncated": len(items) > LIST_LIMIT,
    }


def _compare(new: dict, old: dict, why_new=None, why_old=None) -> dict:
    """같은 키는 값 대조 · 한쪽에만 있는 키는 사유와 함께 목록(새 값 · 옛 값을 고치지 않는다)."""
    common = sorted(set(new) & set(old))
    diffs = [
        {"key": k, "new": new[k], "stored": old[k], "abs_diff": abs(new[k] - old[k])}
        for k in common
        if new[k] != old[k]
    ]

    def side(keys, why):
        return [{"key": k, "reason": why(k) if why else "사유 미확인"} for k in keys]

    return {
        "compared": len(common),
        "equal": len(common) - len(diffs),
        "different": _short_list(diffs),
        "max_abs_diff": max((x["abs_diff"] for x in diffs), default=0),
        "only_new": _short_list(side(sorted(set(new) - set(old)), why_new)),
        "only_stored": _short_list(side(sorted(set(old) - set(new)), why_old)),
    }


def _run_cause(run_end: dict, post_error: Optional[dict]) -> list[str]:
    err = run_end.get("error")
    out = [f"실행 중단: {err['type']} · {err.get('message')}"] if err else []
    if post_error:
        out.append(f"후처리 상한: {post_error.get('message')}")
    return out


def _faulted(run_end: dict, post_error: Optional[dict]) -> bool:
    """실행 · 후처리 오류(상한 · 입력 변경 · 중단)가 기록됐는가 — 그 실행의 자료는 ARCHIVE_READY 가 아니다."""
    return bool(run_end.get("error") or post_error)


def _flow_section(
    tables: dict, run_start: dict, run_end: dict, post_error: Optional[dict]
) -> dict:
    inputs, plan = tables["inputs"], run_start["plan"]
    kospi_dates = [r[0] for r in inputs["kospi"]["rows"]]
    sealed = inputs["sealed"]["dates"]
    first_kospi, end = kospi_dates[0], plan["target_end"]
    full = [d for d in kospi_dates if first_kospi <= d <= end]
    rows = tables["flow_dates"]
    valid = sorted(r["date"] for r in rows if r["status"] == VALID)
    valid_set, requested = set(valid), {r["date"] for r in rows}
    failed = [
        {"date": r["date"], "phase": r["phase"], "reason": r["reason"]}
        for r in rows
        if r["status"] == FAILED
    ]
    fail_reason = {x["date"]: x["reason"] for x in failed}
    not_requested = [d for d in full if d not in requested]
    kw = run_end.get("providers", {}).get("kiwoom", {})
    stop, gate, b = kw.get("stop"), kw.get("gate") or {}, kw.get("b") or {}
    missing_full = [d for d in full if d not in valid_set]
    if not valid:
        status = (
            ACCESS_BLOCKED
            if stop and stop.get("status") == ACCESS_BLOCKED
            else FETCH_FAILED
        )
    elif not missing_full and not _faulted(run_end, post_error):
        status = ARCHIVE_READY
    else:
        status = PARTIAL  # 실행 오류(상한 · 입력 변경 · 중단)가 기록된 실행은 ARCHIVE_READY 가 아니다
    causes = [
        x
        for x in (
            stop and f"공급자 중단: {stop.get('reason')}",
            gate
            and not gate.get("passed")
            and f"장기 조회 안 함: {gate.get('reason')}",
            b.get("skipped_reason") and f"장기 조회 생략: {b['skipped_reason']}",
            b.get("stop")
            and b["stop"] != (stop or {}).get("reason")
            and f"장기 조회 중단: {b['stop']}",
            failed and f"요청했으나 실패 {len(failed)}일",
            not_requested
            and f"코스피 저장 거래일 {first_kospi} ~ {end} 중 요청 안 함 {len(not_requested)}일",
            *_run_cause(run_end, post_error),
        )
        if x
    ]
    stored = {
        (d, inv): net
        for inv, pairs in inputs["stored"]["flows"].items()
        for d, net in pairs
        if d <= end
    }
    lo = min((k[0] for k in stored), default=None)
    overlap = None
    if lo:
        new = {
            (r["date"], r["investor"]): r["net_won"]
            for r in tables["flow_values"]
            if r["date"] >= lo
        }
        pairs = _compare(
            {f"{d}|{i}": v for (d, i), v in new.items()},
            {f"{d}|{i}": v for (d, i), v in stored.items()},
        )
        by_date = _compare(
            {d: 0 for d, _ in new},
            {d: 0 for d, _ in stored},
            why_new=lambda d: "저장본에 없음(사유 미확인)",
            why_old=lambda d: (
                f"이번 실행 실패: {fail_reason[d]}"
                if d in fail_reason
                else "이번 실행에서 요청 안 함" if d not in requested else "사유 미확인"
            ),
        )
        overlap = {
            "unit": "값 대조 = (날짜 · 분류) 쌍 · 한쪽에만 있음 = 날짜",
            "compared_pairs": pairs["compared"],
            "equal": pairs["equal"],
            "different": pairs["different"],
            "max_abs_diff": pairs["max_abs_diff"],
            "compared_dates": by_date["compared"],
            "only_new": by_date["only_new"],
            "only_stored": by_date["only_stored"],
        }
    checks = [r["date_check"] for r in rows if r["status"] == VALID]
    sealed_common = sorted(valid_set & set(sealed))
    return {
        "label": SERIES_LABEL["kospi_flow"],
        "status": status,
        "causes": causes,
        "requested": {
            "samples": plan["flow_samples"],
            "b_start": b.get("start"),
            "end": end,
            "b_planned_dates": b.get("planned"),
            "requested_dates": len(requested),
        },
        "actual": {
            "first": valid[0] if valid else None,
            "last": valid[-1] if valid else None,
            "valid_dates": len(valid),
            **_week_summary(_weeks(valid)),
        },
        "unit": "정수 원(억원 × 100,000,000) · 13분류 원천 그대로 · 기관계 = 세부 합(다시 더하지 않음)",
        "date_check": {
            "direct": checks.count("DIRECT"),
            "indirect": checks.count("INDIRECT"),
            "fields_seen": sorted({r["date_fields"] for r in rows if r["date_fields"]}),
        },
        "failed_dates": _short_list(failed),
        "not_requested_in_target": {
            "count": len(not_requested),
            "first": not_requested[0] if not_requested else None,
            "last": not_requested[-1] if not_requested else None,
        },
        "duplicates": {
            "count": 0,
            "note": "날짜마다 마지막 시도 줄 하나만 판정(재시도 줄은 원시에 보존 · 중복 아님)",
        },
        "not_requested_before_kospi_start": {
            "count": len([d for d in sealed if d < first_kospi]),
            "reason": f"저장 코스피 종가가 {first_kospi} 부터라 지수 대조 근거 없음(결측 · 미제공으로 세지 않음)",
        },
        "repeat_suspect_dates": _short_list(
            [r["date"] for r in rows if r["repeat_suspect"] == 1]
        ),
        "stored_overlap": overlap,
        "sealed_common": {
            "dates": len(sealed_common),
            "first": sealed_common[0] if sealed_common else None,
            "last": sealed_common[-1] if sealed_common else None,
            **_week_summary(_weeks(sealed_common)),
        },
        "time_meaning": TIME_MEANING["kospi_flow"],
    }


def _macro_section(
    sid: str, tables: dict, run_start: dict, run_end: dict, post_error: Optional[dict]
) -> dict:
    inputs, plan = tables["inputs"], run_start["plan"]
    evals = tables["macro_evals"].get(sid, {})
    rows = [r for r in tables["macro"] if r["series_id"] == sid]
    canon = [r for r in rows if r["canonical"] == 1]
    valid = [r for r in canon if r["flag"] != FLAG_FX_NONPOSITIVE]
    dates = sorted(r["obs_date"] for r in valid)
    start, end = plan["macro_target_start"], plan["target_end"]
    full = evals.get(FULL_WINDOW, {})
    yh = run_end.get("providers", {}).get("yahoo", {})
    stop, gate = yh.get("stop"), (yh.get("gates") or {}).get(sid) or {}
    invalid = [r["obs_date"] for r in canon if r["flag"] == FLAG_FX_NONPOSITIVE]
    have = set(dates)
    gaps = sorted(
        {
            d
            for w in {r["window"] for r in canon}
            for d in N.weekdays(evals[w]["start"], evals[w]["end"])
            if d not in have
        }
    )
    longest = N.longest_run(gaps)
    holes = full.get("status") == VALID and longest > MAX_HOLE_WEEKDAYS
    excl = {
        r["obs_date"]: r
        for r in tables.get("macro_excluded", [])
        if r["series_id"] == sid and r["canonical"] == 1
    }
    kinds = {d: GAP_KIND.get(excl.get(d, {}).get("reason"), GAP_NO_BAR) for d in gaps}
    if not dates:
        status = FETCH_FAILED
    elif (
        full.get("status") == VALID
        and dates[0] <= start
        and dates[-1] >= end
        and not invalid
        and not holes
        and not _faulted(run_end, post_error)
    ):
        status = ARCHIVE_READY
    else:
        status = PARTIAL
    symbol_stops = [
        v
        for k, v in (yh.get("phase_stop") or {}).items()
        if k.endswith(sid_symbol(sid))
    ]
    causes = [
        x
        for x in (
            stop and f"공급자 중단: {stop.get('reason')}",
            *[f"조회 중단: {v}" for v in symbol_stops],
            gate
            and not gate.get("passed")
            and f"장기 조회 안 함: {gate.get('reason')}",
            yh.get("b_skipped_reason") and f"장기 조회 생략: {yh['b_skipped_reason']}",
            full
            and full.get("status") == FAILED
            and f"장기 창 실패: {full.get('reason')}",
            dates and dates[0] > start and f"반환 시작 {dates[0]} > 요청 시작 {start}",
            dates and dates[-1] < end and f"반환 끝 {dates[-1]} < 요청 끝 {end}",
            invalid and f"0 이하 손상 값 {len(invalid)}개",
            holes
            and f"중간 공백 최장 연속 평일 {longest}일 > {MAX_HOLE_WEEKDAYS}일"
            "(평일 기준 공백 · 기대 거래일 미확정 · 휴장을 결측으로 확정하지 않음 · 잠정 확인 기준)",
            *_run_cause(run_end, post_error),
        )
        if x
    ]
    stored = {d: v for d, v in inputs["stored"]["macro"].get(sid, []) if d <= end}
    new = {r["obs_date"]: r["close"] for r in valid}
    lo = min(stored, default=None)
    sample_vs_full = {}
    if full.get("status") == VALID:
        full_rows = {
            r["obs_date"]: r["close"] for r in rows if r["window"] == FULL_WINDOW
        }
        for w, ev in sorted(evals.items()):
            if w != FULL_WINDOW and ev["status"] == VALID:
                sample = {d: c for d, c, _, _ in ev["rows"]}
                span = {
                    d: c for d, c in full_rows.items() if ev["start"] <= d <= ev["end"]
                }
                sample_vs_full[w] = _compare(
                    sample,
                    span,
                    why_new=lambda d: "장기 창에 없음(사유 미확인)",
                    why_old=lambda d: "표본 창에 없음(사유 미확인)",
                )
    duplicates = [
        w for w, ev in sorted(evals.items()) if "같은 날짜 봉" in ev["reason"]
    ]
    sealed_weeks = _weeks(inputs["sealed"]["dates"])
    common_weeks = _weeks(dates) & sealed_weeks
    return {
        "label": SERIES_LABEL[sid],
        "status": status,
        "causes": causes,
        "requested": {
            "start": start,
            "end": end,
            "sample_windows": plan["macro_windows"],
        },
        "actual": {
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
            "valid_rows": len(dates),
            **_week_summary(_weeks(dates)),
        },
        "windows": {
            w: {"status": ev["status"], "reason": ev["reason"], "counts": ev["counts"]}
            for w, ev in sorted(evals.items())
        },
        "sample_vs_full": sample_vs_full,
        "duplicate_windows": duplicates,
        "timezone": sorted({r["timezone"] for r in canon}),
        "unit": canon[0]["unit"] if canon else None,
        "nonpositive": {
            "kept_flagged": [
                r["obs_date"] for r in canon if r["flag"] == "NONPOSITIVE_KEPT"
            ],
            "invalid": invalid,
        },
        "weekday_gaps": {
            **_short_list([{"date": d, "kind": kinds[d]} for d in gaps]),
            "longest_run": longest,
            "by_kind": {
                k: list(kinds.values()).count(k) for k in sorted(set(kinds.values()))
            },
            "note": "정규화 계열에 없는 요청 구간 안 평일 · 종류별(원시에 있으나 제외 · 빈 종가 · 봉 없음) · "
            "평일 기준 · 기대 거래일 미확정 · 채우지 않음",
        },
        "stored_overlap": (
            _compare(
                {d: v for d, v in new.items() if d >= lo},
                stored,
                why_new=lambda d: "저장본에 없음(사유 미확인)",
                why_old=lambda d: "새 응답에 없음(사유 미확인)",
            )
            if lo
            else None
        ),
        "sealed_common": {
            **_week_summary(common_weeks),
            "note": "달력이 달라 날짜 문자열로 붙이지 않음 · 두 자료가 모두 관측된 ISO 주",
        },
        "time_meaning": TIME_MEANING[sid],
    }


def build_report(
    tables: dict, run_start: dict, run_end: dict, post_error: Optional[dict] = None
) -> dict:
    """`post_error` = 후처리 상한 초과(postprocess.json 의 LIMIT) — 원인 · 상태 판정에 넣는다(검증자 r2 F3)."""
    flow = _flow_section(tables, run_start, run_end, post_error)
    macro = {
        sid: _macro_section(sid, tables, run_start, run_end, post_error)
        for sid in (USDKRW, WTI)
    }
    flow_dates = [r["date"] for r in tables["flow_dates"] if r["status"] == VALID]
    weeks = {
        "kospi_flow": _weeks(flow_dates),
        **{
            sid: _weeks(
                r["obs_date"]
                for r in tables["macro"]
                if r["series_id"] == sid
                and r["canonical"] == 1
                and r["flag"] != FLAG_FX_NONPOSITIVE
            )
            for sid in (USDKRW, WTI)
        },
    }
    common = set.intersection(*weeks.values())
    sealed_weeks = _weeks(tables["inputs"]["sealed"]["dates"])
    report = {
        "schema": REPORT_SCHEMA,
        "run_id": run_start["run_id"],
        "sources": {"kospi_flow": flow, **macro},
        "three_common": {
            **_week_summary(common),
            "with_sealed_price": _week_summary(common & sealed_weeks),
            "note": "세 자료 모두 관측이 있는 ISO 주(시장 공통 입력의 독립 시간 표본 · ETF 수로 늘리지 않음)",
        },
        "requests": run_end.get("requests"),
        "end_reason": run_end.get("end_reason"),
        "live_changes": run_end.get("live_changes"),
        "sealed_unchanged": run_end.get("sealed_unchanged"),
        "not_claimed": (
            "ARCHIVE_READY 는 수집 사본의 상태다 — ML 효용 · 학습 표본 충분성 · 당시 공개 판 일치 · "
            "새 미사용 시험 · 운영 채택을 뜻하지 않는다. 총수익(분배금) 미확보(POC6-12)는 그대로다."
        ),
    }
    if post_error:  # 넘지 않은 실행의 보고는 이 칸 없이 예전과 같은 바이트
        report["postprocess_error"] = post_error
    return report


def _range_cell(sec: dict) -> str:
    a = sec["actual"]
    if not a["first"]:
        return "확보 없음"
    count = a.get("valid_dates", a.get("valid_rows"))
    return f"{a['first']} ~ {a['last']} · {count}개 · {a['weeks']}주"


def render_md(report: dict) -> str:
    src = report["sources"]
    flow, fx, oil = src["kospi_flow"], src[USDKRW], src[WTI]
    common = report["three_common"]
    lines = [
        f"# POC6-19 과거 시장 자료 사본 — 실행 {report['run_id']}",
        "",
        "| 자료 | 상태 | 요청 / 실제 범위 · 유효 개수 | 날짜 · 단위 대조 / 미확인 | 봉인 가격 판과 공통 | 후속 사용 한계 |",
        "|---|---|---|---|---|---|",
        (
            "| {} | {} | 요청 {} ~ {} / {} | 직접 {} · 간접 {} · 반복 의심 {}일 · 단위 억원 → 원 "
            "| {}일 · {}주 | {} |"
        ).format(
            flow["label"],
            flow["status"],
            flow["requested"]["b_start"] or flow["requested"]["samples"][-1],
            flow["requested"]["end"],
            _range_cell(flow),
            flow["date_check"]["direct"],
            flow["date_check"]["indirect"],
            flow["repeat_suspect_dates"]["count"],
            flow["sealed_common"]["dates"],
            flow["sealed_common"]["weeks"],
            "시장 전체 값(종목별 수급 아님) · 당시 공개 시각 미확인 · 회고 자료",
        ),
    ]
    for sec in (fx, oil):
        lines.append(
            "| {} | {} | 요청 {} ~ {} / {} | 시간대 {} · 0 이하 표시 {} · 손상 {} | {}주 | {} |".format(
                sec["label"],
                sec["status"],
                sec["requested"]["start"],
                sec["requested"]["end"],
                _range_cell(sec),
                ", ".join(sec["timezone"]) or "미확인",
                len(sec["nonpositive"]["kept_flagged"]),
                len(sec["nonpositive"]["invalid"]),
                sec["sealed_common"]["weeks"],
                "현지 날짜 · 한국 신호 시점 미정 · 당시 공개 시각 미확인 · 회고 자료",
            )
        )
    lines += [
        (
            "| 세 자료 공통 | — | {} ~ {} · {}주 | ISO 주 기준(날짜 문자열로 붙이지 않음) | {}주 "
            "| 이미 본 기간 포함 · 새 미사용 시험 아님 |"
        ).format(
            common["first_week"],
            common["last_week"],
            common["weeks"],
            common["with_sealed_price"]["weeks"],
        ),
        "",
        "## 상태 원인",
    ]
    for sec in (flow, fx, oil):
        lines.append(
            f"- {sec['label']} `{sec['status']}`: "
            + (" · ".join(sec["causes"]) or "없음")
        )
    lines += ["", "## 기존 저장본 대조(값 · 날짜 차이는 기록만 · 고치지 않음)"]
    for sec in (flow, fx, oil):
        o = sec["stored_overlap"]
        if not o:
            lines.append(f"- {sec['label']}: 저장본 없음")
            continue
        compared = o.get("compared_pairs", o.get("compared"))
        unit = "쌍" if "compared_pairs" in o else "날"
        lines.append(
            f"- {sec['label']}: 값 대조 {compared}{unit} · 같음 {o['equal']} · 다름 "
            f"{o['different']['count']}(최대 차이 {o['max_abs_diff']}) · 새 자료에만 "
            f"{o['only_new']['count']}날 · 저장본에만 {o['only_stored']['count']}날"
        )
    lines += ["", "## 표본 창 ↔ 장기 창(같은 날짜 값 대조 · 같은 날짜 봉이 둘인 창)"]
    for sec in (fx, oil):
        parts = [
            f"{w} 대조 {c['compared']} · 다름 {c['different']['count']}"
            for w, c in sec["sample_vs_full"].items()
        ]
        lines.append(
            f"- {sec['label']}: "
            + (" · ".join(parts) or "대조 없음(장기 창 없음)")
            + f" · 같은 날짜 봉 둘 = {sec['duplicate_windows'] or '없음'}"
        )
    lines += [
        "",
        "## 빈 날짜 · 실패",
        f"- 코스피 수급: 요청 {flow['requested']['requested_dates']}일 · 실패 "
        f"{flow['failed_dates']['count']}일 · 목표 구간 중 요청 안 함 "
        f"{flow['not_requested_in_target']['count']}일 · 코스피 저장 시작 전 미요청 "
        f"{flow['not_requested_before_kospi_start']['count']}일(결측 아님)",
    ]
    for sec in (fx, oil):
        g = sec["weekday_gaps"]
        kinds = " · ".join(f"{k} {n}개" for k, n in g["by_kind"].items()) or "없음"
        lines.append(
            f"- {sec['label']}: 정규화에 없는 요청 구간 안 평일 {g['count']}개({kinds}) · 최장 연속 "
            f"{g['longest_run']}일(평일 기준 · 기대 거래일 미확정)"
        )
    lines += ["", "## 시간 의미"]
    for sec in (flow, fx, oil):
        lines.append(f"- {sec['label']}: {sec['time_meaning']}")
    lines += [
        "",
        "## 실행",
        f"- 종료 이유: {report['end_reason']}",
        *(
            [f"- 후처리 상한 초과: {report['postprocess_error']['message']}"]
            if report.get("postprocess_error")
            else []
        ),
        f"- 요청 수: {json.dumps(report['requests'], ensure_ascii=False, sort_keys=True)}",
        f"- 봉인 판 파일 전후 같음: {report['sealed_unchanged']}",
        f"- 실행 중 운영 파일 변경 감지: {report['live_changes'] or '없음'}"
        "(감지만 · 연구 코드의 쓰기로 단정하지 않음)",
        "",
        report["not_claimed"],
        "",
    ]
    return "\n".join(lines)


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
