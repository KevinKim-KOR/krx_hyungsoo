"""POC6-04 — 실행 · 저장 · 보고서(PLAN §4 · §10 · 판정 §3 ~ §6).

순서: 입력 해시 확인 → B · C snapshot → 행 구조 확인(A 대 B · B 대 C · 행 수) → B · C 학습(POC6-02 `run_cpu`
그대로 · 재현 확인 두 번 학습 포함) → 대조군 → 표 → 새 폴더(임시 폴더에 다 쓴 뒤 이름 바꾸기).
구조 · 대조군이 어긋나면 그 사유를 담은 CHECK_REQUIRED 보고서를 쓰고 판정하지 않는다.
보조 분석은 같은 예측에서 평가 행만 거른다(재학습 0).
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.d20_expand import checks as K
from app.d20_expand import inputs as IN
from app.d20_pooled import study as S
from app.d20_pooled.snapshot import digest

SCHEMA = "poc6_04_report_v1"
RESEARCH_ROOT = IN.PROJECT_ROOT / "state" / "ml" / "research" / "poc6_04"
COMPLETED, CHECK_REQUIRED = "COMPLETED", "CHECK_REQUIRED"
_KST = timezone(timedelta(hours=9))

LIMITS = [
    "같은 시험 기간을 다시 쓰고 현재 보유 ETF 를 사후 선택한 자료다 — 기준을 충족해도 탐색적 재현 결과이며 "
    "독립 시험 · 투자 수익 검증의 성공이 아니다.",
    "A 와 B 는 같은 행이어도 정답(가격 자료)이 다르다 — 서로 다른 정답의 MAE 를 빼서 모델 개선율로 쓰지 않는다.",
    "B 대 C 의 HGB 차이는 종목 · 과거 학습 이력 · 날짜별 가중치가 함께 확대된 효과다(종목 수만의 인과효과 아님).",
    "보조 (a) 는 두 종목을 평가에서만 뺀 것이다(학습에서 뺀 실험 아님). 보조 (b) 의 'KRX 대조 범위 안'은 그 가격이 "
    "±1원 대조를 모두 통과했다는 뜻이 아니다.",
    "KRX 불일치율은 POC6-03 대조 관측 기간의 값이다 — MAE 시험 기간과 다르며 성능 원인으로 단정하지 않는다.",
    "D20 ≤ −8% 보조 진단은 미래 정답으로 고른 행의 사후 진단이다(급락 사전 탐지 성공률 아님).",
    "사본은 받은 날 기준의 사후 자료다(조정 사유 미확인 · 공식 수정주가 · 총수익 · PIT 보증 아님).",
    "운영 채택 아님(ML_OPERATION_PROMOTION=NOT_APPROVED · CURRENT_DEPLOYABLE_ML_MODEL=none)"
    " · 매수/매도 지시 아님.",
]


class SaveError(Exception):
    """연구 산출물 저장 실패."""


def _check_shapes(prep_a, prep_b, prep_c, inp, expect) -> list[str]:
    four = inp["four"]
    problems = []
    if prep_a["eligible"] != four:
        problems.append(
            f"A 공식 snapshot 의 적격 {prep_a['eligible']} ≠ A 보고서 {four}"
        )
    if prep_b["eligible"] != four:
        problems.append(f"B 적격 {prep_b['eligible']} ≠ 원래 4종 {four}")
    if len(prep_c["eligible"]) != expect["c_etfs"] or not set(four) <= set(
        prep_c["eligible"]
    ):
        problems.append(
            f"C 적격 {len(prep_c['eligible'])}종 ≠ 기대 {expect['c_etfs']}종 또는 4종 미포함"
        )
    missing = sorted(set(inp.get("monthly") or []) - set(prep_c["eligible"]))
    if missing:
        problems.append(f"보조 (a) 월 분배 종목이 C 적격에 없음 {missing}")
    for name, prep, n in (
        ("B", prep_b, expect["b_etfs"]),
        ("C", prep_c, expect["c_etfs"]),
    ):
        want = expect["dates_per_block"] * n
        for b in range(len(prep["blocks"])):
            got = len(S.block_sets(prep, b)["test"])
            if got != want:
                problems.append(f"{name} {b + 1}구간 시험 행 {got} ≠ {want}")
    if problems:
        return problems
    sa, sb, sc = (K.structure(p, four) for p in (prep_a, prep_b, prep_c))
    problems += K.compare_structure(sa, sb, four, "A 대 B")
    problems += K.compare_structure(sb, sc, four, "B 대 C")
    problems += K.compare_values(prep_b, prep_c, four)
    return problems


def run(
    manifest: dict[str, Any] = IN.MANIFEST, root: Path = IN.PROJECT_ROOT
) -> tuple[Path, dict[str, Any]]:
    inp = IN.load_inputs(manifest, root)
    b_snap, c_snap = IN.build_snapshots(inp)
    expect = manifest["expect"]
    inp["monthly"] = list(manifest["monthly"])
    try:
        prep_a = S.prepare(inp["official"])
        prep_b, prep_c = S.prepare(b_snap), S.prepare(c_snap)
    except S.StudyError as e:  # 입력 손상 · 계약 위반 = CHECK_REQUIRED(실행 실패 아님)
        raise IN.InputError(f"snapshot 준비 실패: {e}") from e
    created = datetime.now(_KST)
    head = {
        "schema": SCHEMA,
        "run_id": f"{created.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "created_at": created.isoformat(timespec="seconds"),
        "inputs": inp["files"],
        "official_digest": inp["official_digest"],
        "snapshots": {
            "B": {
                "digest": digest(b_snap),
                "parents": ["official_snapshot", "copy_db"],
            },
            "C": {
                "digest": digest(c_snap),
                "parents": ["official_snapshot", "copy_db"],
            },
        },
        "four": inp["four"],
        "c_etfs": prep_c["eligible"],
        "recipe_digest": inp["a_report"]["recipe_digest"],
        "environment": inp["environment"],
        "environment_same_as_A": True,  # 다르면 load_inputs 가 CHECK_REQUIRED 로 멈춤
        "rules": {
            "control_tolerance": K.CONTROL_TOL,
            "truth_diff_threshold": K.TRUTH_DIFF,
            "monthly_excluded_in_aux_a": manifest["monthly"],
            "krx_end_for_aux_b": manifest["krx_end"],
            "labels": [K.LABEL_MET, K.LABEL_NOT_MET],
        },
        "limits": LIMITS,
    }
    problems = _check_shapes(prep_a, prep_b, prep_c, inp, expect)
    if problems:
        report = {
            **head,
            "status": CHECK_REQUIRED,
            "reason": "행 구조 불일치",
            "problems": problems,
        }
        return _write(report, inp, b_snap, c_snap), report
    cpu_b, cpu_c = S.run_cpu(b_snap), S.run_cpu(c_snap)
    for name, cpu in (("B", cpu_b), ("C", cpu_c)):
        if cpu["status"] != S.COMPLETED:
            report = {
                **head,
                "status": CHECK_REQUIRED,
                "reason": f"{name} CPU 단계 {cpu['status']} {cpu.get('reason') or ''}".strip(),
            }
            return _write(report, inp, b_snap, c_snap), report
    four = set(inp["four"])
    rows_a = inp["a_report"]["rows_by_block"]
    rows_b, rows_c = cpu_b["rows_by_block"], cpu_c["rows_by_block"]
    rows_c4 = K.only(rows_c, lambda r: r["ticker"] in four)
    id_problems = []
    if K.ids(rows_a) != K.ids(rows_b):
        id_problems.append("A 대 B 시험 행 ID 다름")
    if K.ids(rows_b) != K.ids(rows_c4):
        id_problems.append("B 대 C(4종) 시험 행 ID 다름")
    ctrl = None if id_problems else K.control(rows_b, rows_c4)
    if id_problems or not ctrl["ok"]:
        report = {
            **head,
            "status": CHECK_REQUIRED,
            "reason": (
                "시험 행 ID 불일치"
                if id_problems
                else "대조군(MEDIAN · RIDGE) 허용 오차 초과"
            ),
            "problems": id_problems,
            "control": ctrl,
        }
        return _write(report, inp, b_snap, c_snap), report
    report = {
        **head,
        "status": COMPLETED,
        "control": ctrl,
        **_tables(inp, manifest, prep_c, rows_a, rows_b, rows_c, rows_c4, cpu_b, cpu_c),
    }
    return _write(report, inp, b_snap, c_snap), report


def _tables(
    inp, manifest, prep_c, rows_a, rows_b, rows_c, rows_c4, cpu_b, cpu_c
) -> dict[str, Any]:
    monthly = set(manifest["monthly"])
    sc_a, sc_b, sc_c4, sc_c = (K.scores(x) for x in (rows_a, rows_b, rows_c4, rows_c))
    main = K.verdict(sc_c)
    ends = K.window_end(prep_c)
    last_block = len(rows_c) - 1

    def in_krx(r, k):
        return k != last_block or ends[r["date"]] <= manifest["krx_end"]

    def krx_only(rows):
        return [[r for r in blk if in_krx(r, k)] for k, blk in enumerate(rows)]

    rows_c10 = K.only(rows_c, lambda r: r["ticker"] not in monthly)
    b_in, c_in, c4_in = krx_only(rows_b), krx_only(rows_c), krx_only(rows_c4)
    sc_c10 = K.scores(rows_c10)
    aux_b = {
        "B": K.scores([b_in[last_block]]),
        "C": K.scores([c_in[last_block]]),
        "C_on_4": K.scores([c4_in[last_block]]),
        "rows_dates": {
            "B": K.per_block_dates([b_in[last_block]])[0],
            "C": K.per_block_dates([c_in[last_block]])[0],
            "removed_B": len(rows_b[last_block]) - len(b_in[last_block]),
            "removed_C": len(rows_c[last_block]) - len(c_in[last_block]),
        },
    }
    dirs = {
        "main_overall": K.direction(sc_c),
        "main_block3": K.direction(sc_c, block=last_block),
        "aux_a_overall": K.direction(sc_c10),
        "aux_b_block3": K.direction(aux_b["C"]),
    }
    pairs = (
        ("보조 (a) 전체", "aux_a_overall", "주 분석 전체", "main_overall"),
        (
            "보조 (b) 3구간(목표 창 KRX 범위 안)",
            "aux_b_block3",
            "주 분석 3구간(거르기 전)",
            "main_block3",
        ),
    )
    notes = [
        f"{an} 방향(HGB 가 두 기준보다 작음 = {dirs[ak]})이 {mn}({dirs[mk]})과 다름"
        for an, ak, mn, mk in pairs
        if dirs[ak] is not None and dirs[mk] is not None and dirs[ak] != dirs[mk]
    ]
    cprep = cpu_c["prep"]
    return {
        "common4": {
            "A": sc_a,
            "B": sc_b,
            "C_on_4": sc_c4,
            "truth_diff_A_vs_B": K.truth_diff(rows_a, rows_b),
            "rows_dates": K.per_block_dates(rows_b),
            "note": "A 와 B · C 는 정답이 달라 MAE 를 빼지 않는다 · B 대 C 는 같은 정답",
        },
        "c12": {
            "scores": sc_c,
            "verdict": main,
            "per_etf": K.per_etf(rows_c, prep_c["eligible"]),
            "diagnostics": S.diagnostics(rows_c, S.CPU_METHODS),
            "rows_dates": K.per_block_dates(rows_c),
            "blocks": cpu_c["blocks"],
            "repro_cpu_identical": cpu_c["repro_cpu_identical"],
        },
        "b_blocks": cpu_b["blocks"],
        "b_repro_cpu_identical": cpu_b["repro_cpu_identical"],
        "aux_a": {
            "name": "12종 학습 · 10종 평가",
            "scores": sc_c10,
            "rows_dates": K.per_block_dates(rows_c10),
        },
        "aux_b": {"name": "목표 창이 KRX 대조 범위 안인 행(3구간)", **aux_b},
        "directions": dirs,
        "direction_notes": notes,
        "uncertainty": {
            "krx_rates": K.krx_rates(inp["basis"], prep_c["eligible"]),
            "monthly_unconfirmed": sorted(monthly),
            "block3_rows_after_krx_end": aux_b["rows_dates"],
            "train_rows_by_etf": {
                t: [pb["train_n"] for pb in cprep["etfs"][t]["blocks"]]
                for t in prep_c["eligible"]
            },
        },
    }


def _write(report: dict[str, Any], inp: dict[str, Any], b_snap, c_snap) -> Path:
    from app.d20_expand.render import render_md

    root = Path(RESEARCH_ROOT)
    name = report["run_id"]
    folder, staging = root / name, root / f".{name}.partial"
    made = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        staging.mkdir(exist_ok=False)
        made = True
        # A 고정 사본(판정 §6) = 해시를 확인하고 읽은 바이트 그대로
        (staging / "a_report_frozen.json").write_bytes(inp["a_report_bytes"])
        if (
            IN.sha256_file(staging / "a_report_frozen.json")
            != inp["files"]["a_report"]["sha256"]
        ):
            raise OSError("A 고정 사본 해시 다름")
        for fname, body in (
            (
                "manifest.json",
                {
                    k: report[k]
                    for k in (
                        "inputs",
                        "official_digest",
                        "snapshots",
                        "four",
                        "recipe_digest",
                    )
                },
            ),
            ("b_snapshot.json", b_snap),
            ("c_snapshot.json", c_snap),
            ("report.json", report),
        ):
            (staging / fname).write_text(
                json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
        (staging / "report.md").write_text(render_md(report), encoding="utf-8")
        os.rename(staging, folder)
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 반쪽 폴더를 남기지 않음
        if made:
            shutil.rmtree(staging, ignore_errors=True)
        if isinstance(e, OSError):
            raise SaveError(f"연구 산출물 저장 실패: {type(e).__name__}: {e}") from e
        raise
    return folder
