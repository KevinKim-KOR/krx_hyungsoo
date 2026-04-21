"use client";

import { IconDeviceFloppy, IconPlus, IconTrash } from "@tabler/icons-react";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef, RowClassParams } from "ag-grid-community";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import { BUCKET_OPTIONS } from "@/lib/bucket-theme";
import { addStockCandidate, deleteStock, updateStockBucket, validateStockCandidate } from "@/lib/stocks-store";
import {
  readRememberedTickerType,
  writeRememberedTickerType,
} from "../components/account-selection";
import { AppAgGrid } from "../components/AppAgGrid";
import { AppModal } from "../components/AppModal";
import { useToast } from "../components/ToastProvider";

type RankTickerType = {
  ticker_type: string;
  order: number;
  name: string;
  icon: string;
  country_code: string;
};

type RankMaRule = {
  order: number;
  ma_type: string;
  ma_months: number;
  ma_days: number;
  score_column: string;
};

type RankRow = {
  [key: string]: string | number | boolean | null;
  순번: string;
  순위: number | null;
  이전순위: number | null;
  버킷: string;
  bucket: number;
  티커: string;
  종목명: string;
  상장일: string;
  점수: number | null;
  보유: string;
  현재가: number | null;
  "괴리율": number | null;
  "일간(%)": number | null;
  "1주(%)": number | null;
  "2주(%)": number | null;
  "3주(%)": number | null;
  "4주(%)": number | null;
  "1달(%)": number | null;
  "2달(%)": number | null;
  "3달(%)": number | null;
  "4달(%)": number | null;
  "5달(%)": number | null;
  "6달(%)": number | null;
  "7달(%)": number | null;
  "8달(%)": number | null;
  "9달(%)": number | null;
  "10달(%)": number | null;
  "11달(%)": number | null;
  "12달(%)": number | null;
  고점: number | null;
  RSI: number | null;
  배당률: number | null;
  보수: number | null;
  순자산총액: number | null;
  "전일 거래량(주)": number | null;
};

type RankResponse = {
  ticker_types?: RankTickerType[];
  ticker_type?: string;
  ma_rules?: RankMaRule[];
  ma_type_options?: string[];
  ma_months_max?: number;
  as_of_date?: string | null;
  monthly_return_labels?: string[];
  rows?: RankRow[];
  cache_blocked?: boolean;
  latest_trading_day?: string | null;
  cache_updated_at?: string | null;
  ranking_computed_at?: string | null;
  realtime_fetched_at?: string | null;
  previous_trading_day?: string | null;
  missing_tickers?: string[];
  missing_ticker_labels?: string[];
  stale_tickers?: string[];
  error?: string;
};

type RankGridRow = RankRow & {
  id: string;
  __isAddingRow?: boolean;
};

type RankAddingRowState = {
  ticker: string;
  name: string;
  listing_date: string;
  bucket: number;
  status: "active" | "deleted" | "new" | null;
  is_validating: boolean;
  is_validated: boolean;
};

const rankGridTheme = themeQuartz
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

type RankToolbarCache = {
  ticker_types: RankTickerType[];
  ticker_type: string;
  ma_rules: RankMaRule[];
  ma_type_options: string[];
  ma_months_max: number;
};

type RankHeaderSummary = {
  upCount: number;
  upPct: number;
  totalCount: number;
  ruleSummary: string;
};

let rankToolbarCache: RankToolbarCache | null = null;
const HELD_BONUS_SCORE_STORAGE_KEY = "stocks-held-bonus-score";

function getTodayDateInputValue(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
}

function toDateInputValue(value: string | null | undefined): string {
  if (!value) {
    return getTodayDateInputValue();
  }
  return String(value).slice(0, 10);
}

function formatNumber(value: number | null, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${value.toFixed(2)}%`;
}

function getSignedClass(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "";
  }
  return value > 0 ? "metricPositive" : "metricNegative";
}

function getBucketCellClass(bucketLabel: string): string {
  const match = /^(\d+)/.exec(String(bucketLabel || "").trim());
  if (!match) {
    return "rankBucketCell";
  }
  return `rankBucketCell rankBucketCell${match[1]}`;
}

function normalizeTicker(value: string): string {
  return String(value || "").trim().toUpperCase();
}

function getBucketName(bucketId: number): string {
  return BUCKET_OPTIONS.find((option) => option.id === bucketId)?.name ?? BUCKET_OPTIONS[0]?.name ?? "-";
}

function getBucketIdByName(bucketName: string): number {
  return BUCKET_OPTIONS.find((option) => option.name === bucketName)?.id ?? BUCKET_OPTIONS[0]?.id ?? 1;
}

function buildDirtyCellKey(rowId: string, field: string): string {
  return `${rowId}::${field}`;
}

function formatMetaTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function renderSignedPercentCell(value: number | null) {
  return <span className={getSignedClass(value ?? null)}>{formatPercent(value ?? null)}</span>;
}

function formatCurrencyValue(value: number | null, countryCode?: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const digits = countryCode === "au" ? 2 : 0;
  return formatNumber(value, digits);
}

function formatAssetInEok(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${formatNumber(value / 100_000_000, 0)}억`;
}

function clampHeldBonusScore(value: number): number {
  if (Number.isNaN(value) || value < 0) {
    return 0;
  }
  if (value > 50) {
    return 50;
  }
  return Math.round(value / 5) * 5;
}

function readHeldBonusScore(): number {
  if (typeof window === "undefined") {
    return 0;
  }
  return clampHeldBonusScore(Number(window.localStorage.getItem(HELD_BONUS_SCORE_STORAGE_KEY) ?? "0"));
}

function writeHeldBonusScore(value: number): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(HELD_BONUS_SCORE_STORAGE_KEY, String(clampHeldBonusScore(value)));
}

export function StocksManager({ onHeaderSummaryChange }: { onHeaderSummaryChange?: (summary: RankHeaderSummary) => void }) {
  const router = useRouter();
  const toast = useToast();
  const lastBlockedToastRef = useRef<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [pageMode, setPageMode] = useState<"rank" | "manage">("rank");
  const [ticker_types, setAccounts] = useState<RankTickerType[]>(rankToolbarCache?.ticker_types ?? []);
  const [selectedTickerType, setSelectedAccountId] = useState(
    rankToolbarCache?.ticker_type ?? readRememberedTickerType() ?? "",
  );
  const [maRules, setMaRules] = useState<RankMaRule[]>(rankToolbarCache?.ma_rules ?? []);
  const [maTypeOptions, setMaTypeOptions] = useState<string[]>(rankToolbarCache?.ma_type_options ?? []);
  const [maMonthsMax, setMaMonthsMax] = useState(rankToolbarCache?.ma_months_max ?? 12);
  const [metricMode, setMetricMode] = useState<"cumulative" | "monthly" | "info">("cumulative");
  const [heldBonusScore, setHeldBonusScore] = useState(0);
  const [monthlyReturnLabels, setMonthlyReturnLabels] = useState<string[]>([]);
  const [selectedAsOfDate, setSelectedAsOfDate] = useState<string>(getTodayDateInputValue());
  const [rows, setRows] = useState<RankRow[]>([]);
  const [cacheBlocked, setCacheBlocked] = useState(false);
  const [rankingComputedAt, setRankingComputedAt] = useState<string | null>(null);
  const [realtimeFetchedAt, setRealtimeFetchedAt] = useState<string | null>(null);
  const [missingTickers, setMissingTickers] = useState<string[]>([]);
  const [missingTickerLabels, setMissingTickerLabels] = useState<string[]>([]);
  const [staleTickers, setStaleTickers] = useState<string[]>([]);
  const [addingRow, setAddingRow] = useState<RankAddingRowState | null>(null);
  const [addingTickerDraft, setAddingTickerDraft] = useState("");
  const [dirtyRowIds, setDirtyRowIds] = useState<string[]>([]);
  const [dirtyCellKeys, setDirtyCellKeys] = useState<string[]>([]);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function clearCacheWarningState() {
    setCacheBlocked(false);
    setMissingTickers([]);
    setMissingTickerLabels([]);
    setStaleTickers([]);
  }

  async function load(next?: { ticker_type?: string; ma_rule_overrides?: RankMaRule[]; as_of_date?: string }) {
    setLoading(true);
    setError(null);
    clearCacheWarningState();

    try {
      const search = new URLSearchParams();
      if (next?.ticker_type) {
        search.set("ticker_type", next.ticker_type);
      }
      if (next?.as_of_date) {
        search.set("as_of_date", next.as_of_date);
      }
      for (const rule of next?.ma_rule_overrides ?? []) {
        search.set(`rule${rule.order}_ma_type`, rule.ma_type);
        search.set(`rule${rule.order}_ma_months`, String(rule.ma_months));
      }

      const query = search.size > 0 ? `?${search.toString()}` : "";
      const response = await fetch(`/api/rank${query}`, { cache: "no-store" });
      const payload = (await response.json()) as RankResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "순위 데이터를 불러오지 못했습니다.");
      }

      setAccounts(payload.ticker_types ?? []);
      const nextAccountId = payload.ticker_type ?? "";
      setSelectedAccountId(nextAccountId);
      writeRememberedTickerType(nextAccountId);
      setMaRules(payload.ma_rules ?? []);
      setMaTypeOptions(payload.ma_type_options ?? []);
      setMaMonthsMax(payload.ma_months_max ?? 12);
      setSelectedAsOfDate(toDateInputValue(payload.as_of_date));
      setMonthlyReturnLabels(payload.monthly_return_labels ?? []);
      rankToolbarCache = {
        ticker_types: payload.ticker_types ?? [],
        ticker_type: nextAccountId,
        ma_rules: payload.ma_rules ?? [],
        ma_type_options: payload.ma_type_options ?? [],
        ma_months_max: payload.ma_months_max ?? 12,
      };
      setAddingRow(null);
      setAddingTickerDraft("");
      setDirtyRowIds([]);
      setDirtyCellKeys([]);
      setSelectedTickers([]);
      setDeleteConfirmOpen(false);
      setRows(payload.rows ?? []);
      setCacheBlocked(Boolean(payload.cache_blocked));
      setRankingComputedAt(payload.ranking_computed_at ?? null);
      setRealtimeFetchedAt(payload.realtime_fetched_at ?? null);
      setMissingTickers(payload.missing_tickers ?? []);
      setMissingTickerLabels(payload.missing_ticker_labels ?? []);
      setStaleTickers(payload.stale_tickers ?? []);
    } catch (loadError) {
      let msg = loadError instanceof Error ? loadError.message : "순위 데이터를 불러오지 못했습니다.";
      if (msg.includes("Unexpected token") || msg.includes("fetch failed") || msg === "순위 데이터를 불러오지 못했습니다.") {
        msg = "몽고디비 데이터베이스 응답 지연(타임아웃)으로 인해 순위 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.";
      }
      setError(msg);
      if (msg.includes("몽고디비 데이터베이스")) {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("db_error_occurred"));
        }
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load({ ticker_type: readRememberedTickerType() ?? undefined, as_of_date: getTodayDateInputValue() });
  }, []);

  useEffect(() => {
    setHeldBonusScore(readHeldBonusScore());
  }, []);

  function handleHeldBonusScoreChange(nextValue: number) {
    const normalized = clampHeldBonusScore(nextValue);
    setHeldBonusScore(normalized);
    writeHeldBonusScore(normalized);
  }

  const moveToTickerDetail = useMemo(
    () => (ticker: string | null | undefined) => {
      const normalizedTicker = String(ticker ?? "-").trim().toUpperCase();
      if (!normalizedTicker || normalizedTicker === "-") {
        return;
      }
      router.push(`/ticker?ticker=${encodeURIComponent(normalizedTicker)}`);
    },
    [router],
  );

  const selectedTickerTypeItem = useMemo(
    () => ticker_types.find((account) => account.ticker_type === selectedTickerType) ?? null,
    [ticker_types, selectedTickerType],
  );

  const gridRows = useMemo<RankGridRow[]>(
    () =>
      rows.map((row, index) => ({
        ...row,
        id: normalizeTicker(String(row.티커 ?? `${index}`)),
      })),
    [rows],
  );

  const rankedGridRows = useMemo<RankGridRow[]>(() => {
    if (heldBonusScore <= 0) {
      return gridRows;
    }

    return [...gridRows]
      .map((row, index) => {
        const baseScore = typeof row.점수 === "number" ? row.점수 : null;
        const isHeld = String(row.보유 ?? "").trim() !== "";
        return {
          ...row,
          __baseIndex: index,
          점수: baseScore === null ? null : Number((baseScore + (isHeld ? heldBonusScore : 0)).toFixed(1)),
        };
      })
      .sort((left, right) => {
        const leftScore = typeof left.점수 === "number" ? left.점수 : null;
        const rightScore = typeof right.점수 === "number" ? right.점수 : null;
        if (leftScore === null && rightScore === null) {
          return Number(left.__baseIndex ?? 0) - Number(right.__baseIndex ?? 0);
        }
        if (leftScore === null) {
          return 1;
        }
        if (rightScore === null) {
          return -1;
        }
        if (rightScore !== leftScore) {
          return rightScore - leftScore;
        }
        return Number(left.__baseIndex ?? 0) - Number(right.__baseIndex ?? 0);
      })
      .map((row, index) => ({
        ...row,
        순위: index + 1,
      }));
  }, [gridRows, heldBonusScore]);

  const displayGridRows = useMemo<RankGridRow[]>(() => {
    if (pageMode !== "manage" || !addingRow) {
      return pageMode === "rank" ? rankedGridRows : gridRows;
    }
    return [
      {
        id: "__adding__",
        __isAddingRow: true,
        순번: "-",
        순위: null,
        이전순위: null,
        버킷: getBucketName(addingRow.bucket),
        bucket: addingRow.bucket,
        티커: addingRow.ticker,
        종목명: addingRow.name,
        상장일: addingRow.listing_date || "-",
        점수: null,
        보유: "",
        현재가: null,
        괴리율: null,
        "일간(%)": null,
        "1주(%)": null,
        "2주(%)": null,
        "3주(%)": null,
        "4주(%)": null,
        "1달(%)": null,
        "2달(%)": null,
        "3달(%)": null,
        "4달(%)": null,
        "5달(%)": null,
        "6달(%)": null,
        "7달(%)": null,
        "8달(%)": null,
        "9달(%)": null,
        "10달(%)": null,
        "11달(%)": null,
        "12달(%)": null,
        고점: null,
        RSI: null,
        배당률: null,
        보수: null,
        순자산총액: null,
        "전일 거래량(주)": null,
      },
      ...gridRows,
    ];
  }, [addingRow, gridRows, pageMode, rankedGridRows]);

  const maRuleSummary = useMemo(
    () => maRules.map((rule) => `추세${rule.order}: ${rule.ma_type} ${rule.ma_months}개월`),
    [maRules],
  );

  const columns = useMemo<ColDef<RankGridRow>[]>(() => {
    const leadingColumns: ColDef<RankGridRow>[] = [
      {
        field: "순위",
        headerName: "순위",
        minWidth: 52,
        width: 52,
        cellStyle: { textAlign: "center" },
        cellRenderer: (params: { value: number | null | undefined }) => {
          return (
            <span style={{ fontWeight: 700 }}>{params.value == null ? "-" : formatNumber(params.value, 0)}</span>
          );
        },
      },
      {
        field: "이전순위",
        headerName: "이전순위",
        minWidth: 98,
        width: 98,
        cellStyle: { textAlign: "center" },
        sortable: false,
        cellRenderer: (params: { data?: RankGridRow; value: number | null | undefined }) => {
          const currentRank = params.data?.순위 ?? null;
          const previousRank = params.value ?? null;
          if (currentRank === null || currentRank === undefined || previousRank === null || previousRank === undefined) {
            return <span style={{ fontWeight: 600 }}>-</span>;
          }

          if (currentRank === previousRank) {
            return (
              <span style={{ fontWeight: 600 }}>
                {currentRank}(-)
              </span>
            );
          }

          const isRise = currentRank < previousRank;
          const delta = Math.abs(currentRank - previousRank);
          return (
            <span style={{ color: isRise ? "#d63939" : "#206bc4", fontWeight: 700 }}>
              {currentRank}({isRise ? `+${delta}` : `-${delta}`} {isRise ? "▲" : "▼"})
            </span>
          );
        },
      },
      {
        field: "버킷",
        headerName: "버킷",
        minWidth: 108,
        width: 108,
        sortable: true,
        comparator: (_a, _b, nodeA, nodeB) => {
          const aId = Number(nodeA.data?.bucket ?? 0);
          const bId = Number(nodeB.data?.bucket ?? 0);
          return aId - bId;
        },
        cellClass: (params) => {
          const dirtyClass =
            params.data && dirtyCellKeys.includes(buildDirtyCellKey(params.data.id, "버킷")) ? " rankDirtyCell" : "";
          return `${getBucketCellClass(String(params.value ?? ""))}${dirtyClass}`;
        },
        editable: (params) => pageMode === "manage" && !params.data?.__isAddingRow,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: {
          values: BUCKET_OPTIONS.map((option) => option.name),
        },
        valueGetter: (params) => getBucketName(Number(params.data?.bucket ?? 1)),
        valueSetter: (params) => {
          if (!params.data || params.data.__isAddingRow) {
            return false;
          }
          const nextBucketId = getBucketIdByName(String(params.newValue ?? ""));
          params.data.bucket = nextBucketId;
          params.data.버킷 = getBucketName(nextBucketId);
          return true;
        },
        cellRenderer: (params: { data?: RankGridRow }) => {
          if (params.data?.__isAddingRow) {
            return (
              <select
                className="form-select form-select-sm"
                value={addingRow?.bucket ?? 1}
                onChange={(event) =>
                  setAddingRow((prev) =>
                    prev
                      ? {
                          ...prev,
                          bucket: Number(event.target.value),
                        }
                      : null,
                  )
                }
              >
                {BUCKET_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            );
          }
          return <span>{getBucketName(Number(params.data?.bucket ?? 1))}</span>;
        },
      },
      {
        field: "티커",
        headerName: "티커",
        minWidth: 92,
        width: 92,
        cellRenderer: (params: { value: string | null | undefined; data?: RankGridRow }) => {
          if (params.data?.__isAddingRow) {
            return (
              <div className="stocksTickerLookup">
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={addingTickerDraft}
                  onChange={(event) => setAddingTickerDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      void handleValidateAddingTicker(event.currentTarget.value);
                    }
                  }}
                />
              </div>
            );
          }
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
        field: "종목명",
        headerName: "종목명",
        minWidth: 260,
        flex: 1.2,
        cellRenderer: (params: { value: string | null | undefined; data?: RankGridRow }) => {
          if (params.data?.__isAddingRow) {
            const draftTicker = normalizeTicker(addingTickerDraft);
            const validatedTicker = normalizeTicker(addingRow?.ticker ?? "");
            const isDraftDirty = Boolean(draftTicker) && draftTicker !== validatedTicker;
            if (addingRow?.is_validating) {
              return <span className="text-muted">티커 확인 중...</span>;
            }
            if (!isDraftDirty && addingRow?.status === "active") {
              return <span className="text-danger fw-bold">이미 등록된 종목입니다.</span>;
            }
            if (!isDraftDirty && addingRow?.is_validated) {
              return (
                <span className="rankNameCellText fw-semibold" title={addingRow.name}>
                  {addingRow.name}
                </span>
              );
            }
            return (
              <div className="rankAddingNameCell">
                <span className="text-muted">티커 확인 후 종목명이 표시됩니다.</span>
                <button
                  className="btn btn-outline-primary btn-sm"
                  type="button"
                  onClick={() => void handleValidateAddingTicker(addingTickerDraft)}
                  disabled={!addingTickerDraft.trim() || addingRow?.is_validating}
                >
                  확인
                </button>
              </div>
            );
          }
          const value = String(params.value ?? "-");
          return <span className="rankNameCellText" title={value}>{value}</span>;
        },
      },
      {
        field: "현재가",
        headerName: "현재가",
        minWidth: 88,
        width: 88,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) =>
          formatNumber(params.value ?? null, selectedTickerTypeItem?.country_code === "au" ? 2 : 0),
      },
      {
        field: "일간(%)",
        headerName: "일간(%)",
        minWidth: 96,
        width: 96,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
      },
    ];

    const cumulativeColumns: ColDef<RankGridRow>[] = [
      {
        field: "점수",
        headerName: "점수",
        minWidth: 72,
        width: 72,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatNumber(params.value ?? null, 1),
      },
      ...maRules.map(
        (rule) =>
          ({
            field: rule.score_column,
            headerName: `추세${rule.order}`,
            minWidth: 72,
            width: 72,
            type: "rightAligned",
            cellRenderer: (params: { value: number | null | undefined }) => formatNumber(params.value ?? null, 1),
          }) as ColDef<RankGridRow>,
      ),
      ...(selectedTickerTypeItem?.country_code !== "au"
        ? [
            {
              field: "괴리율",
              headerName: "괴리율",
              minWidth: 88,
              width: 88,
              type: "rightAligned",
              cellRenderer: (params: { value: number | null | undefined }) => {
                const val = params.value ?? 0;
                const isExtreme = val > 2.0 || val < -2.0;
                return (
                  <span style={{ color: isExtreme ? "#d63939" : "inherit", fontWeight: isExtreme ? 700 : 400 }}>
                    {formatPercent(params.value ?? null)}
                  </span>
                );
              },
            } as ColDef<RankGridRow>,
          ]
        : []),
      {
        field: "고점",
        headerName: "고점",
        minWidth: 80,
        width: 80,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => {
          const value = params.value ?? null;
          const isHighlighted = value !== null && value >= -5;
          return (
            <span style={{ color: isHighlighted ? "#7952b3" : "inherit", fontWeight: isHighlighted ? 700 : 400 }}>
              {formatPercent(value)}
            </span>
          );
        },
      },
      {
        field: "1주(%)",
        headerName: "1주(%)",
        minWidth: 88,
        width: 88,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
      },
      {
        field: "2주(%)",
        headerName: "2주(%)",
        minWidth: 88,
        width: 88,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
      },
      {
        field: "3주(%)",
        headerName: "3주(%)",
        minWidth: 88,
        width: 88,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
      },
      {
        field: "4주(%)",
        headerName: "4주(%)",
        minWidth: 88,
        width: 88,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
      },
      {
        field: "RSI",
        headerName: "RSI",
        minWidth: 74,
        width: 74,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatNumber(params.value ?? null, 1),
      },
      ...[
        "1달(%)",
        "2달(%)",
        "3달(%)",
        "4달(%)",
        "5달(%)",
        "6달(%)",
        "7달(%)",
        "8달(%)",
        "9달(%)",
        "10달(%)",
        "11달(%)",
        "12달(%)",
      ].map(
        (field) =>
          ({
            field,
            headerName: field,
            minWidth: field.length > 6 ? 94 : 88,
            width: field.length > 6 ? 94 : 88,
            type: "rightAligned",
            cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
          }) as ColDef<RankGridRow>,
      ),
    ];

    const monthlyColumns: ColDef<RankGridRow>[] = monthlyReturnLabels.map(
      (label) =>
        ({
          field: label,
          headerName: label,
          minWidth: 108,
          width: 108,
          type: "rightAligned",
          cellRenderer: (params: { value: number | null | undefined }) => renderSignedPercentCell(params.value ?? null),
        }) as ColDef<RankGridRow>,
    );

    const monthlyLeadingColumns: ColDef<RankGridRow>[] = [
      {
        field: "점수",
        headerName: "점수",
        minWidth: 72,
        width: 72,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatNumber(params.value ?? null, 1),
      },
      ...maRules.map(
        (rule) =>
          ({
            field: rule.score_column,
            headerName: `추세${rule.order}`,
            minWidth: 72,
            width: 72,
            type: "rightAligned",
            cellRenderer: (params: { value: number | null | undefined }) => formatNumber(params.value ?? null, 1),
          }) as ColDef<RankGridRow>,
      ),
    ];

    const infoColumns: ColDef<RankGridRow>[] = [
      {
        field: "배당률",
        headerName: "배당률",
        minWidth: 92,
        width: 92,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatPercent(params.value ?? null),
      },
      {
        field: "보수",
        headerName: "보수",
        minWidth: 92,
        width: 92,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatPercent(params.value ?? null),
      },
      {
        field: "순자산총액",
        headerName: "순자산총액",
        minWidth: 132,
        width: 132,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatAssetInEok(params.value ?? null),
      },
      {
        field: "거래량",
        headerName: "거래량",
        minWidth: 100,
        width: 100,
        type: "rightAligned",
        cellRenderer: (params: { value: number | null | undefined }) => formatNumber(params.value ?? null, 0),
      },
      {
        field: "상장일",
        headerName: "상장일",
        minWidth: 110,
        width: 110,
        cellRenderer: (params: { value: string | null | undefined }) => String(params.value ?? "-"),
      },
    ];

    return [
      ...leadingColumns,
      ...(metricMode === "cumulative"
        ? cumulativeColumns
        : metricMode === "monthly"
          ? [...monthlyLeadingColumns, ...monthlyColumns]
          : [...monthlyLeadingColumns, ...infoColumns]),
    ];
  }, [
    addingRow,
    addingTickerDraft,
    dirtyCellKeys,
    maRules,
    metricMode,
    monthlyReturnLabels,
    pageMode,
    selectedTickerType,
    selectedTickerTypeItem?.country_code,
  ]);

  function handleTickerTypeChange(accountId: string) {
    setSelectedAccountId(accountId);
    writeRememberedTickerType(accountId);
    void load({ ticker_type: accountId, as_of_date: selectedAsOfDate });
  }

  function handleMaRuleTypeChange(order: number, nextMaType: string) {
    const nextRules = maRules.map((rule) => (rule.order === order ? { ...rule, ma_type: nextMaType } : rule));
    setMaRules(nextRules);
    void load({ ticker_type: selectedTickerType, ma_rule_overrides: nextRules, as_of_date: selectedAsOfDate });
  }

  function handleMaRuleMonthsChange(order: number, nextMaMonths: number) {
    const nextRules = maRules.map((rule) => (rule.order === order ? { ...rule, ma_months: nextMaMonths } : rule));
    setMaRules(nextRules);
    void load({ ticker_type: selectedTickerType, ma_rule_overrides: nextRules, as_of_date: selectedAsOfDate });
  }

  function handleAsOfDateChange(nextAsOfDate: string) {
    setSelectedAsOfDate(nextAsOfDate);
    void load({ ticker_type: selectedTickerType, ma_rule_overrides: maRules, as_of_date: nextAsOfDate });
  }

  function showErrorToast(message: string) {
    toast.error(`[ETF-순위] ${message}`);
  }

  function handleAddRow() {
    if (addingRow) {
      return;
    }
    setAddingTickerDraft("");
    setAddingRow({
      ticker: "",
      name: "",
      listing_date: "-",
      bucket: 1,
      status: null,
      is_validating: false,
      is_validated: false,
    });
  }

  function handleBucketChanged(row: RankGridRow | undefined, bucketName: string) {
    if (!row || row.__isAddingRow) {
      return;
    }
    const nextBucketId = getBucketIdByName(bucketName);
    setRows((prev) =>
      prev.map((currentRow) =>
        normalizeTicker(String(currentRow.티커 ?? "")) === row.id
          ? {
              ...currentRow,
              bucket: nextBucketId,
              버킷: getBucketName(nextBucketId),
            }
          : currentRow,
      ),
    );
    setDirtyRowIds((prev) => (prev.includes(row.id) ? prev : [...prev, row.id]));
    const dirtyCellKey = buildDirtyCellKey(row.id, "버킷");
    setDirtyCellKeys((prev) => (prev.includes(dirtyCellKey) ? prev : [...prev, dirtyCellKey]));
  }

  async function handleValidateAddingTicker(tickerInput?: string) {
    const ticker = normalizeTicker(tickerInput ?? addingTickerDraft ?? addingRow?.ticker ?? "");
    if (!ticker || !selectedTickerType || !addingRow || addingRow.is_validating) {
      return;
    }

    try {
      setAddingRow((prev) => (prev ? { ...prev, ticker, is_validating: true } : null));
      const validated = await validateStockCandidate(selectedTickerType, ticker);
      setAddingTickerDraft(normalizeTicker(validated.ticker));
      setAddingRow((prev) =>
        prev
          ? {
              ...prev,
              ticker: normalizeTicker(validated.ticker),
              name: String(validated.name ?? "").trim(),
              listing_date: String(validated.listing_date ?? "-").trim() || "-",
              bucket: Number(validated.bucket_id ?? prev.bucket ?? 1),
              status: validated.status,
              is_validating: false,
              is_validated: validated.status !== "active",
            }
          : null,
      );
      if (validated.status === "active") {
        showErrorToast("이미 등록된 종목입니다.");
        return;
      }
      toast.success(`[ETF-순위] ${validated.name}(${validated.ticker}) 확인 완료`);
    } catch (validationError) {
      setAddingRow((prev) =>
        prev
          ? {
              ...prev,
              ticker,
              is_validating: false,
              is_validated: false,
            }
          : null,
      );
      showErrorToast(validationError instanceof Error ? validationError.message : "티커 확인에 실패했습니다.");
    }
  }

  async function processAddingRow() {
    if (!addingRow || !addingRow.is_validated) {
      throw new Error("추가할 종목을 먼저 확인하세요.");
    }

    const created = await addStockCandidate(selectedTickerType, addingRow.ticker, addingRow.bucket);
    toast.success(`[ETF-순위] ${created.name}(${created.ticker}) 추가 완료`);
  }

  async function processDirtyRows() {
    const dirtyRows = rows.filter((row) => dirtyRowIds.includes(normalizeTicker(String(row.티커 ?? ""))));
    for (const row of dirtyRows) {
      await updateStockBucket(selectedTickerType, String(row.티커 ?? ""), Number(row.bucket ?? 1));
    }
  }

  function handleSaveChanges() {
    if (!selectedTickerType || (!addingRow && dirtyRowIds.length === 0)) {
      return;
    }

    startTransition(async () => {
      try {
        if (addingRow) {
          await processAddingRow();
        }
        if (dirtyRowIds.length > 0) {
          await processDirtyRows();
        }
        toast.success("[ETF-순위] 변경사항 저장 완료");
        void load({ ticker_type: selectedTickerType, ma_rule_overrides: maRules, as_of_date: selectedAsOfDate });
      } catch (saveError) {
        showErrorToast(saveError instanceof Error ? saveError.message : "변경사항 저장에 실패했습니다.");
      }
    });
  }

  function handleDeleteSelected() {
    if (selectedTickers.length === 0) {
      return;
    }
    setDeleteConfirmOpen(true);
  }

  function handleCloseDeleteConfirm() {
    if (isPending) {
      return;
    }
    setDeleteConfirmOpen(false);
  }

  function handleConfirmDeleteSelected() {
    if (selectedTickers.length === 0) {
      setDeleteConfirmOpen(false);
      return;
    }

    const selectedRows = rows.filter((row) => selectedTickers.includes(normalizeTicker(String(row.티커 ?? ""))));
    startTransition(async () => {
      try {
        for (const row of selectedRows) {
          await deleteStock(selectedTickerType, String(row.티커 ?? ""));
        }
        const deletedTickerSet = new Set(selectedRows.map((row) => normalizeTicker(String(row.티커 ?? ""))));
        setRows((prev) => prev.filter((row) => !deletedTickerSet.has(normalizeTicker(String(row.티커 ?? "")))));
        setSelectedTickers([]);
        setDeleteConfirmOpen(false);
        clearCacheWarningState();
        toast.success(`[ETF-순위] ${selectedRows.length}개 종목 삭제 완료`);
        void load({ ticker_type: selectedTickerType, ma_rule_overrides: maRules, as_of_date: selectedAsOfDate });
      } catch (deleteError) {
        showErrorToast(deleteError instanceof Error ? deleteError.message : "종목 삭제에 실패했습니다.");
      }
    });
  }

  const blockedMessage = useMemo(() => {
    if (!cacheBlocked) {
      return null;
    }

    const parts: string[] = ["일부 종목의 가격 캐시가 없습니다."];
    if (missingTickerLabels.length > 0) {
      parts.push(`누락 ${missingTickerLabels.join(", ")}`);
    } else if (missingTickers.length > 0) {
      parts.push(`누락 ${missingTickers.join(", ")}`);
    }
    if (staleTickers.length > 0) {
      parts.push(`오래된 캐시 ${staleTickers.join(", ")}`);
    }
    return parts.join(" | ");
  }, [cacheBlocked, missingTickerLabels, missingTickers, staleTickers]);

  useEffect(() => {
    if (!blockedMessage) {
      lastBlockedToastRef.current = null;
      return;
    }

    if (lastBlockedToastRef.current === blockedMessage) {
      return;
    }

    lastBlockedToastRef.current = blockedMessage;
    toast.error(`[ETF-순위] ${blockedMessage}`);
  }, [blockedMessage, toast]);

  const headerSummary = useMemo<RankHeaderSummary>(() => {
    const totalCount = gridRows.length;
    const upCount = gridRows.filter((r) => (r["점수"] ?? 0) > 0).length;
    const upPct = totalCount > 0 ? Math.round((upCount / totalCount) * 100) : 0;
    return {
      upCount,
      upPct,
      totalCount,
      ruleSummary: maRuleSummary.join(" / ") || "-",
    };
  }, [gridRows, maRuleSummary]);

  useEffect(() => {
    onHeaderSummaryChange?.(headerSummary);
  }, [headerSummary, onHeaderSummaryChange]);

  return (
    <div className="appPageStack appPageStackFill">
      {error ? (
        <div className="appBannerStack">
          <div className="bannerError alert alert-danger mb-0">{error}</div>
        </div>
      ) : null}

      <section className="appSection appSectionFill">
        <div className="card appCard appTableCardFill">
          <div className="card-header">
            <div className="appMainHeader">
              <div className="appMainHeaderLeft rankMainHeaderLeft">
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">기준일</span>
                  <input
                    className="form-control"
                    type="date"
                    value={selectedAsOfDate}
                    max={getTodayDateInputValue()}
                    onChange={(event) => handleAsOfDateChange(event.target.value)}
                  />
                </label>
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">종목풀</span>
                  <select
                    className="form-select"
                    value={selectedTickerType}
                    onChange={(event) => handleTickerTypeChange(event.target.value)}
                    disabled={ticker_types.length === 0}
                  >
                    {ticker_types.length === 0 ? (
                      <option value="">종목풀 불러오는 중...</option>
                    ) : (
                      ticker_types.map((account) => (
                        <option key={account.ticker_type} value={account.ticker_type}>
                          {account.name}
                        </option>
                      ))
                    )}
                  </select>
                </label>
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">화면 모드</span>
                  <div className="appSegmentedToggle appSegmentedToggleCompact" role="group" aria-label="순위 화면 모드">
                    <button
                      type="button"
                      className={pageMode === "rank" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setPageMode("rank")}
                    >
                      순위모드
                    </button>
                    <button
                      type="button"
                      className={pageMode === "manage" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setPageMode("manage")}
                    >
                      관리모드
                    </button>
                  </div>
                </label>
                {pageMode === "rank" ? (
                  <>
                    {maRules.map((rule) => (
                      <label key={rule.order} className="appLabeledField">
                        <span className="appLabeledFieldLabel">{`추세${rule.order}`}</span>
                        <div className="rankRuleFieldRow">
                          <select
                            className="form-select"
                            value={rule.ma_type}
                            onChange={(event) => handleMaRuleTypeChange(rule.order, event.target.value)}
                            disabled={maTypeOptions.length === 0}
                          >
                            {maTypeOptions.map((option) => (
                              <option key={`${rule.order}-${option}`} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                          <select
                            className="form-select"
                            value={String(rule.ma_months)}
                            onChange={(event) => handleMaRuleMonthsChange(rule.order, Number(event.target.value))}
                            disabled={maTypeOptions.length === 0}
                          >
                            {Array.from({ length: maMonthsMax }, (_, index) => index + 1).map((month) => (
                              <option key={`${rule.order}-${month}`} value={month}>
                                {month}개월
                              </option>
                            ))}
                          </select>
                        </div>
                      </label>
                    ))}
                    <label className="appLabeledField">
                      <span className="appLabeledFieldLabel">보유종목점수</span>
                      <select
                        className="form-select"
                        value={String(heldBonusScore)}
                        onChange={(event) => handleHeldBonusScoreChange(Number(event.target.value))}
                      >
                        {Array.from({ length: 11 }, (_, index) => index * 5).map((score) => (
                          <option key={score} value={score}>
                            {score}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                ) : null}
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">컬럼</span>
                  <div className="appSegmentedToggle appSegmentedToggleCompact" role="group" aria-label="컬럼 표시 방식">
                    <button
                      type="button"
                      className={metricMode === "cumulative" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setMetricMode("cumulative")}
                    >
                      누적
                    </button>
                    <button
                      type="button"
                      className={metricMode === "monthly" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setMetricMode("monthly")}
                    >
                      월별
                    </button>
                    <button
                      type="button"
                      className={metricMode === "info" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setMetricMode("info")}
                    >
                      정보
                    </button>
                  </div>
                </label>
              </div>
            </div>
          </div>

          {pageMode === "manage" ? (
            <div className="card-header appActionHeader bg-light-subtle border-top">
              <div className="appActionHeaderInner">
                <button
                  className="btn btn-primary btn-sm px-3 fw-bold d-flex align-items-center gap-1"
                  type="button"
                  onClick={handleAddRow}
                  disabled={loading || isPending || Boolean(addingRow)}
                >
                  <IconPlus size={16} stroke={2} />
                  <span>추가</span>
                </button>
                <button
                  className="btn btn-success btn-sm px-3 fw-bold d-flex align-items-center gap-1"
                  type="button"
                  onClick={handleSaveChanges}
                  disabled={loading || isPending || (!addingRow && dirtyRowIds.length === 0)}
                >
                  <IconDeviceFloppy size={16} stroke={2} />
                  <span>저장</span>
                </button>
                <button
                  className="btn btn-outline-danger btn-sm px-3 fw-bold d-flex align-items-center gap-1"
                  type="button"
                  onClick={handleDeleteSelected}
                  disabled={loading || isPending || selectedTickers.length === 0}
                >
                  <IconTrash size={16} stroke={2} />
                  <span>삭제</span>
                </button>
              </div>
            </div>
          ) : null}

          <div className="card-body appCardBodyTight appTableCardBodyFill">
            <div className="appGridFillWrap">
              <AppAgGrid
                className="rankAgGrid"
                rowData={displayGridRows}
                columnDefs={columns}
                loading={loading || isPending}
                theme={rankGridTheme}
                getRowClass={(params: RowClassParams<RankGridRow>) => {
                  const classes: string[] = [];
                  if ((params.data?.점수 ?? 0) < 0) {
                    classes.push("rankNegativeTrendRow");
                  }
                  if (String(params.data?.보유 || "").trim() !== "") {
                    classes.push("rankHeldRow");
                  }
                  return classes.join(" ");
                }}
                minHeight="100%"
                gridOptions={{
                  suppressMovableColumns: true,
                  rowSelection: pageMode === "manage"
                    ? {
                        mode: "multiRow",
                        checkboxes: (params) => !params.data?.__isAddingRow,
                        headerCheckbox: true,
                        hideDisabledCheckboxes: true,
                        enableClickSelection: false,
                      }
                    : undefined,
                  selectionColumnDef: pageMode === "manage"
                    ? {
                        width: 52,
                        minWidth: 52,
                        maxWidth: 52,
                        pinned: "left",
                        sortable: false,
                        resizable: false,
                        suppressMovable: true,
                        headerName: "",
                        cellClass: "stocksSelectCell",
                      }
                    : undefined,
                  onSelectionChanged: (params: { api: { getSelectedRows: () => RankGridRow[] } }) => {
                    if (pageMode !== "manage") {
                      setSelectedTickers([]);
                      return;
                    }
                    setSelectedTickers(
                      params.api
                        .getSelectedRows()
                        .map((row) => row.id)
                        .filter((rowId) => rowId !== "__adding__"),
                    );
                  },
                  onCellValueChanged: (params: {
                    data?: RankGridRow;
                    newValue?: unknown;
                    oldValue?: unknown;
                  }) => {
                    if (pageMode !== "manage" || !params.data || params.data.__isAddingRow || params.newValue === params.oldValue) {
                      return;
                    }
                    handleBucketChanged(params.data, String(params.newValue ?? ""));
                  },
                }}
              />
            </div>
          </div>
        </div>
      </section>

      <AppModal
        open={deleteConfirmOpen}
        title="종목 삭제 확인"
        subtitle="선택 종목은 즉시 영구 삭제됩니다."
        onClose={handleCloseDeleteConfirm}
        footer={(
          <>
            <button type="button" className="btn btn-outline-secondary" onClick={handleCloseDeleteConfirm} disabled={isPending}>
              취소
            </button>
            <button type="button" className="btn btn-danger" onClick={handleConfirmDeleteSelected} disabled={isPending}>
              삭제
            </button>
          </>
        )}
      >
        <div className="d-flex flex-column gap-2">
          <div className="fw-semibold">
            {selectedTickers.length === 1
              ? `${rows.find((row) => selectedTickers.includes(normalizeTicker(String(row.티커 ?? ""))))?.종목명 ?? ""}(${selectedTickers[0]}) 종목을 삭제합니다.`
              : `${selectedTickers.length}개 종목을 삭제합니다.`}
          </div>
          <div className="text-secondary small">삭제된 종목은 복구되지 않으며 즉시 제거됩니다.</div>
        </div>
      </AppModal>
    </div>
  );
}
