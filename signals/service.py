# signals/service.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Optional
#from utils.config import get_report_cfg_defaults, get_signals_cfg_defaults, load_watchlist
from utils.config import get_report_cfg_defaults, get_signals_cfg_defaults
from .queries import recent_trading_dates_kr, load_universe_from_json, load_prices_for_dates, load_names, load_turnover_for_dates
from reporting_eod import _load_cfg, _send_notify
# signals/service.py
import os

def _load_watchlist_safe() -> List[str]:
    """
    외부 의존성 없이 스스로 해결:
      1) reporting_eod._load_watchlist() 시도
      2) 파일 후보(KRX_WATCHLIST > watchlist.yaml > conf/watchlist.yaml > ~/.config/...)
    허용 포맷:
      - ["069500","005930", ...]
      - {"codes":[...]} / {"tickers":[...]} / {"watchlist":[...]}
      - [{"code":"069500","is_active":true}, ...] (is_active=false 제외)
    """
    # 1) reporting_eod 로더 우선
    try:
        from reporting_eod import _load_watchlist as _wl
        wl = _wl()
        if wl:
            return sorted({str(x).strip() for x in wl if str(x).strip()})
    except Exception:
        pass

    # 2) 파일 후보
    cand = []
    envp = os.environ.get("KRX_WATCHLIST")
    for p in (envp, "watchlist.yaml", "conf/watchlist.yaml",
              os.path.expanduser("~/.config/krx_alertor_modular/watchlist.yaml")):
        if p:
            cand.append(p)

    try:
        import yaml
    except Exception:
        return []

    for p in cand:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    y = yaml.safe_load(f) or []
                if isinstance(y, dict):
                    lst = y.get("codes") or y.get("tickers") or y.get("watchlist") or []
                else:
                    lst = y
                out: List[str] = []
                for it in lst:
                    if isinstance(it, str):
                        c = it.strip()
                        if c: out.append(c)
                    elif isinstance(it, dict):
                        if it.get("is_active") is False:
                            continue
                        c = str(it.get("code") or it.get("ticker") or "").strip()
                        if c: out.append(c)
                return sorted(set(out))
        except Exception:
            continue
    return []

def _merge_cfg(base: Dict, overrides: Optional[Dict]) -> Dict:
    if not overrides: return base
    out = dict(base)
    for k,v in overrides.items():
        if v is not None:
            if k=="filters": out["filters"] = {**base.get("filters",{}), **(v or {})}
            else: out[k]=v
    return out

def _mean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs)/len(xs) if xs else None

def compute_daily_signals(codes: Optional[List[str]] = None,
                          overrides: Optional[Dict] = None) -> Dict[str, object]:
    """
    멀티-모멘텀 + 전략 필터(유동성/변동성/SMA 추세)
    - 병렬 금지, 휴장일에는 생성 안 함(최근 거래일 리스트 기반)
    """
    cfg = _merge_cfg(get_signals_cfg_defaults(), overrides)
    filt = cfg["filters"]
    top_n, min_abs = get_report_cfg_defaults()

    # 필요한 히스토리 길이
    need_hist = max(max(cfg["windows"]), int(filt["sma_long"]), int(filt["vol_window"])) + 1
    dates = recent_trading_dates_kr(limit=need_hist + 60)
    if not dates:  # 휴장/데이터 부족
        return {"date": None, "signals": [], "mode": cfg["mode"], "windows": cfg["windows"]}

    d0_idx = len(dates)-1
    d0 = dates[d0_idx]
    start_idx = max(0, d0_idx - need_hist + 1)
    need_dates = dates[start_idx:d0_idx+1]  # 연속 구간(평균/표준편차/SMA 계산용)

    # 유니버스 결정 부분
    if codes is None:
        if cfg.get("use_watchlist"):
            codes = _load_watchlist_safe() or []
        if not codes:
            codes = load_universe_from_json()

    names = load_names(codes)
    px_map  = load_prices_for_dates(codes, need_dates)
    tov_map = load_turnover_for_dates(codes, need_dates)

    rows: List[Dict] = []
    counts = {"insufficient_price":0, "liquidity":0, "volatility":0, "sma":0}

    for code in codes:
        series_map = px_map.get(code, {})
        closes = [series_map.get(d) for d in need_dates]  # 시간순
        if closes[-1] is None:        # 당일 종가 없어도 제외
            counts["insufficient_price"] += 1; continue
        # 수익률들(1D/5D/20D 등)
        rets = []
        ok = True
        for w in cfg["windows"]:
            idx = len(closes)-1 - int(w)
            if idx < 0 or closes[idx] is None or closes[-1] is None or closes[idx]==0:
                ok = False; break
            rets.append((closes[-1]-closes[idx])/closes[idx])
        if not ok:
            counts["insufficient_price"] += 1; continue

        # --- 유동성 필터: 평균 거래대금 ---
        passed_liq = True
        liq_avg = None
        if float(filt["min_turnover_krw"]) > 0:
            tov_series = [tov_map.get(code,{}).get(d) for d in need_dates[-int(filt["turnover_window"]):]]
            liq_avg = _mean([float(x) for x in tov_series if x is not None])
            if liq_avg is None or liq_avg < float(filt["min_turnover_krw"]):
                passed_liq = False
        if not passed_liq:
            counts["liquidity"] += 1; continue

        # --- 변동성 필터: 표준편차(일간 수익률) ---
        passed_vol = True
        if float(filt["max_vol_std"]) < 1.0:   # 1.0(=100%)면 사실상 비활성
            win = int(filt["vol_window"])
            rr = []
            for i in range(len(closes)-win, len(closes)):
                if i<=0: continue
                p0, p1 = closes[i], closes[i-1]
                if p0 is None or p1 in (None,0): continue
                rr.append((p0-p1)/p1)
            if rr:
                mu = sum(rr)/len(rr)
                var = sum((x-mu)**2 for x in rr)/len(rr)
                std = var**0.5
                if std > float(filt["max_vol_std"]):
                    passed_vol = False
            else:
                passed_vol = False
        if not passed_vol:
            counts["volatility"] += 1; continue

        # --- SMA 추세 필터 ---
        passed_sma = True
        req = str(filt["sma_require"]).lower()
        if req in ("up","down"):
            sN = int(filt["sma_short"]); lN = int(filt["sma_long"])
            s_vals = [x for x in closes[-sN:] if x is not None]
            l_vals = [x for x in closes[-lN:] if x is not None]
            if len(s_vals)<sN or len(l_vals)<lN:
                passed_sma = False
            else:
                sma_s = sum(s_vals)/sN
                sma_l = sum(l_vals)/lN
                if req=="up"   and not (sma_s >= sma_l): passed_sma = False
                if req=="down" and not (sma_s <= sma_l): passed_sma = False
        if not passed_sma:
            counts["sma"] += 1; continue

        # 점수/신호
        score = sum(r * float(wt) for r, wt in zip(rets, cfg["weights"]))
        if cfg["mode"]=="score_abs":
            thr = float(cfg["score_threshold"])
            if score >= thr: sig="BUY"
            elif score <= -thr: sig="SELL"
            else: sig="HOLD"
        else:
            sig="HOLD"  # rank 모드는 이후 라벨링

        rows.append({
            "code": code, "name": names.get(code, code), "date": d0,
            "r1": rets[0] if len(rets)>0 else None,
            "r5": rets[1] if len(rets)>1 else None,
            "r20": rets[2] if len(rets)>2 else None,
            "score": score, "signal": sig,
            "liq_avg": liq_avg,
        })

    # rank 모드 라벨링
    if cfg["mode"]=="rank":
        rows = sorted(rows, key=lambda x: x["score"], reverse=True)
        for i, row in enumerate(rows):
            if i < int(cfg["top_k"]): row["signal"]="BUY"
            elif i >= max(0, len(rows)-int(cfg["bottom_k"])): row["signal"]="SELL"
            else: row["signal"]="HOLD"
    else:
        rows = sorted(rows, key=lambda x: abs(x["score"]), reverse=True)

    return {
        "date": d0, "signals": rows, "mode": cfg["mode"],
        "windows": cfg["windows"], "weights": cfg["weights"],
        "score_threshold": float(cfg["score_threshold"]),
        "top_k": int(cfg["top_k"]), "bottom_k": int(cfg["bottom_k"]),
        "use_watchlist": bool(cfg.get("use_watchlist", False)),
        "filters": filt, "filtered_counts": counts,
        "min_abs": min_abs,
    }

def build_signals_summary(payload: Dict, top: int = 5) -> str:
    d0 = payload.get("date") or "-"
    mode = payload.get("mode")
    windows = payload.get("windows", [])
    rows: List[Dict] = payload.get("signals", [])

    buys  = [r for r in rows if r.get("signal") == "BUY"][:top]
    sells = [r for r in rows if r.get("signal") == "SELL"][:top]

    lines = []
    lines.append(f"[Signals] {d0}")
    lines.append(f"mode={mode}, windows={windows}")
    lines.append("")
    lines.append("BUY Top")
    if buys:
        for r in buys:
            lines.append(f" · {r['name']}({r['code']}): {r['score']*100:+.2f}%")
    else:
        lines.append(" · (none)")
    lines.append("")
    lines.append("SELL Top")
    if sells:
        for r in sells:
            lines.append(f" · {r['name']}({r['code']}): {r['score']*100:+.2f}%")
    else:
        lines.append(" · (none)")
    return "\n".join(lines)

def send_signals_to_telegram(payload: Dict, top: int = 5) -> bool:
    """보내기 전에 로그에 미리보기와 결과를 남긴다."""
    log = logging.getLogger(__name__)
    text = build_signals_summary(payload, top=top)
    log.info("[signals.notify] preview:\n%s", text)
    
    try:
        text = build_signals_summary(payload, top=top)
        _send_notify(text, _load_cfg())   # 텔레그램 설정 없으면 콘솔 출력
        return True
    except Exception:
        return False