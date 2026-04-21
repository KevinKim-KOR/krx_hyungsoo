"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { IconPlus } from "@tabler/icons-react";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef, RowClassParams } from "ag-grid-community";
import { useRouter } from "next/navigation";

import { BUCKET_OPTIONS } from "@/lib/bucket-theme";
import { addStockCandidate, loadStocksTable } from "@/lib/stocks-store";
import { AppAgGrid } from "../components/AppAgGrid";
import { AppModal } from "../components/AppModal";
import { useToast } from "../components/ToastProvider";

type MarketRowItem = {
  ticker: string;
  ticker_pools: string;
  name: string;
  listed_at: string;
  daily_change_pct: number | null;
  current_price: number | null;
  nav: number | null;
  deviation: number | null;
  return_3m_pct: number | null;
  prev_volume: number;
  market_cap: number;
  is_held: boolean;
};

type MarketResponse = {
  updated_at?: string | null;
  rows?: MarketRowItem[];
  error?: string;
};

type MarketTickerPool = {
  ticker_type: string;
  order: number;
  name: string;
  icon: string;
};

type MarketGridRow = MarketRowItem & {
  row_number: number;
  __selected__?: boolean;
};

const EXCLUSION_KEYWORD_GROUPS: Record<string, string[]> = {
  인버스: ["인버스"],
  "2X": ["2X"],
  레버리지: ["레버리지"],
  선물: ["선물"],
  "채권(모든종류)": ["채권", "미국채", "국채", "회사채", "단기채", "장기채"],
  혼합: ["혼합"],
  리츠: ["리츠"],
  합성: ["합성"],
  커버드콜: ["커버드콜"],
};

const DEFAULT_EXCLUDED_GROUPS = ["인버스", "2X", "레버리지", "선물", "채권(모든종류)", "혼합", "리츠"];

const marketGridTheme = themeQuartz
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

function formatKrwEok(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function formatNullableNumber(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${value.toFixed(2)}%`;
}

function getSignedMetricClass(value: number | null): string | undefined {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return undefined;
  }
  if (value > 0) {
    return "metricPositive";
  }
  if (value < 0) {
    return "metricNegative";
  }
  return undefined;
}

function getDeviationClass(value: number | null): string | undefined {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return undefined;
  }
  if (value >= 2) {
    return "metricPositive metricStrong";
  }
  if (value <= -2) {
    return "metricNegative metricStrong";
  }
  return undefined;
}

export function MarketManager({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: { filteredCount: number; totalCount: number; updatedAt: string | null }) => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [rows, setRows] = useState<MarketRowItem[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [tickerPools, setTickerPools] = useState<MarketTickerPool[]>([]);
  const [query, setQuery] = useState("");
  const [minMarketCap, setMinMarketCap] = useState("500"); // 시가총액(억)
  const [minPrevVolume, setMinPrevVolume] = useState("100000"); // 거래량(주)
  const [excludedGroups, setExcludedGroups] = useState<string[]>(DEFAULT_EXCLUDED_GROUPS);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [selectedTickerPool, setSelectedTickerPool] = useState("");
  const [selectedBucketId, setSelectedBucketId] = useState<number | "">("");
  const [adding, setAdding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [marketResponse, stocksPayload] = await Promise.all([
        fetch("/api/market", { cache: "no-store" }),
        loadStocksTable().catch(
          () =>
            ({
              ticker_types: [],
              rows: [],
              ticker_type: "",
            }) as { ticker_types: MarketTickerPool[]; rows: unknown[]; ticker_type: string },
        ),
      ]);
      const payload = (await marketResponse.json()) as MarketResponse;
      if (!marketResponse.ok) {
        throw new Error(payload.error ?? "ETF 마켓 데이터를 불러오지 못했습니다.");
      }
      setRows(payload.rows ?? []);
      setUpdatedAt(payload.updated_at ?? null);
      setTickerPools(stocksPayload.ticker_types ?? []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "ETF 마켓 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toUpperCase();
    const expandedKeywords = excludedGroups.flatMap((group) => EXCLUSION_KEYWORD_GROUPS[group] ?? []);
    const marketCapFilter = Number(minMarketCap || 0);
    const volumeFilter = Number(minPrevVolume || 0);

    return rows
      .filter((row) => {
        if (
          normalizedQuery &&
          !row.ticker.toUpperCase().includes(normalizedQuery) &&
          !row.name.toUpperCase().includes(normalizedQuery)
        ) {
          return false;
        }

        if (expandedKeywords.some((keyword) => row.name.includes(keyword))) {
          return false;
        }

        if (marketCapFilter > 0 && row.market_cap < marketCapFilter) {
          return false;
        }

        if (volumeFilter > 0 && row.prev_volume < volumeFilter) {
          return false;
        }

        return true;
      })
      .sort((left, right) => {
        const leftValue = left.daily_change_pct ?? Number.NEGATIVE_INFINITY;
        const rightValue = right.daily_change_pct ?? Number.NEGATIVE_INFINITY;
        if (leftValue !== rightValue) {
          return rightValue - leftValue;
        }
        return left.ticker.localeCompare(right.ticker);
      });
  }, [excludedGroups, minMarketCap, minPrevVolume, query, rows]);

  const gridRows = useMemo<MarketGridRow[]>(
    () => filteredRows.map((row, index) => ({ ...row, row_number: index + 1 })),
    [filteredRows],
  );

  useEffect(() => {
    const visibleTickers = new Set(gridRows.map((row) => row.ticker));
    setSelectedTickers((current) => current.filter((ticker) => visibleTickers.has(ticker)));
  }, [gridRows]);

  useEffect(() => {
    onHeaderSummaryChange?.({
      filteredCount: filteredRows.length,
      totalCount: rows.length,
      updatedAt,
    });
  }, [filteredRows.length, onHeaderSummaryChange, rows.length, updatedAt]);

  const moveToTickerDetail = useCallback(
    (ticker: string) => {
      const normalizedTicker = String(ticker || "").trim().toUpperCase();
      if (!normalizedTicker) {
        return;
      }
      router.push(`/ticker?ticker=${encodeURIComponent(normalizedTicker)}`);
    },
    [router],
  );

  const hasSelectedRows = selectedTickers.length > 0;
  const allVisibleSelected = useMemo(
    () => gridRows.length > 0 && gridRows.every((row) => selectedTickers.includes(row.ticker)),
    [gridRows, selectedTickers],
  );

  const toggleTickerSelection = useCallback((ticker: string) => {
    setSelectedTickers((current) =>
      current.includes(ticker) ? current.filter((item) => item !== ticker) : [...current, ticker],
    );
  }, []);

  const toggleSelectAllVisible = useCallback(() => {
    const visibleTickers = gridRows.map((row) => row.ticker);
    setSelectedTickers((current) => {
      if (visibleTickers.length === 0) {
        return current;
      }
      const allSelected = visibleTickers.every((ticker) => current.includes(ticker));
      if (allSelected) {
        return current.filter((ticker) => !visibleTickers.includes(ticker));
      }
      return [...new Set([...current, ...visibleTickers])];
    });
  }, [gridRows]);

  const handleOpenAddModal = useCallback(() => {
    if (!hasSelectedRows) {
      return;
    }
    setSelectedTickerPool("");
    setSelectedBucketId("");
    setAddModalOpen(true);
  }, [hasSelectedRows]);

  const handleCloseAddModal = useCallback(() => {
    if (adding) {
      return;
    }
    setAddModalOpen(false);
  }, [adding]);

  const handleAddSelected = useCallback(async () => {
    const tickerPool = String(selectedTickerPool || "").trim().toLowerCase();
    const bucketId = Number(selectedBucketId || 0);
    if (!tickerPool || !bucketId) {
      toast.error("종목풀과 버킷을 모두 선택하세요.");
      return;
    }

    setAdding(true);
    let addedCount = 0;
    let duplicateCount = 0;
    const failedTickers: string[] = [];

    for (const ticker of selectedTickers) {
      try {
        await addStockCandidate(tickerPool, ticker, bucketId);
        addedCount += 1;
      } catch (addError) {
        const message = addError instanceof Error ? addError.message : "종목 추가 처리에 실패했습니다.";
        if (message.includes("이미 등록된 종목입니다.")) {
          duplicateCount += 1;
          continue;
        }
        failedTickers.push(ticker);
      }
    }

    setAdding(false);
    setAddModalOpen(false);

    if (addedCount > 0) {
      toast.success(`종목 ${addedCount}개를 추가했습니다.`);
    }
    if (duplicateCount > 0) {
      toast.error(`이미 등록된 종목 ${duplicateCount}개는 건너뛰었습니다.`);
    }
    if (failedTickers.length > 0) {
      toast.error(`추가 실패: ${failedTickers.join(", ")}`);
    }

    if (addedCount > 0) {
      setSelectedTickers([]);
      await load();
    }
  }, [load, selectedBucketId, selectedTickerPool, selectedTickers, toast]);

  const columns = useMemo<ColDef<MarketGridRow>[]>(
    () => [
      { field: "row_number", headerName: "#", width: 72, maxWidth: 80 },
      {
        field: "ticker_pools",
        headerName: "종목풀",
        width: 108,
        maxWidth: 116,
        cellRenderer: (params: { value: string }) => String(params.value ?? "").trim() || "-",
      },
      {
        field: "ticker",
        headerName: "티커",
        width: 104,
        cellRenderer: (params: { value: string }) => {
          const value = String(params.value ?? "-");
          return (
            <button
              type="button"
              className="appCodeText"
              style={{ color: "inherit", textDecoration: "none", background: "none", border: "none", padding: 0 }}
              onClick={() => moveToTickerDetail(value)}
            >
              {value}
            </button>
          );
        },
      },
      {
        field: "name",
        headerName: "종목명",
        minWidth: 220,
        flex: 1,
        cellClass: "marketNameCell",
        cellRenderer: (params: { value: string | null | undefined }) => {
          const value = String(params.value ?? "-");
          return (
            <span className="marketNameMain" title={value}>
              {value}
            </span>
          );
        },
      },
      {
        field: "daily_change_pct",
        headerName: "일간(%)",
        width: 112,
        type: "rightAligned",
        sort: "desc",
        comparator: (a, b) => (a ?? Number.NEGATIVE_INFINITY) - (b ?? Number.NEGATIVE_INFINITY),
        cellRenderer: (params: { value: number | null }) => (
          <span className={getSignedMetricClass(params.value)}>{formatPercent(params.value)}</span>
        ),
      },
      {
        field: "current_price",
        headerName: "현재가",
        width: 110,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => formatNullableNumber(params.value),
      },
      {
        field: "nav",
        headerName: "Nav",
        width: 110,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => formatNullableNumber(params.value),
      },
      {
        field: "deviation",
        headerName: "괴리율",
        width: 96,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => (
          <span className={getDeviationClass(params.value)}>{formatPercent(params.value)}</span>
        ),
      },
      {
        field: "return_3m_pct",
        headerName: "3달(%)",
        width: 96,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null }) => (
          <span className={getSignedMetricClass(params.value)}>{formatPercent(params.value)}</span>
        ),
      },
      { field: "listed_at", headerName: "상장일", width: 112 },
      {
        field: "prev_volume",
        headerName: "전일거래량(주)",
        width: 128,
        type: "rightAligned",
        cellRenderer: (params: { value: number }) => formatCount(params.value),
      },
      {
        field: "market_cap",
        headerName: "시가총액(억)",
        width: 128,
        type: "rightAligned",
        cellRenderer: (params: { value: number }) => formatKrwEok(params.value),
      },
      {
        field: "__selected__",
        headerName: "",
        width: 52,
        maxWidth: 52,
        sortable: false,
        filter: false,
        suppressHeaderMenuButton: true,
        suppressColumnsToolPanel: true,
        headerComponent: () => (
          <input
            type="checkbox"
            aria-label="전체 선택"
            checked={allVisibleSelected}
            onChange={() => toggleSelectAllVisible()}
          />
        ),
        cellRenderer: (params: { data?: MarketGridRow }) => {
          const ticker = String(params.data?.ticker ?? "").trim();
          if (!ticker) {
            return null;
          }
          return (
            <input
              type="checkbox"
              aria-label={`${ticker} 선택`}
              checked={selectedTickers.includes(ticker)}
              onChange={() => toggleTickerSelection(ticker)}
              onClick={(event) => event.stopPropagation()}
            />
          );
        },
      },
    ],
    [allVisibleSelected, moveToTickerDetail, selectedTickers, toggleSelectAllVisible, toggleTickerSelection],
  );

  function toggleGroup(group: string) {
    setExcludedGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  }

  return (
    <div className="appPageStack appPageStackFill">
      {error ? (
        <div className="appBannerStack">
          <div className="bannerError">{error}</div>
        </div>
      ) : null}
      <section className="appSection appSectionFill">
        <div className="card appCard appTableCardFill">
          <div className="card-header">
            <div className="appMainHeader marketMainHeader">
              <div className="appMainHeaderLeft marketMainHeaderLeft">
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">티커/종목명</span>
                  <input
                    className="field compactField"
                    type="text"
                    placeholder="티커 또는 종목명을 입력"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">시가총액(억)</span>
                  <input
                    className="field compactField"
                    type="number"
                    placeholder="최소 시가총액"
                    value={minMarketCap}
                    onChange={(event) => setMinMarketCap(event.target.value)}
                  />
                </label>
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">거래량(주)</span>
                  <input
                    className="field compactField"
                    type="number"
                    placeholder="최소 전일 거래량"
                    value={minPrevVolume}
                    onChange={(event) => setMinPrevVolume(event.target.value)}
                  />
                </label>
              </div>
              <div className="appMainHeaderRight">
                <button
                  type="button"
                  className="btn btn-success btn-sm px-3 fw-bold d-flex align-items-center gap-1"
                  onClick={handleOpenAddModal}
                  disabled={!hasSelectedRows}
                >
                  <IconPlus size={16} stroke={2} />
                  추가
                </button>
              </div>
            </div>
          </div>
          <div className="card-body appCardBodyTight appTableCardBodyFill">
            <div className="pillRow">
              {Object.keys(EXCLUSION_KEYWORD_GROUPS).map((group) => {
                const isActive = excludedGroups.includes(group);
                return (
                  <button
                    key={group}
                    type="button"
                    className={isActive ? "filterPill filterPillActive" : "filterPill"}
                    onClick={() => toggleGroup(group)}
                  >
                    {group}
                  </button>
                );
              })}
            </div>

            <div className="appGridFillWrap" style={{ minHeight: 0 }}>
              <AppAgGrid
                rowData={gridRows}
                columnDefs={columns}
                loading={loading}
                minHeight="100%"
                theme={marketGridTheme}
                getRowClass={(params: RowClassParams<MarketGridRow>) => (params.data?.is_held ? "appHeldRow" : "")}
                gridOptions={{
                  suppressMovableColumns: true,
                }}
              />
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        .marketNameCell {
          min-width: 0;
          overflow: hidden;
        }
      `}</style>

      <style jsx>{`
        .marketNameMain {
          display: block;
          width: 100%;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .appModalFormStack {
          display: grid;
          gap: 0.875rem;
        }
      `}</style>

      <AppModal
        open={addModalOpen}
        title="종목풀 추가"
        subtitle={`선택한 종목 ${selectedTickers.length}개를 추가합니다.`}
        onClose={handleCloseAddModal}
        footer={
          <>
            <button type="button" className="btn btn-ghost-secondary" onClick={handleCloseAddModal} disabled={adding}>
              취소
            </button>
            <button
              type="button"
              className="btn btn-success"
              onClick={() => void handleAddSelected()}
              disabled={!selectedTickerPool || !selectedBucketId || adding}
            >
              {adding ? "추가 중..." : "추가"}
            </button>
          </>
        }
      >
        <div className="appModalFormStack">
          <label className="appLabeledField">
            <span className="appLabeledFieldLabel">종목풀</span>
            <select
              className="field compactField"
              value={selectedTickerPool}
              onChange={(event) => setSelectedTickerPool(event.target.value)}
            >
              <option value="">종목풀 선택</option>
              {tickerPools.map((pool) => (
                <option key={pool.ticker_type} value={pool.ticker_type}>
                  {pool.name}
                </option>
              ))}
            </select>
          </label>
          <label className="appLabeledField">
            <span className="appLabeledFieldLabel">버킷</span>
            <select
              className="field compactField"
              value={selectedBucketId}
              onChange={(event) => setSelectedBucketId(event.target.value ? Number(event.target.value) : "")}
            >
              <option value="">버킷 선택</option>
              {BUCKET_OPTIONS.map((bucket) => (
                <option key={bucket.id} value={bucket.id}>
                  {bucket.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </AppModal>
    </div>
  );
}
