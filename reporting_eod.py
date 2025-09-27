# reporting_eod.py  (PC에서 수정)
# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Dict
from sqlalchemy import select, func
from db import SessionLocal, PriceDaily, Security
from scanner import load_config_yaml
from notifications import send_notify

# DB에 저장된 코드 포맷이 종종 '069500' 형태입니다.
# 혹시 '.KS'로 저장되어 있다면 아래 후보 둘 다 체크해서 잡습니다.
MARKET_CANDIDATES = ("069500", "069500.KS")

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

    # 종목명 매핑(있으면)
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
        data.append({
            "code": code,
            "name": names.get(code, code),
            "ret": ret
        })

    # 시장 지표(두 가지 코드 포맷 모두 탐색)
    mkt = None
    for c in MARKET_CANDIDATES:
        mkt = next((x for x in data if x["code"] == c), None)
        if mkt:
            break
    return data, mkt

def _fmt_pct(x: float) -> str:
    return f"{x*100:+.2f}%"

def _compose_message(d0: str, d1: str, data: List[Dict], mkt: Optional[Dict]) -> str:
    if not data:
        return f"[KRX EOD Report] {d0}\n데이터가 없습니다."
    data_sorted = sorted(data, key=lambda x: x["ret"])
    losers = data_sorted[:5]
    winners = list(reversed(data_sorted[-5:]))

    lines = []
    lines.append(f"[KRX EOD Report] {d0}")
    lines.append(f"커버리지: {len(data)} 종목 (전일 {d1} 대비)")
    lines.append(f"시장(069500): {_fmt_pct(mkt['ret']) if mkt else 'N/A'}")
    lines.append("")
    lines.append("상승 Top 5")
    for x in winners:
        lines.append(f" · {x['name']} ({x['code']}): {_fmt_pct(x['ret'])}")
    lines.append("")
    lines.append("하락 Top 5")
    for x in losers:
        lines.append(f" · {x['name']} ({x['code']}): {_fmt_pct(x['ret'])}")
    return "\n".join(lines)

def generate_and_send_report_eod(target_date: Optional[str] = "auto") -> int:
    """DB 최신일(d0)과 그 전일(d1) 비교 Top5 요약 → 텔레그램/슬랙 전송"""
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
            msg = f"[KRX EOD Report] 데이터 부족으로 스킵 (d0={d0}, d1={d1})"
            print(msg)
            cfg = load_config_yaml("config.yaml")
            send_notify(msg, cfg)
            return 0

        data, mkt = _returns_for_dates(session, d0, d1)
        text = _compose_message(d0, d1, data, mkt)
        print(text)
        cfg = load_config_yaml("config.yaml")
        send_notify(text, cfg)
        return 0
