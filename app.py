# -*- coding: utf-8 -*-
"""
app.py
- ETF 데이터 수집/리포트/전략 실행 CLI
"""

import argparse
import pandas as pd
from db import init_db, SessionLocal, Security, Position
from fetchers import ingest_eod, ingest_realtime_once
# 지연 임포트: report 커맨드에서만 사용
try:
    from analyzer import make_report  # optional at import time
except Exception:
    make_report = None

from scanner import recommend_buy_sell, load_config_yaml
# --- compat wrapper: route legacy send_slack() to new send_notify() ---
from notifications import send_notify
def send_slack(text, webhook):
    cfg = load_config_yaml("config.yaml")
    return send_notify(text, cfg)

from backtest import run_backtest
from sector_autotag import autotag_sectors
from notifications import send_notify
import logging, os
from logging.handlers import RotatingFileHandler

from calendar_kr import is_trading_day, next_trading_day, load_trading_days


# -----------------------------
# 명령어 핸들러
# -----------------------------

def cmd_init(args):
    """DB 초기화 및 시드 로드"""
    init_db()
    print("DB 초기화 완료")

def cmd_ingest_eod(args):
    """일별 종가 수집"""
    asof = pd.to_datetime(pd.Timestamp.today().date() if args.date == "auto" else args.date)
    load_trading_days(asof)
    if not is_trading_day(asof):
        log.info(f"[INGEST] 휴장일 {asof.date()} → 수집 스킵")
        print(f"[SKIP] 휴장일 {asof.date()} — ingest-eod 생략")
        return
    ingest_eod(asof.strftime("%Y-%m-%d"))


def cmd_ingest_realtime(args):
    """실시간 가격 수집 (단발 실행)"""
    ingest_realtime_once(args.code)

def cmd_report(args):
    """기간 성과 리포트"""
    global make_report
    # 지연 임포트: report 커맨드가 실제로 호출될 때만 analyzer 로드
    if make_report is None:
        try:
            from analyzer import make_report as _make_report
            make_report = _make_report
        except Exception as e:
            print(f"[ERROR] analyzer.make_report 임포트 실패: {e}")
            print("→ requirements / analyzer.py 를 확인하세요. "
                  "init·autotag·scanner 명령에는 영향 없습니다.")
            return
    # 실제 실행
    make_report(start=args.start, end=args.end, benchmark=args.benchmark)

def cmd_scanner(args):
    """BUY/SELL 추천"""
    asof = pd.to_datetime(args.date)
    load_trading_days(asof)
    if not is_trading_day(asof):
        log.info(f"[SCANNER] 휴장일 {asof.date()} → 스캐너 스킵")
        print(f"[SKIP] 휴장일 {asof.date()} — scanner 생략")
        return
    
    cfg = load_config_yaml("config.yaml")
    buy_df, sell_df, meta = recommend_buy_sell(asof=args.date, cfg=cfg)

    print(f"\n기준일: {meta['asof'].date()} (ETF)")
    print(f"레짐 상태: {'ON(투자 가능)' if meta['regime_ok'] else 'OFF(투자 중단)'}")
    print(f"유니버스 크기: {meta['universe_size']} → 조건 충족: {meta['after_filters']} 종목\n")

    if buy_df is not None and not buy_df.empty:
        print("--- BUY 추천 TOP N ---")
        for _, row in buy_df.iterrows():
            print(f"  - {row['code']} (섹터:{row['sector']}): 점수 {row['score']:.1f}, "
                  f"1일 {row['ret1']*100:.2f}%, 20일 {row['ret20']*100:.2f}%, "
                  f"60일 {row['ret60']*100:.2f}%, ADX {row['adx']:.1f}, "
                  f"MFI {row['mfi']:.1f}, VolZ {row['volz']:.2f}")
    else:
        print("BUY 추천 없음")

    if sell_df is not None and not sell_df.empty:
        print("\n--- SELL 추천 (보유 종목 중 조건 위반) ---")
        for _, row in sell_df.iterrows():
            print(f"  - {row['code']}: {row['reason']} "
                  f"(close={row['close']}, sma50={row['sma50']}, sma200={row['sma200']})")
    else:
        print("\nSELL 추천 없음")

def cmd_scanner_slack(args):
    """BUY/SELL 추천 + Slack 알림 전송"""
    asof = pd.to_datetime(args.date)
    load_trading_days(asof)
    if not is_trading_day(asof):
        log.info(f"[SCANNER] 휴장일 {asof.date()} → 슬랙 전송도 스킵")
        print(f"[SKIP] 휴장일 {asof.date()} — scanner-slack 생략")
        return
    
    cfg = load_config_yaml("config.yaml")
    buy_df, sell_df, meta = recommend_buy_sell(asof=args.date, cfg=cfg)

    header = f"*[KRX Scanner]* {meta['asof'].date()}  |  레짐: {'ON' if meta['regime_ok'] else 'OFF'}  |  유니버스: {meta['universe_size']}  |  조건충족: {meta['after_filters']}"
    lines = [header, ""]  # 빈 줄

    # BUY
    if buy_df is not None and not buy_df.empty:
        lines.append("*BUY 추천 TOP N*")
        for _, row in buy_df.iterrows():
            lines.append(
                f"- `{row['code']}` [{row['sector']}] 점수 {row['score']:.1f} | "
                f"1D {row['ret1']*100:.2f}% / 20D {row['ret20']*100:.2f}% / 60D {row['ret60']*100:.2f}% | "
                f"ADX {row['adx']:.1f} / MFI {row['mfi']:.1f} / VolZ {row['volz']:.2f}"
            )
    else:
        lines.append("_BUY 추천 없음_")

    lines.append("")  # 빈 줄

    # SELL
    if sell_df is not None and not sell_df.empty:
        lines.append("*SELL 추천 (보유 위반)*")
        for _, row in sell_df.iterrows():
            lines.append(
                f"- `{row['code']}`: {row['reason']} "
                f"(close={row['close']}, SMA50={row['sma50']}, SMA200={row['sma200']})"
            )
    else:
        lines.append("_SELL 추천 없음_")

    text = "\n".join(lines)

    webhook = (cfg.get("ui", {}) or {}).get("slack_webhook", "")
    ok = send_slack(text, webhook)
    print(text)
    if not ok:
        print("⚠️ Slack 전송 실패 또는 webhook 미설정 (config.yaml > ui.slack_webhook 확인)")
        
def cmd_report_eod(args):
    """장마감 요약 Top5 리포트 전송"""
    try:
        from reporting_eod import generate_and_send_report_eod
    except Exception as e:
        print(f"[ERROR] reporting_eod 모듈 임포트 실패: {e}")
        return
    exit(generate_and_send_report_eod(args.date))
    
def cmd_report_eod(args):
    """장마감 요약 Top5 리포트 전송"""
    try:
        from reporting_eod import generate_and_send_report_eod
    except Exception as e:
        print(f"[ERROR] reporting_eod 모듈 임포트 실패: {e}")
        return
    exit(generate_and_send_report_eod(args.date))




# -----------------------------
# 메인 엔트리
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="KRX Alertor Modular")
    sub = parser.add_subparsers()

    # init
    sp = sub.add_parser("init", help="DB 초기화 및 시드 로드")
    sp.set_defaults(func=cmd_init)

    # ingest-eod
    sp = sub.add_parser("ingest-eod", help="일별 종가 수집")
    sp.add_argument("--date", required=True, help="YYYY-MM-DD 또는 auto")
    sp.set_defaults(func=cmd_ingest_eod)

    # ingest-realtime
    sp = sub.add_parser("ingest-realtime", help="실시간 가격 단발 수집")
    sp.add_argument("--code", required=True, help="종목 코드")
    sp.set_defaults(func=cmd_ingest_realtime)

    # report
    sp = sub.add_parser("report", help="성과 리포트")
    sp.add_argument("--start", required=True, help="YYYY-MM-DD 시작일")
    sp.add_argument("--end", required=True, help="YYYY-MM-DD 종료일")
    sp.add_argument("--benchmark", required=True, help="벤치마크 코드 (예: 069500)")
    sp.set_defaults(func=cmd_report)

    # scanner
    sp = sub.add_parser("scanner", help="BUY/SELL 추천 스캐너 실행")
    sp.add_argument("--date", required=True, help="YYYY-MM-DD 기준일")
    sp.set_defaults(func=cmd_scanner)
    
    # report-eod
    sp = sub.add_parser("report-eod", help="EOD 요약 Top5 텔레그램/슬랙 전송")
    sp.add_argument("--date", default="auto", help="YYYY-MM-DD 또는 auto")
    sp.set_defaults(func=cmd_report_eod)
    
    # main() 안의 subparser 정의들 뒤에 이어서 추가
    sp = sub.add_parser("backtest", help="급등+추세+강도+섹터TOP 규칙 백테스트")
    sp.add_argument("--start", required=True, help="YYYY-MM-DD 시작일")
    sp.add_argument("--end", required=True, help="YYYY-MM-DD 종료일")
    sp.add_argument("--config", default="config.yaml", help="설정 파일 경로")
    sp.set_defaults(func=lambda args: run_backtest(args.start, args.end, args.config))

    sp = sub.add_parser("autotag", help="ETF 이름 기반 섹터 자동 분류 실행")
    sp.add_argument("--output", default="sectors_map.csv", help="저장 파일 경로")
    sp.set_defaults(func=lambda args: autotag_sectors(args.output))

    sp = sub.add_parser("scanner-slack", help="스캐너 실행 후 Slack 전송")
    sp.add_argument("--date", required=True, help="YYYY-MM-DD 기준일")
    sp.set_defaults(func=cmd_scanner_slack)
    
    sp = sub.add_parser("report-eod", help="EOD 요약 Top5 텔레그램/슬랙 전송")
    sp.add_argument("--date", default="auto", help="YYYY-MM-DD 또는 auto")
    sp.set_defaults(func=cmd_report_eod)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = RotatingFileHandler("logs/app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt); root.addHandler(fh)
    sh = logging.StreamHandler(); sh.setFormatter(fmt); root.addHandler(sh)

setup_logging()
log = logging.getLogger(__name__)

if __name__ == "__main__":
    main()
