import os
import sys

# 현재 디렉토리를 파이썬 경로에 추가하여 utils 등을 임포트할 수 있게 함
sys.path.append(os.getcwd())

import warnings

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from utils.notification import send_slack_message_v2

# 사용자 종목풀 정보 로드 모듈
from utils.settings_loader import get_ticker_type_settings, list_available_ticker_types
from utils.stock_list_io import get_etfs

# 환경 변수 로드
load_dotenv()

# yfinance 버전 업데이트 경고숨김 처리
warnings.simplefilter(action="ignore", category=FutureWarning)


class OutputCollector:
    """print() 출력을 가로채서 문자열로 모으는 헬퍼 클래스"""

    def __init__(self, slack_mode=False):
        self.buffer = []
        self.slack_mode = slack_mode

    def print(self, *args, **kwargs):
        msg = " ".join(map(str, args))
        print(msg, **kwargs)
        if self.slack_mode:
            self.buffer.append(msg)

    def get_full_text(self):
        return "\n".join(self.buffer)


def get_yfinance_5min_stats(code, name, country="kor", period="1mo"):
    """
    단일 종목의 5분봉 데이터를 분석하여
    (출력용 텍스트, 시간대별 통계 DataFrame) 을 반환합니다.
    """
    if country == "au":
        symbol = f"{code}.AX"
    else:
        symbol = f"{code}.KS"

    # 모든 시간을 한국 시간(Asia/Seoul)으로 통일
    tz_name = "Asia/Seoul"

    try:
        # progress=False로 지저분한 로그 방지
        df = yf.download(symbol, period=period, interval="5m", progress=False)
    except Exception:
        return f" - {code}\t{name} - 데이터 통신 오류 발생", None

    if df.empty:
        return f" - {code}\t{name} - 데이터를 찾을 수 없습니다.", None

    # MultiIndex 대응
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df.columns = df.columns.droplevel("Ticker")
            df.columns.name = None
        except KeyError:
            pass

    # 시간대 한국 강제 변환
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(tz_name)

    df["Date"] = df.index.date
    df["Time"] = df.index.strftime("%H:%M")

    open_p = df["Open"].iloc[:, 0] if isinstance(df["Open"], pd.DataFrame) else df["Open"]
    close_p = df["Close"].iloc[:, 0] if isinstance(df["Close"], pd.DataFrame) else df["Close"]

    df["Open_Single"] = open_p
    df["Close_Single"] = close_p

    daily_open = df.groupby("Date")["Open_Single"].first()
    df["Daily_Open_Price"] = df["Date"].map(daily_open)

    # 시가 대비 등락률 계산
    df["Pct_Change_From_Open"] = ((df["Close_Single"] - df["Daily_Open_Price"]) / df["Daily_Open_Price"]) * 100
    df = df.dropna(subset=["Pct_Change_From_Open"])

    if df.empty:
        return f" - {code}\t{name} - 계산 가능한 유효 데이터가 없습니다.", None

    # 시간대별 통계 계산
    time_stats = df.groupby("Time")["Pct_Change_From_Open"].mean().reset_index()

    best_buy = time_stats.sort_values(by="Pct_Change_From_Open").iloc[0]
    best_sell = time_stats.sort_values(by="Pct_Change_From_Open", ascending=False).iloc[0]

    res_str = (
        f" - {code}\t{name:<15} - "
        f"최적 매수 시간: {best_buy['Time']} (평균 {best_buy['Pct_Change_From_Open']:+.3f}%), "
        f"최적 매도 시간: {best_sell['Time']} (평균 {best_sell['Pct_Change_From_Open']:+.3f}%)"
    )
    return res_str, time_stats


if __name__ == "__main__":
    # 항상 슬랙으로 결과를 전송합니다.
    collector = OutputCollector(slack_mode=True)

    collector.print(
        "[분석 시작] 국가별 최근 1개월 간의 5분봉 데이터를 수집 중입니다. (종목 수가 많아 약 1~2분 소요될 수 있습니다)\n"
    )

    try:
        ticker_types = list_available_ticker_types()
    except Exception as e:
        collector.print("종목풀 정보를 불러오지 못했습니다:", e)
        sys.exit(1)

    type_list = sorted(ticker_types)

    all_time_stats = {"kor": {}, "au": {}}
    account_outputs = []
    # 통계용 국가별 정보
    meta_info = {"kor": {"ticker_types": set()}, "au": {"ticker_types": set()}}

    # 다운로드 중복 방지 캐시: {code: (res_str, stats_df)}
    cached_stats = {}

    # 1. 모든 종목풀에서 국가별 정보를 먼저 수집
    for t_id in type_list:
        settings = get_ticker_type_settings(t_id)
        country = settings.get("country_code", "").lower()
        if country in ["kor", "au"]:
            meta_info[country]["ticker_types"].add(t_id)
            # 타입별 출력물 생성
            acc_name = settings.get("name", t_id)
            lines = [f"● {acc_name} ({t_id})"]
            etfs = get_etfs(t_id)
            if not etfs:
                lines.append(" - (등록된 종목이 없습니다)")
            else:
                for etf in etfs:
                    code = etf.get("ticker", "")
                    name = etf.get("name", "Unknown")
                    if code:
                        if code not in cached_stats:
                            res_str, stats_df = get_yfinance_5min_stats(
                                code=code, name=name, country=country, period="1mo"
                            )
                            cached_stats[code] = (res_str, stats_df)
                            if stats_df is not None:
                                all_time_stats[country][code] = stats_df

                        res_str, _ = cached_stats[code]
                        lines.append(res_str)
            lines.append("")
            account_outputs.append("\n".join(lines))

    # 2. 종합 통계 산출 및 최상단 출력
    header_lines = []
    header_separator = "=" * 60
    header_lines.append(header_separator)
    for c_code, c_name in [("kor", "한국 시장"), ("au", "호주 시장")]:
        stats_dict = all_time_stats[c_code]
        if stats_dict:
            combined_stats = pd.concat(list(stats_dict.values()))
            global_stats = combined_stats.groupby("Time")["Pct_Change_From_Open"].mean().reset_index()

            global_best_buy = global_stats.sort_values(by="Pct_Change_From_Open").iloc[0]
            global_best_sell = global_stats.sort_values(by="Pct_Change_From_Open", ascending=False).iloc[0]

            n_stocks = len(stats_dict)
            n_types = len(meta_info[c_code]["ticker_types"])
            header_lines.append(f"🏆 [{c_name} 평균] 총 {n_stocks}개 종목 평균({n_types}개 종목풀)")
            header_lines.append(
                f"👉 전체 최적 매수 시간 : {global_best_buy['Time']} (평균 {global_best_buy['Pct_Change_From_Open']:+.3f}%)"
            )
            header_lines.append(
                f"👉 전체 최적 매도 시간 : {global_best_sell['Time']} (평균 {global_best_sell['Pct_Change_From_Open']:+.3f}%)\n"
            )
    header_lines.append(header_separator + "\n")

    for hl in header_lines:
        collector.print(hl)

    # 3. 개별 종목풀 결과 출력
    for out in account_outputs:
        collector.print(out)

    # 4. 슬랙 전송
    full_text = collector.get_full_text()
    # 마크다운 코드 블록으로 감싸서 가독성 확보
    slack_msg = f"*🕒 국가별/종목풀별 최적 매매 시간 분석 요약*\n```\n{full_text}\n```"
    send_slack_message_v2(slack_msg)
    print("\n[알림] 분석 결과가 슬랙으로 전송되었습니다.")
