import os
import sys
import warnings

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

from utils.logger import get_app_logger

"""
find_kor.py

네이버 금융 ETF API를 사용하여 지정된 등락률 이상 상승한 국내 ETF를 찾고,
현재 국내 종목풀들에 등록된 종목 / 삭제된 종목 / 신규 발견 종목으로 분류합니다.

[사용법]
python scripts/find_kor.py
"""

from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd
import requests
from pykrx import stock

from utils.settings_loader import get_ticker_type_settings, list_available_ticker_types
from utils.stock_list_io import get_deleted_etfs, get_etfs

# --- 설정 ---
MIN_CHANGE_PCT = 3.0
EXCLUDE_KEYWORDS = ["레버리지", "채권", "커버드콜", "인버스", "ETN"]
INCLUDE_KEYWORDS: list[str] = []
MIN_VOLUME = 20000


def fetch_naver_etf_data(min_change_pct: float) -> pd.DataFrame | None:
    """네이버 금융 ETF API에서 기준 이상 상승한 ETF 목록을 가져옵니다."""
    from config import NAVER_FINANCE_ETF_API_URL, NAVER_FINANCE_HEADERS

    logger = get_app_logger()

    try:
        logger.info("네이버 API에서 ETF 데이터를 가져오는 중입니다...")
        response = requests.get(NAVER_FINANCE_ETF_API_URL, headers=NAVER_FINANCE_HEADERS, timeout=5)
        response.raise_for_status()

        data = response.json()
        items = data.get("result", {}).get("etfItemList")
        if not isinstance(items, list) or not items:
            logger.warning("네이버 API 응답에 ETF 데이터가 없습니다.")
            return None

        gainers_list: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            ticker = str(item.get("itemcode", "")).strip()
            name = str(item.get("itemname", "")).strip()
            change_rate = item.get("changeRate", 0)
            volume = item.get("quant", 0)
            risefall_rate = item.get("risefallRate")
            three_month_rate = item.get("threeMonthEarnRate")
            now_val = item.get("nowVal")
            nav = item.get("nav")

            try:
                change_rate_float = float(change_rate)
                volume_int = int(volume) if volume else 0

                risefall_float = None
                if risefall_rate is not None:
                    risefall_float = float(risefall_rate)
                elif now_val is not None and nav is not None:
                    now_val_float = float(now_val)
                    nav_float = float(nav)
                    if nav_float > 0:
                        risefall_float = ((now_val_float / nav_float) - 1.0) * 100.0

                three_month_float = float(three_month_rate) if three_month_rate is not None else None

                if change_rate_float >= min_change_pct:
                    gainers_list.append(
                        {
                            "티커": ticker,
                            "종목명": name,
                            "등락률": change_rate_float,
                            "거래량": volume_int,
                            "괴리율": risefall_float,
                            "3개월수익률": three_month_float,
                        }
                    )
            except (TypeError, ValueError):
                continue

        if not gainers_list:
            logger.warning("등락률 %.2f%% 이상인 종목이 없습니다.", min_change_pct)
            return pd.DataFrame(columns=["티커", "종목명", "등락률", "거래량", "괴리율", "3개월수익률"])

        df = pd.DataFrame(gainers_list)
        logger.info("네이버 API에서 %d개 종목 데이터를 가져왔습니다.", len(df))
        return df

    except requests.exceptions.RequestException as exc:
        logger.error("네이버 API 요청 실패: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("네이버 API 데이터 처리 중 오류: %s", exc)
        return None


def get_latest_trading_day() -> str:
    """가장 최근 국내 거래일을 YYYYMMDD 형식으로 반환합니다."""
    dt = datetime.now()
    for days_back in range(10):
        date_str = (dt - timedelta(days=days_back)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(date_str, date_str, "005930")
        if not df.empty:
            return date_str
    return datetime.now().strftime("%Y%m%d")


def _load_target_types() -> list[str]:
    """국내 종목풀 목록만 동적으로 로드합니다."""
    targets: list[str] = []
    for t_id in list_available_ticker_types():
        try:
            settings = get_ticker_type_settings(t_id)
        except Exception:  # noqa: BLE001
            continue
        if str(settings.get("country_code") or "").strip().lower() == "kor":
            targets.append(t_id)
    return targets


def _print_item(item: dict[str, object], *, is_deleted: bool = False) -> None:
    ticker = str(item["티커"])
    name = str(item["종목명"])
    change_rate = float(item["등락률"])
    volume = int(item.get("거래량", 0) or 0)
    volume_str = f"{volume:,}" if volume else "N/A"
    risefall = item.get("괴리율")
    risefall_str = f"{float(risefall):+.2f}%" if risefall is not None and pd.notna(risefall) else "N/A"
    three_month = item.get("3개월수익률")
    three_month_str = f"{float(three_month):+.2f}%" if three_month is not None and pd.notna(three_month) else "아직없음"

    accounts_str = ""
    if "accounts" in item:
        accounts_str = f"[{', '.join(item['accounts'])}] "

    base_msg = (
        f"  - {accounts_str}{name} ({ticker}): "
        f"금일수익률: +{change_rate:.2f}%, 3개월: {three_month_str}, 거래량: {volume_str}, 괴리율: {risefall_str}"
    )

    if not is_deleted:
        print(base_msg)
        return

    deleted_infos = item.get("deleted_infos", [])
    parts: list[str] = []
    for info in deleted_infos:
        type_id = info.get("ticker_type", "?")
        deleted_at = info.get("deleted_at")
        deleted_reason = info.get("deleted_reason") or "사유없음"
        if hasattr(deleted_at, "strftime"):
            deleted_date = deleted_at.strftime("%Y-%m-%d")
        else:
            deleted_date = str(deleted_at or "")[:10]
        parts.append(f"[{type_id}] {deleted_date} ({deleted_reason})")

    print(f"{base_msg} | 🗑️ 삭제: {' | '.join(parts)}")


def _print_basic_item(item: dict[str, object]) -> None:
    """상승 종목 기본 목록 한 줄을 출력합니다."""
    ticker = str(item["티커"])
    name = str(item["종목명"])
    change_rate = float(item["등락률"])
    volume = int(item.get("거래량", 0) or 0)
    volume_str = f"{volume:,}" if volume else "N/A"
    risefall = item.get("괴리율")
    risefall_str = f"{float(risefall):+.2f}%" if risefall is not None and pd.notna(risefall) else "N/A"
    three_month = item.get("3개월수익률")
    three_month_str = f"{float(three_month):+.2f}%" if three_month is not None and pd.notna(three_month) else "아직없음"

    print(
        f"  - {name} ({ticker}): "
        f"금일수익률: +{change_rate:.2f}%, 3개월: {three_month_str}, 거래량: {volume_str}, 괴리율: {risefall_str}"
    )


def find_top_gainers(min_change_pct: float = MIN_CHANGE_PCT) -> None:
    """국내 ETF 상승 종목을 종목풀별 등록 상태 기준으로 분류해 출력합니다."""
    latest_day = get_latest_trading_day()
    print(f"기준일: {latest_day[:4]}-{latest_day[4:6]}-{latest_day[6:]} (ETF)")

    top_gainers = fetch_naver_etf_data(min_change_pct)
    if top_gainers is None:
        print("❌ 네이버 API에서 데이터를 가져올 수 없습니다.")
        return
    if top_gainers.empty:
        print(f"등락률 {min_change_pct:.2f}% 이상 상승한 종목이 없습니다.")
        return

    print("✅ 네이버 API 사용 (빠른 조회 성공)")

    initial_count = len(top_gainers)

    if INCLUDE_KEYWORDS:
        include_pattern = "|".join(INCLUDE_KEYWORDS)
        top_gainers = top_gainers[top_gainers["종목명"].str.contains(include_pattern, na=False)]
        filtered = initial_count - len(top_gainers)
        if filtered > 0:
            print(f"포함 키워드({', '.join(INCLUDE_KEYWORDS)})에 따라 {filtered}개 종목을 제외했습니다.")

    if EXCLUDE_KEYWORDS:
        before_exclude = len(top_gainers)
        exclude_pattern = "|".join(EXCLUDE_KEYWORDS)
        top_gainers = top_gainers[~top_gainers["종목명"].str.contains(exclude_pattern, na=False)]
        filtered = before_exclude - len(top_gainers)
        if filtered > 0:
            print(f"제외 키워드({', '.join(EXCLUDE_KEYWORDS)})에 따라 {filtered}개 종목을 제외했습니다.")

    if MIN_VOLUME > 0 and "거래량" in top_gainers.columns:
        before_volume = len(top_gainers)
        top_gainers = top_gainers[top_gainers["거래량"] >= MIN_VOLUME]
        filtered = before_volume - len(top_gainers)
        if filtered > 0:
            print(f"최소 거래량({MIN_VOLUME:,})에 따라 {filtered}개 종목을 제외했습니다.")

    if top_gainers.empty:
        print("\n필터링 후 남은 종목이 없습니다.")
        return

    target_types = _load_target_types()
    if not target_types:
        print("국내 종목풀을 찾지 못했습니다.")
        return

    print(f"등락률 {min_change_pct:.2f}% 이상 상승한 종목 {len(top_gainers)}개를 찾았습니다.")
    print()
    print("--- 상승중인 ETF 목록 ---")
    for item in sorted(top_gainers.to_dict("records"), key=lambda row: float(row.get("등락률", 0.0)), reverse=True):
        _print_basic_item(item)

    existing_tickers_map: dict[str, list[str]] = defaultdict(list)
    deleted_tickers_map: dict[str, list[dict[str, object]]] = defaultdict(list)

    for t_id in target_types:
        try:
            for item in get_etfs(t_id):
                ticker = str(item.get("ticker") or "").strip().upper()
                if ticker:
                    existing_tickers_map[ticker].append(t_id)

            for item in get_deleted_etfs(t_id):
                ticker = str(item.get("ticker") or "").strip().upper()
                if not ticker:
                    continue
                info = dict(item)
                info["ticker_type"] = t_id
                deleted_tickers_map[ticker].append(info)
        except Exception as exc:  # noqa: BLE001
            get_app_logger().warning("%s 종목 로드 중 오류 발생: %s", t_id, exc)

    my_type_list: list[dict[str, object]] = []
    deleted_list: list[dict[str, object]] = []
    new_discovery_list: list[dict[str, object]] = []

    for item in top_gainers.to_dict("records"):
        ticker = str(item["티커"]).strip().upper()
        if ticker in existing_tickers_map:
            item["accounts"] = existing_tickers_map[ticker]
            my_type_list.append(item)
        elif ticker in deleted_tickers_map:
            item["deleted_infos"] = deleted_tickers_map[ticker]
            deleted_list.append(item)
        else:
            new_discovery_list.append(item)

    print()
    print("--- 종목풀 등록 ETF 목록 ---")
    if my_type_list:
        for item in sorted(my_type_list, key=lambda row: float(row.get("등락률", 0.0)), reverse=True):
            _print_item(item)

    print()
    print("--- 삭제된 ETF 목록 ---")
    if deleted_list:
        for item in sorted(deleted_list, key=lambda row: float(row.get("등락률", 0.0)), reverse=True):
            _print_item(item, is_deleted=True)

    print()
    print("--- 신규 발견 종목 ---")
    if new_discovery_list:
        for item in sorted(new_discovery_list, key=lambda row: float(row.get("등락률", 0.0)), reverse=True):
            _print_item(item)


if __name__ == "__main__":
    find_top_gainers()
