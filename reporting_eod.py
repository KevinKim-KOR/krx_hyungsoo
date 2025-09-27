# reporting_eod.py
# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Dict
from sqlalchemy import select, func
from db import SessionLocal, PriceDaily, Security

# 옵션 의존성(없어도 동작)
try:
    import yaml
except Exception:
    yaml = None
try:
    import requests
except Exception:
    requests = None
from urllib.parse import quote_plus
from urllib.request import urlopen
import datetime as dt

MARKET_CANDIDATES = ("069500", "069500.KS")

def _load_cfg(path: str = "config.yaml") -> Dict:
    if yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def _send_notify(text: str, cfg: Optional[Dict] = None, fallback_print: bool = True) -> None:
    cfg = cfg or _load_cfg()
    tg = (cfg.get("telegram") or {})
    token, chat_id = tg.get("token"), tg.get("chat_id")
    if not (token and chat_id):
        if fallback_print:
            print(text)  # 설정 없으면 콘솔로만
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={quote_plus(text)}&disable_web_page_preview=true"
    try:
        if requests is not None:
            requests.get(url, timeout=10)
        else:
            with urlopen(url) as r:
                r.read()
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")

def _latest_two_dates(session) -> Tuple[Optional[str], Optional[str]]:
    d0 = session.execute(select(func.max(PriceDaily.date))).scalar()
    if not d0:
        return None, None
    d1 = session.execute(
        select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)
    ).scalar()
    return (str(d0), str(d1) if d1 else None)

def _returns_for_dates(session, d0: str, d1: str):
    rows0 = session.execute(
        select(PriceDaily.code, PriceDaily.close).where(PriceDaily.date == d0)
    ).all()
    rows1 = session.execute(
        select(PriceDaily.code, PriceDaily.close).where(PriceDaily.date == d1)
    ).all()
    px0 = {c: (float(x) if x is not None else None) for c, x in rows0}
    px1 = {c: (float(x) if x is not None else None) for c, x in rows1}
    codes = sorted(set(px0) & set(px1))

    # 종목명(없어도 안전)
    try:
        name_rows = session.execute(select(Security.code, Security.name)).all()
        names: Dict[str, str] = dict(name_rows)
    except Exception:
        names = {}

    data: List[Dict[str, float]] = []
    for code in codes:
        p0, p1 = px0.get(code), px1.get(code)
        if p0 is None or p1 is None or p1 == 0:
            continue
        ret = (p0 - p1) / p1
        data.append({"code": code, "name": names.get(code, code), "ret": ret})

    # 시장 지표
    mkt = None
    for c in MARKET_CANDIDATES:
        mkt = next((x for x in data if x["code"] == c), None)
        if mkt:
            break
    return data, mkt

def _fmt_pct(x: float) -> str:
    return f"{x*100:+.2f}%"

def _arrow(x: float) -> str:
    return "▲" if x > 0 else ("▼" if x < 0 else "→")

def _load_report_cfg_defaults():
    cfg = _load_cfg()
    r = (cfg.get("report") or {}) if isinstance(cfg, dict) else {}
    try:
        top_n = int(r.get("top_n", 5))
    except Exception:
        top_n = 5
    try:
        min_abs = float(r.get("min_abs_ret", 0.003))  # 0.3%
    except Exception:
        min_abs = 0.003
    return top_n, min_abs


def _compose_message(d0: str, d1: str, data: List[Dict], mkt: Optional[Dict]) -> str:
    if not data:
        return f"[KRX EOD Report] {d0}\n데이터가 없습니다."

    top_n, min_abs = _load_report_cfg_defaults()

    # 임계치 필터 적용
    pos = [x for x in data if x.get("ret") is not None and x["ret"] >=  min_abs]
    neg = [x for x in data if x.get("ret") is not None and x["ret"] <= -min_abs]

    winners = sorted(pos, key=lambda x: x["ret"], reverse=True)[:top_n]
    losers  = sorted(neg, key=lambda x: x["ret"])[:top_n]

    # 시장 라인
    if mkt and mkt.get("ret") is not None:
        mkt_line = f"시장(069500): {_fmt_pct(mkt['ret'])} {_arrow(mkt['ret'])}"
    else:
        mkt_line = "시장(069500): N/A"

    lines = []
    lines.append(f"[KRX EOD Report] {d0}")
    lines.append(mkt_line)
    lines.append(f"커버리지: {len(data)} 종목 (전일 {d1} 대비)")
    lines.append("")

    # 상승
    lines.append(f"상승 Top {len(winners)} (≥ {min_abs*100:.1f}%)" if winners else f"상승 없음 (≥ {min_abs*100:.1f}%)")
    for x in winners:
        lines.append(f" · {_arrow(x['ret'])} {x['name']} ({x['code']}): {_fmt_pct(x['ret'])}")
    lines.append("")

    # 하락
    lines.append(f"하락 Top {len(losers)} (≥ {min_abs*100:.1f}%)" if losers else f"하락 없음 (≥ {min_abs*100:.1f}%)")
    for x in losers:
        lines.append(f" · {_arrow(x['ret'])} {x['name']} ({x['code']}): {_fmt_pct(x['ret'])}")

    return "\n".join(lines)


# === Watchlist Report (append) ===============================================

def _load_watchlist(path: str = "watchlist.yaml") -> List[str]:
    if yaml is None:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return []
    for key in ("watchlist", "basket", "codes"):
        if key in cfg and isinstance(cfg[key], list):
            wl = [str(x).strip() for x in cfg[key] if str(x).strip()]
            return wl
    return []

def _norm(code: str) -> str:
    return code.replace(".KS", "")

def generate_and_send_watchlist_report(target_date: Optional[str] = "auto",
                                       watchlist_path: str = "watchlist.yaml") -> int:
    wl = _load_watchlist(watchlist_path)
    if not wl:
        text = "[KRX Watchlist EOD] watchlist.yaml 비어있음(또는 없음) — 스킵"
        print(text)
        _send_notify(text, _load_cfg(), fallback_print=False)
        return 0

    wl_set = set(_norm(c) for c in wl)

    with SessionLocal() as session:
        if target_date and target_date != "auto":
            d0 = target_date
            d1 = session.execute(
                select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)
            ).scalar()
            d1 = str(d1) if d1 else None
        else:
            d0, d1 = _latest_two_dates(session)

        if not d0 or not d1:
            text = f"[KRX Watchlist EOD] 데이터 부족으로 스킵 (d0={d0}, d1={d1})"
            print(text)
            _send_notify(text, _load_cfg(), fallback_print=False)
            return 0

        # 전체 수익률 표에서 watchlist만 필터
        data, mkt = _returns_for_dates(session, d0, d1)
        basket = [x for x in data if (_norm(x["code"]) in wl_set or x["code"] in wl_set)]
        if not basket:
            text = f"[KRX Watchlist EOD] {d0}\nwatchlist 매칭 종목이 없습니다."
            print(text)
            _send_notify(text, _load_cfg(), fallback_print=False)
            return 0

        pos = [x for x in basket if x.get("ret") is not None and x["ret"] > 0]
        neg = [x for x in basket if x.get("ret") is not None and x["ret"] < 0]
        winners = sorted(pos, key=lambda x: x["ret"], reverse=True)[:5]
        losers  = sorted(neg, key=lambda x: x["ret"])[:5]

        avg_ret = None
        try:
            avg_ret = sum(x["ret"] for x in basket) / len(basket)
        except Exception:
            pass

        lines = []
        lines.append(f"[KRX Watchlist EOD] {d0}")
        if avg_ret is not None:
            lines.append(f"바스켓 평균: {_fmt_pct(avg_ret)}  (커버: {len(basket)}/{len(wl)})")
        else:
            lines.append(f"커버: {len(basket)}/{len(wl)}")
        lines.append("")
        lines.append(f"상승 Top {len(winners)}")
        for x in winners:
            lines.append(f" · {x['name']} ({x['code']}): {_fmt_pct(x['ret'])}")
        lines.append("")
        lines.append(f"하락 Top {len(losers)}")
        for x in losers:
            lines.append(f" · {x['name']} ({x['code']}): {_fmt_pct(x['ret'])}")
        text = "\n".join(lines)

        print(text)  # 로그 1회
        _send_notify(text, _load_cfg(), fallback_print=False)
        return 0

# ---- EXIT CODE 참고 ----
# 0: 성공 또는 정상 스킵(휴장/데이터 없음 통지)
# 1: 예외/치명적 오류
# 2: 지연 데이터(오늘 평일인데 d0 < 오늘) -> 재시도 대상
# ------------------------

def _is_weekday(d: dt.date) -> bool:
    return d.weekday() < 5  # 0~4: 월~금

def generate_and_send_report_eod(target_date: Optional[str] = "auto",
                                 expect_today: bool = True) -> int:
    """
    target_date: 'YYYY-MM-DD' | 'auto'
    expect_today: 평일에는 오늘 데이터가 들어오길 기대(지연시 EXIT 2)
    """
    try:
        today = dt.date.today()
        with SessionLocal() as session:
            if target_date and target_date != "auto":
                d0 = target_date
                d1 = session.execute(
                    select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)
                ).scalar()
                d1 = str(d1) if d1 else None
            else:
                d0, d1 = _latest_two_dates(session)

            # 지연 감지: 평일이며 expect_today=True, 그리고 d0가 오늘보다 과거
            if expect_today and _is_weekday(today):
                if d0 is None or d0 < str(today):
                    text = f"[KRX EOD Report] 지연 감지: 최신일={d0}, 오늘={today} -> 재시도 권장"
                    print(text)
                    _send_notify(text, _load_cfg(), fallback_print=False)
                    return 2  # STALE_DATA

            if not d0 or not d1:
                text = f"[KRX EOD Report] 데이터 부족으로 스킵 (d0={d0}, d1={d1})"
                print(text)
                _send_notify(text, _load_cfg(), fallback_print=False)
                return 0

            data, mkt = _returns_for_dates(session, d0, d1)
            text = _compose_message(d0, d1, data, mkt)
            print(text)  # 로그 1회
            _send_notify(text, _load_cfg(), fallback_print=False)
            return 0
    except Exception as e:
        # 에러 메시지 간결/표준화
        print(f"[KRX EOD Report] ERROR: {e}")
        _send_notify(f"[KRX EOD Report] ❗ 실패: {e}", _load_cfg(), fallback_print=False)
        return 1