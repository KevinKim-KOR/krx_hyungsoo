"""POC3-ML-02 — Relative Upside Score Validity Gate · 평가 실행 CLI.

실행:
  python scripts/run_ml_score_validity_eval_v1.py
  python scripts/run_ml_score_validity_eval_v1.py --limit-dates 5   (스모크)

PLAN V1 §8 산출물:
  state/ml/validity/relative_upside_validity_v1_latest.json
  state/ml/validity/relative_upside_validity_v1_run_latest.json

본 스크립트는 오케스트레이션만 한다 — 지표 산식은 `ml_score_validity_metrics`,
PIT 재현은 `ml_score_validity_eval`, U2 재현은 `ml_score_validity_screen`,
집계·판정은 `ml_score_validity_report` 에 있다 (KS-10 책임 분리).

하지 않는 것 — OCI 전달 / Telegram / PARAM / 운영 snapshot 갱신.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import socket
import sys
import time
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.ml_relative_upside_features import KODEX200_TICKER  # noqa: E402
from app.ml_relative_upside_model import (  # noqa: E402
    normalize_to_display_scores,
    predict_raw_scores,
)
from app.ml_score_validity_eval import (  # noqa: E402
    E1_SNAPSHOT_ASOF,
    MIN_OBSERVATIONS,
    PHASE_EVALUATION,
    PHASE_WARMUP,
    QUANTILE_BUCKETS,
    SCORE_TOP_N,
    TOP_DECILE_FRACTION,
    assert_evaluation_window,
    classify_phase,
    build_calendar,
    build_close_maps,
    build_tag_map,
    file_sha256,
    forward_excess,
    is_filter_universe,
    is_pit_eligible,
    load_prices,
    observations_upto,
    price_projection_sha256,
    regime_at,
    reproduce_scores_at,
    run_e1_gate,
    trading_days,
)
from app.ml_score_validity_metrics import (  # noqa: E402
    SHUFFLE_SEED_END,
    SHUFFLE_SEED_START,
    mean,
    median,
    quantile_means,
    shuffle_control_verdict,
    shuffle_permutation_means,
    spearman,
    top_fraction,
    win_rate,
)
from app.ml_score_validity_report import (  # noqa: E402
    NON_DETERMINISTIC_FIELDS,
    SCHEMA_VERSION,
    aggregate,
    canonical_sha256,
    now_iso,
    preflight_gate,
)
from app.ml_score_validity_screen import replay_screen_slates  # noqa: E402

OUT_DIR = _PROJECT_ROOT / "state" / "ml" / "validity"
RESULT_FILENAME = "relative_upside_validity_v1_latest.json"
RUN_META_FILENAME = "relative_upside_validity_v1_run_latest.json"

FROZEN_MODULES = (
    "app/ml_relative_upside_features.py",
    "app/ml_relative_upside_model.py",
    "app/ml_relative_upside_score.py",
)


def _logger() -> logging.Logger:
    lg = logging.getLogger("ml_score_validity")
    if not lg.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        lg.addHandler(h)
    lg.setLevel(logging.INFO)
    return lg


def _node_info() -> dict:
    """실행 노드 정보 (PLAN §8.1)."""
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["device"] = "cpu"
        info["cuda_available"] = torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        pass
    return info


def _cleanup(out_dir: Path) -> None:
    """U2 재현용 임시 DB 제거."""
    replay_db = out_dir / "_pit_replay.sqlite"
    if replay_db.exists():
        replay_db.unlink()


def build_frozen_descriptor() -> dict:
    """PLAN §2.1 — 재현 기술자 6종. artifact 부재(C-1)를 대체한다."""
    return {
        "score_version": "relative_upside_score.v0",
        "model_name": "relative_upside_v0_linear",
        "module_sha256": {m: file_sha256(_PROJECT_ROOT / m) for m in FROZEN_MODULES},
        "price_projection_sha256_full": price_projection_sha256(),
        "price_projection_sha256_e1_cutoff": price_projection_sha256(
            cutoff_date=E1_SNAPSHOT_ASOF
        ),
        "hyperparameters": {
            "seed": 42,
            "epochs": 200,
            "learning_rate": 0.001,
            "train_split_ratio": 0.8,
            "model": "nn.Linear(7,1)",
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="POC3-ML-02 참고점수 유효성 평가")
    parser.add_argument(
        "--limit-dates", type=int, default=None, help="스모크용 기준일 제한"
    )
    parser.add_argument("--skip-e1", action="store_true")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)

    log = _logger()
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / RESULT_FILENAME
    meta_path = out_dir / RUN_META_FILENAME

    wall0 = time.perf_counter()
    started = now_iso()
    log.info("가격 적재 시작")
    prices = load_prices()
    days = trading_days(prices)
    close_maps = build_close_maps(prices)
    tag_map = build_tag_map()
    kodex_closes = [c for _, c in prices[KODEX200_TICKER]]
    day_index = {d: i for i, d in enumerate(days)}
    log.info("ticker=%d 거래일=%d (%s ~ %s)", len(prices), len(days), days[0], days[-1])

    cal_1m = build_calendar(days, months_ahead=1)
    cal_3m = build_calendar(days, months_ahead=3)
    if args.limit_dates:
        cal_1m = cal_1m[-args.limit_dates :]  # noqa: E203
        keep = {p.signal_date for p in cal_1m}
        cal_3m = [p for p in cal_3m if p.signal_date in keep]
    log.info("1M 기준일=%d 3M 기준일=%d", len(cal_1m), len(cal_3m))

    # --- E1 게이트 ---------------------------------------------------------
    if args.skip_e1:
        e1 = {"status": "E1_UNAVAILABLE", "reason": "--skip-e1"}
        e1_model = None
        e1_train_end = None
    else:
        e1 = run_e1_gate(prices, log=log)
        e1_model = e1.pop("_model", None)
        e1.pop("_scores", None)
        e1_train_end = e1.pop("_train_end", None)
    log.info("E1 게이트: %s (train_end=%s)", e1["status"], e1_train_end)

    # --- U2 화면 슬레이트 PIT 재현 ----------------------------------------
    log.info("U2 화면 슬레이트 재현 시작")
    t_screen = time.perf_counter()
    slates = replay_screen_slates(
        [p.signal_date for p in cal_1m],
        temp_db_path=out_dir / "_pit_replay.sqlite",
    )
    log.info("U2 완료 (%.1fs)", time.perf_counter() - t_screen)

    # --- E2 재현 + 라벨 ----------------------------------------------------
    exits_3m = {p.signal_date: p for p in cal_3m}
    per_date: list[dict] = []
    leak_violations = {
        "L1_future_input": 0,
        "L2_label_before_entry": 0,
        "L3_target_end": 0,
    }

    for i, point in enumerate(cal_1m, 1):
        t0 = time.perf_counter()
        need_rows = bool(e1_model and e1_train_end and point.signal_date > e1_train_end)
        run = reproduce_scores_at(prices, point.signal_date, keep_rows=need_rows)

        # L-1 / L-3
        if run.max_input_date and run.max_input_date > point.signal_date:
            leak_violations["L1_future_input"] += 1
        if run.max_target_end_date and run.max_target_end_date > point.signal_date:
            leak_violations["L3_target_end"] += 1
        # L-2
        if point.entry_date <= point.signal_date:
            leak_violations["L2_label_before_entry"] += 1

        regime = regime_at(kodex_closes, point.signal_index)

        # 커버리지 분모 = PIT 편입 가능 **필터** universe (PLAN §4.7)
        denom = 0
        reasons = {
            "lookback_부족": 0,
            "KODEX_날짜없음": 0,
            "close_결측": 0,
            "진입일_가격없음": 0,
            "청산일_가격없음": 0,
        }
        rows_1m: list[tuple[str, float, float]] = []
        rows_all: list[tuple[str, float, float]] = []
        simple_rows: list[tuple[str, float, float]] = []
        rows_3m: list[tuple[str, float, float]] = []
        p3 = exits_3m.get(point.signal_date)

        for ticker, history in prices.items():
            if ticker == KODEX200_TICKER:
                continue
            obs = observations_upto(history, point.signal_date)
            if obs <= 0:
                continue
            in_filter = is_filter_universe(tag_map.get(ticker, []))
            # 분모는 **PIT 편입 가능** 필터 universe (설계자 보완 §2):
            # 태그 제외 + 유효종가 21개 이상 + 첫 종가 이후 20거래일 경과.
            eligible = in_filter and is_pit_eligible(
                history, point.signal_date, day_index
            )
            if eligible:
                denom += 1
            score = run.display_scores.get(ticker)
            if score is None:
                if eligible:
                    if obs < MIN_OBSERVATIONS:
                        reasons["lookback_부족"] += 1
                    else:
                        reasons["KODEX_날짜없음"] += 1
                continue
            label = forward_excess(
                close_maps, ticker, point.entry_date, point.exit_date
            )
            if label is None:
                if eligible:
                    has_entry = close_maps.get(ticker, {}).get(point.entry_date)
                    if not has_entry:
                        reasons["진입일_가격없음"] += 1
                    else:
                        reasons["청산일_가격없음"] += 1
                continue
            rows_all.append((ticker, score, label))
            if eligible:
                rows_1m.append((ticker, score, label))
                simple = run.simple_signal.get(ticker)
                if simple is not None:
                    simple_rows.append((ticker, simple, label))
                if p3 is not None:
                    lab3 = forward_excess(
                        close_maps, ticker, p3.entry_date, p3.exit_date
                    )
                    if lab3 is not None:
                        rows_3m.append((ticker, score, lab3))

        numer = len(rows_1m)
        asof_match = [
            1
            for tk in run.display_scores
            if run.inference_asof.get(tk) == point.signal_date
        ]
        rec = {
            "phase": classify_phase(point.signal_date),
            "signal_date": point.signal_date,
            "entry_date": point.entry_date,
            "exit_date": point.exit_date,
            "next_signal_date": point.next_signal_date,
            "regime": regime,
            "train_row_count": run.train_row_count,
            "test_row_count": run.test_row_count,
            "scored_count": len(run.display_scores),
            "asof_equals_signal_ratio": (
                len(asof_match) / len(run.display_scores)
                if run.display_scores
                else None
            ),
            "coverage_denominator": denom,
            "coverage_numerator": numer,
            "coverage": (numer / denom) if denom else None,
            "missing_reasons": reasons,
            "max_input_date": run.max_input_date,
            "max_target_end_date": run.max_target_end_date,
            "ic_filter": spearman([r[1] for r in rows_1m], [r[2] for r in rows_1m]),
            "ic_all": spearman([r[1] for r in rows_all], [r[2] for r in rows_all]),
            "ic_simple_momentum": spearman(
                [r[1] for r in simple_rows], [r[2] for r in simple_rows]
            ),
            "ic_3m": spearman([r[1] for r in rows_3m], [r[2] for r in rows_3m]),
            "n_filter": len(rows_1m),
            "n_all": len(rows_all),
            "n_3m": len(rows_3m),
            "quantile_means": {
                str(k): v for k, v in quantile_means(rows_1m, QUANTILE_BUCKETS).items()
            },
            "_scores": [r[1] for r in rows_1m],
            "_labels": [r[2] for r in rows_1m],
        }
        # E1 보조 평가 — 재현 모델을 그대로 써서 학습 종료 이후 월말만 평가.
        if need_rows:
            e1_raw = predict_raw_scores(e1_model, run.inference_rows)
            e1_disp = normalize_to_display_scores(e1_raw)
            e1_rows = [
                (tk, e1_disp[tk], lb) for tk, _sc, lb in rows_1m if tk in e1_disp
            ]
            rec["e1_ic"] = spearman([r[1] for r in e1_rows], [r[2] for r in e1_rows])
            e1_paired = [
                (
                    s2["ticker"],
                    e1_disp[s2["ticker"]],
                    forward_excess(
                        close_maps, s2["ticker"], point.entry_date, point.exit_date
                    ),
                )
                for s2 in (slates.get(point.signal_date) or [])
                if s2.get("ticker") in e1_disp
            ]
            e1_paired = [(a, b, c) for a, b, c in e1_paired if c is not None]
            if len(e1_paired) >= 4:
                o = sorted(e1_paired, key=lambda x: x[1], reverse=True)
                h = len(o) // 2
                th, bh = mean([x[2] for x in o[:h]]), mean([x[2] for x in o[h:]])
                rec["e1_screen_diff"] = (
                    (th - bh) if th is not None and bh is not None else None
                )

        top = top_fraction(rows_1m, TOP_DECILE_FRACTION)
        rec["top_decile_tickers"] = [r[0] for r in top]
        rec["top_decile_mean"] = mean([r[2] for r in top])
        rec["top_decile_median"] = median([r[2] for r in top])
        rec["top_decile_win_rate"] = win_rate([r[2] for r in top])
        rec["top_decile_values"] = [r[2] for r in top]

        # 점수 기준 top-N 바스켓 (설계자 보완 §4) — 화면 슬레이트와 별개다.
        score_top = sorted(rows_1m, key=lambda x: x[1], reverse=True)[:SCORE_TOP_N]
        rec["score_top10_tickers"] = [r[0] for r in score_top]
        rec["score_top10_values"] = [r[2] for r in score_top]
        rec["score_top10_mean"] = mean([r[2] for r in score_top])
        rec["score_top10_median"] = median([r[2] for r in score_top])
        rec["score_top10_size"] = len(score_top)
        rec["score_top10_missing_reason"] = (
            None if len(score_top) >= SCORE_TOP_N else "필터 universe 표본 부족"
        )

        # 3M 상세 — 비중첩 부분집합 집계에 연결 (설계자 보완 §3)
        rec["is_quarter_end"] = point.signal_date[5:7] in ("03", "06", "09", "12")
        if p3 is None:
            rec["exclusion_3m"] = "3M 청산일 부재 (달력 끝)"
        elif not rows_3m:
            rec["exclusion_3m"] = "3M 라벨 산출 가능 종목 0건"
        else:
            rec["exclusion_3m"] = None
        rec["quantile_means_3m"] = {
            str(k): v for k, v in quantile_means(rows_3m, QUANTILE_BUCKETS).items()
        }
        top3 = top_fraction(rows_3m, TOP_DECILE_FRACTION)
        rec["top_decile_3m_tickers"] = [r[0] for r in top3]
        rec["top_decile_3m_values"] = [r[2] for r in top3]
        rec["top_decile_3m_mean"] = mean([r[2] for r in top3])

        # U2 화면 슬레이트
        slate = slates.get(point.signal_date) or []
        paired = [
            (
                s["ticker"],
                run.display_scores[s["ticker"]],
                forward_excess(
                    close_maps, s["ticker"], point.entry_date, point.exit_date
                ),
            )
            for s in slate
            if s.get("ticker") in run.display_scores
        ]
        paired = [(tk, sc, lb) for tk, sc, lb in paired if lb is not None]
        if len(paired) >= 4:
            ordered = sorted(paired, key=lambda x: x[1], reverse=True)
            half = len(ordered) // 2
            top_half = mean([x[2] for x in ordered[:half]])
            bot_half = mean([x[2] for x in ordered[half:]])
            rec["screen_slate_size"] = len(ordered)
            rec["screen_top_half_mean"] = top_half
            rec["screen_bottom_half_mean"] = bot_half
            rec["screen_diff"] = (
                top_half - bot_half
                if top_half is not None and bot_half is not None
                else None
            )
            rec["screen_tickers"] = [x[0] for x in ordered]
        else:
            rec["screen_slate_size"] = len(paired)
            rec["screen_diff"] = None
            rec["screen_tickers"] = []

        per_date.append(rec)
        log.info(
            "[%d/%d] %s ic=%s n=%d cov=%s (%.1fs)",
            i,
            len(cal_1m),
            point.signal_date,
            None if rec["ic_filter"] is None else round(rec["ic_filter"], 4),
            rec["n_filter"],
            None if rec["coverage"] is None else round(rec["coverage"], 3),
            time.perf_counter() - t0,
        )

    # --- warmup 분리 (설계자 보완 §1) -----------------------------------
    warmup = [r for r in per_date if r["phase"] == PHASE_WARMUP]
    evaluation = [r for r in per_date if r["phase"] == PHASE_EVALUATION]
    log.info(
        "phase 분리: %s=%d · %s=%d",
        PHASE_WARMUP,
        len(warmup),
        PHASE_EVALUATION,
        len(evaluation),
    )
    if not args.limit_dates:
        # 평가 구간 계약(2014-06-30 시작 · 145개) 위반이면 즉시 중단.
        assert_evaluation_window([r["signal_date"] for r in evaluation])

    # --- fail-closed 게이트 (설계자 보완 §1 · §7) -------------------------
    # N-1 은 게이트 입력이므로 집계 **전에** 계산한다.
    n1_pairs = [
        (r["_scores"], r["_labels"]) for r in evaluation if len(r["_scores"]) >= 2
    ]
    n1 = shuffle_control_verdict(
        shuffle_permutation_means(
            n1_pairs, seed_start=SHUFFLE_SEED_START, seed_end=SHUFFLE_SEED_END
        )
    )
    gate = preflight_gate(evaluation, n1)
    log.info("preflight: %s (%s)", gate["status"], ", ".join(gate["blocked"]) or "-")

    if gate["status"] != "OK":
        # 최종 지표와 모델 판정을 산출하지 않는다. validity_latest 미발행.
        meta = {
            "schema_version": SCHEMA_VERSION + ".run",
            "status": gate["status"],
            "blocked": gate["blocked"],
            "blocked_details": gate["details"],
            "started_at": started,
            "finished_at": now_iso(),
            "elapsed_seconds": round(time.perf_counter() - wall0, 2),
            "node": _node_info(),
            "result_path": None,
            "error": "fail-closed: 집계·최종 판정을 산출하지 않았다",
        }
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if result_path.exists():
            result_path.unlink()
        _cleanup(out_dir)
        log.error("%s — validity_latest 미발행", gate["status"])
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 3

    payload = aggregate(
        evaluation,
        e1,
        days,
        build_frozen_descriptor(),
        {
            "rebalance_points_1m_total": len(per_date),
            "rebalance_points_3m": len(cal_3m),
        },
        warmup_records=warmup,
    )
    payload["preflight_gate"] = gate
    payload["run_arguments"] = {
        "limit_dates": args.limit_dates,
        "skip_e1": args.skip_e1,
    }
    payload["determinism"] = {
        "excluded_fields": list(NON_DETERMINISTIC_FIELDS),
        "canonical_sha256": None,
    }
    # 해시는 payload 가 완성된 뒤 마지막에 계산한다 (자기 자신은 None 상태로 포함).
    payload["determinism"]["canonical_sha256"] = canonical_sha256(payload)

    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    meta = {
        "schema_version": SCHEMA_VERSION + ".run",
        "status": payload["verdict"]["final"],
        "canonical_sha256": payload["determinism"]["canonical_sha256"],
        "canonical_excluded_fields": list(NON_DETERMINISTIC_FIELDS),
        "started_at": started,
        "finished_at": now_iso(),
        "elapsed_seconds": round(time.perf_counter() - wall0, 2),
        "node": _node_info(),
        "result_path": str(result_path),
        "error": None,
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _cleanup(out_dir)

    log.info("완료 %.1fs → %s", time.perf_counter() - wall0, result_path)
    print(
        json.dumps(
            {
                "status": payload["verdict"]["final"],
                "elapsed_seconds": meta["elapsed_seconds"],
                "result_path": str(result_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
