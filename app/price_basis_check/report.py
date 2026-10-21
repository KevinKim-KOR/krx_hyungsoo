"""POC6-03 — 대조 실행 · 보고서(PLAN §7-4 · 판정 §5).

대조 결과는 사본 폴더 아래 `compare_<KST시각>_<id>/report.json · report.md` 새 폴더에 쓴다(임시 폴더에 다 쓴 뒤
이름 바꾸기 · 덮어쓰기 없음). 대조 코드 결함은 같은 사본으로 대조만 다시 한다(전체 재수집 없음).
KRX 봉인 판은 실행 전후 `verify_sealed_source` 결과가 같아야 쓴다.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app import krx_sealed_reader as krx
from app.d20_pooled.snapshot import SnapshotError, digest, load_snapshot
from app.price_basis_check import compare as C

SCHEMA = "poc6_03_report_v1"
_KST = timezone(timedelta(hours=9))

LIMITS = [
    "사본도 받은 날 기준의 사후 자료다 — 공식 수정주가 · 총수익률 · PIT 자료라는 보증이 아니다.",
    "같은 날 받았다고 동시점 snapshot 이 보장되지 않는다(종목마다 수집 시각이 다르다).",
    "경계 0 은 06 경계 검사에서 경계를 찾지 못했다는 뜻일 뿐이다. 사본의 change 는 원천 라이브러리가 같은 응답의 "
    "종가로 계산하므로(FinanceDataReader naver `Close.pct_change()`) 사본 안 BASIS_BREAK 는 구조적으로 생기지 "
    "않는다 — 사본 일관성의 주 근거는 KRX 대조다(종목별 'change = 종가 비율' 실측을 함께 싣는다).",
    "사본으로 다시 센 적격 수는 위 이유로 06 경계가 사라져 늘 수 있다 — KRX 대조 결과와 함께 읽는다.",
    "기준가 조정 후보를 분배금 지급으로 단정하지 않는다 — 사건 근거가 없으면 '조정 사유 미확인'.",
    "±1원은 이번 진단의 허용 폭이며 공급자의 실제 반올림 방식을 알아냈다는 뜻이 아니다.",
    "KRX 봉인 판 범위 밖 날짜는 KRX 로 검증하지 않았다.",
    "POC6-02 의 snapshot · 기간 · 모델 · 판정 · 결과는 바꾸지 않는다. 성과(학습 · 예측 · 오차) 계산 0.",
]


class ReportSaveError(Exception):
    """대조 보고서 저장 실패."""


def run_compare(copy_dir: Path, *, krx_db: Path = krx.DEFAULT_SEALED_DB) -> Path:
    copy_dir = Path(copy_dir)
    copy = C.load_copy(copy_dir)
    meta = copy["meta"]
    try:
        snap = load_snapshot(Path(meta["snapshot_path"]))
    except SnapshotError as e:
        raise C.CompareError(f"공식 snapshot: {e}") from e
    if digest(snap) != meta.get("snapshot_digest"):
        raise C.CompareError("공식 snapshot 이 사본을 만들 때와 다름(digest 불일치)")
    try:
        before = krx.verify_sealed_source(krx_db)
        panel = krx.load_panel(krx_db)
    except krx.SealedSourceError as e:
        raise C.CompareError(f"KRX 봉인 판: {e}") from e
    per = C.compare(snap, copy, panel)
    rec = C.recount(snap, copy["rows"])
    try:
        krx.assert_same_source(before, krx.verify_sealed_source(krx_db))
    except krx.SealedSourceError as e:
        raise C.CompareError(f"KRX 봉인 판: {e}") from e
    created = datetime.now(_KST)
    name = f"compare_{created.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    report = {
        "schema": SCHEMA,
        "compare_id": name,
        "created_at": created.isoformat(timespec="seconds"),
        "copy": {k: meta[k] for k in sorted(meta)},
        "fetch_log": copy["log"],
        "snapshot": {
            "path": meta["snapshot_path"],
            "digest": meta["snapshot_digest"],
            "T": snap["T"],
        },
        "krx_source": before,
        "rules": {
            "unit_range": list(C.UNIT_RANGE),
            "candidate_min_won": C.HALF_WON,
            "interval": "(A_t−1)/(A_prev+1) ≤ C_t/B_t ≤ (A_t+1)/(A_prev−1) · A_prev−1 > 0",
            "pairs": "연구 축 연속 · KRX 거래일 연속 · 양쪽 값 있음(건너뛰기 없음)",
            "reasons": C.REASON_TEXT,
        },
        "summary": C.summarize(per, copy["log"]),
        "per_ticker": per,
        "recount": rec,
        "limits": LIMITS,
    }
    return _write(copy_dir, name, report)


def _write(copy_dir: Path, name: str, report: dict[str, Any]) -> Path:
    folder, staging = copy_dir / name, copy_dir / f".{name}.partial"
    made = False
    try:
        staging.mkdir(exist_ok=False)
        made = True
        (staging / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        (staging / "report.md").write_text(render_md(report), encoding="utf-8")
        os.rename(staging, folder)
    except OSError as e:
        if made:
            shutil.rmtree(staging, ignore_errors=True)
        raise ReportSaveError(f"대조 보고서 저장 실패: {type(e).__name__}") from e
    return folder


def _f(v: Any, nd: int = 6) -> str:
    return "—" if v is None else f"{v:.{nd}f}"


def render_md(r: dict[str, Any]) -> str:
    sm, rec = r["summary"], r["recount"]
    L = [
        "# POC6-03 가격 이력 기준 일관성 검증 — 대조 보고",
        "",
        f"- 대조 `{r['compare_id']}` · 사본 `{r['copy']['copy_id']}` · 기준일 T {r['snapshot']['T']}"
        f" · snapshot digest `{r['snapshot']['digest']}`",
        f"- 묶음 조회 {r['copy']['batch_started_at']} ~ {r['copy']['batch_finished_at']}"
        f" · 원천 {r['copy']['source']} · 라이브러리 {r['copy']['libraries']}",
        f"- KRX 봉인 판 {r['krx_source']['version_id']} · {r['krx_source']['first_date']}"
        f" ~ {r['krx_source']['last_date']} · 실행 전후 같음",
        "",
        "## 요약",
        "",
        f"- 조회: {sm['fetch']}",
        f"- 경계(06 판정): 기존 이력 {sm['live_breaks']} · 사본 {sm['copy_breaks']}"
        " (사본 change = 같은 응답 종가 비율 → 사본 경계 0 은 근거가 아님 · 한계 참고)",
        f"- 사본 change = 종가 비율: {sm['copy_change_equal']}/{sm['copy_change_checked']} 행",
        f"- KRX 대조: 일치 {sm['krx_match']} · 불일치 {sm['krx_mismatch']}"
        f" · 대조 불가 {sm['krx_not_comparable']} · KRX 행 있는 종목 {sm['tickers_with_krx']}",
        f"- 적격(POC6-02 규칙): 공식 {len(rec['official']['eligible'])}종"
        f" → 사본 {len(rec['copy']['eligible'])}종"
        f" · 다시 세지 못한 종목 {rec['not_recounted'] or '없음'}"
        " (사본은 06 경계가 구조적으로 사라져 늘 수 있음 — KRX 대조와 함께 읽기)",
        f"- KRX 불일치 나눔(실제 조회 전에 고정한 분류): {sm['krx_mismatch_breakdown']}",
        "",
        "## 종목별",
        "",
        "| ETF | 묶음 | 조회 | 사본 행(≤T) | 경계 기존→사본 | KRX 일치 | 불일치 | 대조 불가 |"
        " 후보(짝 위) | A/C 변화 · 후보 곱 |",
        "|---|---|---|---:|---|---:|---:|---|---:|---|",
    ]
    status = {e["ticker"]: e["status"] for e in r["fetch_log"]}
    for t, v in r["per_ticker"].items():
        k = v["krx"]
        ac = k["a_over_c"]
        L.append(
            f"| {t} {v['name'] or ''} | {rec['groups'].get(t)} | {status.get(t)}"
            f" | {v['copy_rows_to_T']} | "
            f"{len(v['live_breaks'])}→{len(v['copy_breaks'])} | {k['match']} | {k['mismatch']} | "
            f"{k['not_comparable'] or '—'} | {len(k['candidates_on_pairs'])} | "
            + (
                f"{_f(ac['observed_change'])} · {_f(ac['krx_candidate_product'])}"
                if ac
                else "—"
            )
            + " |"
        )
    L += ["", "## 기존 이력 수집 묶음별 차이(기존/사본 배율)", ""]
    for t, v in r["per_ticker"].items():
        for b in v["batches"]:
            L.append(
                f"- {t} · 수집일 {b['batch']} · 행 {b['rows']}"
                f" · 배율 {_f(b['live_over_copy_min'])} ~ "
                f"{_f(b['live_over_copy_max'])} · KRX 기대 {_f(b['expected_from_krx'])}"
                f" · {b['status']}"
            )
    L += ["", "## 적격 다시 세기(학습 · 예측 · 오차 0)", "", f"- 규칙: {rec['rule']}"]
    L.append(f"- 공식 적격: {', '.join(rec['official']['eligible']) or '없음'}")
    L.append(f"- 사본 적격: {', '.join(rec['copy']['eligible']) or '없음'}")
    for t, why in rec["copy"]["excluded"].items():
        L.append(f"  - 사본 제외 {t}: {' / '.join(why)}")
    L += ["", "## 대조 불가 사유", ""] + [
        f"- {k}: {v}" for k, v in r["rules"]["reasons"].items()
    ]
    L += ["", "## 한계", ""] + [f"- {x}" for x in r["limits"]]
    return "\n".join(L) + "\n"
