// POC5-07 — 가격 비교 기준일 시장 흐름 화면 test 자료 = 실제 백엔드 출력(tests/test_poc5_05_market_flow 의
// tmp 시세 DB · 2026 캘린더로 build_market_flow 를 실행해 그대로 옮김 · 기준일 2026-01-01(휴장 → 01-02)).
import type { MarketFlowResponse } from "@/lib/api";

export const FLOW_REF_OPEN: MarketFlowResponse = {
  "schema": "holdings_market_flow_v1",
  "read_only": true,
  "ticker": "069500",
  "cycle_id": "cyc-ref",
  "opened_by": "BASELINE",
  "cycle_status": "OPEN",
  "purchase_date_unknown": true,
  "purchase_date_note": "매수일 미상 — 매수 전후 변화 계산 안 함",
  "reference_date": "2026-01-01",
  "reference_flow": {
    "name": "가격 비교 기준일 이후 종가 변화",
    "reference_date": "2026-01-01",
    "basis": {
      "trade_date": "2026-01-01",
      "trade_date_is_trading_day": false,
      "trade_date_decided_by": "snapshot",
      "basis_date": "2026-01-02",
      "basis_date_decided_by": "snapshot",
      "moved_to_next_trading_day": true,
      "basis_note": "비거래일(연도 파일) → 다음 거래일(연도 파일)"
    },
    "window_label": "가격 비교 기준일 → 마지막 저장일",
    "latest_stored_date": "2026-10-07",
    "ticker": {
      "series": "ETF",
      "series_name": "ETF 저장 종가",
      "table": "etf_daily_price",
      "status": "OK",
      "reason_code": null,
      "reason": null,
      "start_date": "2026-01-02",
      "end_date": "2026-10-07",
      "start": {
        "date": "2026-01-02",
        "close": 100.0,
        "source": "NAVER_FDR"
      },
      "end": {
        "date": "2026-10-07",
        "close": 120.0,
        "source": "FinanceDataReader"
      },
      "change_pct": "20",
      "source_differs": true
    },
    "market": {
      "series": "KOSPI",
      "series_name": "KOSPI 저장 종가",
      "table": "market_benchmark_daily_price",
      "status": "OK",
      "reason_code": null,
      "reason": null,
      "start_date": "2026-01-02",
      "end_date": "2026-10-07",
      "start": {
        "date": "2026-01-02",
        "close": 3000.0,
        "source": "NAVER_FDR"
      },
      "end": {
        "date": "2026-10-07",
        "close": 3600.0,
        "source": "NAVER_FDR"
      },
      "change_pct": "20",
      "source_differs": false
    }
  },
  "reference_note": "가격 비교 기준일은 종가 비교의 출발점이다 — 그날 보유 · 매수했다는 뜻이 아니며 개인 손익이 아니다.",
  "db_present": true,
  "asset_kind": "ETF",
  "series": {
    "ticker": {
      "table": "etf_daily_price",
      "series_name": "ETF 저장 종가",
      "comparable_sources": [
        "FinanceDataReader",
        "NAVER_FDR"
      ]
    },
    "market": {
      "table": "market_benchmark_daily_price",
      "benchmark_id": "KOSPI",
      "series_name": "KOSPI 저장 종가",
      "comparable_sources": [
        "FinanceDataReader/KS11",
        "KRX_OPEN_API/idx_kospi_dd_trd",
        "NAVER_FDR"
      ]
    }
  },
  "latest_stored_date": "2026-10-07",
  "latest_stored_close": 120.0,
  "latest_stored_source": "FinanceDataReader",
  "events": [],
  "holding_period": {
    "reason_code": "CYCLE_OPEN",
    "reason": "보유 중 — 보유 기간 변화는 전량매도 뒤 계산",
    "start_record_id": null,
    "end_record_id": null,
    "start_basis": null,
    "end_basis": null,
    "ticker": null,
    "market": null,
    "computed": false,
    "window_label": "가격 비교 기준일 → 마지막 매도 기준일",
    "reference_date": "2026-01-01"
  },
  "notes": [
    "저장 종가 비교값 — 체결단가로 계산한 개인 손익과 다르다.",
    "마지막 저장일은 PC 시세 DB 에 저장된 마지막 날짜이며 오늘 시세가 아니다.",
    "기준일 종가가 없으면 인접일 · 다른 계열로 메우지 않는다.",
    "정형 값만 제공 — 자유 생성 코멘트 · 모델 판단 없음."
  ],
  "free_commentary": null
} as unknown as MarketFlowResponse;

export const FLOW_REF_SOLD: MarketFlowResponse = {
  "schema": "holdings_market_flow_v1",
  "read_only": true,
  "ticker": "069500",
  "cycle_id": "cyc-ref",
  "opened_by": "BASELINE",
  "cycle_status": "CLOSED",
  "purchase_date_unknown": true,
  "purchase_date_note": "매수일 미상 — 매수 전후 변화 계산 안 함",
  "reference_date": "2026-01-02",
  "reference_flow": {
    "name": "가격 비교 기준일 이후 종가 변화",
    "reference_date": "2026-01-02",
    "basis": {
      "trade_date": "2026-01-02",
      "trade_date_is_trading_day": true,
      "trade_date_decided_by": "snapshot",
      "basis_date": "2026-01-02",
      "basis_date_decided_by": "snapshot",
      "moved_to_next_trading_day": false,
      "basis_note": "거래일 그대로(연도 파일)"
    },
    "window_label": "가격 비교 기준일 → 마지막 저장일",
    "latest_stored_date": "2026-10-07",
    "ticker": {
      "series": "ETF",
      "series_name": "ETF 저장 종가",
      "table": "etf_daily_price",
      "status": "OK",
      "reason_code": null,
      "reason": null,
      "start_date": "2026-01-02",
      "end_date": "2026-10-07",
      "start": {
        "date": "2026-01-02",
        "close": 100.0,
        "source": "NAVER_FDR"
      },
      "end": {
        "date": "2026-10-07",
        "close": 120.0,
        "source": "FinanceDataReader"
      },
      "change_pct": "20",
      "source_differs": true
    },
    "market": {
      "series": "KOSPI",
      "series_name": "KOSPI 저장 종가",
      "table": "market_benchmark_daily_price",
      "status": "OK",
      "reason_code": null,
      "reason": null,
      "start_date": "2026-01-02",
      "end_date": "2026-10-07",
      "start": {
        "date": "2026-01-02",
        "close": 3000.0,
        "source": "NAVER_FDR"
      },
      "end": {
        "date": "2026-10-07",
        "close": 3600.0,
        "source": "NAVER_FDR"
      },
      "change_pct": "20",
      "source_differs": false
    }
  },
  "reference_note": "가격 비교 기준일은 종가 비교의 출발점이다 — 그날 보유 · 매수했다는 뜻이 아니며 개인 손익이 아니다.",
  "db_present": true,
  "asset_kind": "ETF",
  "series": {
    "ticker": {
      "table": "etf_daily_price",
      "series_name": "ETF 저장 종가",
      "comparable_sources": [
        "FinanceDataReader",
        "NAVER_FDR"
      ]
    },
    "market": {
      "table": "market_benchmark_daily_price",
      "benchmark_id": "KOSPI",
      "series_name": "KOSPI 저장 종가",
      "comparable_sources": [
        "FinanceDataReader/KS11",
        "KRX_OPEN_API/idx_kospi_dd_trd",
        "NAVER_FDR"
      ]
    }
  },
  "latest_stored_date": "2026-10-07",
  "latest_stored_close": 120.0,
  "latest_stored_source": "FinanceDataReader",
  "events": [
    {
      "record_id": "s1",
      "kind": "SELL",
      "trade_date": "2026-03-02",
      "basis": {
        "trade_date": "2026-03-02",
        "trade_date_is_trading_day": true,
        "trade_date_decided_by": "snapshot",
        "basis_date": "2026-03-02",
        "basis_date_decided_by": "snapshot",
        "moved_to_next_trading_day": false,
        "basis_note": "거래일 그대로(연도 파일)"
      },
      "window_label": "매도 기준일 → 마지막 저장일",
      "latest_stored_date": "2026-10-07",
      "ticker": {
        "series": "ETF",
        "series_name": "ETF 저장 종가",
        "table": "etf_daily_price",
        "status": "OK",
        "reason_code": null,
        "reason": null,
        "start_date": "2026-03-02",
        "end_date": "2026-10-07",
        "start": {
          "date": "2026-03-02",
          "close": 110.0,
          "source": "FinanceDataReader"
        },
        "end": {
          "date": "2026-10-07",
          "close": 120.0,
          "source": "FinanceDataReader"
        },
        "change_pct": "9.090909090909090909090909090909090909091",
        "source_differs": false
      },
      "market": {
        "series": "KOSPI",
        "series_name": "KOSPI 저장 종가",
        "table": "market_benchmark_daily_price",
        "status": "OK",
        "reason_code": null,
        "reason": null,
        "start_date": "2026-03-02",
        "end_date": "2026-10-07",
        "start": {
          "date": "2026-03-02",
          "close": 3300.0,
          "source": "NAVER_FDR"
        },
        "end": {
          "date": "2026-10-07",
          "close": 3600.0,
          "source": "NAVER_FDR"
        },
        "change_pct": "9.090909090909090909090909090909090909091",
        "source_differs": false
      }
    }
  ],
  "holding_period": {
    "reason_code": null,
    "reason": null,
    "start_record_id": null,
    "end_record_id": "s1",
    "start_basis": {
      "trade_date": "2026-01-02",
      "trade_date_is_trading_day": true,
      "trade_date_decided_by": "snapshot",
      "basis_date": "2026-01-02",
      "basis_date_decided_by": "snapshot",
      "moved_to_next_trading_day": false,
      "basis_note": "거래일 그대로(연도 파일)"
    },
    "end_basis": {
      "trade_date": "2026-03-02",
      "trade_date_is_trading_day": true,
      "trade_date_decided_by": "snapshot",
      "basis_date": "2026-03-02",
      "basis_date_decided_by": "snapshot",
      "moved_to_next_trading_day": false,
      "basis_note": "거래일 그대로(연도 파일)"
    },
    "ticker": {
      "series": "ETF",
      "series_name": "ETF 저장 종가",
      "table": "etf_daily_price",
      "status": "OK",
      "reason_code": null,
      "reason": null,
      "start_date": "2026-01-02",
      "end_date": "2026-03-02",
      "start": {
        "date": "2026-01-02",
        "close": 100.0,
        "source": "NAVER_FDR"
      },
      "end": {
        "date": "2026-03-02",
        "close": 110.0,
        "source": "FinanceDataReader"
      },
      "change_pct": "10",
      "source_differs": true
    },
    "market": {
      "series": "KOSPI",
      "series_name": "KOSPI 저장 종가",
      "table": "market_benchmark_daily_price",
      "status": "OK",
      "reason_code": null,
      "reason": null,
      "start_date": "2026-01-02",
      "end_date": "2026-03-02",
      "start": {
        "date": "2026-01-02",
        "close": 3000.0,
        "source": "NAVER_FDR"
      },
      "end": {
        "date": "2026-03-02",
        "close": 3300.0,
        "source": "NAVER_FDR"
      },
      "change_pct": "10",
      "source_differs": false
    },
    "computed": true,
    "window_label": "가격 비교 기준일 → 마지막 매도 기준일",
    "reference_date": "2026-01-02"
  },
  "notes": [
    "저장 종가 비교값 — 체결단가로 계산한 개인 손익과 다르다.",
    "마지막 저장일은 PC 시세 DB 에 저장된 마지막 날짜이며 오늘 시세가 아니다.",
    "기준일 종가가 없으면 인접일 · 다른 계열로 메우지 않는다.",
    "정형 값만 제공 — 자유 생성 코멘트 · 모델 판단 없음."
  ],
  "free_commentary": null
} as unknown as MarketFlowResponse;
