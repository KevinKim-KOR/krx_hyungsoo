"""POC5-04 — 리포트 출력: Markdown(사람용) · JSON(재현용) · 새 폴더에만 쓴다.

PLAN §1-6. 산출물 = `state/ml/research/poc5_04/<r0|r1>_<종료일>_<생성시각>/report.md · report.json`
(기존 PC 연구 산출물 관례 · gitignore · DB 쓰기 0 · 기존 폴더 덮어쓰기 0).
수익률은 원시값의 표시용 반올림만 한다 — 성공 · 실패 색 · 배지 · 적중률 0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.ledger_reports.r1 import EXPOSURE_LABEL, EXPOSURES

DEFAULT_ROOT = Path("state/ml/research/poc5_04")
VIEW_LABEL = {"observed": "관측 분포", "delivered": "전달된 본문 항목"}


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v * 100:+.2f}%"


def _v(v: Any) -> str:
    return "—" if v is None or v == "" else str(v)


def _cell(v: Any) -> str:
    """표 칸 — `|` 를 이스케이프한다(가격 기준 `KRX_ETF_UNADJUSTED|분류` 등)."""
    return _v(v).replace("|", "\\|")


def write(report: dict[str, Any], root: Path, stamp: str) -> Path:
    """새 폴더를 만들어 report.md · report.json 을 쓴다. 폴더가 이미 있으면 FileExistsError."""
    end = report["window"]["end"]
    folder = Path(root) / f"{report['report'].lower()}_{end}_{stamp}"
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    body = r0_markdown(report) if report["report"] == "R0" else r1_markdown(report)
    (folder / "report.md").write_text(body, encoding="utf-8")
    return folder


def _head(report: dict[str, Any], title: str) -> list[str]:
    inp = report["input"]
    w = report["window"]
    return [
        f"# {title}",
        "",
        f"- 생성 {report['generated_at']} · 버전 `{report['version']}`",
        f"- 입력 `{inp['path']}` · digest `{inp['digest']}`",
        f"- 원장 시작 {_v(inp['meta']['primary_start_date'])}"
        f" · 첫 활성 {_v(inp['meta']['first_active_at'])}"
        f" · 마지막 성공 동기화 {_v(inp['sync']['last_success_at'])}",
        f"- 기간 {_v(w['start'])} ~ {w['end']} · 운영 거래일 {w['trading_days']}일",
        f"- 행 수 {inp['counts']}",
        f"- 계약 버전 {inp['contract_versions']}",
        "",
    ]


def r0_markdown(r: dict[str, Any]) -> str:
    lines = _head(r, "R0 수집 점검")
    lines += [
        f"## 판정: `{r['verdict']}`",
        "",
        f"- {r['verdict_note']}",
        f"- D10 = {_v(r['window'].get('d10'))}",
    ]
    lines += [f"- 준비 안 됨: {x}" for x in r["not_ready_reasons"]]
    lines += [f"- 점검 필요: {x}" for x in r["problems"]]
    rec = r["reconciliation"]
    lines += [
        "",
        "## 1. OCI 대조",
        "",
        f"- 상태 `{rec['state']}` · 사유 {_v(rec['reason'])}",
        f"- 근거 기간 {rec['period']} · 종료일 뒤 실행 포함 {_v(rec['includes_after_end'])}",
        f"- 건수 {rec['counts']} · ID {rec['ids']}",
    ]
    s = r["schedule"] or {}
    lines += [
        "",
        "## 2. 예정 실행",
        "",
        f"- 예정 {_v(s.get('expected'))} · 예정 시각 기록 {_v(s.get('recorded_on_schedule'))}"
        f" · 예정 외 {_v(s.get('off_schedule_runs'))} · 비거래일 기록 {_v(s.get('non_trading_day_runs'))}",
        f"- 누락 {s.get('missing')} · 중복 {s.get('duplicates')}",
        f"- 종류별 상태 {s.get('status_by_kind')}",
        "",
        "## 3. 무결성",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in r["integrity"].items()]
    ops_fail = r.get("operations") or {}
    lines += ["", "## 3-1. 운영 실패 기록(원장)", ""]
    lines += [f"- {k}: {v}" for k, v in ops_fail.items()]
    o = r["outcomes"] or {}
    lines += [
        "",
        "## 4 · 5. 가격 결과 · 대기",
        "",
        f"- 예상 슬롯 {_v(o.get('expected_slots'))} · 기록 {_v(o.get('recorded'))}"
        f" · 상태별 {o.get('by_status')}",
        f"- PENDING_NOT_DUE(평가일 미도래) {_v(o.get('pending_not_due'))}",
        f"- PENDING_DUE {_v(o.get('pending_due'))} — {_v(o.get('pending_due_note'))}",
        "",
        "## 6. 운영 근거",
        "",
        f"- 배치 확인 {r['ops']['batch_confirmed']} · 사유 {_v(r['ops']['reason'])}",
        f"- 개발자 확인 운영 오류(ops_error_count) {_v(r['ops']['error_count'])}"
        f" · 사유 {_v(r['ops']['error_count_reason'])}",
        f"- 값 {r['ops']['values']}",
    ]
    lines += [f"- 메모: {x}" for x in r["ops"]["notes"]]
    return "\n".join(lines) + "\n"


def r1_markdown(r: dict[str, Any]) -> str:
    lines = _head(r, "R1 원시 가격 결과")
    pop = r["population"]
    lines += [
        "수익률은 저장된 원시값(표시만 반올림)이며 성공 · 실패 · 적중을 뜻하지 않는다. "
        "관측과 전달 집계는 알림 효과의 인과 비교가 아니다.",
        "",
        f"- 표본 item {pop['items']} · event {pop['events']}"
        f" · partial 발송 item(건수만) {pop['partial_sent_items']}",
        f"- 제외 사유 {pop['exclusions']}",
        f"- bootstrap {r['settings']}",
        f"- 평가(부가 · 표본과 무관) {r['feedback']}",
        "",
    ]
    extra = sorted({g["exposure"] for g in r["groups"]} - set(EXPOSURES))
    for exposure in (*EXPOSURES, *extra):
        rows = [g for g in r["groups"] if g["exposure"] == exposure]
        label = EXPOSURE_LABEL.get(exposure, f"알 수 없는 노출값({exposure})")
        lines += [f"## {label}", ""]
        if not rows:
            lines += ["- 해당 없음", ""]
            continue
        lines += [
            "| 보기 | 종류 | subject | state | 계약 | 가격 기준 | h | 성숙 | 상태 | 미도래 | 도래·미기록"
            " | 평균 | 중앙 | 25% | 75% | 최소 | 최대 | 상승폭 중앙 | 하락폭 중앙"
            " | event | item | 관측 | 날짜 | 구간(95%) |",
            "|" + "---|" * 24,
        ]
        for g in rows:
            b = g["bootstrap"]
            ci = (
                f"{_pct(b['low'])} ~ {_pct(b['high'])}"
                if b["status"] == "OK"
                else b["status"]
            )
            lines.append(
                f"| {VIEW_LABEL[g['view']]} | {_cell(g['push_kind'])}"
                f" | {_cell(g['subject_kind'])} | {_cell(g['state'])}"
                f" | {_cell(g['contract_version'])} | {_cell(g['price_basis'])} | {g['horizon']}"
                f" | {g['n_matured']}"
                f" | {_cell(g['status_counts'])} | {g['pending_not_due']} | {g['pending_due']}"
                f" | {_pct(g['mean'])} | {_pct(g['median'])} | {_pct(g['q25'])} | {_pct(g['q75'])}"
                f" | {_pct(g['min'])} | {_pct(g['max'])} | {_pct(g['max_up_median'])}"
                f" | {_pct(g['max_down_median'])} | {g['n_event']} | {g['n_item']}"
                f" | {g['n_price_observation']} | {g['n_signal_date']} | {ci} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"
