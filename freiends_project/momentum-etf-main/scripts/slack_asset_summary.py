#!/usr/bin/env python
"""
Total Asset Summary Slack Notifier.
Aggregates data from all accounts and sends a summary message to Slack,
with detailed accounts and portfolio composition in a threaded reply.
"""

import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.account_registry import load_account_configs
from utils.db_manager import get_db_connection
from utils.env import load_env_if_present
from utils.notification import send_slack_message_v2
from utils.portfolio_io import (
    MissingPriceCacheError,
    get_latest_daily_snapshot,
    load_portfolio_master,
    load_real_holdings_table,
    save_daily_snapshot,
)
from utils.report import format_kr_money

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


format_korean_currency = format_kr_money
WEEKLY_COLLECTION = "weekly_fund_data"
INITIAL_TOTAL_PRINCIPAL_DATE = "2024-01-31"
INITIAL_TOTAL_PRINCIPAL_VALUE = 56_000_000
KST = ZoneInfo("Asia/Seoul")


def get_trend_emoji(val):
    if val > 0:
        return ":small_red_triangle:"
    elif val < 0:
        return ":chart_with_downwards_trend:"
    return ""


def _to_int(value):
    return int(value or 0)


def _calculate_total_expense(doc):
    return (
        _to_int(doc.get("withdrawal_personal", 0))
        + _to_int(doc.get("withdrawal_mom", 0))
        + _to_int(doc.get("nh_principal_interest", 0))
    )


def _load_latest_weekly_metrics():
    """주별 데이터 테이블과 동일한 정의로 최신 주간 손익 지표를 계산한다."""
    db = get_db_connection()
    if db is None:
        raise RuntimeError("DB 연결 실패로 주별 데이터를 조회할 수 없습니다.")

    docs = list(db[WEEKLY_COLLECTION].find().sort("week_date", 1))
    if not docs:
        raise RuntimeError("weekly_fund_data 데이터가 없어 주간 손익을 계산할 수 없습니다.")

    running_total_principal = INITIAL_TOTAL_PRINCIPAL_VALUE
    running_total_expense = 0
    previous_cumulative_profit = 0
    latest_metrics = None

    for doc in docs:
        week_date = str(doc.get("week_date") or "").strip()
        if not week_date:
            raise RuntimeError("weekly_fund_data에 week_date가 비어 있는 행이 있습니다.")

        if week_date <= INITIAL_TOTAL_PRINCIPAL_DATE:
            total_principal = INITIAL_TOTAL_PRINCIPAL_VALUE
        else:
            running_total_principal += _to_int(doc.get("deposit_withdrawal", 0))
            total_principal = running_total_principal

        running_total_expense += _calculate_total_expense(doc)
        total_assets = _to_int(doc.get("total_assets", 0))
        cumulative_profit = total_assets - total_principal - running_total_expense
        weekly_profit = cumulative_profit - previous_cumulative_profit

        latest_metrics = {
            "week_date": week_date,
            "weekly_profit": weekly_profit,
            "weekly_return_pct": (weekly_profit / total_principal * 100) if total_principal else 0.0,
            "cumulative_profit": cumulative_profit,
            "cumulative_return_pct": (cumulative_profit / total_principal * 100) if total_principal else 0.0,
        }
        previous_cumulative_profit = cumulative_profit

    if latest_metrics is None:
        raise RuntimeError("주간 손익 계산 결과를 만들지 못했습니다.")

    return latest_metrics


def _build_missing_cache_alert(account_id: str, tickers: list[str]) -> str:
    ticker_text = ", ".join(tickers)
    return (
        f"⚠️ 자산 요약 발송 중단 ({account_id})\n"
        f"가격 캐시가 없는 보유 종목: {ticker_text}\n"
        f"종목 관리에서 해당 종목의 메타/캐시 새로고침을 실행하세요."
    )


def main():
    load_env_if_present()

    accounts = load_account_configs()
    if not accounts:
        logger.error("No account configurations found.")
        return

    all_holdings_dict = {}
    account_summaries = []
    global_principal = 0.0
    global_cash = 0.0
    total_purchase = 0.0

    logger.info("Aggregating data from %d accounts...", len(accounts))

    for account in accounts:
        account_id = account["account_id"]
        if not account.get("settings", {}).get("show_hold", True):
            continue

        account_name = account.get("name") or account_id.upper()

        # Load principal and cash
        m_data = load_portfolio_master(account_id)
        if m_data:
            global_principal += m_data.get("total_principal", 0.0)
            global_cash += m_data.get("cash_balance", 0.0)

        # Load holdings
        try:
            # 일부 공용 유틸이 환경 설정을 필요로 할 수 있어 예외를 명확히 처리한다.
            df = load_real_holdings_table(account_id, strict_price_cache=True)
        except MissingPriceCacheError as e:
            alert_msg = _build_missing_cache_alert(account_id, e.tickers)
            logger.error(alert_msg)
            send_slack_message_v2(alert_msg)
            sys.exit(1)
        except Exception as e:
            error_msg = f"❌ 자산 요약 생성 중 치명적 에러 발생 ({account_id} 계좌):\n```{e}```\n\n잘못된 자산 리포트가 발송되는 것을 방지하기 위해 오늘 알림을 중단합니다."
            logger.error(error_msg)
            send_slack_message_v2(error_msg)
            sys.exit(1)

        acc_valuation = 0.0
        acc_purchase = 0.0
        if df is not None and not df.empty:
            all_holdings_dict[account_id] = df
            acc_valuation = df["평가금액(KRW)"].sum()
            acc_purchase = df["매입금액(KRW)"].sum()

        acc_principal = m_data.get("total_principal", 0.0) if m_data else 0.0
        acc_cash = m_data.get("cash_balance", 0.0) if m_data else 0.0
        acc_total_assets = acc_valuation + acc_cash
        acc_net_profit = acc_total_assets - acc_principal
        acc_net_profit_pct = (acc_net_profit / acc_principal * 100) if acc_principal > 0 else 0.0

        acc_stock_profit = acc_valuation - acc_purchase
        acc_stock_profit_pct = (acc_stock_profit / acc_purchase * 100) if acc_purchase > 0 else 0.0

        if acc_principal > 0 or acc_cash > 0 or acc_valuation > 0:
            account_summaries.append(
                {
                    "account_id": account_id,
                    "name": account_name,
                    "principal": acc_principal,
                    "total_assets": acc_total_assets,
                    "net_profit": acc_net_profit,
                    "net_profit_pct": acc_net_profit_pct,
                    "valuation": acc_valuation,
                    "stock_profit": acc_stock_profit,
                    "stock_profit_pct": acc_stock_profit_pct,
                    "cash": acc_cash,
                }
            )
            total_purchase += acc_purchase

    if not account_summaries:
        logger.warning("No data found to report.")
        return

    # Global Calculations
    total_assets = sum(acc["total_assets"] for acc in account_summaries)

    # Fetch previous snapshots
    prev_global = get_latest_daily_snapshot("TOTAL", before_today=True)
    global_change = 0.0
    global_change_pct = 0.0
    if prev_global:
        prev_total = prev_global.get("total_assets", 0.0)
        if prev_total > 0:
            global_change = total_assets - prev_total
            global_change_pct = (global_change / prev_total) * 100

    weekly_metrics = _load_latest_weekly_metrics()
    cash_pct = (global_cash / total_assets * 100) if total_assets > 0 else 0.0

    # 1. Compose Main Message (Total Summary)
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    main_text = (
        f"*📊 총 자산 요약 ({now_str})*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *총 자산*: *{format_korean_currency(total_assets)}*\n"
        f"🏛️ *투자 원금*: {format_korean_currency(global_principal)}\n"
        f"💵 *현금 잔고*: {format_korean_currency(global_cash)} ({cash_pct:.1f}%)\n"
        f"📆 *금일 손익*: {format_korean_currency(global_change)} ({global_change_pct:+.2f}%) {get_trend_emoji(global_change)}\n"
        f"🗓️ *금주 손익*: {format_korean_currency(weekly_metrics['weekly_profit'])} ({weekly_metrics['weekly_return_pct']:+.2f}%) {get_trend_emoji(weekly_metrics['weekly_profit'])}\n"
        f"🏁 *누적 손익*: *{format_korean_currency(weekly_metrics['cumulative_profit'])} ({weekly_metrics['cumulative_return_pct']:+.2f}%)* {get_trend_emoji(weekly_metrics['cumulative_profit'])}\n"
    )

    main_ts = send_slack_message_v2(main_text)
    if not main_ts:
        logger.error("Failed to send main Slack message.")
        return

    # 2. Compose Account Details (Thread)
    acc_details = ["*📂 계좌별 상세 현황*"]
    for acc in account_summaries:
        # Fetch previous account snapshot
        prev_acc = get_latest_daily_snapshot(acc["account_id"], before_today=True)
        acc_change = 0.0
        acc_change_pct = 0.0
        if prev_acc:
            prev_acc_total = prev_acc.get("total_assets", 0.0)
            if prev_acc_total > 0:
                acc_change = acc["total_assets"] - prev_acc_total
                acc_change_pct = (acc_change / prev_acc_total) * 100

        emoji = get_trend_emoji(acc["net_profit"])
        change_emoji = get_trend_emoji(acc_change)
        acc_cash_pct = (acc["cash"] / acc["total_assets"] * 100) if acc["total_assets"] > 0 else 0.0
        line = (
            f"• *{acc['name']}*\n"
            f"  - 자산: {format_korean_currency(acc['total_assets'])} (원금: {format_korean_currency(acc['principal'])})\n"
            f"  - 누적수익: {emoji} {acc['net_profit_pct']:+.2f}% ({format_korean_currency(acc['net_profit'])})\n"
            f"  - 금일변동: {change_emoji} {acc_change_pct:+.2f}% ({format_korean_currency(acc_change)})\n"
            f"  - 현금: {format_korean_currency(acc['cash'])} ({acc_cash_pct:.1f}%)"
        )
        acc_details.append(line)

    send_slack_message_v2("\n\n".join(acc_details), thread_ts=main_ts)

    # 3. Compose Portfolio Composition (Thread)
    if all_holdings_dict:
        combined_df = pd.concat(all_holdings_dict.values(), ignore_index=True)
        bucket_cols = ["1. 모멘텀", "2. 시장지수", "3. 배당방어", "4. 대체헷지"]
        comp_details = ["*🏗️ 포트폴리오 구성 비중*"]

        for b in bucket_cols:
            b_val = combined_df.loc[combined_df["버킷"] == b, "평가금액(KRW)"].sum()
            b_pct = (b_val / total_assets * 100) if total_assets > 0 else 0.0
            comp_details.append(f"• {b}: {b_pct:.1f}%")

        cash_pct = (global_cash / total_assets * 100) if total_assets > 0 else 0.0
        comp_details.append(f"• 5. 현금: {cash_pct:.1f}%")

        send_slack_message_v2("\n".join(comp_details), thread_ts=main_ts)

    # 4. Compose Account Cash Ratio (Thread)
    cash_ratio_details = ["*💵 계좌별 현금 비율*"]
    for acc in account_summaries:
        acc_cash_pct = (acc["cash"] / acc["total_assets"] * 100) if acc["total_assets"] > 0 else 0.0
        cash_ratio_details.append(f"• {acc['name']}: {acc_cash_pct:.1f}%")

    send_slack_message_v2("\n".join(cash_ratio_details), thread_ts=main_ts)

    # 5. Save Snapshots for next time (Consolidated)
    # Save individual accounts first, then TOTAL (which updates the same document for today)
    for acc in account_summaries:
        # 계좌별 실보유 종목 추출 (티커, 보유주수 정수값)
        holding_list = []
        target_df = all_holdings_dict.get(acc["account_id"])
        if target_df is not None:
            for _, row in target_df.iterrows():
                ticker = str(row.get("티커", "")).strip().upper()
                if ticker and ticker != "IS": # International Shares 등 가상 종목 제외
                    holding_list.append({
                        "ticker": ticker,
                        "days_held_int": int(row.get("days_held_int", 1))
                    })

        save_daily_snapshot(
            acc["account_id"],
            acc["total_assets"],
            acc["principal"],
            acc["cash"],
            acc["valuation"],
            acc.get("valuation", 0.0) - acc.get("stock_profit", 0.0),
            holding_details=holding_list
        )

    save_daily_snapshot(
        "TOTAL", total_assets, global_principal, global_cash, total_assets - global_cash, total_purchase
    )

    logger.info("Slack asset summary sent successfully.")


if __name__ == "__main__":
    main()
