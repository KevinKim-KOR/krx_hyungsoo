"""POC6-02 — 결과 폴더 · RTX PC 실행 묶음 · 보고서(설계 개정 2 §8 · PLAN 판정 §3).

```text
폴더    state/ml/research/poc6_02/<KST시각>_<id>/ — 임시 폴더에 다 쓴 뒤 이름 바꾸기(반쪽 폴더 없음 · 06 방식)
          report.md · report.json · input_snapshot.json
          gpu_bundle/(mlp.py · gpu_runner.py · gpu_input.json ·
          run_gpu.bat · README_KO.txt) · gpu_bundle.zip
취합    GPU OK      → gpu_merged/report_with_gpu.md · .json(네 방법 · 한 번만 · 있으면 거절)
        GPU OK 아님 → gpu_attempts/<시각>_<상태>_<id>/report_with_gpu.md · .json
                      (부분 완료 기록 · 뒤의 OK 취합을 막지 않음)
        둘 다 임시 폴더에 다 쓴 뒤 이름 바꾸기 · CPU 보고서는 덮지 않음
```
쓰기 실패는 실패로 끝난다(정상 완료로 보이지 않음). 개인 값 · 비밀값은 어떤 파일에도 없다.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.d20_pooled import study as S

RESEARCH_ROOT = Path(
    "state/ml/research/poc6_02"
)  # 호출 때 읽는다(시험이 tmp 로 바꾼다)
HERE = Path(__file__).resolve().parent
SCHEMA = "poc6_02_report_v1"

GPU_STATUSES = (
    "OK",
    S.GPU_NOT_RUN,
    S.CHECK_REQUIRED,
    S.RUN_FAILED,
)  # gpu_runner 가 쓰는 상태만
CODE_FILES = (
    "mlp.py",
    "gpu_runner.py",
)  # RTX PC 에서 실행되는 코드(묶음 입력에 해시를 넣어 대조)


def code_sha256(folder: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in CODE_FILES:
        try:
            out[name] = hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest()
        except OSError:
            out[name] = None
    return out


LIMITS = [
    "현재 보유 목록에 한정한 회고 연구다 — 상장폐지 · 과거 비보유 ETF 를 포함한 시장 전체 성과나 PIT 모집단이 아니다.",
    "결과 범위는 적격 ETF(최소 4종 · 설계자 판정)에 한정한다 — 시장 전체 · 보유 ETF {etf}종의 개선 입증으로 넓히지 않는다. "
    "시험 행은 겹치는 20거래일 목표라 행 수만큼의 독립 사례가 아니다.",
    "가격 = 저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정) · 사후 수정 가능 — 시간 분리는 지키지만 "
    "진정한 당시 가용 자료 검증이 아니다.",
    "가격 경계는 06 판정 그대로다(연결 · change 수정 · 재수집 없음). 경계의 원인 추정(수집 묶음 간 수정주가 기준 차이 · "
    "분배금 조정 가능성)은 확인된 사실이 아니다.",
    "이미 조사한 역사 구간이다 — 신규 독립 확증 시험이 아니다. 유의확률 · 적중률 · 승률은 만들지 않는다.",
    "연구 유망 ≠ 투자 유효성 · 운영 채택(ML_OPERATION_PROMOTION=NOT_APPROVED · "
    "CURRENT_DEPLOYABLE_ML_MODEL=none · Q6 OPEN).",
    "이 값은 매수/매도 지시가 아니다.",
]
BREAK_CAUSE_NOTE = (
    "원인 추정(사실 아님): 같은 날 여러 ETF 의 FinanceDataReader change 가 저장 종가 비율과 다른 자리는 수집 묶음이 "
    "이어진 곳이며(앞뒤 행의 수집 시각이 다름), 나중 수집의 수정주가 기준(분배금 조정)이 달랐을 가능성이 있다."
)


def limits_for(snap: dict[str, Any]) -> list[str]:
    """한계 문구 — 보유 ETF 수는 이번 snapshot 값(고정 숫자 없음)."""
    return [x.format(etf=snap["holdings"]["etf"]) for x in LIMITS]


def completion_of(stage: str, status: Any, gpu_status: Any = None) -> str:
    """전체 완료 여부(설계 §5-1 · 판정 §5-4) — GPU 미실행 · 실패는 부분 완료로 드러낸다."""
    if stage == "SMOKE" or status != S.COMPLETED:
        return str(status)
    if stage == "CPU":
        return "CPU_PARTIAL_GPU_PENDING"
    if gpu_status == "OK":
        return "FULL"
    return "PARTIAL_" + (
        S.GPU_NOT_RUN if gpu_status == S.GPU_NOT_RUN else f"GPU_{gpu_status}"
    )


def public_etf_info(prep: dict[str, Any]) -> dict[str, Any]:
    return {
        t: {k: v for k, v in e.items() if not k.startswith("_")}
        for t, e in prep["etfs"].items()
    }


def break_summary(prep: dict[str, Any]) -> list[dict[str, Any]]:
    """경계 검출 사실을 (날짜, 종류)로 모은다 — ETF 수 · ticker · 앞뒤 수집 시각 날짜."""
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for t, e in prep["etfs"].items():
        for b in e["breaks"]:
            k = (b["date"], b["kind"])
            g = acc.setdefault(
                k,
                {"date": b["date"], "kind": b["kind"], "tickers": [], "fetched": set()},
            )
            g["tickers"].append(t)
            g["fetched"].add(
                (str(b["prev_fetched_at"] or "")[:10], str(b["fetched_at"] or "")[:10])
            )
    out = []
    for k in sorted(acc):
        g = acc[k]
        out.append(
            {
                "date": g["date"],
                "kind": g["kind"],
                "kind_text": S.prices.REASON_TEXT.get(g["kind"], g["kind"]),
                "etfs": len(g["tickers"]),
                "tickers": sorted(g["tickers"]),
                "fetched_before_after": sorted(g["fetched"]),
            }
        )
    return out


def build_report(
    *,
    study_id: str,
    created_at: str,
    snap: dict[str, Any],
    cpu: dict[str, Any],
    input_digest: str,
    recipe_digest: str,
    environment: dict[str, Any],
    resources: dict[str, Any],
    smoke: bool,
) -> dict[str, Any]:
    prep = cpu["prep"]
    etf_info = public_etf_info(prep)
    report = {
        "schema": SCHEMA,
        "study_id": study_id,
        "created_at": created_at,
        "stage": "SMOKE" if smoke else "CPU",
        "status": cpu["status"],
        "completion": completion_of("SMOKE" if smoke else "CPU", cpu["status"]),
        "reason": cpu.get("reason"),
        "T": prep["T"],
        "holdings": snap["holdings"],
        "eligibility": {
            "min_etfs": S.MIN_ETFS,
            "min_etfs_original": S.MIN_ETFS_ORIGINAL,
            "min_etfs_change": S.RECIPE["eligibility"]["min_etfs_change"],
            "eligible": [
                {"ticker": t, "name": etf_info[t]["name"]} for t in prep["eligible"]
            ],
            "excluded": [
                {"ticker": t, "name": e["name"], "reasons": e["ineligible_reasons"]}
                for t, e in etf_info.items()
                if not e["eligible"]
            ],
            "etfs": etf_info,
        },
        "price_breaks": break_summary(prep),
        "price_break_cause_note": BREAK_CAUSE_NOTE,
        "blocks": cpu.get("blocks", []),
        "repro_cpu_identical": cpu.get("repro_cpu_identical"),
        "limits": limits_for(snap),
        "recipe": S.RECIPE,
        "recipe_resolved": {"hgb_get_params": S.hgb_resolved_params()},
        "recipe_digest": recipe_digest,
        "input_digest": input_digest,
        "environment": environment,
        "resources": resources,
        "gpu": {"status": S.GPU_NOT_RUN, "reason": "RTX PC 실행 결과 취합 전"},
    }
    if cpu["status"] == S.COMPLETED:
        report.update(
            scores=cpu["scores"],
            candidates=cpu["candidates"],
            diagnostics=cpu["diagnostics"],
            rows_by_block=cpu["rows_by_block"],
        )
    elif cpu["status"] == "SMOKE":
        report["smoke_rows"] = sum(b["test_rows"] for b in cpu["blocks"])
    return report


def merge_report(report: dict[str, Any], gpu: dict[str, Any]) -> dict[str, Any]:
    """CPU 보고서 + RTX 결과 → 네 방법 보고서(같은 행 · 같은 정답). 대조 실패는 ValueError."""
    if gpu.get("status") not in GPU_STATUSES:
        raise ValueError(f"알 수 없는 GPU 상태 {gpu.get('status')!r}")
    out = {
        **report,
        "stage": "MERGED",
        "completion": completion_of("MERGED", report["status"], gpu.get("status")),
    }
    gpu_view = {k: v for k, v in gpu.items() if k not in ("blocks", "traceback")}
    gpu_view["traceback_tail"] = (gpu.get("traceback") or "")[-800:] or None
    out["gpu"] = gpu_view
    if gpu.get("status") != "OK":
        status = (
            S.GPU_NOT_RUN if gpu.get("status") == S.GPU_NOT_RUN else gpu.get("status")
        )
        out["candidates"] = {
            **report["candidates"],
            S.GPU_MLP: {"verdict": status, "reason": gpu.get("reason")},
        }
        return out
    rows = S.merge_gpu(report["rows_by_block"], gpu["blocks"])
    methods = (*S.CPU_METHODS, S.GPU_MLP)
    scores = {m: S.method_scores(rows, m) for m in methods}
    out.update(
        rows_by_block=rows,
        scores=scores,
        candidates={
            S.HGB: S.verdict_for(scores, S.HGB),
            S.GPU_MLP: S.verdict_for(scores, S.GPU_MLP),
        },
        diagnostics=S.diagnostics(rows, methods),
    )
    return out


# ── 보고서 글 ──────────────────────────────────────────────────────────────────


def _pp(v: Any) -> str:
    return "—" if v is None else f"{v:.4f}"


def render_md(r: dict[str, Any]) -> str:
    L = [
        f"# POC6-02 ETF D20 공동 학습 비교 — {r['stage']}",
        "",
        f"- study_id `{r['study_id']}` · 생성 {r['created_at']} · 기준일 T {r['T']}"
        f" · 상태 **{r['status']}** · 완료 범위 **{r.get('completion')}**"
        + (f" · 사유 {r['reason']}" if r.get("reason") else ""),
        f"- 입력 digest `{r['input_digest']}` · recipe digest `{r['recipe_digest']}`",
        f"- 보유: 행 {r['holdings']['rows']} · ticker {r['holdings']['tickers']}"
        f" · ETF {r['holdings']['etf']} · "
        f"개별주 {r['holdings']['non_etf']}(대상 밖)",
        "",
        "## 대상(적격) · 제외",
        "",
        f"- 최소 ETF {r['eligibility']['min_etfs']}종(최초 {r['eligibility']['min_etfs_original']}종 · "
        f"{r['eligibility']['min_etfs_change']})",
        "- 적격: "
        + (
            " · ".join(
                f"{e['ticker']} {e['name']}" for e in r["eligibility"]["eligible"]
            )
            or "없음"
        ),
        f"- 제외 {len(r['eligibility']['excluded'])}종:",
    ]
    L += [
        f"  - {e['ticker']} {e['name']}: {' / '.join(e['reasons'])}"
        for e in r["eligibility"]["excluded"]
    ]
    L += ["", "## 가격 경계(06 판정 · 검출 사실)", ""]
    L += [
        f"- {b['date']} {b['kind']}({b['kind_text']}) · ETF {b['etfs']}종 · 앞/뒤 수집일 "
        + ", ".join(f"{a}→{c}" for a, c in b["fetched_before_after"])
        for b in r["price_breaks"]
    ] or ["- 없음"]
    L += [f"- {r['price_break_cause_note']}", ""]
    if r.get("blocks"):
        L += [
            "## 구간",
            "",
            "| 구간 | 날짜 | 학습 행(공동) | 시험 행 | 시험 날짜 | 날짜별 ETF | 학습 정답 끝 < 시작 |",
            "|---|---|---:|---:|---:|---|---|",
        ]
        for b in r["blocks"]:
            L.append(
                f"| {b['block']} | {b['first_date']} ~ {b['last_date']}"
                f" | {b['train_rows_pooled']} | {b['test_rows']} | "
                f"{b['test_dates']} | {b['etfs_per_date']['min']} ~ {b['etfs_per_date']['max']} | "
                f"{b['label_before_start']}({b['train_label_end_max']}) |"
            )
        L.append("")
        etfs = r["eligibility"]["etfs"]
        L += [
            "## 적격 ETF × 구간(학습 행 · 시험 날짜 · 마지막 학습 정답 끝일)",
            "",
            "| ETF | " + " | ".join(f"{b['block']}구간" for b in r["blocks"]) + " |",
            "|---|" + "---|" * len(r["blocks"]),
        ]
        for e in r["eligibility"]["eligible"]:
            per = etfs[e["ticker"]]["blocks"]
            L.append(
                f"| {e['ticker']} | "
                + " | ".join(
                    f"{pb['train_n']} · {pb['test_dates']} · {pb['train_label_end']}"
                    for pb in per[: len(r["blocks"])]
                )
                + " |"
            )
        L.append("")
    if r.get("scores"):
        L += [
            "## 날짜 균형 MAE(%p · 반올림 전 판정)",
            "",
            "| 방법 | 전체 | 1구간 | 2구간 | 3구간 | 날짜 | 행 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for m, s in r["scores"].items():
            L.append(
                f"| {m} | {_pp(s['overall'])} | "
                + " | ".join(_pp(x) for x in s["blocks"])
                + f" | {s['dates']} | {s['rows']} |"
            )
        L += ["", "## 판정", ""]
        for c, v in r["candidates"].items():
            L.append(
                f"- **{c} = {v['verdict']}**"
                + (f" — {v['reason']}" if v.get("reason") else "")
            )
            for b, j in (v.get("against") or {}).items():
                if j.get("base_zero"):
                    L.append(f"  - 대 {b}: {j['reason']}")
                    continue
                cond = j["conditions"]
                L.append(
                    f"  - 대 {b}: 전체 개선 {j['relative_improvement'] * 100:.2f}%"
                    f"(≥5% {cond['overall_improve']}) · "
                    f"이긴 구간 {j['block_wins']}(≥2 {cond['block_wins']}) · "
                    f"5% 넘게 나빠진 구간 없음 {cond['no_block_worse_5pct']}"
                    + (
                        f" · 경계 근처: {', '.join(j['near_boundary'])}"
                        if j["near_boundary"]
                        else ""
                    )
                )
        d = r["diagnostics"]
        L += [
            "",
            "## 보조 보고(주 판정을 바꾸지 않음)",
            "",
            f"- D20 ≤ {d['deep_loss']['threshold'] * 100:.0f}% 행 {d['deep_loss']['rows']}"
            f" · 날짜 {d['deep_loss']['dates']}",
        ]
        for m in r["scores"]:
            if m in d["deep_loss"]:
                x = d["deep_loss"][m]
                L.append(
                    f"  - {m}: MAE {_pp(x['mae_pp'])}%p · 위험 과소 추정 평균 {_pp(x['under_pp'])}%p"
                )
        for c, per in d["per_etf_spread"].items():
            for b, x in per.items():
                L.append(
                    f"- {c} 대 {b}: ETF 개선 {x['improved_etfs']} · 악화 {x['worse_etfs']}"
                )
        methods = list(r["scores"])
        L += [
            "",
            "### ETF별 MAE(%p · 행 = 그 ETF 의 시험 행 수)",
            "",
            "| ETF | 행 | " + " | ".join(methods) + " |",
            "|---|---:|" + "---:|" * len(methods),
        ]
        for t, x in d["per_etf"].items():
            L.append(
                f"| {t} | {x['rows']} | "
                + " | ".join(_pp(x["mae_pp"].get(m)) for m in methods)
                + " |"
            )
        L.append("")
    L += [
        "## GPU(RTX PC)",
        "",
        f"- 상태 {r['gpu'].get('status')}"
        + (f" · {r['gpu'].get('reason')}" if r["gpu"].get("reason") else ""),
    ]
    env = r["gpu"].get("env") or {}
    if env:
        L.append(
            f"- 환경: {env.get('platform')} · Python {env.get('python')}"
            f" · torch {env.get('torch')} · CUDA {env.get('cuda_runtime')} · "
            f"장치 {env.get('device')}"
        )
    res = r["gpu"].get("resources") or {}
    if res:
        cmp_ = res.get("same_mlp_cpu_vs_cuda") or {}
        L.append(
            "- 같은 MLP CPU/CUDA(이 PC 안 비교만): 가속 "
            f"{cmp_.get('cuda_speedup_excluding_transfer')}"
            f" · microbatch {res.get('chosen_microbatch')}"
        )
    L += ["", "## 자원 · 환경(맥북)", ""]
    e = r["environment"]
    L.append(
        f"- {e['platform']} · {e['machine']} · 논리 CPU {e['logical_cpus']} · Python {e['python']} · "
        + " · ".join(f"{k} {v}" for k, v in e["libraries"].items())
    )
    res = r["resources"]
    mem = e.get("memory_bytes")
    L.append(
        f"- 벽시계 {res.get('wall_seconds', 0):.2f}초 · 최대 메모리 {res.get('max_rss_mb')}MB"
        + (f" · 설치 메모리 {mem / 1024 ** 3:.0f}GB" if mem else "")
    )
    for b in r.get("blocks") or []:
        L.append(
            f"  - {b['block']}구간 학습 · 예측 초: "
            + " · ".join(f"{m} {sec:.3f}" for m, sec in b["seconds"].items())
        )
    for p in res.get("hgb_thread_probe") or []:
        L.append(
            f"  - HGB 학습(1구간 · 예측 0) 스레드 {p['threads']}: {p['fit_seconds_median']:.3f}초"
        )
    L += ["", "## 한계", ""] + [f"- {x}" for x in r["limits"]]
    return "\n".join(L) + "\n"


# ── 쓰기 ──────────────────────────────────────────────────────────────────────


class ArtifactSaveError(Exception):
    """연구 산출물 저장 실패 — 결과를 정상 완료로 보이지 않는다."""


def _dump(path: Path, body: Any) -> None:
    path.write_text(
        json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


# 인터프리터를 먼저 하나 고르고 실행기는 한 번만 돌린다(실패 결과를 다른 인터프리터로 다시 덮지 않음).
BAT = (
    '@echo off\r\nchcp 65001 > nul\r\ncd /d "%~dp0"\r\n'
    'set "PY=py -3"\r\n'
    'where python >nul 2>nul && set "PY=python"\r\n'
    "%PY% gpu_runner.py\r\npause\r\n"
)
README = """POC6-02 RTX PC GPU 실행 묶음

1. 이 폴더(또는 gpu_bundle.zip 을 푼 폴더)를 RTX 4070 SUPER 가 있는 PC 로 옮깁니다.
2. 명령 프롬프트(cmd)를 열고 이 폴더로 이동합니다(cd /d <이 폴더>).
3. 쓰던 Python 가상환경이 있으면 그 창에서 켭니다(예: <가상환경 폴더>\\Scripts\\activate).
4. 같은 창에서 run_gpu.bat 또는 `python gpu_runner.py` 를 실행합니다.
   (탐색기에서 더블클릭하면 켜 둔 가상환경을 물려받지 않습니다 — 가상환경이 없을 때만 더블클릭)
5. 같은 폴더에 생긴 gpu_result.json 을 맥북으로 옮겨 주세요. 실행은 한 번이면 됩니다.

필요한 것: Python + CUDA 용 PyTorch 뿐입니다(저장소 · 시장 DB · 개발 서버 · API 키 · 인터넷 불필요).
CUDA 를 쓸 수 없으면 학습하지 않고 'GPU_NOT_RUN'(원인)으로 끝납니다 — CPU 로 바꿔 실행하지 않습니다.
CUDA 용 PyTorch 가 없다면 설치 범위는 PyTorch 하나입니다(예: pip install torch --index-url
https://download.pytorch.org/whl/cu124) — 설치는 사용자 승인 뒤에만 합니다.
"""


def write_run(
    report: dict[str, Any],
    snap: dict[str, Any],
    gpu_input: dict[str, Any] | None,
) -> Path:
    root = Path(RESEARCH_ROOT)
    name = report["study_id"]
    folder, staging = root / name, root / f".{name}.partial"
    made = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        staging.mkdir(exist_ok=False)
        made = True
        _dump(staging / "report.json", report)
        (staging / "report.md").write_text(render_md(report), encoding="utf-8")
        _dump(staging / "input_snapshot.json", snap)
        if gpu_input is not None:
            bundle = staging / "gpu_bundle"
            bundle.mkdir()
            shutil.copyfile(HERE / "mlp.py", bundle / "mlp.py")
            shutil.copyfile(HERE / "gpu_runner.py", bundle / "gpu_runner.py")
            _dump(bundle / "gpu_input.json", gpu_input)
            (bundle / "run_gpu.bat").write_bytes(BAT.encode("utf-8"))
            (bundle / "README_KO.txt").write_text(README, encoding="utf-8")
            shutil.make_archive(str(staging / "gpu_bundle"), "zip", root_dir=bundle)
        os.rename(staging, folder)
    except OSError as e:
        if made:
            shutil.rmtree(staging, ignore_errors=True)
        raise ArtifactSaveError(f"연구 산출물 저장 실패: {type(e).__name__}") from e
    return folder


MERGED_DIR, ATTEMPTS_DIR = "gpu_merged", "gpu_attempts"


def write_merged(run_dir: Path, merged: dict[str, Any]) -> Path:
    """GPU OK = gpu_merged/(한 번만) · OK 아님 = gpu_attempts/<시각>_<상태>_<id>/ — 임시 폴더에 둘 다 쓴 뒤 이름 바꾸기."""
    run_dir = Path(run_dir)
    status = merged["gpu"]["status"]
    if status == "OK":
        folder = run_dir / MERGED_DIR
        if folder.exists():
            raise ArtifactSaveError("이미 GPU 취합 보고서가 있음(덮어쓰지 않음)")
    else:
        stamp = "".join(ch for ch in merged["merged_at"][:19] if ch.isdigit())
        folder = (
            run_dir
            / ATTEMPTS_DIR
            / f"{stamp[:8]}T{stamp[8:]}_{status}_{uuid.uuid4().hex[:8]}"
        )
    staging = folder.parent / f".{folder.name}.partial"
    made = False
    try:
        folder.parent.mkdir(parents=True, exist_ok=True)
        staging.mkdir(exist_ok=False)
        made = True
        _dump(staging / "report_with_gpu.json", merged)
        (staging / "report_with_gpu.md").write_text(render_md(merged), encoding="utf-8")
        os.rename(staging, folder)
    except OSError as e:
        if made:
            shutil.rmtree(staging, ignore_errors=True)
        raise ArtifactSaveError(f"취합 보고서 저장 실패: {type(e).__name__}") from e
    return folder / "report_with_gpu.json"
