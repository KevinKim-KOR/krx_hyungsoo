"use client";

import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef, RowClassParams } from "ag-grid-community";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppAgGrid } from "../components/AppAgGrid";

type HoldingsRow = {
  account_name: string;
  currency: string;
  ticker: string;
  name: string;
  quantity: number;
  current_price: string;
  current_price_num: number;
  days_held: string;
  pnl_krw: number;
  pnl_krw_num: number;
  return_pct: number;
  daily_change_pct: number | null;
  buy_amount_krw: number;
  valuation_krw: number;
  bucket_id: number;
  bucket: string;
  memo: string;
};

type AccountSummary = {
  account_id: string;
  cash_balance_krw: number;
};

type AggregatedHoldingRow = HoldingsRow;

type HoldingsHeaderSummary = {
  accountCount: number;
  holdingCount: number;
  totalValuation: number;
};

const holdingsGridTheme = themeQuartz
  .withPart(iconSetQuartzBold)
  .withParams({
    accentColor: "#206bc4",
    backgroundColor: "#ffffff",
    foregroundColor: "#182433",
    headerBackgroundColor: "#f8fafc",
    headerTextColor: "#5b6778",
    spacing: 8,
    fontSize: 14,
    wrapperBorderRadius: 10,
    rowHeight: 38,
    headerHeight: 38,
    cellHorizontalPadding: 12,
    headerColumnBorder: true,
    headerColumnBorderHeight: "70%",
    columnBorder: true,
    oddRowBackgroundColor: "#fbfdff",
    headerCellHoverBackgroundColor: "#eef4fb",
    headerCellMovingBackgroundColor: "#e8f0fb",
    iconButtonHoverBackgroundColor: "#eef4fb",
    iconButtonHoverColor: "#206bc4",
    iconSize: 18,
  });

export function HoldingsManager({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: HoldingsHeaderSummary) => void;
}) {
  const router = useRouter();
  const [holdings, setHoldings] = useState<HoldingsRow[]>([]);
  const [totalCashKrw, setTotalCashKrw] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showAmounts, setShowAmounts] = useState(true);

  const loadHoldings = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/assets", { cache: "no-store" });
      if (!res.ok) {
        setHoldings([]);
        setTotalCashKrw(0);
        return;
      }
      const data = await res.json();
      const rows = (data.rows || []).filter((r: HoldingsRow) => r.ticker && r.quantity > 0);
      // 계좌별 현금 합산
      const cashSum = ((data.account_summaries || []) as AccountSummary[]).reduce(
        (sum: number, acc: AccountSummary) => sum + (acc.cash_balance_krw || 0),
        0,
      );
      setHoldings(rows);
      setTotalCashKrw(cashSum);
    } catch (err) {
      console.error(err);
      setHoldings([]);
      setTotalCashKrw(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHoldings();
  }, [loadHoldings]);

  const accountNames = [...new Set(holdings.map((h) => h.account_name))];
  const aggregatedBaseHoldings = Array.from(
    holdings.reduce((acc, row) => {
      const key = `${row.currency}:${row.ticker}`;
      const existing = acc.get(key);

      if (!existing) {
        acc.set(key, { ...row });
        return acc;
      }

      const nextBuyAmount = existing.buy_amount_krw + row.buy_amount_krw;
      const nextValuation = existing.valuation_krw + row.valuation_krw;
      const nextPnl = existing.pnl_krw + row.pnl_krw;
      const existingDaysHeldInt = parseHoldingDaysToInt(existing.days_held);
      const rowDaysHeldInt = parseHoldingDaysToInt(row.days_held);
      const weightedDailyChange =
        existing.daily_change_pct !== null && row.daily_change_pct !== null
          ? (
              ((existing.daily_change_pct * existing.valuation_krw) + (row.daily_change_pct * row.valuation_krw)) /
              Math.max(nextValuation, 1)
            )
          : (existing.daily_change_pct ?? row.daily_change_pct);

      acc.set(key, {
        ...existing,
        quantity: existing.quantity + row.quantity,
        buy_amount_krw: nextBuyAmount,
        valuation_krw: nextValuation,
        pnl_krw: nextPnl,
        pnl_krw_num: nextPnl,
        return_pct: nextBuyAmount > 0 ? Number(((nextPnl / nextBuyAmount) * 100).toFixed(2)) : 0,
        daily_change_pct:
          weightedDailyChange === null ? null : Number(weightedDailyChange.toFixed(2)),
        bucket_id: row.valuation_krw > existing.valuation_krw ? row.bucket_id : existing.bucket_id,
        bucket: row.valuation_krw > existing.valuation_krw ? row.bucket : existing.bucket,
        memo: existing.memo || row.memo,
        account_name: accountNames.join(", "),
        days_held:
          rowDaysHeldInt > existingDaysHeldInt
            ? row.days_held
            : existing.days_held,
      });
      return acc;
    }, new Map<string, AggregatedHoldingRow>()).values(),
  );

  const holdingsValuation = aggregatedBaseHoldings.reduce((sum, row) => sum + row.valuation_krw, 0);
  const totalValuation = holdingsValuation + totalCashKrw;
  const aggregatedHoldings: (AggregatedHoldingRow & { portfolio_weight_pct: number })[] = aggregatedBaseHoldings
    .map((row) => ({
      ...row,
      portfolio_weight_pct: totalValuation > 0 ? Number(((row.valuation_krw / totalValuation) * 100).toFixed(1)) : 0,
    }));

  // 현금 행 추가
  if (totalCashKrw > 0) {
    aggregatedHoldings.push({
      account_name: "",
      currency: "KRW",
      ticker: "__CASH__",
      name: "현금",
      quantity: 0,
      current_price: "-",
      current_price_num: 0,
      days_held: "-",
      pnl_krw: 0,
      pnl_krw_num: 0,
      return_pct: 0,
      daily_change_pct: null,
      buy_amount_krw: totalCashKrw,
      valuation_krw: totalCashKrw,
      bucket_id: 0,
      bucket: "",
      memo: "",
      portfolio_weight_pct: totalValuation > 0 ? Number(((totalCashKrw / totalValuation) * 100).toFixed(1)) : 0,
    });
  }

  // 비중(평가금액) 순 정렬
  aggregatedHoldings.sort((a, b) => b.valuation_krw - a.valuation_krw);

  useEffect(() => {
    onHeaderSummaryChange?.({
      accountCount: accountNames.length,
      holdingCount: aggregatedHoldings.length,
      totalValuation,
    });
  }, [accountNames.length, aggregatedHoldings.length, onHeaderSummaryChange, totalValuation]);

  const moveToTickerDetail = useCallback(
    (ticker: string | null | undefined) => {
      const normalizedTicker = normalizeDisplayTicker(String(ticker ?? "-"));
      if (!normalizedTicker || normalizedTicker === "-" || normalizedTicker === "IS") {
        return;
      }
      router.push(`/ticker?ticker=${encodeURIComponent(normalizedTicker)}`);
    },
    [router],
  );

  const isCashRow = useCallback((row: AggregatedHoldingRow | undefined) => row?.ticker === "__CASH__", []);

  const columnDefs = useMemo<ColDef<(AggregatedHoldingRow & { portfolio_weight_pct: number })>[]>(() => [
    {
      headerName: "버킷",
      field: "bucket",
      width: 108,
      sortable: true,
      comparator: (_a, _b, nodeA, nodeB) => {
        const aId = Number(nodeA.data?.bucket_id ?? 0);
        const bId = Number(nodeB.data?.bucket_id ?? 0);
        return aId - bId;
      },
      cellClass: (params) => `${getBucketCellClass(String(params.data?.bucket ?? ""))} tableAlignCenter`,
      cellRenderer: (params: { data?: AggregatedHoldingRow }) => {
        if (!params.data || isCashRow(params.data)) {
          return <span style={{ color: "#8b949e" }}>-</span>;
        }
        return <span>{params.data.bucket || "-"}</span>;
      },
    },
    {
      headerName: "티커",
      field: "ticker",
      width: 110,
      sortable: true,
      cellClass: "tableAlignCenter holdingsTickerCell",
      cellRenderer: (params: { value?: string | null; data?: AggregatedHoldingRow }) => {
        const rawTicker = String(params.value ?? "-");
        if (rawTicker === "__CASH__") {
          return <span className="appCodeText" style={{ color: "#8b949e" }}>-</span>;
        }
        const normalizedTicker = normalizeDisplayTicker(rawTicker);
        if (normalizedTicker === "IS") {
          return <span className="appCodeText">{normalizedTicker}</span>;
        }
        return (
          <button
            type="button"
            className="appCodeText"
            style={{ color: "inherit", textDecoration: "none", background: "none", border: "none", padding: 0 }}
            onClick={() => moveToTickerDetail(normalizedTicker)}
          >
            {normalizedTicker}
          </button>
        );
      },
    },
    {
      headerName: "종목명",
      field: "name",
      flex: 1.4,
      minWidth: 210,
      sortable: true,
      cellClass: "holdingsNameCell",
      cellRenderer: (params: { value?: string | null; data?: AggregatedHoldingRow }) => {
        if (!params.value) {
          return "-";
        }
        const isCash = params.data?.ticker === "__CASH__";
        return (
          <span
            className="holdingsNameMain"
            title={params.value}
            style={isCash ? { color: "#8b949e", fontWeight: 500 } : undefined}
          >
            {params.value}
          </span>
        );
      },
    },
    {
      headerName: "비중",
      field: "portfolio_weight_pct",
      width: 92,
      type: "rightAligned",
      valueFormatter: (params) => `${Number(params.value ?? 0).toFixed(1)}%`,
    },
    {
      headerName: "보유일",
      field: "days_held",
      width: 92,
      cellClass: "tableAlignCenter",
    },
    {
      headerName: "평가금액",
      field: "valuation_krw",
      width: 160,
      type: "rightAligned",
      valueFormatter: (params) => showAmounts ? formatHoldingsKrw(Number(params.value ?? 0)) : "••••",
    },
    {
      headerName: "현재가",
      field: "current_price_num",
      width: 140,
      type: "rightAligned",
      cellRenderer: (params: { data?: AggregatedHoldingRow & { portfolio_weight_pct: number } }) => {
        const row = params.data;
        if (!row || isCashRow(row)) {
          return "-";
        }
        const value = showAmounts ? formatHoldingPrice(row.current_price_num, row.currency) : "••••";
        return <span className={getSignedClass(row.daily_change_pct)}>{value}</span>;
      },
    },
    {
      headerName: "일간(%)",
      field: "daily_change_pct",
      width: 120,
      type: "rightAligned",
      cellRenderer: (params: { value?: number | null; data?: AggregatedHoldingRow }) => {
        if (params.data?.ticker === "__CASH__") return "-";
        const value = params.value ?? null;
        return <span className={getSignedClass(value)}>{formatSignedPercent(value)}</span>;
      },
    },
    {
      headerName: "평가손익",
      field: "pnl_krw",
      width: 150,
      type: "rightAligned",
      cellRenderer: (params: { data?: AggregatedHoldingRow & { portfolio_weight_pct: number } }) => {
        const row = params.data;
        if (!row || isCashRow(row)) {
          return "-";
        }
        const value = showAmounts ? formatHoldingsKrw(row.pnl_krw) : "••••";
        return <span className={getSignedClass(row.return_pct)}>{value}</span>;
      },
    },
    {
      headerName: "수익률(%)",
      field: "return_pct",
      width: 120,
      type: "rightAligned",
      cellRenderer: (params: { value?: number | null; data?: AggregatedHoldingRow }) => {
        if (params.data?.ticker === "__CASH__") return "-";
        const value = params.value ?? null;
        return <span className={getSignedClass(value)}>{formatSignedPercent(value)}</span>;
      },
    },
  ], [isCashRow, moveToTickerDetail, showAmounts]);

  return (
    <div className="appPageStack appPageStackFill">
      <section className="appSection appSectionFill">
        <div className="card appCard appTableCardFill">
          <div className="card-header">
            <div className="appMainHeader">
              <div className="appMainHeaderLeft" />
              <div className="appMainHeaderRight">
                <button
                  type="button"
                  className={`btn btn-sm shadow-sm ${showAmounts ? "btn-outline-secondary" : "btn-dark"}`}
                  onClick={() => setShowAmounts((prev) => !prev)}
                >
                  {showAmounts ? "금액 가리기" : "금액 보기"}
                </button>
              </div>
            </div>
          </div>

          <div className="card-body appCardBodyTight appTableCardBodyFill">
            <div className="appGridFillWrap">
              <AppAgGrid
                rowData={loading ? [] : aggregatedHoldings}
                columnDefs={columnDefs}
                loading={loading}
                minHeight="100%"
                className="holdingsGrid"
                theme={holdingsGridTheme}
                getRowClass={(params: RowClassParams<AggregatedHoldingRow & { portfolio_weight_pct: number }>) =>
                  params.data?.ticker === "__CASH__" ? "holdingsRow holdingsRowCash" : "holdingsRow"
                }
                gridOptions={{
                  rowHeight: 38,
                  suppressMovableColumns: true,
                  getRowId: (params) => `${params.data.currency}:${params.data.ticker}`,
                  overlayNoRowsTemplate: '<span class="ag-overlay-no-rows-center">보유 종목이 없습니다.</span>',
                }}
              />
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        .holdingsGrid .ag-cell {
          display: flex;
          align-items: center;
        }
        .holdingsGrid .tableAlignCenter {
          justify-content: center;
          text-align: center;
        }
        .holdingsGrid .holdingsTickerCell {
          font-weight: 600;
          color: #5f6b82;
        }
        .holdingsGrid .holdingsNameCell {
          min-width: 0;
          overflow: hidden;
        }
        .holdingsGrid .ag-row.holdingsRowCash .ag-cell {
          background-color: #f4f5f7;
        }
        .holdingsGrid .rankBucketCell {
          justify-content: center;
          font-weight: 600;
          white-space: nowrap;
        }
        .holdingsGrid .rankBucketCell1 {
          background: var(--bucket-1);
          color: #fff;
        }
        .holdingsGrid .rankBucketCell2 {
          background: var(--bucket-2);
          color: #fff;
        }
        .holdingsGrid .rankBucketCell3 {
          background: var(--bucket-3);
          color: #fff;
        }
        .holdingsGrid .rankBucketCell4 {
          background: var(--bucket-4);
          color: #fff;
        }
      `}</style>

      <style jsx>{`
        .holdingsNameMain {
          display: block;
          width: 100%;
          min-width: 0;
          font-size: 0.95rem;
          font-weight: 700;
          color: #1d273b;
          word-break: keep-all;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      `}</style>
    </div>
  );
}

function formatHoldingPrice(val: number, currency: string) {
  if (currency === "AUD") {
    return `A$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  if (currency === "USD") {
    return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${Math.floor(val).toLocaleString()}원`;
}

function formatHoldingsKrw(val: number) {
  return `${Math.round(val).toLocaleString()}원`;
}

function formatSignedPercent(value: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function getBucketCellClass(bucketLabel: string): string {
  const match = /^(\d+)/.exec(String(bucketLabel || "").trim());
  if (!match) {
    return "rankBucketCell";
  }
  return `rankBucketCell rankBucketCell${match[1]}`;
}

function normalizeDisplayTicker(value: string | null | undefined) {
  const raw = String(value ?? "").trim().toUpperCase();
  if (!raw) {
    return "-";
  }
  return raw.replace(/^ASX:/, "");
}

function getSignedClass(value: number | null) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "";
  }
  return value > 0 ? "metricPositive" : "metricNegative";
}

function parseHoldingDaysToInt(value: string | null | undefined): number {
  const raw = String(value ?? "").trim().toUpperCase();
  if (!raw || raw === "-") {
    return 0;
  }

  let totalDays = 0;
  const weekMatch = raw.match(/(\d+)\s*W/);
  const dayMatch = raw.match(/(\d+)\s*D/);

  if (weekMatch) {
    totalDays += Number(weekMatch[1]) * 7;
  }
  if (dayMatch) {
    totalDays += Number(dayMatch[1]);
  }

  return totalDays;
}
