"""POC7-02 비교표 · AC4 판정(PLAN §3-3 · §3-5 · 판정 Q4 · §3) — 회수한 본 요약 기록 + 사용 기록 · 채점에서 계산만.

```text
판정 불가     본 요약 시도가 없음 · 둘 이상(설계자 판단) · 기록 미완(해시로 검증 못 함) · 한 장 없음
              · '완료'가 아님(기술 실패 · 입력 미확인) · 채점 없음
품질 미달     최초 한 장의 중요한 오류 ≥ 1(본 요약이 있을 때)
관찰          중요한 오류 0 · L 세 답 틀림 0 · 각 답 L ≥ U(맞음 > 부분 > 틀림) · 형수님 직접 시간 L < U
              · 총 사람 시간(직접 + 개발자 반복) L < U · 사실 수정 L ≤ U · 다시 쓰겠음 = 예
미확인        정확성은 충족했지만 위 조건이 하나라도 아님 · 실측이 빠짐(빠진 항목은 '판정 불가(항목)'로 적음)
```
모르는 값 = 없음 · null = '미측정'(추정하지 않음). 잘못된 값(음수 · 글자 · 참/거짓 · 무한대 · NaN · 하루를 넘는 초
· 0초 직접 시간 · 직접 시간 > 전체 경과 · 실행기 기록보다 짧은 L 전체 경과 · 잘못 적은 답 · 수정 · 재사용 · 객체가 아닌
채점 · 사용 기록)은 ValueError(검증자 r2 F8). 채점 전에 메모 잠금을 다시 확인한다(출력 뒤 고침 거부).
채점(score)은 회수한 그 한 장의 해시(`one_page_sha256`)를 적어야 한다. 개발자 반복 시간(L)의 최소값은 그 사례의
모든 pack · merge 명령 기록(ms) 합이다(직접 잰 값이 더 작으면 오류 · 없으면 그 합 · 출처 표시). 평소 방식(U) = 0 고정.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Optional

from app.entry_timing.protocol import CheckRequired
from app.review_summary.bundle import bundles_of, merged_runs, read_bundle
from app.review_summary.case import check_lock

GRADES = {"맞음": 2, "부분": 1, "틀림": 0}
QUESTIONS = (("direction", "방향"), ("limits", "근거의 한계"), ("next", "다음 확인"))
REUSE = ("예", "아니오", "모르겠음")
NA = "미측정"
SIDE_KEYS = ("user_s", "dev_s", "elapsed_s")
MAX_SECONDS = 86400  # 한 사례 측정 = 하루 안(잠정 상한 · 설계자 확인 항목 · 검토 '실측일 수 없는 큰 값')


def secs(side: Mapping[str, Any], key: str) -> Optional[float]:
    """초 값 — 없음 · null = None(미측정) · 0 이상 숫자만 · 그 밖은 ValueError(잘못 적은 값을 미측정으로 숨기지 않음)."""
    v = side.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{key} 는 0 이상 초(숫자)여야 함: {v!r}")
    try:
        f = float(v)
    except OverflowError:
        raise ValueError(f"{key} 는 잴 수 있는 초여야 함(너무 큼)") from None
    if not math.isfinite(f) or f < 0:  # NaN · 무한대는 실측이 아니다(검증자 r2 F8)
        raise ValueError(f"{key} 는 0 이상 유한한 초여야 함: {v!r}")
    if f > MAX_SECONDS:
        raise ValueError(
            f"{key} 는 하루({MAX_SECONDS}초) 이하여야 함(잠정 상한): {v!r}"
        )
    return f


def _count(v: Any, key: str) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError(f"{key} 는 0 이상 정수여야 함: {v!r}")
    return v


def _u(usage: Mapping[str, Any]) -> dict[str, Any]:
    """평소 방식 — 개발자 반복 시간은 계약상 0 으로 고정(PLAN §3-3 · 검증자 r1 F4) · 다른 값은 오류."""
    u = dict(_side(usage, "U"))
    if u.get("dev_s") is not None and secs(u, "dev_s") != 0:
        raise ValueError(
            f"평소 방식의 개발자 반복 시간은 0 으로 고정(PLAN §3-3): {u.get('dev_s')!r}"
        )
    u["dev_s"] = 0
    return u


def _side(usage: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """사용 기록 한쪽(L · U) — 없으면 빈 기록 · 객체가 아니면 ValueError."""
    v = usage.get(key)
    if v is None:
        return {}
    if not isinstance(v, Mapping):
        raise ValueError(f"사용 기록 {key} 는 JSON 객체여야 함: {type(v).__name__}")
    return v


def _inputs(score: Any, usage: Any) -> None:
    for name, v in (("채점", score), ("사용 기록", usage)):
        if not isinstance(v, Mapping):
            raise ValueError(f"{name}은 JSON 객체여야 함: {type(v).__name__}")


def _fixes(side: Mapping[str, Any], key: str) -> Optional[int]:
    v = side.get("fixes")
    if v is None:
        return None
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"{key}.fixes 는 고친 내용(글) 목록이어야 함: {v!r}")
    return len(v)


def _reuse(side: Mapping[str, Any]) -> Optional[str]:
    v = side.get("reuse")
    if v is None:
        return None
    if v not in REUSE:
        raise ValueError(f"reuse 는 {' · '.join(REUSE)} 중 하나여야 함: {v!r}")
    return v


def check_side(side: Mapping[str, Any], key: str) -> None:
    """한쪽 사용 기록의 꼴 — 답 · 수정 · 재사용 · 초(직접 시간 > 0 · 직접 시간 ≤ 전체 경과) · 틀리면 ValueError."""
    a = side.get("answers")
    if a is not None:
        if not isinstance(a, Mapping):
            raise ValueError(f"{key}.answers 는 JSON 객체여야 함: {a!r}")
        for k, v in a.items():
            if v is not None and (not isinstance(v, str) or v not in GRADES):
                raise ValueError(
                    f"{key}.answers.{k} 는 맞음 · 부분 · 틀림 중 하나: {v!r}"
                )
    _fixes(side, key)
    if key == "L":
        _reuse(side)
    _count(side.get("reopen"), f"{key}.reopen")
    user, wall = secs(side, "user_s"), secs(side, "elapsed_s")
    secs(side, "dev_s")
    for name, v in (("user_s", user), ("elapsed_s", wall)):
        if v is not None and v <= 0:
            raise ValueError(f"{key}.{name} 는 0초보다 커야 함(실제 조작 · 경과)")
    if user is not None and wall is not None and user > wall:
        raise ValueError(f"{key} 직접 시간 {user}초 > 전체 경과 {wall}초")


def total_human(side: Mapping[str, Any]) -> Optional[float]:
    u, d = secs(side, "user_s"), secs(side, "dev_s")
    return None if u is None or d is None else u + d


def _grades(side: Mapping[str, Any]) -> Optional[dict[str, int]]:
    a = side.get("answers") or {}
    got = {k: GRADES.get(a.get(k)) for k, _ in QUESTIONS}
    return None if any(v is None for v in got.values()) else got  # type: ignore[return-value]


def ac4(
    score: Mapping[str, Any], usage: Mapping[str, Any], run: Optional[Mapping[str, Any]]
) -> dict[str, Any]:
    """{verdict, reasons, missing}. run = 회수한 본 요약 기록(merge.json) 또는 None."""
    L, U = _side(usage, "L"), _u(usage)
    # 입력 꼴은 실행 상태와 상관없이 늘 본다(잘못 적은 값을 판정 불가 뒤에 숨기지 않음)
    check_side(L, "L")
    check_side(U, "U")
    if run is None:
        return {
            "verdict": "판정 불가",
            "reasons": ["본 요약이 보관되지 않음(실행)"],
            "missing": ["run"],
        }
    crit = _count(score.get("critical_errors"), "critical_errors")
    if crit is None:
        return {
            "verdict": "판정 불가",
            "reasons": ["최초 한 장 채점 없음"],
            "missing": ["critical_errors"],
        }
    if crit > 0:
        return {
            "verdict": "품질 미달",
            "reasons": [f"최초 한 장의 중요한 오류 {crit}건"],
            "missing": [],
        }
    # 응답 구분과 실행 상태가 둘 다 완료여야 한다(중단 · 실행기 오류로 끝난 실행 제외 · 검증자 r3 F11)
    if run.get("main_status") != "COMPLETED" or run.get("status") != "COMPLETED":
        why = f"본 요약이 완료가 아님(응답 {run.get('main_status')} · 실행 {run.get('status')})"
        return {"verdict": "판정 불가", "reasons": [why], "missing": ["run"]}
    need: dict[str, Any] = {
        "L.user_s": secs(L, "user_s"),
        "U.user_s": secs(U, "user_s"),
        "L.dev_s": secs(L, "dev_s"),
        "U.dev_s": secs(U, "dev_s"),
        "L.fixes": _fixes(L, "L"),
        "U.fixes": _fixes(U, "U"),
        "L.answers": _grades(L),
        "U.answers": _grades(U),
        "L.reuse": _reuse(L),
    }
    missing = [k for k, v in need.items() if v is None]
    no = []
    gl, gu = need["L.answers"], need["U.answers"]
    if gl is not None and 0 in gl.values():
        no.append("L 세 답에 '틀림'이 있음")
    if gl is not None and gu is not None:
        no += [
            f"L 의 '{lab}' 답이 U 보다 낮음" for k, lab in QUESTIONS if gl[k] < gu[k]
        ]
    if (
        None not in (need["L.user_s"], need["U.user_s"])
        and not need["L.user_s"] < need["U.user_s"]
    ):
        no.append("형수님 직접 시간이 줄지 않음")
    tl, tu = total_human(L), total_human(U)
    if None not in (tl, tu) and not tl < tu:  # type: ignore[operator]
        no.append("총 사람 시간(직접 + 개발자 반복)이 줄지 않음")
    if (
        None not in (need["L.fixes"], need["U.fixes"])
        and need["L.fixes"] > need["U.fixes"]
    ):
        no.append("사실 수정이 늘었음")
    if need["L.reuse"] is not None and need["L.reuse"] != "예":
        no.append("다시 쓰겠다고 하지 않음")
    if missing:
        no.append("사용 실측이 빠짐(빠진 항목 = 판정 불가)")
    if no:
        return {"verdict": "사용 이점 미확인", "reasons": no, "missing": missing}
    return {
        "verdict": "사용 이점 관찰",
        "reasons": ["이 사례 한 건의 관찰"],
        "missing": [],
    }


def _s(v: Optional[float]) -> str:
    """분 · 초(소수 한 자리 — 판정에 쓴 차이가 표에서 같은 값으로 보이지 않게)."""
    if v is None:
        return NA
    m, sec = divmod(round(v, 1), 60)
    return f"{int(m)}분 {sec:.1f}초"


def table_md(
    score: Mapping[str, Any],
    usage: Mapping[str, Any],
    run: Optional[Mapping[str, Any]],
    answers: bool,
    dev_source: str = "직접 잰 값",
) -> str:
    """형수님께 드릴 한 표(PLAN §3-3) + 실행 줄 + AC4 판정 줄."""
    L, U = _side(usage, "L"), _u(usage)

    def fixes(side: Mapping[str, Any]) -> str:
        f = side.get("fixes")
        if not isinstance(f, list):
            return NA
        return f"{len(f)}건" + (" — " + " / ".join(str(x) for x in f) if f else "")

    def grades(side: Mapping[str, Any]) -> str:
        a = side.get("answers") or {}
        return " · ".join(f"{lab} {a.get(k) or NA}" for k, lab in QUESTIONS)

    def cnt(side: Mapping[str, Any]) -> str:
        v = _count(side.get("reopen"), "reopen")
        return NA if v is None else f"{v}회"

    crit = _count(score.get("critical_errors"), "critical_errors")
    main = (run or {}).get("checks", {}).get("main") or {}
    checked = " · ".join(main.get("input") or []) or "입력 대조 모두 맞음"
    gpu = (main.get("gpu") or {}).get("status", NA)
    rows = [
        (
            "본 요약 실행",
            (run or {}).get("main_status") or (run or {}).get("status") or "보관 안 됨",
            "—",
        ),
        ("입력 확인 · GPU", f"{checked} · GPU {gpu}" if run else NA, "—"),
        ("형수님 직접 시간", _s(secs(L, "user_s")), _s(secs(U, "user_s"))),
        (
            f"개발자 반복 작업 시간({dev_source})",
            _s(secs(L, "dev_s")),
            "0초(계약 고정)",
        ),
        ("총 사람 시간", _s(total_human(L)), _s(total_human(U))),
        (
            "전체 경과(모델 대기 포함)",
            _s(secs(L, "elapsed_s")),
            _s(secs(U, "elapsed_s")),
        ),
        ("다시 열기", cnt(L), cnt(U)),
        ("사실 수정 · 고친 내용", fixes(L), fixes(U)),
        ("세 답 정확도", grades(L), grades(U)),
        ("다시 쓰겠는가", L.get("reuse") or NA, "—"),
        ("한 장 최초 출력 중요한 오류", NA if crit is None else f"{crit}건", "—"),
        ("AI 답", "있음" if answers else "없음 — 긴 AI 답 대조의 효용 미측정", "같음"),
    ]
    out = ["| 항목 | 로컬 한 장(L · 먼저) | 평소 방식(U · 다음) |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    v = ac4(score, usage, run)
    out += ["", f"AC4 판정: **{v['verdict']}** — " + " · ".join(v["reasons"])]
    if v["missing"]:
        out.append("판정 불가(항목): " + " · ".join(v["missing"]))
    return "\n".join(out) + "\n"


def _other_models(runs: list[dict[str, Any]], run: Mapping[str, Any]) -> list[str]:
    """시도와 같은 묶음에서 합성 점검 이상 간 실행 가운데 모델 digest 가 다른 것(회수 순서와 상관없이)."""
    mine = run.get("model_digest")
    out = []
    for r in runs:
        reached = r.get("main_started") or r.get("trial_categories") is not None
        if (
            r is not run
            and r.get("bundle_id") == run.get("bundle_id")
            and reached
            and r.get("model_digest")
            and mine
            and r.get("model_digest") != mine
        ):
            out.append(str(r.get("run_id")))
    return out


def build(
    root: Path,
    case_id: str,
    score: Mapping[str, Any],
    usage: Mapping[str, Any],
    answers: bool,
) -> tuple[str, dict[str, Any]]:
    """회수한 본 요약 시도(한 사례에 하나)를 찾아 채점 해시를 대조하고 표 · 판정을 만든다.

    시도가 둘 이상이면(같은 묶음을 두 번 풀기 등 규칙 밖) 판정하지 않는다 — 어느 것을 쓸지는 설계자 판단.
    채점은 그 시도의 한 장 해시(빈 값 불가)에 묶인다. 한 장이 없거나(만들기 실패 · 꺼짐) 기록 미완이면 판정 불가.
    """
    _inputs(score, usage)
    # 잘못 적은 입력은 판정 불가로 일찍 끝나는 경우에도 오류(검토 G)
    check_side(_side(usage, "L"), "L")
    check_side(_u(usage), "U")
    _count(score.get("critical_errors"), "critical_errors")
    # 채점 전 메모 잠금 다시 확인(출력 뒤 고침 거부 · PLAN §1-3)
    for b in bundles_of(root, case_id):
        check_lock(root, case_id, read_bundle(root, case_id, b)["input"])
    runs = merged_runs(root, case_id)
    attempts = [r for r in runs if r.get("main_started")]
    if len(attempts) > 1:
        names = " · ".join(
            f"{r.get('run_id')}(시작 {r.get('started_at')})" for r in attempts
        )
        v = {
            "verdict": "판정 불가",
            "reasons": [f"본 요약 시도 {len(attempts)}건 — 설계자 판단: {names}"],
            "missing": ["run"],
        }
        return f"AC4 판정: **판정 불가** — {v['reasons'][0]}\n", v
    run = attempts[0] if attempts else None
    odd = _other_models(runs, run) if run is not None else []
    # 같은 묶음 앞 실행과 다른 모델로 돈 시도 — 모델 교체는 설계자 판단(판정 Q3)
    if odd:
        v = {
            "verdict": "판정 불가",
            "reasons": [
                f"같은 묶음 앞 실행과 모델 digest 가 다름({', '.join(odd)}) — 설계자 판단"
            ],
            "missing": ["run"],
        }
        return f"AC4 판정: **판정 불가** — {v['reasons'][0]}\n", v
    if run is not None and run.get("status") == "INCOMPLETE_RECORD":
        v = {
            "verdict": "판정 불가",
            "reasons": [
                "본 요약 기록이 다 쓰이지 않음(해시로 검증하지 못함) — 설계자 판단"
            ],
            "missing": ["run"],
        }
        return f"AC4 판정: **판정 불가** — {v['reasons'][0]}\n", v
    if run is not None:
        sha = run.get("one_page_sha256")
        if not sha:
            v = {
                "verdict": "판정 불가",
                "reasons": ["본 요약의 한 장이 없음(만들기 실패 · 꺼짐)"],
                "missing": ["one_page"],
            }
            return f"AC4 판정: **판정 불가** — {v['reasons'][0]}\n", v
        if score.get("one_page_sha256") != sha:
            raise CheckRequired("채점이 회수한 한 장(one_page_sha256)과 이어지지 않음")
    usage = {k: dict(_side(usage, k)) for k in ("L", "U")}
    source = "직접 잰 값"
    # 전체 경과는 실행기 기록과 대조(PLAN §3-3) — 실행기의 단조 시계 실행 시간(벽시계 맞춤과 상관없음 · 검토 H)
    if run is not None:
        took = run.get("run_wall_s")
        wall = secs(usage["L"], "elapsed_s")
        ok_took = isinstance(took, (int, float)) and not isinstance(took, bool)
        if ok_took and wall is not None and wall < took:
            raise ValueError(f"L 전체 경과 {wall}초 < 실행기 기록 {took}초")
    L = usage.setdefault("L", {})
    # 사례의 모든 포장 · 회수(멈춤 뒤 새 묶음 포함 · PLAN §3-3 '매회 포장 · 회수')
    if run is not None:
        bids = bundles_of(root, case_id)
        packs = [read_bundle(root, case_id, b)["pack"] for b in bids]
        # 기록 미완 뒤 완전한 회수도 각각 한 번
        every = merged_runs(root, case_id, every=True)
        ms = sum(int(p.get("dev_ms") or 0) for p in packs)
        floor = (ms + sum(int(r.get("dev_ms") or 0) for r in every)) / 1000
        given = secs(L, "dev_s")
        if given is None:
            L["dev_s"] = floor
            source = f"명령 기록 pack {len(packs)}회 · merge {len(every)}회"
        elif given < floor:
            raise ValueError(
                f"로컬 방식의 개발자 반복 시간 {given}초 < 명령 기록 {floor}초"
            )
    return table_md(score, usage, run, answers, source), ac4(score, usage, run)
