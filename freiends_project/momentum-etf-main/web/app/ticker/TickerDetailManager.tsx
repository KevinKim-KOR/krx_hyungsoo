"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { IconCheck, IconPlus } from "@tabler/icons-react";
import { useSearchParams } from "next/navigation";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import type {
  IChartApi,
  LineData,
  Logical,
  Time,
  MouseEventParams,
} from "lightweight-charts";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef, GridApi, GridReadyEvent } from "ag-grid-community";

import { AppAgGrid } from "../components/AppAgGrid";
import { useToast } from "../components/ToastProvider";
import { persistRecentTickerSearch } from "@/lib/recent-ticker-searches";
import { addStockCandidate } from "@/lib/stocks-store";

// --- 타입 ---

type TickerItem = {
  ticker: string;
  name: string;
  ticker_type: string;
  country_code: string;
};

type PriceRow = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  change_pct: number | null;
};

type MonthlyPriceRow = {
  month: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  change_pct: number | null;
};

type ChartInterval = "day" | "week" | "month";

type TickerDetailResponse = {
  ticker: string;
  rows: PriceRow[];
  holdings: TickerHoldingRow[];
  holdings_as_of_date?: string | null;
  holdings_price_as_of_date?: string | null;
  holdings_error?: string | null;
  error?: string;
};

type TickerHoldingRow = {
  ticker: string;
  name: string;
  contracts: number | null;
  amount: number | null;
  raw_code?: string | null;
  raw_name?: string | null;
  reuters_code?: string | null;
  yahoo_symbol?: string | null;
  current_price?: number | null;
  previous_close?: number | null;
  change_pct?: number | null;
  price_currency?: string | null;
  weight: number | null;
  is_us_pool_candidate?: boolean;
  in_us_pool?: boolean;
};

type CrosshairInfo = {
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  change_pct: number | null;
};

type ChartRangeBadge = {
  text: string;
  left: number;
  top: number;
  anchorLeft: number;
  tone: "high" | "low";
};

// --- 상수 ---

const MA_PERIODS = [
  { period: 5, color: "#2196F3", label: "5" },
  { period: 20, color: "#FF9800", label: "20" },
  { period: 60, color: "#E91E63", label: "60" },
  { period: 120, color: "#9C27B0", label: "120" },
];

const gridTheme = themeQuartz
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
    rowHeight: 34,
    headerHeight: 36,
    cellHorizontalPadding: 12,
    headerColumnBorder: true,
    headerColumnBorderHeight: "70%",
    columnBorder: true,
    oddRowBackgroundColor: "#fbfdff",
  });

// --- 유틸 ---

function formatNumber(value: number | null, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatUnsignedPercent(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value.toFixed(2)}%`;
}

function formatDateWithWeekday(value: string): string {
  if (!value) return "-";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  return `${value}(${weekdays[date.getDay()]})`;
}

function getSignedClass(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return "";
  return value > 0 ? "metricPositive" : "metricNegative";
}

function calculateMA(data: PriceRow[], period: number): LineData[] {
  const result: LineData[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    let count = 0;
    for (let j = i - period + 1; j <= i; j++) {
      if (data[j].close !== null) { sum += data[j].close!; count++; }
    }
    if (count === period) {
      result.push({ time: data[i].date as Time, value: sum / count });
    }
  }
  return result;
}

function getWeekBucketStart(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  return date.toISOString().slice(0, 10);
}

function aggregatePriceRows(data: PriceRow[], bucket: "week" | "month"): PriceRow[] {
  const aggregatedRows: PriceRow[] = [];
  let currentKey = "";
  let currentRow: PriceRow | null = null;
  let previousClose: number | null = null;

  for (const row of data) {
    const nextKey = bucket === "week" ? getWeekBucketStart(row.date) : row.date.slice(0, 7);
    if (!nextKey) {
      continue;
    }

    if (nextKey !== currentKey) {
      if (currentRow) {
        if (currentRow.close !== null && previousClose !== null && previousClose !== 0) {
          currentRow.change_pct = Number((((currentRow.close - previousClose) / previousClose) * 100).toFixed(2));
        }
        if (currentRow.close !== null) {
          previousClose = currentRow.close;
        }
        aggregatedRows.push(currentRow);
      }

      currentKey = nextKey;
      currentRow = { ...row };
      continue;
    }

    if (!currentRow) {
      continue;
    }

    if (currentRow.open === null && row.open !== null) {
      currentRow.open = row.open;
    }
    if (row.high !== null) {
      currentRow.high = currentRow.high === null ? row.high : Math.max(currentRow.high, row.high);
    }
    if (row.low !== null) {
      currentRow.low = currentRow.low === null ? row.low : Math.min(currentRow.low, row.low);
    }
    if (row.close !== null) {
      currentRow.close = row.close;
    }
    if (row.volume !== null) {
      currentRow.volume = (currentRow.volume ?? 0) + row.volume;
    }
    currentRow.date = row.date;
  }

  if (currentRow) {
    if (currentRow.close !== null && previousClose !== null && previousClose !== 0) {
      currentRow.change_pct = Number((((currentRow.close - previousClose) / previousClose) * 100).toFixed(2));
    }
    aggregatedRows.push(currentRow);
  }

  return aggregatedRows;
}

function aggregateMonthlyRows(data: PriceRow[]): MonthlyPriceRow[] {
  return aggregatePriceRows(data, "month").map((row) => ({
    month: row.date.slice(0, 7),
    open: row.open,
    high: row.high,
    low: row.low,
    close: row.close,
    volume: row.volume,
    change_pct: row.change_pct,
  }));
}

function formatTickerPrice(value: number | null, countryCode: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  const normalized = String(countryCode || "").trim().toLowerCase();
  if (normalized === "au" || normalized === "aud") {
    return `A$${new Intl.NumberFormat("en-AU", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)}`;
  }

  if (normalized === "us" || normalized === "usd") {
    return `$${new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)}`;
  }

  if (normalized === "eur") {
    return `€${new Intl.NumberFormat("de-DE", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)}`;
  }

  if (normalized === "cny") {
    return `${new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)} CNY`;
  }

  return `${new Intl.NumberFormat("ko-KR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)}원`;
}

function buildRangeBadgeText(
  anchorPrice: number,
  currentPrice: number,
  date: string,
  countryCode: string,
): string {
  const pct = anchorPrice === 0 ? null : ((currentPrice / anchorPrice) - 1) * 100;
  return `${formatTickerPrice(anchorPrice, countryCode)} (${formatPercent(pct)}, ${date})`;
}

function getInitialVisibleLogicalRange(
  data: PriceRow[],
  interval: ChartInterval,
): { from: number; to: number } | null {
  if (data.length === 0) {
    return null;
  }

  const lastIndex = data.length - 1;
  if (interval === "month") {
    return {
      from: -3,
      to: lastIndex + 3.5,
    };
  }

  const lastRow = data[lastIndex];

  const lastDate = new Date(`${lastRow.date}T00:00:00`);
  if (Number.isNaN(lastDate.getTime())) {
    return null;
  }

  const startDate = new Date(lastDate);
  if (interval === "day") {
    startDate.setFullYear(startDate.getFullYear() - 1);
  } else {
    startDate.setFullYear(startDate.getFullYear() - 2);
  }

  const startDateText = startDate.toISOString().slice(0, 10);
  const visibleStartIndex = data.findIndex((row) => row.date >= startDateText);
  return {
    from: Math.max((visibleStartIndex >= 0 ? visibleStartIndex : 0) - 1, -1),
    to: lastIndex + 2.5,
  };
}

// --- 컴포넌트 ---

export function TickerDetailManager({
}: {
}) {
  const searchParams = useSearchParams();
  const toast = useToast();

  // URL query params
  const qTicker = searchParams.get("ticker") ?? "";
  const qTickerType = searchParams.get("ticker_type") ?? "";
  const qCountryCode = searchParams.get("country_code") ?? "";
  const qName = searchParams.get("name") ?? "";

  // 전체 종목 목록
  const [allTickers, setAllTickers] = useState<TickerItem[]>([]);

  // 현재 선택된 종목
  const [selectedTicker, setSelectedTicker] = useState<TickerItem | null>(null);

  // 데이터
  const [rows, setRows] = useState<PriceRow[]>([]);
  const [holdings, setHoldings] = useState<TickerHoldingRow[]>([]);
  const [holdingsAsOfDate, setHoldingsAsOfDate] = useState<string | null>(null);
  const [holdingsPriceAsOfDate, setHoldingsPriceAsOfDate] = useState<string | null>(null);
  const [holdingsError, setHoldingsError] = useState<string | null>(null);
  const [addingUsTickers, setAddingUsTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const holdingsGridApiRef = useRef<GridApi<TickerHoldingRow> | null>(null);
  const addingUsTickersRef = useRef<string[]>([]);
  const [chartInterval, setChartInterval] = useState<ChartInterval>("day");

  // 차트
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [crosshairInfo, setCrosshairInfo] = useState<CrosshairInfo | null>(null);
  const [chartBadges, setChartBadges] = useState<ChartRangeBadge[]>([]);

  // --- 종목 목록 로드 ---

  useEffect(() => {
    let alive = true;
    async function fetchAll() {
      try {
        const res = await fetch("/api/ticker-tickers", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as TickerItem[];
        if (alive && Array.isArray(data)) setAllTickers(data);
      } catch { /* 무시 */ }
    }
    fetchAll();
    return () => { alive = false; };
  }, []);

  // URL에서 ticker가 있으면 자동 조회
  useEffect(() => {
    if (!qTicker) {
      setSelectedTicker(null);
      setRows([]);
      setHoldings([]);
      setHoldingsAsOfDate(null);
      setHoldingsPriceAsOfDate(null);
      setHoldingsError(null);
      setError(null);
      return;
    }

    if (qTickerType) {
      const item: TickerItem = { ticker: qTicker, name: qName, ticker_type: qTickerType, country_code: qCountryCode };
      setSelectedTicker(item);
      void loadTickerData(item);
      return;
    }

    if (allTickers.length === 0) {
      return;
    }

    const matches = allTickers.filter((item) => item.ticker.toLowerCase() === qTicker.toLowerCase());
    if (matches.length === 1) {
      setSelectedTicker(matches[0]);
      void loadTickerData(matches[0]);
      return;
    }

    setRows([]);
    setHoldings([]);
    setHoldingsAsOfDate(null);
    setHoldingsPriceAsOfDate(null);
    setHoldingsError(null);
    if (matches.length > 1) {
      setSelectedTicker(null);
      setError(`동일한 티커 ${qTicker}가 여러 종목풀에 등록되어 있습니다.`);
      return;
    }

    setSelectedTicker(null);
    setError(`${qTicker} 티커를 찾지 못했습니다.`);
  }, [allTickers, qTicker, qTickerType, qCountryCode, qName]);

  // --- 데이터 로드 ---

  async function loadTickerData(item: TickerItem) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setRows([]);
    setHoldings([]);
    setHoldingsAsOfDate(null);
    setHoldingsPriceAsOfDate(null);
    setHoldingsError(null);
    setAddingUsTickers([]);
    setCrosshairInfo(null);
    setChartBadges([]);

    try {
      const search = new URLSearchParams({
        ticker: item.ticker,
      });
      const response = await fetch(`/api/ticker-detail?${search.toString()}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      const payload = (await response.json()) as TickerDetailResponse;
      if (!response.ok) throw new Error(payload.error ?? "데이터를 불러오지 못했습니다.");
      if (payload.error) throw new Error(payload.error);
      const latestRow = payload.rows[payload.rows.length - 1] ?? null;
      const matchedItem =
        allTickers.find(
          (candidate) => candidate.ticker === item.ticker && candidate.ticker_type === item.ticker_type,
        ) ?? item;
      setRows(payload.rows);
      setHoldings(payload.holdings ?? []);
      setHoldingsAsOfDate(payload.holdings_as_of_date ?? null);
      setHoldingsPriceAsOfDate(payload.holdings_price_as_of_date ?? null);
      setHoldingsError(payload.holdings_error ?? null);
      persistRecentTickerSearch({
        ticker: matchedItem.ticker,
        name: matchedItem.name,
        ticker_type: matchedItem.ticker_type,
        country_code: matchedItem.country_code,
        current_price: latestRow?.close ?? null,
        change_pct: latestRow?.change_pct ?? null,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "데이터를 불러오지 못했습니다.");
      setRows([]);
      setHoldings([]);
      setHoldingsAsOfDate(null);
      setHoldingsPriceAsOfDate(null);
      setHoldingsError(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    addingUsTickersRef.current = addingUsTickers;
    holdingsGridApiRef.current?.refreshCells({
      force: true,
      columns: ["ticker"],
    });
  }, [addingUsTickers]);

  // --- 핸들러 ---

  async function handleAddUsTicker(row: TickerHoldingRow) {
    const ticker = String(row.ticker || "").trim().toUpperCase();
    if (!ticker) {
      return;
    }
    setAddingUsTickers((current) => (
      current.includes(ticker) ? current : [...current, ticker]
    ));
    try {
      await addStockCandidate("us", ticker, 1);
      setHoldings((current) =>
        current.map((row) =>
          row.ticker === ticker
            ? { ...row, in_us_pool: true }
            : row,
        ),
      );
      toast.success(`${ticker}를 미국 종목풀의 1. 모멘텀에 추가하였습니다.`);
    } catch (addError) {
      const message = addError instanceof Error ? addError.message : "미국 종목풀 추가에 실패했습니다.";
      if (message.includes("이미 등록된 종목입니다.")) {
        setHoldings((current) =>
          current.map((row) =>
            row.ticker === ticker
              ? { ...row, in_us_pool: true }
              : row,
          ),
        );
        toast.success(`${ticker}를 미국 종목풀의 1. 모멘텀에 추가하였습니다.`);
        return;
      }
      toast.error(`${ticker} 미국 종목풀 추가에 실패했습니다. ${message}`);
    } finally {
      setAddingUsTickers((current) => current.filter((item) => item !== ticker));
    }
  }

  // --- 차트 관련 ---

  const selectedCountryCode = selectedTicker?.country_code ?? "kor";
  const priceDigits =
    selectedTicker?.country_code === "au" || selectedTicker?.country_code === "us"
      ? 2
      : 0;
  const priceMinMove = priceDigits > 0 ? 0.01 : 1;

  const chartRows = useMemo(() => {
    if (chartInterval === "week") {
      return aggregatePriceRows(rows, "week");
    }
    if (chartInterval === "month") {
      return aggregatePriceRows(rows, "month");
    }
    return rows;
  }, [chartInterval, rows]);

  const dateRowMap = useMemo(() => {
    const map = new Map<string, PriceRow>();
    for (const row of chartRows) map.set(row.date, row);
    return map;
  }, [chartRows]);

  const lastInfo = useMemo<CrosshairInfo | null>(() => {
    if (chartRows.length === 0) return null;
    const last = chartRows[chartRows.length - 1];
    return { open: last.open, high: last.high, low: last.low, close: last.close, change_pct: last.change_pct };
  }, [chartRows]);

  useEffect(() => {
    if (!chartContainerRef.current || chartRows.length === 0) {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      setCrosshairInfo(null);
      setChartBadges([]);
      return;
    }
    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
    setCrosshairInfo(null);
    setChartBadges([]);

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 420,
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#5b6778", fontSize: 12 },
      grid: { vertLines: { color: "#f0f2f5" }, horzLines: { color: "#f0f2f5" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#e6e8ec", scaleMargins: { top: 0.12, bottom: 0.25 } },
      timeScale: { borderColor: "#e6e8ec", timeVisible: false },
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a", downColor: "#ef5350",
      borderUpColor: "#26a69a", borderDownColor: "#ef5350",
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
      priceFormat: {
        type: "custom",
        minMove: priceMinMove,
        formatter: (price: number) => formatTickerPrice(price, selectedCountryCode),
      },
    });
    candleSeries.setData(
      chartRows
        .filter((r) => r.open !== null && r.high !== null && r.low !== null && r.close !== null)
        .map((r) => ({ time: r.date as Time, open: r.open!, high: r.high!, low: r.low!, close: r.close! })),
    );

    function updateRangeBadges(logicalRange?: { from: number; to: number } | null) {
      const safeFrom = logicalRange ? Math.max(Math.floor(logicalRange.from), 0) : 0;
      const safeTo = logicalRange ? Math.min(Math.ceil(logicalRange.to), chartRows.length - 1) : chartRows.length - 1;
      const visibleRows = chartRows.slice(safeFrom, safeTo + 1).filter(
        (row) => row.high !== null && row.low !== null && row.close !== null,
      );

      if (visibleRows.length === 0) {
        setChartBadges([]);
        return;
      }

      const currentRow = visibleRows[visibleRows.length - 1];
      if (currentRow.close === null) {
        setChartBadges([]);
        return;
      }

      let highRow = visibleRows[0];
      let lowRow = visibleRows[0];
      for (const row of visibleRows) {
        if ((row.high ?? Number.NEGATIVE_INFINITY) > (highRow.high ?? Number.NEGATIVE_INFINITY)) {
          highRow = row;
        }
        if ((row.low ?? Number.POSITIVE_INFINITY) < (lowRow.low ?? Number.POSITIVE_INFINITY)) {
          lowRow = row;
        }
      }

      const highIndex = chartRows.findIndex((row) => row.date === highRow.date);
      const lowIndex = chartRows.findIndex((row) => row.date === lowRow.date);
      const highX = chart.timeScale().logicalToCoordinate(highIndex as Logical);
      const lowX = chart.timeScale().logicalToCoordinate(lowIndex as Logical);
      const highY = candleSeries.priceToCoordinate(highRow.high!);
      const lowY = candleSeries.priceToCoordinate(lowRow.low!);

      if (highX === null || lowX === null || highY === null || lowY === null) {
        setChartBadges([]);
        return;
      }

      const chartWidth = container.clientWidth;
      const badgeWidth = 240;
      const clampLeft = (value: number, width = badgeWidth) => Math.max(12, Math.min(value, chartWidth - width - 12));
      const getBadgeLeft = (anchorX: number) => clampLeft(anchorX - badgeWidth / 2);

      setChartBadges([
        {
          tone: "high",
          text: buildRangeBadgeText(highRow.high!, currentRow.close, highRow.date, selectedTicker?.country_code ?? "kor"),
          left: getBadgeLeft(highX),
          top: Math.max(highY - 78, 10),
          anchorLeft: Math.max(10, Math.min(highX - getBadgeLeft(highX), badgeWidth - 10)),
        },
        {
          tone: "low",
          text: buildRangeBadgeText(lowRow.low!, currentRow.close, lowRow.date, selectedTicker?.country_code ?? "kor"),
          left: getBadgeLeft(lowX),
          top: Math.min(lowY + 40, 382),
          anchorLeft: Math.max(10, Math.min(lowX - getBadgeLeft(lowX), badgeWidth - 10)),
        },
      ]);
    }

    const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume" });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volumeSeries.setData(
      chartRows
        .filter((r) => r.volume !== null && r.close !== null)
        .map((r, i) => {
          const prevClose = i > 0 ? chartRows[i - 1].close : null;
          const isUp = prevClose !== null && r.close !== null ? r.close >= prevClose : true;
          return { time: r.date as Time, value: r.volume!, color: isUp ? "rgba(38, 166, 154, 0.3)" : "rgba(239, 83, 80, 0.3)" };
        }),
    );

    for (const ma of MA_PERIODS) {
      if (chartRows.length < ma.period) continue;
      const maData = calculateMA(chartRows, ma.period);
      if (maData.length === 0) continue;
      chart.addSeries(LineSeries, {
        color: ma.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        priceFormat: {
          type: "custom",
          minMove: priceMinMove,
          formatter: (price: number) => formatTickerPrice(price, selectedCountryCode),
        },
      }).setData(maData);
    }

    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (!param.time) { setCrosshairInfo(null); return; }
      const row = dateRowMap.get(String(param.time));
      if (row) setCrosshairInfo({ open: row.open, high: row.high, low: row.low, close: row.close, change_pct: row.change_pct });
    });

    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      updateRangeBadges(range);
    });

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
        updateRangeBadges(chart.timeScale().getVisibleLogicalRange());
      }
    });
    observer.observe(container);
    const initialVisibleRange = getInitialVisibleLogicalRange(chartRows, chartInterval);
    if (initialVisibleRange) {
      chart.timeScale().setVisibleLogicalRange(initialVisibleRange);
    } else {
      chart.timeScale().fitContent();
    }
    updateRangeBadges(chart.timeScale().getVisibleLogicalRange());

    return () => {
      observer.disconnect();
      setChartBadges([]);
      chart.remove();
      chartRef.current = null;
    };
  }, [chartInterval, chartRows, dateRowMap, priceMinMove, selectedCountryCode]);

  const reversedRows = useMemo(
    () => [...rows].reverse().map((r, i) => ({ ...r, id: `${r.date}-${i}` })),
    [rows],
  );

  const monthlyRows = useMemo(
    () => aggregateMonthlyRows(rows).reverse().map((row, i) => ({ ...row, id: `${row.month}-${i}` })),
    [rows],
  );

  const holdingsRows = useMemo(
    () => holdings.map((row, index) => ({ ...row, id: `${row.ticker}-${index}` })),
    [holdings],
  );
  const showHoldingsWeightColumn = useMemo(
    () => holdingsRows.some((row) => (row.weight ?? 0) > 0),
    [holdingsRows],
  );

  const holdingsAsOfDateLabel = useMemo(() => {
    if (!holdingsAsOfDate || holdingsAsOfDate.length !== 8) return null;
    return `${holdingsAsOfDate.slice(0, 4)}-${holdingsAsOfDate.slice(4, 6)}-${holdingsAsOfDate.slice(6, 8)}`;
  }, [holdingsAsOfDate]);
  const holdingsPriceAsOfDateLabel = useMemo(() => {
    if (!holdingsPriceAsOfDate || holdingsPriceAsOfDate.length !== 8) return null;
    return `${holdingsPriceAsOfDate.slice(0, 4)}-${holdingsPriceAsOfDate.slice(4, 6)}-${holdingsPriceAsOfDate.slice(6, 8)}`;
  }, [holdingsPriceAsOfDate]);
  const holdingsPanelTitle = showHoldingsWeightColumn ? "구성종목비중" : "구성종목";
  const hasKoreanHoldings = useMemo(
    () => holdingsRows.some((row) => /^\d{6}$/.test(String(row.ticker || "").trim())),
    [holdingsRows],
  );
  const hasForeignHoldings = useMemo(
    () => holdingsRows.some((row) => !/^\d{6}$/.test(String(row.ticker || "").trim())),
    [holdingsRows],
  );
  const holdingsPanelMeta = useMemo(() => {
    if (holdingsRows.length === 0) {
      return "데이터 없음";
    }
    if (hasForeignHoldings && !hasKoreanHoldings) {
      return holdingsPriceAsOfDateLabel ? `해외 가격 기준 ${holdingsPriceAsOfDateLabel}` : "해외 가격 기준 없음";
    }
    if (hasForeignHoldings && hasKoreanHoldings) {
      if (holdingsAsOfDateLabel && holdingsPriceAsOfDateLabel) {
        return `적용일 ${holdingsAsOfDateLabel}(해외 가격 기준 ${holdingsPriceAsOfDateLabel})`;
      }
      if (holdingsAsOfDateLabel) {
        return `적용일 ${holdingsAsOfDateLabel}`;
      }
      return `상위 ${new Intl.NumberFormat("ko-KR").format(holdingsRows.length)}개`;
    }
    if (holdingsAsOfDateLabel) {
      return `적용일 ${holdingsAsOfDateLabel}`;
    }
    return `상위 ${new Intl.NumberFormat("ko-KR").format(holdingsRows.length)}개`;
  }, [hasForeignHoldings, hasKoreanHoldings, holdingsAsOfDateLabel, holdingsPriceAsOfDateLabel, holdingsRows.length]);

  const dailyColumns = useMemo<ColDef[]>(
    () => [
      {
        field: "date",
        headerName: "날짜",
        minWidth: 138,
        flex: 1.45,
        cellStyle: { fontWeight: 600 },
        cellRenderer: (params: { value: string }) => formatDateWithWeekday(params.value),
      },
      { field: "close", headerName: "종가", minWidth: 84, flex: 0.95, type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => formatTickerPrice(params.value, selectedCountryCode) },
      { field: "change_pct", headerName: "등락률", minWidth: 92, flex: 0.95, type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => (
          <span className={getSignedClass(params.value)}>{formatPercent(params.value)}</span>
        ) },
      { field: "volume", headerName: "거래량", minWidth: 118, flex: 1.2, type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => formatNumber(params.value, 0) },
    ],
    [selectedCountryCode],
  );

  const monthlyColumns = useMemo<ColDef[]>(
    () => [
      {
        field: "month",
        headerName: "년월",
        minWidth: 92,
        flex: 1.1,
        cellStyle: { fontWeight: 600 },
      },
      { field: "close", headerName: "월말 종가", minWidth: 88, flex: 0.95, type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => formatTickerPrice(params.value, selectedCountryCode) },
      { field: "change_pct", headerName: "월간 등락률", minWidth: 96, flex: 0.95, type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => (
          <span className={getSignedClass(params.value)}>{formatPercent(params.value)}</span>
        ) },
      { field: "volume", headerName: "월간 거래량", minWidth: 120, flex: 1.25, type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => formatNumber(params.value, 0) },
    ],
    [selectedCountryCode],
  );

  const holdingColumns = useMemo<ColDef[]>(
    () => {
      const columns: ColDef[] = [
        {
          field: "ticker",
          headerName: "종목코드",
          minWidth: 120,
          width: 120,
          cellClass: "tickerDetailCodeCell",
          cellStyle: { fontWeight: 700 },
          cellRenderer: (params: { value: string; data?: TickerHoldingRow }) => {
            const ticker = String(params.value ?? "").trim();
            const row = params.data;
            const isUsCandidate = Boolean(row?.is_us_pool_candidate);
            const inUsPool = Boolean(row?.in_us_pool);

            return (
              <div className="tickerDetailCodeContent">
                <span className="tickerDetailCodeText">{ticker || "-"}</span>
                {isUsCandidate ? (
                  inUsPool ? (
                    <span className="tickerDetailPoolState is-done" title="미국 종목풀에 이미 등록됨" aria-label="미국 종목풀 등록 완료">
                      <IconCheck size={14} stroke={2.2} />
                    </span>
                  ) : addingUsTickersRef.current.includes(ticker) ? (
                    <span className="tickerDetailPoolState is-loading" title="미국 종목풀 추가 중" aria-label="미국 종목풀 추가 중">
                      <span className="spinner-border spinner-border-sm" />
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="tickerDetailPoolState is-add"
                      title="미국 종목풀에 추가"
                      aria-label={`${ticker} 미국 종목풀 추가`}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (row) {
                          void handleAddUsTicker(row);
                        }
                      }}
                    >
                      <IconPlus size={14} stroke={2.2} />
                    </button>
                  )
                ) : null}
              </div>
            );
          },
        },
        {
          field: "name",
          headerName: "종목명",
          minWidth: 148,
          flex: 1.2,
          cellClass: "tickerDetailNameCell",
        },
      ];

      if (showHoldingsWeightColumn) {
        columns.push({
          field: "weight",
          headerName: "비중",
          minWidth: 76,
          width: 76,
          type: "rightAligned",
          cellRenderer: (params: { value: number | null }) => formatUnsignedPercent(params.value),
        });
      }

      columns.push(
        {
          field: "current_price",
          headerName: "현재가",
          minWidth: 108,
          width: 108,
          type: "rightAligned",
          cellRenderer: (params: { value: number | null; data?: TickerHoldingRow }) =>
            formatTickerPrice(params.value, String(params.data?.price_currency || "kor")),
        },
        {
          field: "change_pct",
          headerName: "일간(%)",
          minWidth: 88,
          width: 88,
          type: "rightAligned",
          cellRenderer: (params: { value: number | null }) => (
            <span className={getSignedClass(params.value)}>{formatPercent(params.value)}</span>
          ),
        },
      );

      return columns;
    },
    [showHoldingsWeightColumn],
  );

  const displayTitle = selectedTicker
    ? (selectedTicker.name ? `${selectedTicker.name}(${selectedTicker.ticker})` : selectedTicker.ticker)
    : null;

  return (
    <div className="appPageStack appPageStackFill">
      {error ? (
        <div className="appBannerStack">
          <div className="bannerError alert alert-danger mb-0">{error}</div>
        </div>
      ) : null}

      <section className="appSection appSectionFill">
        <div className="card appCard appTableCardFill">
          <div className="card-body appCardBodyTight appTableCardBodyFill">
            {!selectedTicker && !loading ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flex: 1, color: "#5b6778" }}>
                <span style={{ fontSize: 15 }}>티커 또는 종목명을 검색하세요.</span>
              </div>
            ) : (
              <>
                {displayTitle ? (
                  <div className="tickerDetailHero">
                    <div className="tickerDetailHeroLeft">
                      <div className="tickerDetailHeroTitle">{displayTitle}</div>
                      {lastInfo?.close != null ? (
                        <span className="tickerDetailHeroPrice">{formatTickerPrice(lastInfo.close, selectedCountryCode)}</span>
                      ) : null}
                      {lastInfo?.change_pct != null ? (
                        <span className={`tickerDetailHeroChange ${getSignedClass(lastInfo.change_pct)}`}>
                          {formatPercent(lastInfo.change_pct)}
                        </span>
                      ) : null}
                    </div>
                    {rows.length > 0 ? (
                      <div className="tickerDetailHeroRight">
                        <div className="appSegmentedToggle appSegmentedToggleCompact" role="group" aria-label="차트 봉 기준">
                          {[
                            { value: "day", label: "일" },
                            { value: "week", label: "주" },
                            { value: "month", label: "월" },
                          ].map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              className={chartInterval === option.value ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                              onClick={() => setChartInterval(option.value as ChartInterval)}
                            >
                              {option.label}
                            </button>
                          ))}
                        </div>
                        <span style={{ fontSize: 12, color: "#5b6778", fontWeight: 600 }}>이동평균선</span>
                        {MA_PERIODS.map((ma) => (
                          chartRows.length >= ma.period ? (
                            <span key={ma.period} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
                              <span style={{ width: 14, height: 2, backgroundColor: ma.color, display: "inline-block" }} />
                              <span style={{ color: ma.color, fontWeight: 600 }}>{ma.label}</span>
                            </span>
                          ) : null
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {/* 캔들스틱 차트 (고정 높이) */}
                {loading && rows.length === 0 ? (
                  <div style={{ height: 420, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <span className="spinner-border" />
                  </div>
                ) : rows.length > 0 ? (
                  <div style={{ flexShrink: 0 }}>
                    <div className={selectedCountryCode === "kor" ? "tickerDetailTopGrid" : ""}>
                      {selectedCountryCode === "kor" ? (
                        <div className="tickerDetailHoldingsPanel">
                          <div className="tickerDetailTableHeader">
                            <span className="tickerDetailTableTitle">{holdingsPanelTitle}</span>
                            <span className="text-muted tickerDetailTableMeta">{holdingsPanelMeta}</span>
                          </div>
                          {holdingsRows.length > 0 ? (
                            <div className="appGridFillWrap">
                              <AppAgGrid
                                className="tickerDetailHoldingsGrid"
                                rowData={holdingsRows}
                                columnDefs={holdingColumns}
                                loading={loading}
                                theme={gridTheme}
                                gridOptions={{
                                  suppressMovableColumns: true,
                                  getRowId: (params) => String(params.data.id),
                                  onGridReady: (event: GridReadyEvent<TickerHoldingRow>) => {
                                    holdingsGridApiRef.current = event.api;
                                  },
                                }}
                              />
                            </div>
                          ) : (
                            <div className="tickerDetailHoldingsEmpty">
                              {holdingsError ?? "구성종목 데이터를 확인할 수 없습니다."}
                            </div>
                          )}
                        </div>
                      ) : null}
                      <div className="tickerDetailChartWrap">
                        <div ref={chartContainerRef} style={{ width: "100%", position: "relative" }} />
                        {chartBadges.map((badge, index) => (
                          <div
                            key={`${badge.tone}-${index}`}
                            className={badge.tone === "high" ? "tickerDetailChartBadge is-high" : "tickerDetailChartBadge is-low"}
                            style={{ left: badge.left, top: badge.top }}
                          >
                            {badge.tone === "low" ? <span className="tickerDetailChartBadgeArrow" style={{ left: badge.anchorLeft }}>↑</span> : null}
                            <span className="tickerDetailChartBadgeText">{badge.text}</span>
                            {badge.tone === "high" ? <span className="tickerDetailChartBadgeArrow" style={{ left: badge.anchorLeft }}>↓</span> : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                {/* 일별/월별 테이블 (나머지 공간 채움) */}
                {selectedTicker ? (
                  <div className="tickerDetailTables">
                    <div className="tickerDetailTablePanel">
                      <div className="tickerDetailTableHeader">
                        <span className="tickerDetailTableTitle">일별</span>
                        <span className="text-muted tickerDetailTableMeta">
                          총 {new Intl.NumberFormat("ko-KR").format(rows.length)}일
                        </span>
                      </div>
                      <div className="appGridFillWrap">
                        <AppAgGrid
                          rowData={reversedRows}
                          columnDefs={dailyColumns}
                          loading={loading}
                          theme={gridTheme}
                          gridOptions={{ suppressMovableColumns: true }}
                        />
                      </div>
                    </div>
                    <div className="tickerDetailTablePanel">
                      <div className="tickerDetailTableHeader">
                        <span className="tickerDetailTableTitle">월별</span>
                        <span className="text-muted tickerDetailTableMeta">
                          총 {new Intl.NumberFormat("ko-KR").format(monthlyRows.length)}개월
                        </span>
                      </div>
                      <div className="appGridFillWrap">
                        <AppAgGrid
                          rowData={monthlyRows}
                          columnDefs={monthlyColumns}
                          loading={loading}
                          theme={gridTheme}
                          gridOptions={{ suppressMovableColumns: true }}
                        />
                      </div>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
