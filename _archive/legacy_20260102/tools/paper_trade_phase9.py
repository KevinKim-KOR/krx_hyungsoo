# tools/paper_trade_phase9.py
# Phase 12: Non-Intrusive Paper Trading Orchestrator (Final Version)
# - Safe Sell Logic (Only explicit SELL/EXIT)
# - Duplicate Run Prevention (Idempotency)
# - Correct JSON Schema (positions, asof)

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

try:
    from pykrx import stock
except Exception as e:
    raise RuntimeError("pykrx가 필요합니다. (pip install pykrx)") from e


DEFAULT_STATE_PATH = Path("state/paper_portfolio.json")
DEFAULT_REPORT_DIR = Path("reports/paper")


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_json(path: Path, obj: Any) -> None:
    _safe_mkdir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def _load_state(path: Path, initial_capital: int) -> Dict[str, Any]:
    if not path.exists():
        _safe_mkdir(path.parent)
        state = {
            "asof": None,
            "cash": int(initial_capital),
            "positions": {},  # code -> {qty:int, avg_price:float}
            "last_equity": int(initial_capital),
            "meta": {
                "initial_capital": int(initial_capital),
                "created_at": datetime.now(KST).isoformat(timespec="seconds"),
            },
        }
        _save_json(path, state)
        return state

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _infer_date_from_signal_filename(signal_file: Path) -> Optional[date]:
    # reports/signals_YYYYMMDD.yaml
    name = signal_file.stem  # signals_20251228
    if "signals_" not in name:
        return None
    ymd = name.replace("signals_", "")
    if len(ymd) != 8 or not ymd.isdigit():
        return None
    return date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))


def _find_latest_signal_file(reports_dir: Path = Path("reports")) -> Optional[Path]:
    files = sorted(reports_dir.glob("signals_*.yaml"))
    return files[-1] if files else None


def _get_close_price(code: str, d: date) -> Optional[float]:
    # 휴장일이면 None
    try:
        df = stock.get_market_ohlcv_by_date(d.strftime("%Y%m%d"), d.strftime("%Y%m%d"), code)
        if df is None or len(df) == 0:
            return None
        if "종가" not in df.columns:
            return None
        return float(df["종가"].iloc[-1])
    except:
        return None


def _get_close_prices(codes: List[str], target_date: date, max_back_days: int = 10) -> Tuple[date, Dict[str, float]]:
    d = target_date
    for _ in range(max_back_days + 1):
        prices: Dict[str, float] = {}
        any_code = codes[0] if codes else "069500"
        probe = _get_close_price(any_code, d)
        if probe is None:
            d = d - timedelta(days=1)
            continue

        for c in codes:
            px = _get_close_price(c, d)
            if px is not None:
                prices[c] = px
        
        if prices or not codes: # codes가 비어있어도 날짜는 확정해야 함
             return d, prices

    raise RuntimeError(f"최근 {max_back_days}일 내 유효한 종가 데이터를 찾지 못했습니다. target_date={target_date}")


@dataclass
class Signal:
    code: str
    signal_type: str
    score: float
    reason: str


def _normalize_signals(raw: Any) -> List[Signal]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []

    out: List[Signal] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        code = str(r.get("code", "")).strip()
        st = str(r.get("signal_type", "")).strip().upper()
        score = float(r.get("score", 0.0) or 0.0)
        reason = str(r.get("reason", "")).strip()
        if not code or not st:
            continue
        out.append(Signal(code=code, signal_type=st, score=score, reason=reason))
    return out


def _calc_equity(state: Dict[str, Any], close_prices: Dict[str, float]) -> float:
    cash = float(state.get("cash", 0))
    pos = state.get("positions", {}) or {}
    mv = 0.0
    for code, p in pos.items():
        qty = int(p.get("qty", 0))
        px = close_prices.get(code)
        if px is None:
            continue
        mv += qty * float(px)
    return cash + mv


def _collect_sells(signals: List[Signal]) -> List[Signal]:
    return [s for s in signals if s.signal_type in ("SELL", "EXIT")]


def _sort_buys(signals: List[Signal]) -> List[Signal]:
    buys = [s for s in signals if s.signal_type == "BUY"]
    buys.sort(key=lambda x: x.score, reverse=True)
    return buys


def run_paper_trade(
    signal_file: Path,
    state_path: Path,
    initial_capital: int,
    max_positions: int,
    fees_bps: float = 0.0,
    force: bool = False
) -> int:
    raw = _load_yaml(signal_file)
    signals = _normalize_signals(raw)

    inferred = _infer_date_from_signal_filename(signal_file)
    if inferred is None:
        raise ValueError(f"signal 파일명에서 날짜를 추론할 수 없습니다: {signal_file}")

    # state load/create
    state = _load_state(state_path, initial_capital=initial_capital)

    # universe setup
    positions_codes = list(state.get("positions", {}).keys())
    signal_codes = [s.code for s in signals]
    universe = sorted(list(set(positions_codes + signal_codes)))
    
    # 1. Date Check & Duplicate Prevention
    exec_date, close_prices = _get_close_prices(universe, inferred)
    
    last_asof_str = state.get("asof")
    if last_asof_str and not force:
        # ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        last_asof = last_asof_str.split("T")[0]
        exec_date_str = exec_date.isoformat()
        if last_asof == exec_date_str:
            print(f"[SKIP] 이미 실행된 날짜입니다 ({last_asof}). 강제 실행하려면 --force 옵션을 사용하세요.")
            return 0
            
    print(f"[INFO] 실행일: {exec_date} (신호일: {inferred})")

    # before snapshot
    before_state = json.loads(json.dumps(state))
    before_equity = _calc_equity(state, close_prices)

    positions: Dict[str, Dict[str, Any]] = state.get("positions", {}) or {}
    cash: float = float(state.get("cash", 0.0))
    trades: List[Dict[str, Any]] = []

    # 2. Execution Logic
    if not signals:
        print(f"[INFO] 신호가 없습니다 (0건). 현 상태를 유지합니다.")
        # 신호가 없어도 equity 업데이트 및 리포트는 생성 (No-Op)
    else:
        # SELL Logic
        sell_signals = _collect_sells(signals)
        for s in sell_signals:
            if s.code not in positions: continue
            
            px = close_prices.get(s.code)
            if px is None: continue
            
            qty = int(positions[s.code].get("qty", 0))
            if qty <= 0: continue

            gross = qty * px
            fee = gross * (fees_bps / 10000.0)
            net = gross - fee

            cash += net
            trades.append({
                "date": exec_date.isoformat(),
                "code": s.code,
                "side": "SELL",
                "qty": qty,
                "price": px,
                "gross": gross,
                "fee": fee,
                "net": net,
                "reason": s.reason,
                "signal_type": s.signal_type,
            })
            positions.pop(s.code, None)

        # BUY Logic
        buys = _sort_buys(signals)
        slots_left = max_positions - len(positions)
        
        if slots_left > 0 and buys:
            candidates = [b for b in buys if b.code not in positions][:slots_left]
            if candidates:
                alloc_each = cash / len(candidates)
                for b in candidates:
                    px = close_prices.get(b.code)
                    if px is None or px <= 0: continue
                    
                    qty = int( (alloc_each * 0.99) // px )
                    if qty <= 0: continue
                    
                    gross = qty * px
                    fee = gross * (fees_bps / 10000.0)
                    total = gross + fee
                    
                    if total > cash:
                        qty = int( (cash / (1.0 + (fees_bps/10000.0))) // px )
                        gross = qty * px
                        fee = gross * (fees_bps / 10000.0)
                        total = gross + fee
                    
                    if qty <= 0 or total > cash: continue

                    cash -= total
                    positions[b.code] = {"qty": qty, "avg_price": float(px)}
                    trades.append({
                        "date": exec_date.isoformat(),
                        "code": b.code,
                        "side": "BUY",
                        "qty": qty,
                        "price": px,
                        "gross": gross,
                        "fee": fee,
                        "net": -total,
                        "reason": b.reason,
                        "signal_type": b.signal_type,
                        "score": b.score,
                    })

    # write back state
    state["asof"] = exec_date.isoformat()
    state["cash"] = int(round(cash))
    state["positions"] = positions
    
    after_equity = _calc_equity(state, close_prices)
    state["last_equity"] = float(after_equity)

    _save_json(state_path, state)

    # daily report
    report = {
        "signal_file": str(signal_file),
        "execution_date": exec_date.isoformat(),
        "before_equity": before_equity,
        "after_equity": after_equity,
        "pnl": after_equity - before_equity,
        "trades_count": len(trades),
        "trades": trades,
        "holdings_snapshot": positions
    }

    report_path = DEFAULT_REPORT_DIR / f"paper_{exec_date.strftime('%Y%m%d')}.json"
    _save_json(report_path, report)
    
    if trades:
        csv_path = DEFAULT_REPORT_DIR / f"trades_{exec_date.strftime('%Y%m%d')}.csv"
        _safe_mkdir(csv_path.parent)
        pd.DataFrame(trades).to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"[OK] Paper Trade Done. Date={exec_date}, Trades={len(trades)}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Phase 12 Paper Trading (Safe + Idempotent)")
    p.add_argument("--signal-file", type=str, default="")
    p.add_argument("--state-path", type=str, default=str(DEFAULT_STATE_PATH))
    p.add_argument("--initial-capital", type=int, default=10_000_000)
    p.add_argument("--max-positions", type=int, default=5)
    p.add_argument("--fees-bps", type=float, default=0.0)
    p.add_argument("--force", action="store_true", help="중복 실행 방지 무시")
    args = p.parse_args()

    signal_file = Path(args.signal_file) if args.signal_file else None
    if signal_file is None:
        latest = _find_latest_signal_file(Path("reports"))
        if latest is None:
            print("[INFO] 처리할 signals 파일이 없습니다. (scan 미실행?)")
            return 0
        signal_file = latest

    return run_paper_trade(
        signal_file=signal_file,
        state_path=Path(args.state_path),
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        fees_bps=args.fees_bps,
        force=args.force
    )

if __name__ == "__main__":
    import sys
    sys.exit(main())
