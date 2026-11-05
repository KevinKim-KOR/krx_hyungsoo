"""POC6-21 필수 근거 계약 — 실행 폴더 파일 · 정지 주장 · 식별자 · 보고 칸(verify 가 부른다).

```text
파일     계약 안 파일만 · 정상 완료 = 필수 근거 전부 · DATA_SHORT = 보고만 · FAILED = 보고 파일이 남으면 문제
정지     선행 재생 정지 = 다시 적용한 선행 재생 장부의 미확정 목록과 문구가 같고 주 평가 산출물 없음
         주 평가 산출물이 있으면 선행 재생 장부 5개가 모두 OK(판정 Q6) · DATA_SHORT = 잠금 사실의 부족 기록
단계     POC6-20 단계 계약 그대로(경과 · 오름차순 · BUDGET_STOP ⇔ 마지막 단계만 초과 · 정상 = finish · 기록 시각)
식별자   한 잠금 아래 실행 1개 · run.json · report.json 의 schema · protocol · 잠금 · 실행 id
보고     계약 밖 칸 금지 · coverage · fits · 구간 밖 신호 재계산 · 멈춘 실행 = NOT_JUDGED · bootstrap 없음
```

완벽한 위조 인증은 목표가 아니다. run.json 자체는 해시로 묶이지 않으며, 이 계약은 기록끼리 · 다시 계산한 값과의
모순을 찾는다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.market_context_value import evidence as EV20
from app.ml_evidence import store
from app.trend_switch import protocol as P21
from app.trend_switch import report as RP
from app.trend_switch import study as ST
from app.weekly_selection import report as R

stage_problems = EV20.stage_problems
FIXED = EV20.FIXED
REPORT_KEYS = {
    "schema",
    "lock_id",
    "run_id",
    "note",
    "price_note",
    "coverage",
    "stop",
    "validation",
    "validation_trades",
    "validation_signal_after_end",
    "test",
    "test_trades",
    "test_signal_after_end",
    "fits",
    "bootstrap",
    "bootstrap_tail_excluded",
    "judgment",
}
_MODEL = re.compile(r"^models/(\d{4}Q[1-4])_M(\.txt|\.json|\.mismatch\.json)$")


def _norm(obj: Any) -> Any:
    return store.canonical(obj)


def model_ids(fx: dict) -> set[str]:
    return {
        f"{q['id']}_{P21.INPUT}"
        for tag in ("val", "test")
        for q in fx["quarter_detail"][tag]
    }


def _book_files() -> set[str]:
    return {f"validation/{n}.json" for n, _k, _c in P21.val_books()} | {
        f"test/{n}.json" for n, _k, _c in P21.test_books()
    }


def files_problems(fx: dict, rdir: Path, status: str) -> list[str]:
    out = []
    ids = model_ids(fx)
    rels = sorted(
        str(f.relative_to(rdir)) for f in Path(rdir).rglob("*") if f.is_file()
    )
    books = _book_files()

    def ok(rel: str) -> bool:
        if rel in FIXED or rel in books or rel == "run.json":
            return True
        m = _MODEL.match(rel)
        return bool(m) and f"{m.group(1)}_{P21.INPUT}" in ids

    outside = [r for r in rels if not ok(r)]
    if outside:
        out.append(f"계약 밖 파일: {outside[:5]}")
    have = set(rels)
    if status == "OK":
        need = (
            FIXED | books | {f"models/{i}{s}" for i in ids for s in (".txt", ".json")}
        )
        miss = sorted(need - have)
        if miss:
            out.append(f"정상 완료인데 필수 근거 없음: {miss[:5]}")
    if status in ("OK", "CHECK_REQUIRED", "BUDGET_STOP", "DATA_SHORT"):
        # 정상 · 정지 실행은 늘 보고 두 파일을 쓴다(지우고 상태만 바꾼 기록 검출)
        gone = sorted({"report.json", "report.md"} - have)
        if gone:
            out.append(f"상태 {status} 인데 보고 파일 없음: {gone}")
    if status == "DATA_SHORT":
        extra = sorted(have - {"run.json", "report.json", "report.md"})
        if extra:
            out.append(f"DATA_SHORT 인데 계산 산출물이 있음: {extra[:5]}")
    elif status == "FAILED":
        left = sorted(have & {"report.json", "report.md"})
        if left:
            out.append(f"실패 실행에 보고 파일이 남음(유효한 판정 아님): {left}")
    return out


def stop_problems(lk, meta, rep, rdir, recs, vstat, tstat) -> list[str]:
    """정지 주장 ↔ 다시 적용한 장부 상태(vstat · tstat = 저장 장부 이름 → 재적용 상태)."""
    out = []
    status = meta.get("status")
    stop = (rep or {}).get("stop")
    test_made = any(r.get("phase") == "test" for r in recs.values()) or any(
        (rdir / x).exists()
        for x in ("test", "predictions_test.json", "schedule_test.json")
    )
    vbad = [n for n, s in vstat.items() if s != "OK"]
    if test_made and (len(vstat) < len(P21.val_books()) or vbad):
        out.append("선행 재생 장부가 모두 OK 가 아닌데 주 평가 산출물이 있음(판정 Q6)")
    if rep is None:
        return out
    if status == "OK":
        if "stop" in rep:
            out.append("정상 완료 보고에 정지 문구가 있음")
        return out
    if not isinstance(stop, str):
        return out + [f"정지 문구 없음(상태 {status})"]
    if status == "DATA_SHORT":
        short = lk["facts"].get("data_short") or []
        if not short or stop != " · ".join(short):
            out.append("DATA_SHORT 근거 없음(잠금 사실의 부족 기록과 다름)")
    elif status == "CHECK_REQUIRED":
        if stop.startswith(ST.VAL_STOP.split("{")[0]):
            if not vbad or stop != ST.VAL_STOP.format(bad=vbad) or test_made:
                out.append("선행 재생 정지 문구 ≠ 다시 적용한 선행 재생 장부 상태")
        elif stop.startswith(ST.TEST_STOP.split("{")[0]):
            tbad = [n for n, s in tstat.items() if s != "OK"]
            if vbad or not tbad or stop != ST.TEST_STOP.format(bad=tbad):
                out.append("주 평가 정지 문구 ≠ 다시 적용한 주 평가 장부 상태")
        elif not stop.startswith("CheckRequired: "):
            out.append("정지 문구 형식 ≠ CHECK_REQUIRED")
        elif vbad or any(s != "OK" for s in tstat.values()):
            out.append("장부 미확정인데 장부 정지 문구가 아닌 일반 정지 문구")
    elif status == "BUDGET_STOP":
        last = (meta.get("stages") or [{}])[-1].get("stage")
        if not stop.startswith(f"BudgetStop: {last}:"):
            out.append("BUDGET_STOP 정지 문구 ≠ 마지막 단계 기록")
    return out


def identity_problems(lk: dict, meta: dict, ldir: Path, rdir: Path) -> list[str]:
    out = []
    runs = [d for d in (Path(ldir) / "runs").iterdir() if d.is_dir()]
    if len(runs) != 1:
        out.append(f"한 잠금 아래 실행이 {len(runs)}개(공식 실행 1회)")
    if (
        meta.get("schema") != P21.SCHEMA["run"]
        or meta.get("protocol_id") != P21.PROTOCOL_ID
        or meta.get("lock_id") != lk.get("lock_id")
        or meta.get("run_id") != Path(rdir).name
    ):
        out.append("run.json 식별자(schema · protocol · 잠금 · 실행 id) ≠ 잠금 · 폴더")
    return out


def report_meta_problems(p, sig, fx, lk, meta, rdir, rep, recs) -> list[str]:
    out = []
    extra = sorted(set(rep) - REPORT_KEYS)
    if extra:
        out.append(f"report.json 계약 밖 칸: {extra}")
    if (
        rep.get("schema") != P21.SCHEMA["report"]
        or rep.get("lock_id") != lk.get("lock_id")
        or rep.get("run_id") != Path(rdir).name
        or rep.get("note") != RP.NOTE
        or rep.get("price_note") != R.PRICE_NOTE
    ):
        out.append("report.json 식별자 · 의미 문구 다름")
    if meta.get("status") == "OK":
        need = sorted(REPORT_KEYS - {"stop"} - set(rep))
        if (
            need
        ):  # 정상 완료 보고는 계약 칸 전부(빠진 칸이 report.md 에서도 조용히 빠지는 것 방지)
            out.append(f"정상 완료 report.json 필수 칸 없음: {need}")
    if "coverage" in rep and _norm(rep["coverage"]) != _norm(ST.coverage(fx)):
        out.append("report.json coverage ≠ 잠금 사실")
    if "fits" in rep and _norm({r["id"]: r for r in rep["fits"]}) != _norm(recs):
        out.append("report.json fits ≠ 모델 기록")
    for tag, key in (
        ("val", "validation_signal_after_end"),
        ("test", "test_signal_after_end"),
    ):
        if key in rep and rep[key] != ST.after_end(p, sig, ST.window(fx, tag, p)):
            out.append(f"report.json {key} ≠ 재계산")
    if meta.get("status") != "OK":
        if _norm(rep.get("judgment")) != _norm(
            RP.judge(meta.get("status"), None, None, None)
        ):
            out.append("멈춘 실행의 판정 ≠ NOT_JUDGED 규칙")
        if any(k in rep for k in ("bootstrap", "bootstrap_tail_excluded")):
            out.append("정상 완료가 아닌데 bootstrap 칸이 있음")
    md = Path(rdir) / "report.md"
    if not md.exists() or md.read_text(encoding="utf-8") != RP.markdown(rep):
        out.append("report.md ≠ report.json 에서 다시 만든 보고")
    return out
