"""POC7-03 주간 ETF 전체 비교와 우선 검토 후보 — 맥북 연구 CLI(PLAN V1 · 판정 2026-11-24).

```text
prepare [--reason R]   잠금(분모 · 자리 판정 · 설정 · 코드 해시) — 성과 계산 0
run                    공식 1회(잠금과 같을 때만)
verify                 독립 재계산 대조
week [--end D]         이번 주 로컬 연구 HTML 한 장(PC 시세 DB 읽기 전용 · 구성 · 겹침 = 주간 점검과 같은 읽기)
cross-check            AC1 대조(이번 주 세 곳 · 보관 응답 · 봉인 안 한 주) — 로컬 서버 GET · 읽기 전용
```
마지막 줄 = `RESULT {json}` · 종료 코드 0 = 됨 · 2 = 확인 필요(CheckRequired).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.candidate_compare import crosscheck as CC  # noqa: E402
from app.candidate_compare import current as CU  # noqa: E402
from app.candidate_compare import flow as FW  # noqa: E402
from app.candidate_compare import page as PG  # noqa: E402
from app.candidate_compare import verify as VF  # noqa: E402
from app.candidate_compare import verify_records as VR  # noqa: E402
from app.candidate_compare.protocol import SCHEMA, CheckRequired, Config  # noqa: E402
from app.entry_timing.protocol import (  # noqa: E402
    dumps,
    new_id,
    real_root,
    write_once,
)

MARKET_DB = REPO / "state" / "market" / "market_data.sqlite"
STORED = (
    REPO
    / "state"
    / "ml"
    / "research"
    / "poc7_02"
    / "cases"
    / "20261123T164430Z_65004b7e"
    / "response.json"
)
SEALED_WEEK = "2026-09-18"
WEEKLY_FILTERS = {
    "exclude_inverse": True,
    "exclude_leveraged": True,
    "exclude_synthetic": True,
    "exclude_futures": True,
}


def _research(end: str | None, with_detail: bool) -> dict:
    from app import api_etf_compare as AE

    official, _ = AE._official()
    dictionary, _ = AE._dictionary()
    reader = CU.default_reader(MARKET_DB) if with_detail else None
    return CU.build(
        CU.read_market(MARKET_DB, end),
        filters=WEEKLY_FILTERS,
        official=official,
        dictionary=dictionary,
        reader=reader,
    )


def _verdict_text(cfg: Config) -> str | None:
    """검산이 일치한 공식 실행의 판정 — 한 장 맨 위 '과거 비교 결과' 줄(읽기 전용 · 없으면 None).

    마지막 잠금(previous_lock 이어짐)의 실행 하나 · 그 실행의 가장 최근(차례 번호) 검산이 VERIFIED_OK · 어긋남 0 ·
    지금 검산 지문(검산이 쓰는 코드 전부 + 환경)이고 지금 파일 여섯 개가 그 기록과 같을 때만 보인다(검증자 r1 F2 ·
    r2 F6). 연구 기록을 못 읽거나 형식이 틀리면 판정을 보이지 않고 한 장은 만든다(r2 F5).
    """
    try:
        if not cfg.root.exists():
            return None
        rep = VR.display_report(real_root(cfg.root))
    except Exception:
        return None
    if rep is None:
        return None
    verdict = rep.get("verdict")
    label = verdict.get("label") if isinstance(verdict, dict) else None
    if not isinstance(label, str):
        return None
    if label == "미달":
        return (
            "미달 — 2021 ~ 2026 회고 비교(비용 후 · 20거래일)에서 이 순서가 1개월 수익률 순서보다 "
            "나았다는 것이 확인되지 않았습니다 · 운영 채택 아님"
        )
    return f"{label}(2021 ~ 2026 회고 비교 · 검산 일치) · 운영 채택 아님"


def _sources() -> tuple:
    from app import api_etf_compare as AE

    official, _ = AE._official()
    dictionary, _ = AE._dictionary()
    return official, dictionary


def cmd_week(cfg: Config, now: datetime, end: str | None) -> dict:
    official, dictionary = _sources()
    market = CU.read_market(MARKET_DB, end)
    data = CU.build(
        market,
        filters=WEEKLY_FILTERS,
        official=official,
        dictionary=dictionary,
        reader=CU.default_reader(MARKET_DB),
    )
    if data.get("status") != "ok" or not data.get("items"):
        raise CheckRequired(f"이번 주 목록을 만들 수 없음: {data.get('status')}")
    again = CU.read_market(MARKET_DB, end)
    if again["end"] != market["end"] or CU.fingerprint(again) != CU.fingerprint(market):
        # 상세(구성 · 겹침)를 읽는 사이 가격이 다시 저장됨 — 한 시점 자료가 아니므로 만들지 않음
        # (끝날짜가 같아도 같은 날짜 값 · 저장 시각이 바뀌면 멈춤 · PLAN §5-1 · 검증자 r1 F4 같은 종류)
        raise CheckRequired("한 장을 만드는 사이 시세 자료가 바뀜 — 다시 실행")
    root = real_root(cfg.root)
    wid = new_id(now)
    d = root / "weeks" / f"{data['end']}_{wid}"
    gen = now.astimezone(CU.KST).isoformat(timespec="seconds")
    page = PG.render(data, generated_at=gen, verdict=_verdict_text(cfg)).encode("utf-8")
    body = dumps(
        {
            "schema": SCHEMA["week"],
            "week_id": wid,
            "generated_at": gen,
            "market_fingerprint": CU.fingerprint(market),
            "data": data,
        }
    )
    hashes = {
        "page.html": write_once(root, d / "page.html", page),
        "data.json": write_once(root, d / "data.json", body),
    }
    return {
        "dir": str(d),
        "end": data["end"],
        "weekly": data["weekly"],
        "files": hashes,
        "picks_a": data["picks_a"],
        "picks_b": data["picks_b"],
        "population": data["counts"]["population"],
    }


def _part(fn) -> dict:
    """AC1 한 부분 — 응답 · 파일이 깨지거나 조회가 실패해도 예외로 끝내지 않고 ERROR 로 기록(r2 F5 같은 종류)."""
    try:
        return fn()
    except Exception as e:
        return {"status": "ERROR", "error": f"{type(e).__name__}: {e}"[:300]}


def _sealed_ok(sealed: dict) -> bool:
    """봉인 주: 순위 · 1개월 값 차이는 가격판 설명용(PLAN §1-3 ②) · 후보 집합 · 상위 30 · 오른 주 · 선정은 같아야 함."""
    if sealed.get("status") == "ERROR":
        return False
    picks = sealed.get("picks_same")
    return (
        sealed.get("only_sealed") == []
        and sealed.get("only_pc") == []
        and sealed.get("top30_same") is True
        and sealed.get("up_differs") == 0
        and isinstance(picks, dict)
        and picks.get("same") is True
    )


def cmd_cross(cfg: Config, now: datetime) -> dict:
    out = {
        "schema": SCHEMA["cross_check"],
        "at": now.isoformat(timespec="seconds"),
        "current": _part(
            lambda: CC.current_week(
                CC.http_fetch, lambda: _research(None, with_detail=False)
            )
        ),
        "stored": _part(
            lambda: CC.stored_response(
                STORED, lambda e: _research(e, with_detail=False)
            )
        ),
        "sealed": _part(
            lambda: CC.sealed_week(
                cfg, SEALED_WEEK, lambda e: _research(e, with_detail=False)
            )
        ),
    }
    root = real_root(cfg.root)
    cid = new_id(now)
    # 응답에서 온 글 · 수(깨진 유니코드 · NaN)도 기록할 수 있게 — 쓰다가 예외로 끝내지 않음(r2 반박 6)
    sha = write_once(root, root / "cross_check" / f"{cid}.json", dumps(VR.safe(out)))
    sealed = out["sealed"]
    sealed_ok = _sealed_ok(sealed)
    return {
        "id": cid,
        "sha256": sha,
        "all_same": out["current"].get("status") == "SAME"
        and out["stored"].get("status") == "SAME"
        and sealed_ok,
        "current": out["current"].get("status"),
        "stored": out["stored"].get("status"),
        "sealed_ok": sealed_ok,
        "sealed": {
            k: sealed.get(k)
            for k in (
                "status",
                "sealed_pop",
                "pc_pop",
                "rank_differs",
                "up_differs",
                "max_1m_gap_pctp",
                "top30_same",
            )
        },
    }


def main(argv: list[str] | None = None) -> int:
    os.chdir(
        REPO
    )  # 운영 모듈의 기본 경로(보유 · 시세 캐시 · 공식 CSV)는 저장소 기준 상대 경로
    ap = argparse.ArgumentParser(description="POC7-03 주간 ETF 전체 비교 연구")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--reason")
    sub.add_parser("run")
    sub.add_parser("verify")
    w = sub.add_parser("week")
    w.add_argument("--end")
    sub.add_parser("cross-check")
    args = ap.parse_args(argv)
    cfg = Config()
    now = datetime.now(timezone.utc)
    try:
        if args.cmd == "prepare":
            lock = FW.prepare(cfg, now, args.reason)
            res = {
                "lock_id": lock["lock_id"],
                "counts": lock["counts"],
                "slot_counts": lock["slot_counts"],
                "weeks_sha256": lock["weeks_sha256"],
            }
        elif args.cmd == "run":
            res = FW.run(cfg, now)
        elif args.cmd == "verify":
            res = VF.verify(cfg, now)
        elif args.cmd == "week":
            res = cmd_week(cfg, now, args.end)
        else:
            res = cmd_cross(cfg, now)
    except CheckRequired as e:
        print(
            "RESULT "
            + json.dumps(
                {"status": "CHECK_REQUIRED", "reason": str(e)}, ensure_ascii=False
            )
        )
        return 2
    # 검산 어긋남 · 대조 차이는 정상 종료(0)로 내지 않는다(반박 m2 — 자동 실행이 '통과'로 읽지 않게)
    differs = (args.cmd == "verify" and res.get("status") != "VERIFIED_OK") or (
        args.cmd == "cross-check" and not res.get("all_same")
    )
    out = {
        "status": "DIFFERENT" if differs else "OK",
        **res,
    }  # 검산은 VERIFIED_OK · MISMATCH 그대로
    print("RESULT " + json.dumps(out, ensure_ascii=False, default=str))
    return 2 if differs else 0


if __name__ == "__main__":
    raise SystemExit(main())
