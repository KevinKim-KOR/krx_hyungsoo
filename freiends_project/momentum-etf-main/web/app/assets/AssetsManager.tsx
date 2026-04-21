"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef, ColumnState, GridApi, GridOptions, RowClassParams } from "ag-grid-community";
import { IconCheck, IconLoader2, IconPlus, IconTrash } from "@tabler/icons-react";
import { useRouter } from "next/navigation";

import { AppAgGrid } from "../components/AppAgGrid";
import { AppLoadingState } from "../components/AppLoadingState";
import { useToast } from "../components/ToastProvider";

type HoldingsRow = {
  account_id: string;
  account_name: string;
  currency: string;
  bucket: string;
  bucket_id: number;
  ticker: string;
  name: string;
  quantity: number;
  average_buy_price: string | number;
  current_price: string;
  current_price_num?: number;
  days_held: string;
  pnl_krw: number;
  return_pct: number;
  weight_pct: number;
  daily_change_pct?: number | null;
  buy_amount_krw: number;
  valuation_krw: number;
  target_ratio?: number | null;
  sort_order?: number | null;
  original_quantity?: number;
  original_average_buy_price?: number;
};

type GridRow = HoldingsRow & { id: string };

type AccountSummary = {
  account_id: string;
  order: number;
  name: string;
  account_url?: string | null;
  icon: string;
  currency: string;
  total_principal: number;
  cash_balance_krw: number;
  cash_balance_native: number | null;
  cash_currency: string;
  cash_target_ratio: number;
  intl_shares_value: number | null;
  intl_shares_change: number | null;
  updated_at: string | null;
  valuation_krw: number;
  total_assets_krw: number;
  holdings_count: number;
  target_ratio_total: number;
  cash_ratio: number;
  net_profit: number;
  net_profit_pct: number;
  daily_profit: number;
  weekly_profit: number;
};

type ParentGridRow =
  | (AccountSummary & {
      id: string;
      rowType: "main";
      cash_edit_value: number;
    })
  | {
      id: string;
      rowType: "total";
      name: string;
      total_assets_krw: number;
      valuation_krw: number;
      total_principal: number;
      cash_edit_value: number;
      target_ratio_total: number | null;
      holdings_count: number;
      cash_ratio: number;
      net_profit: number;
      net_profit_pct: number;
      daily_profit: number;
      weekly_profit: number;
    }
  | {
      id: string;
      rowType: "detail";
      parentId: string;
      summary: AccountSummary;
      rows: HoldingsRow[];
    };

type HoldingsResponse = {
  rows?: HoldingsRow[];
  account_summaries?: AccountSummary[];
  error?: string;
};

type AssetsHeaderSummary = {
  totalAssets: number;
  totalValuation: number;
  totalCash: number;
  accountCount: number;
};

type AddingRowState = {
  ticker: string;
  quantity: string;
  average_buy_price: string;
  target_ratio: string;
  isValidatingTicker?: boolean;
  name?: string;
  bucketId?: number;
  isValidated?: boolean;
};

const CASH_ROW_TICKER = "__CASH__";

type HoldingEditableSnapshot = {
  quantity: number;
  average_buy_price: number;
  target_ratio: number;
};

const assetsGridTheme = themeQuartz.withPart(iconSetQuartzBold).withParams({
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

function buildGridRowId(row: Pick<HoldingsRow, "ticker" | "account_id">): string {
  return `${row.account_id}-${row.ticker}`;
}

function buildDirtyCellKey(rowId: string, field: string): string {
  return `${rowId}::${field}`;
}

function formatKrw(value: number): string {
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

function formatPrice(value: number | null | undefined, currency: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const normalizedCurrency = String(currency || "KRW").trim().toUpperCase();
  if (normalizedCurrency === "AUD") {
    return `A$${new Intl.NumberFormat("en-AU", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(value)}`;
  }
  if (normalizedCurrency === "USD") {
    return `$${new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(value)}`;
  }
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
}

function getSignedClass(value: number): string {
  if (value === 0 || Number.isNaN(value)) return "";
  return value > 0 ? "metricPositive" : "metricNegative";
}

function getSignedNullableClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return "";
  return value > 0 ? "metricPositive" : "metricNegative";
}

function getWeightTextColor(weightPct: number, targetRatio: number | null | undefined): string {
  if (targetRatio === null || targetRatio === undefined || Number.isNaN(targetRatio) || targetRatio <= 0) {
    return ASSETS_WEIGHT_TEXT_COLOR;
  }

  const allowedDelta = targetRatio * 0.1;
  return Math.abs(weightPct - targetRatio) > allowedDelta ? "#dc3545" : ASSETS_WEIGHT_TEXT_COLOR;
}

function getBucketCellClass(bucketId: number): string {
  if (!bucketId) return "appBucketCell";
  return `appBucketCell appBucketCell${bucketId}`;
}

function parseRawPrice(formatted: unknown): string {
  if (formatted === null || formatted === undefined) return "0";
  return String(formatted).replace(/A\$|\$|₩|원|,|\s/g, "");
}

function safeParseFloat(value: unknown): number {
  const parsed = parseFloat(parseRawPrice(value));
  return Number.isNaN(parsed) ? 0 : parsed;
}

function parseEditableQuantity(value: unknown): number {
  const parsed = parseInt(parseRawPrice(value), 10);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function buildHoldingEditableSnapshot(row: Pick<HoldingsRow, "quantity" | "average_buy_price" | "target_ratio">): HoldingEditableSnapshot {
  return {
    quantity: parseEditableQuantity(row.quantity),
    average_buy_price: safeParseFloat(row.average_buy_price),
    target_ratio: Number(row.target_ratio ?? 0),
  };
}

function formatRatioPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

function buildAutoSaveToastMessage(row: Pick<HoldingsRow, "name" | "currency">, before: HoldingEditableSnapshot, after: HoldingEditableSnapshot): string | null {
  const changes: string[] = [];
  if (before.quantity !== after.quantity) {
    changes.push(`수량 ${new Intl.NumberFormat("ko-KR").format(before.quantity)}→${new Intl.NumberFormat("ko-KR").format(after.quantity)}`);
  }
  if (before.average_buy_price !== after.average_buy_price) {
    changes.push(`매입단가 ${formatPrice(before.average_buy_price, row.currency)}→${formatPrice(after.average_buy_price, row.currency)}`);
  }
  if (before.target_ratio !== after.target_ratio) {
    changes.push(`목표비중 ${formatRatioPercent(before.target_ratio)}→${formatRatioPercent(after.target_ratio)}`);
  }
  if (changes.length === 0) {
    return null;
  }
  return `${row.name} 저장: ${changes.join(", ")}`;
}

function getCurrentPriceNumber(row: GridRow): number {
  const currentPriceNum = Number(row.current_price_num ?? NaN);
  if (!Number.isNaN(currentPriceNum) && currentPriceNum > 0) {
    return currentPriceNum;
  }
  return safeParseFloat(row.current_price);
}

function getPreviewQuantity(row: GridRow): number {
  return parseEditableQuantity(row.quantity);
}

function getPreviewAverageBuyPrice(row: GridRow): number {
  return safeParseFloat(row.average_buy_price);
}

function getPreviewValuationKrw(row: GridRow): number {
  if (String(row.ticker || "").trim().toUpperCase() === CASH_ROW_TICKER) {
    return Number(row.valuation_krw ?? 0);
  }
  const quantity = getPreviewQuantity(row);
  if (quantity <= 0) {
    return 0;
  }
  if (row.currency === "KRW") {
    return getCurrentPriceNumber(row) * quantity;
  }
  const currentQuantity = Number(row.original_quantity ?? row.quantity ?? 0);
  if (currentQuantity > 0) {
    return (Number(row.valuation_krw ?? 0) / currentQuantity) * quantity;
  }
  return Number(row.valuation_krw ?? 0);
}

function getPreviewBuyAmountKrw(row: GridRow): number {
  if (String(row.ticker || "").trim().toUpperCase() === CASH_ROW_TICKER) {
    return Number(row.buy_amount_krw ?? 0);
  }
  const quantity = getPreviewQuantity(row);
  if (quantity <= 0) {
    return 0;
  }
  const averageBuyPrice = getPreviewAverageBuyPrice(row);
  if (row.currency === "KRW") {
    return averageBuyPrice * quantity;
  }
  const currentQuantity = Number(row.original_quantity ?? row.quantity ?? 0);
  const currentAverageBuyPrice = Number(row.original_average_buy_price ?? safeParseFloat(row.average_buy_price));
  if (currentQuantity > 0 && currentAverageBuyPrice > 0) {
    const fxFactor = Number(row.buy_amount_krw ?? 0) / (currentQuantity * currentAverageBuyPrice);
    return averageBuyPrice * quantity * fxFactor;
  }
  return Number(row.buy_amount_krw ?? 0);
}

function getPreviewWeightPct(row: GridRow, rows: HoldingsRow[], summary: AccountSummary): number {
  const normalizedTicker = String(row.ticker || "").trim().toUpperCase();
  if (normalizedTicker === "IS") {
    return 0;
  }
  const previewTotalValuation = rows.reduce((sum, currentRow) => {
    return sum + getPreviewValuationKrw({ ...currentRow, id: buildGridRowId(currentRow) });
  }, 0);
  const previewIsValuation = rows.reduce((sum, currentRow) => {
    if (String(currentRow.ticker || "").trim().toUpperCase() !== "IS") {
      return sum;
    }
    return sum + getPreviewValuationKrw({ ...currentRow, id: buildGridRowId(currentRow) });
  }, 0);
  const currency = String(summary.currency || "KRW").trim().toUpperCase();
  const denominator =
    currency === "AUD"
      ? Number(summary.cash_balance_krw ?? 0) + previewTotalValuation - previewIsValuation
      : Number(summary.cash_balance_krw ?? 0) + previewTotalValuation;
  if (denominator <= 0) {
    return 0;
  }
  if (normalizedTicker === CASH_ROW_TICKER) {
    return (Number(summary.cash_balance_krw ?? 0) / denominator) * 100;
  }
  const rowId = buildGridRowId(row);
  const targetRow = rows.find((currentRow) => buildGridRowId(currentRow) === rowId);
  if (!targetRow) {
    return 0;
  }
  const rowValuation = getPreviewValuationKrw({ ...targetRow, id: rowId });
  return (rowValuation / denominator) * 100;
}

function buildSyncedHoldingRows(rows: HoldingsRow[], summary: AccountSummary): HoldingsRow[] {
  return rows.map((row) => {
    const previewRow = { ...row, id: buildGridRowId(row) };
    const quantity = getPreviewQuantity(previewRow);
    const averageBuyPrice = getPreviewAverageBuyPrice(previewRow);
    const valuationKrw = Math.round(getPreviewValuationKrw(previewRow));
    const buyAmountKrw = Math.round(getPreviewBuyAmountKrw(previewRow));
    const pnlKrw = valuationKrw - buyAmountKrw;
    const returnPct = buyAmountKrw > 0 ? Number(((pnlKrw / buyAmountKrw) * 100).toFixed(2)) : 0;
    const weightPct = Number(getPreviewWeightPct(previewRow, rows, summary).toFixed(1));

    return {
      ...row,
      quantity,
      average_buy_price: averageBuyPrice,
      valuation_krw: valuationKrw,
      buy_amount_krw: buyAmountKrw,
      pnl_krw: pnlKrw,
      pnl_krw_num: pnlKrw,
      return_pct: returnPct,
      weight_pct: weightPct,
    };
  });
}

function isDetailRow(row: ParentGridRow | undefined): row is Extract<ParentGridRow, { rowType: "detail" }> {
  return row?.rowType === "detail";
}

function isTotalRow(row: ParentGridRow | undefined): row is Extract<ParentGridRow, { rowType: "total" }> {
  return row?.rowType === "total";
}

function formatAccountCash(summary: AccountSummary): string {
  const currency = String(summary.currency || "KRW").trim().toUpperCase();
  if (currency === "AUD") {
    return formatPrice(summary.cash_balance_native, "AUD");
  }
  return formatKrw(summary.cash_balance_krw);
}

function buildCashGridRow(summary: AccountSummary): GridRow {
  const cashValue = Number(summary.cash_balance_krw ?? 0);
  return {
    id: `${summary.account_id}-${CASH_ROW_TICKER}`,
    account_id: summary.account_id,
    account_name: summary.name,
    currency: "KRW",
    bucket: "",
    bucket_id: 0,
    ticker: CASH_ROW_TICKER,
    name: "현금",
    quantity: 0,
    average_buy_price: 0,
    current_price: "-",
    current_price_num: 0,
    days_held: "-",
    pnl_krw: 0,
    return_pct: 0,
    weight_pct: 0,
    daily_change_pct: null,
    buy_amount_krw: cashValue,
    valuation_krw: cashValue,
    target_ratio: Number(summary.cash_target_ratio ?? 0),
    sort_order: -1,
    original_quantity: 0,
    original_average_buy_price: 0,
  };
}


function reorderRowsByTickers(rows: HoldingsRow[], orderedTickers: string[]): HoldingsRow[] {
  const normalizedTickers = orderedTickers.map((ticker) => String(ticker || "").trim().toUpperCase());
  const rowMap = new Map(
    rows
      .filter((row) => String(row.ticker || "").trim().toUpperCase() !== "IS")
      .map((row) => [String(row.ticker || "").trim().toUpperCase(), row] as const),
  );
  const orderedRows: HoldingsRow[] = [];
  const seen = new Set<string>();

  for (const ticker of normalizedTickers) {
    const row = rowMap.get(ticker);
    if (!row || seen.has(ticker)) {
      continue;
    }
    orderedRows.push({ ...row });
    seen.add(ticker);
  }

  const remainingRows = rows.filter((row) => {
    const ticker = String(row.ticker || "").trim().toUpperCase();
    return ticker === "IS" || !seen.has(ticker);
  });

  return [...orderedRows, ...remainingRows.map((row) => ({ ...row }))].map((row, index) => ({
    ...row,
    sort_order: index,
  }));
}

const ASSETS_WEIGHT_TEXT_COLOR = "#7952b3";

function StableInlineInput({
  initialValue,
  onSave,
  onCancel,
  onChange,
  className,
  style,
  placeholder,
  autoFocus = false,
  disabled = false,
}: {
  initialValue: string;
  onSave?: (val: string) => void;
  onCancel?: () => void;
  onChange?: (val: string) => void;
  className?: string;
  style?: CSSProperties;
  placeholder?: string;
  autoFocus?: boolean;
  disabled?: boolean;
}) {
  const [localValue, setLocalValue] = useState(initialValue);

  useEffect(() => {
    setLocalValue(initialValue);
  }, [initialValue]);

  return (
    <input
      type="text"
      className={className}
      style={style}
      placeholder={placeholder}
      value={localValue}
      autoFocus={autoFocus}
      disabled={disabled}
      onMouseDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
      }}
      onChange={(event) => {
        event.stopPropagation();
        setLocalValue(event.target.value);
        onChange?.(event.target.value);
      }}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.nativeEvent.isComposing) return;
        if (event.key === "Enter") {
          onSave?.(localValue);
        } else if (event.key === "Escape") {
          setLocalValue(initialValue);
          onCancel?.();
        }
      }}
      onBlur={() => {
        if (localValue !== initialValue) {
          onSave?.(localValue);
        }
      }}
    />
  );
}

function AccountHoldingsDetailPanel({
  summary,
  initialRows,
  initialSortState,
  onReload,
  onRowsSync,
  onCashSync,
  onPreviewTargetRatioTotalChange,
  onSortStateChange,
}: {
  summary: AccountSummary;
  initialRows: HoldingsRow[];
  initialSortState: ColumnState[];
  onReload: () => Promise<void>;
  onRowsSync: (accountId: string, rows: HoldingsRow[]) => void;
  onCashSync: (accountId: string, cashBalanceKrw: number, cashTargetRatio: number) => void;
  onPreviewTargetRatioTotalChange: (accountId: string, total: number) => void;
  onSortStateChange: (accountId: string, state: ColumnState[]) => void;
}) {
  const toast = useToast();
  const router = useRouter();
  const hydrateRows = useCallback(
    (sourceRows: HoldingsRow[]) =>
      sourceRows.map((row) => ({
        ...row,
        original_quantity: Number(row.original_quantity ?? row.quantity ?? 0),
        original_average_buy_price: Number(row.original_average_buy_price ?? safeParseFloat(row.average_buy_price)),
      })),
    [],
  );
  const [rows, setRows] = useState<HoldingsRow[]>(() => hydrateRows(initialRows));
  const [addingRow, setAddingRow] = useState<AddingRowState | null>(null);
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [dirtyRowIds, setDirtyRowIds] = useState<string[]>([]);
  const [dirtyCellKeys, setDirtyCellKeys] = useState<string[]>([]);
  const [selectedRowIds, setSelectedRowIds] = useState<string[]>([]);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [isReorderDirty, setIsReorderDirty] = useState(false);
  const qtyRef = useRef<HTMLInputElement>(null);
  const priceRef = useRef<HTMLInputElement>(null);
  const targetRatioRef = useRef<HTMLInputElement>(null);
  const rowsRef = useRef<HoldingsRow[]>(initialRows);
  const summaryRef = useRef(summary);
  const dirtyRowIdsRef = useRef<string[]>([]);
  const isReorderDirtyRef = useRef(false);
  const gridApiRef = useRef<GridApi<GridRow> | null>(null);
  const lastSavedSnapshotsRef = useRef<Map<string, HoldingEditableSnapshot>>(new Map());
  const childSaveTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const childSavingRowIdsRef = useRef<Set<string>>(new Set());
  const childQueuedRowIdsRef = useRef<Set<string>>(new Set());
  const reorderSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reorderSavingRef = useRef(false);
  const reorderQueuedRef = useRef(false);
  const cashDraftRef = useRef({
    cashBalanceKrw: Number(summary.cash_balance_krw ?? 0),
    cashTargetRatio: Number(summary.cash_target_ratio ?? 0),
  });
  const isAusAccount = String(summary.currency || "KRW").toUpperCase() === "AUD";
  const intlDraftRef = useRef({
    intlSharesValue: Number(summary.intl_shares_value ?? 0),
    intlSharesChange: Number(summary.intl_shares_change ?? 0),
    cashNative: Number(summary.cash_balance_native ?? 0),
  });
  const [intlDirtyFields, setIntlDirtyFields] = useState<string[]>([]);
  useEffect(() => {
    const nextRows = hydrateRows(initialRows);
    setRows(nextRows);
    rowsRef.current = nextRows;
    dirtyRowIdsRef.current = [];
    isReorderDirtyRef.current = false;
    lastSavedSnapshotsRef.current = new Map(
      nextRows.map((row) => [buildGridRowId(row), buildHoldingEditableSnapshot(row)]),
    );
    setDirtyRowIds([]);
    setDirtyCellKeys([]);
    setSelectedRowIds([]);
    setEditingRowId(null);
    setAddingRow(null);
    setIsReorderDirty(false);
    queueMicrotask(() => {
      if (!gridApiRef.current || initialSortState.length === 0) {
        return;
      }
      gridApiRef.current.applyColumnState({
        state: initialSortState,
        applyOrder: false,
      });
    });
  }, [hydrateRows, initialRows, initialSortState]);

  useEffect(() => {
    rowsRef.current = rows;
  }, [rows]);

  useEffect(() => {
    summaryRef.current = summary;
    cashDraftRef.current = {
      cashBalanceKrw: Number(summary.cash_balance_krw ?? 0),
      cashTargetRatio: Number(summary.cash_target_ratio ?? 0),
    };
  }, [summary]);

  useEffect(() => {
    dirtyRowIdsRef.current = dirtyRowIds;
  }, [dirtyRowIds]);

  useEffect(() => {
    isReorderDirtyRef.current = isReorderDirty;
  }, [isReorderDirty]);

  useEffect(() => {
    const previewTargetRatioTotal = rows.reduce((sum, row) => {
      return sum + Number(row.target_ratio ?? 0);
    }, 0) + Number(summary.cash_target_ratio ?? 0);
    onPreviewTargetRatioTotalChange(summary.account_id, parseFloat(previewTargetRatioTotal.toFixed(1)));
  }, [onPreviewTargetRatioTotalChange, rows, summary.account_id, summary.cash_target_ratio]);

  const isEditableHoldingRow = useCallback(
    (row: GridRow | undefined | null) =>
      Boolean(row && row.id !== "__adding__" && row.ticker !== "IS" && row.ticker !== CASH_ROW_TICKER),
    [],
  );
  const isCashGridRow = useCallback(
    (row: GridRow | undefined | null) => Boolean(row && row.ticker === CASH_ROW_TICKER),
    [],
  );
  const moveToTickerDetail = useCallback(
    (ticker: string | null | undefined) => {
    const normalizedTicker = String(ticker || "").trim().toUpperCase().replace(/^ASX:/, "");
      if (!normalizedTicker || normalizedTicker === "IS" || normalizedTicker === CASH_ROW_TICKER) {
        return;
      }
      router.push(`/ticker?ticker=${encodeURIComponent(normalizedTicker)}`);
    },
    [router],
  );

  const gridRows = useMemo<GridRow[]>(() => {
    const cashRow = buildCashGridRow(summary);
    const baseRows = rows
      .map((row, index) => ({
        ...row,
        id: buildGridRowId(row),
        quantity: typeof row.quantity === "number" ? row.quantity : parseInt(String(row.quantity), 10) || 0,
        average_buy_price: safeParseFloat(row.average_buy_price),
        target_ratio: row.target_ratio ?? 0,
      }));

    if (!addingRow) {
      return [cashRow, ...baseRows];
    }

    return [
      cashRow,
      {
        id: "__adding__",
        account_id: summary.account_id,
        account_name: summary.name,
        currency: summary.currency,
        bucket: "",
        bucket_id: 0,
        ticker: addingRow.ticker,
        name: addingRow.name || "",
        quantity: 0,
        average_buy_price: 0,
        current_price: "-",
        days_held: "-",
        pnl_krw: 0,
        return_pct: 0,
        weight_pct: 0,
        buy_amount_krw: 0,
        valuation_krw: 0,
        target_ratio: 0,
      } as GridRow,
      ...baseRows,
    ];
  }, [addingRow, rows, summary]);

  const hasPendingAdd = Boolean(addingRow);
  const hasSelectedRows = selectedRowIds.length > 0;
  const hasPendingSave = hasPendingAdd || dirtyRowIds.length > 0 || isReorderDirty;

  const isDirtyEditableCell = useCallback(
    (rowId: string | undefined, field: string) => Boolean(rowId && dirtyCellKeys.includes(buildDirtyCellKey(rowId, field))),
    [dirtyCellKeys],
  );

  const handleValidateTicker = useCallback(async (tickerToUse?: string) => {
    const ticker = String(tickerToUse || addingRow?.ticker || "").trim().toUpperCase();
    if (!ticker || addingRow?.isValidatingTicker) {
      return;
    }

    const normalizedTicker = ticker.replace(/^ASX:/, "");
    const hasDuplicate = rows.some(
      (row) => String(row.ticker || "").trim().toUpperCase().replace(/^ASX:/, "") === normalizedTicker,
    );

    if (hasDuplicate) {
      const message = "이미 해당 계좌에 추가된 종목입니다.";
      setAddingRow((previous) =>
        previous
          ? {
              ...previous,
              ticker,
              name: message,
              bucketId: undefined,
              isValidated: false,
              isValidatingTicker: false,
            }
          : null,
      );
      toast.error(message);
      return;
    }

    setAddingRow((previous) =>
      previous
        ? {
            ...previous,
            ticker,
            name: "",
            bucketId: undefined,
            isValidated: false,
            isValidatingTicker: true,
          }
        : null,
    );

    try {
      const response = await fetch("/api/assets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "validate",
          account_id: summary.account_id,
          ticker,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "검증 실패");
      }
      setAddingRow((previous) =>
        previous
          ? {
              ...previous,
              ticker: payload.ticker,
              name: payload.name,
              bucketId: payload.bucket_id,
              isValidated: true,
              isValidatingTicker: false,
            }
          : null,
      );
      toast.success(`조회 성공: ${payload.name}`);
    } catch (error) {
      setAddingRow((previous) =>
        previous
          ? {
              ...previous,
              name: previous.name || "",
              isValidatingTicker: false,
            }
          : null,
      );
      toast.error(error instanceof Error ? error.message : "검증 실패");
    }
  }, [addingRow?.isValidatingTicker, addingRow?.ticker, rows, summary.account_id, toast]);

  const processAddingRow = useCallback(async () => {
    if (!addingRow?.isValidated) {
      throw new Error("먼저 종목 확인을 완료해 주세요.");
    }

    const rawQuantity = qtyRef.current?.value ?? "";
    const rawPrice = priceRef.current?.value ?? "";
    const rawTargetRatio = targetRatioRef.current?.value ?? "0";

    const quantity = parseInt(parseRawPrice(rawQuantity), 10);
    const averageBuyPrice = safeParseFloat(rawPrice);
    const targetRatio = parseFloat(rawTargetRatio);

    if (Number.isNaN(quantity) || quantity < 0 || Number.isNaN(averageBuyPrice) || averageBuyPrice < 0) {
      throw new Error("수량과 매입 단가를 확인해 주세요.");
    }
    if (Number.isNaN(targetRatio) || targetRatio < 0 || targetRatio > 100) {
      throw new Error("목표비중은 0~100 사이여야 합니다.");
    }

    const response = await fetch("/api/assets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: summary.account_id,
        ticker: addingRow.ticker,
        quantity,
        average_buy_price: averageBuyPrice,
        target_ratio: parseFloat(targetRatio.toFixed(1)),
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "종목 추가에 실패했습니다.");
    }
  }, [addingRow, summary.account_id]);

  const processRowUpdate = useCallback(async (row: GridRow) => {
    const quantity = parseEditableQuantity(row.quantity);
    const averageBuyPrice = safeParseFloat(row.average_buy_price);
    const targetRatio = Number(row.target_ratio ?? 0);

    if (Number.isNaN(quantity) || quantity < 0 || Number.isNaN(averageBuyPrice) || averageBuyPrice < 0) {
      throw new Error("입력값이 올바르지 않습니다.");
    }
    if (Number.isNaN(targetRatio) || targetRatio < 0 || targetRatio > 100) {
      throw new Error("목표비중은 0~100 사이여야 합니다.");
    }

    const response = await fetch("/api/assets", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: summary.account_id,
        ticker: row.ticker.replace("ASX:", ""),
        quantity,
        average_buy_price: averageBuyPrice,
        target_ratio: parseFloat(targetRatio.toFixed(1)),
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "종목 수정에 실패했습니다.");
    }
  }, [summary.account_id]);

  const processCashUpdate = useCallback(async (cashBalanceKrw: number, cashTargetRatio: number) => {
    const isAud = String(summary.currency || "KRW").toUpperCase() === "AUD";
    const currentCashKrw = Number(summary.cash_balance_krw ?? 0);
    const currentCashNative = Number(summary.cash_balance_native ?? 0);
    const nextCashNative =
      isAud && currentCashKrw > 0 && currentCashNative > 0
        ? (cashBalanceKrw / currentCashKrw) * currentCashNative
        : (isAud ? currentCashNative : cashBalanceKrw);
    const response = await fetch("/api/assets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: summary.account_id,
        total_principal: summary.total_principal,
        cash_balance_krw: cashBalanceKrw,
        cash_balance_native: nextCashNative,
        cash_currency: summary.cash_currency,
        cash_target_ratio: cashTargetRatio,
        intl_shares_value: summary.account_id === "aus_account" ? summary.intl_shares_value : null,
        intl_shares_change: summary.account_id === "aus_account" ? summary.intl_shares_change : null,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "현금 저장에 실패했습니다.");
    }
  }, [summary]);

  const processIntlUpdate = useCallback(async (intlSharesValue: number, intlSharesChange: number, cashNative?: number) => {
    const finalCashNative = cashNative ?? Number(summary.cash_balance_native ?? 0);
    const currentCashKrw = Number(summary.cash_balance_krw ?? 0);
    const currentCashNative = Number(summary.cash_balance_native ?? 0);
    // AUD 변경 시 KRW도 비율로 환산
    const nextCashKrw =
      currentCashNative > 0
        ? (finalCashNative / currentCashNative) * currentCashKrw
        : currentCashKrw;
    const response = await fetch("/api/assets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: summary.account_id,
        total_principal: summary.total_principal,
        cash_balance_krw: nextCashKrw,
        cash_balance_native: finalCashNative,
        cash_currency: summary.cash_currency,
        cash_target_ratio: summary.cash_target_ratio,
        intl_shares_value: intlSharesValue,
        intl_shares_change: intlSharesChange,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "호주 계좌 저장에 실패했습니다.");
    }
  }, [summary]);

  const clearDirtyRowState = useCallback((rowId: string) => {
    setDirtyRowIds((previous) => {
      const next = previous.filter((id) => id !== rowId);
      dirtyRowIdsRef.current = next;
      return next;
    });
    setDirtyCellKeys((previous) => previous.filter((key) => !key.startsWith(`${rowId}::`)));
  }, []);

  const processReorderUpdate = useCallback(async (orderedRows: HoldingsRow[]) => {
    const orderedTickers = orderedRows
      .map((row) => String(row.ticker || "").trim().toUpperCase())
      .filter((ticker) => ticker && ticker !== "IS" && ticker !== CASH_ROW_TICKER);

    if (!orderedTickers.length) {
      return;
    }

    const response = await fetch("/api/assets", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "reorder",
        account_id: summary.account_id,
        ordered_tickers: orderedTickers,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "순서 저장에 실패했습니다.");
    }
  }, [summary.account_id]);

  const silentlySaveRow = useCallback(async (rowId: string) => {
    if (childSavingRowIdsRef.current.has(rowId)) {
      childQueuedRowIdsRef.current.add(rowId);
      return;
    }

    const sourceRow = rowsRef.current.find((row) => buildGridRowId(row) === rowId);
    if (!sourceRow) {
      clearDirtyRowState(rowId);
      return;
    }

    childSavingRowIdsRef.current.add(rowId);
    try {
      const previousSnapshot = lastSavedSnapshotsRef.current.get(rowId) ?? buildHoldingEditableSnapshot(sourceRow);
      const nextSnapshot = buildHoldingEditableSnapshot(sourceRow);
      await processRowUpdate({
        ...sourceRow,
        id: rowId,
        quantity: typeof sourceRow.quantity === "number" ? sourceRow.quantity : parseInt(String(sourceRow.quantity), 10) || 0,
        average_buy_price: safeParseFloat(sourceRow.average_buy_price),
        target_ratio: sourceRow.target_ratio ?? 0,
      });
      lastSavedSnapshotsRef.current.set(rowId, nextSnapshot);
      const message = buildAutoSaveToastMessage(sourceRow, previousSnapshot, nextSnapshot);
      if (message) {
        toast.success(message);
      }
      clearDirtyRowState(rowId);
    } catch (error) {
      await onReload();
      toast.error(error instanceof Error ? error.message : "변경사항 저장에 실패했습니다.");
    } finally {
      childSavingRowIdsRef.current.delete(rowId);
      if (childQueuedRowIdsRef.current.has(rowId)) {
        childQueuedRowIdsRef.current.delete(rowId);
        const nextTimer = setTimeout(() => {
          childSaveTimersRef.current.delete(rowId);
          void silentlySaveRow(rowId);
        }, 400);
        childSaveTimersRef.current.set(rowId, nextTimer);
      }
    }
  }, [clearDirtyRowState, onReload, processRowUpdate, toast]);

  const scheduleSilentRowSave = useCallback((rowId: string) => {
    const currentTimer = childSaveTimersRef.current.get(rowId);
    if (currentTimer) {
      clearTimeout(currentTimer);
    }
    const nextTimer = setTimeout(() => {
      childSaveTimersRef.current.delete(rowId);
      void silentlySaveRow(rowId);
    }, 700);
    childSaveTimersRef.current.set(rowId, nextTimer);
  }, [silentlySaveRow]);

  const persistRowOrder = useCallback(async (orderedRows: HoldingsRow[]) => {
    if (reorderSavingRef.current) {
      reorderQueuedRef.current = true;
      return;
    }

    reorderSavingRef.current = true;
    try {
      await processReorderUpdate(orderedRows);
      setIsReorderDirty(false);
      isReorderDirtyRef.current = false;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "순서 저장에 실패했습니다.");
    } finally {
      reorderSavingRef.current = false;
      if (reorderQueuedRef.current) {
        reorderQueuedRef.current = false;
        const nextRows = rowsRef.current;
        const nextTimer = setTimeout(() => {
          reorderSaveTimerRef.current = null;
          void persistRowOrder(nextRows);
        }, 400);
        reorderSaveTimerRef.current = nextTimer;
      }
    }
  }, [onReload, processReorderUpdate, toast]);

  const scheduleSilentReorderSave = useCallback((orderedRows: HoldingsRow[]) => {
    if (reorderSaveTimerRef.current) {
      clearTimeout(reorderSaveTimerRef.current);
    }
    const nextTimer = setTimeout(() => {
      reorderSaveTimerRef.current = null;
      void persistRowOrder(orderedRows);
    }, 700);
    reorderSaveTimerRef.current = nextTimer;
  }, [persistRowOrder]);

  const flushPendingSaves = useCallback(() => {
    childSaveTimersRef.current.forEach((timer) => clearTimeout(timer));
    childSaveTimersRef.current.clear();
    if (reorderSaveTimerRef.current) {
      clearTimeout(reorderSaveTimerRef.current);
      reorderSaveTimerRef.current = null;
    }
  }, []);

  const flushPendingSavesOnUnmount = useCallback(() => {
    childSaveTimersRef.current.forEach((timer) => clearTimeout(timer));
    childSaveTimersRef.current.clear();
    if (reorderSaveTimerRef.current) {
      clearTimeout(reorderSaveTimerRef.current);
      reorderSaveTimerRef.current = null;
    }

    const cashRowId = `${summary.account_id}-${CASH_ROW_TICKER}`;
    if (dirtyRowIdsRef.current.includes(cashRowId)) {
      void processCashUpdate(
        cashDraftRef.current.cashBalanceKrw,
        cashDraftRef.current.cashTargetRatio,
      ).catch(() => undefined);
    }

    const dirtyRows = rowsRef.current
      .map((row) => ({ ...row, id: buildGridRowId(row) }))
      .filter((row) => dirtyRowIdsRef.current.includes(row.id));

    for (const row of dirtyRows) {
      void processRowUpdate(row).catch(() => undefined);
    }

    if (isReorderDirtyRef.current) {
      void processReorderUpdate(rowsRef.current).catch(() => undefined);
    }

  }, [processCashUpdate, processReorderUpdate, processRowUpdate, summary.account_id]);

  useEffect(() => {
    return () => {
      flushPendingSavesOnUnmount();
    };
  }, [flushPendingSavesOnUnmount]);

  const handleSaveChanges = useCallback(async () => {
    if (processingId === "__adding__" || processingId === "__deleting__") {
      return;
    }

    gridApiRef.current?.stopEditing();
    flushPendingSaves();

    try {
      const cashRowId = `${summary.account_id}-${CASH_ROW_TICKER}`;
      if (dirtyRowIds.includes(cashRowId)) {
        await processCashUpdate(
          cashDraftRef.current.cashBalanceKrw,
          cashDraftRef.current.cashTargetRatio,
        );
        clearDirtyRowState(cashRowId);
      }

      const dirtyRows = rowsRef.current
        .map((row) => ({
          ...row,
          id: buildGridRowId(row),
          quantity: typeof row.quantity === "number" ? row.quantity : parseInt(String(row.quantity), 10) || 0,
          average_buy_price: safeParseFloat(row.average_buy_price),
          target_ratio: row.target_ratio ?? 0,
        }))
        .filter((row) => dirtyRowIds.includes(row.id));

      for (const row of dirtyRows) {
        await processRowUpdate(row);
        lastSavedSnapshotsRef.current.set(row.id, buildHoldingEditableSnapshot(row));
        clearDirtyRowState(row.id);
      }

      if (isReorderDirty) {
        await persistRowOrder(rowsRef.current);
      }

      if (addingRow) {
        setProcessingId("__adding__");
        await processAddingRow();
        await onReload();
        toast.success("종목 추가 완료");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "변경사항 저장에 실패했습니다.");
    } finally {
      setProcessingId(null);
    }
  }, [
    addingRow,
    clearDirtyRowState,
    dirtyRowIds,
    flushPendingSaves,
    isReorderDirty,
    onReload,
    persistRowOrder,
    processAddingRow,
    processCashUpdate,
    processRowUpdate,
    processingId,
    summary,
    toast,
  ]);

  const handleDeleteSelected = useCallback(async () => {
    if (!selectedRowIds.length) {
      return;
    }
    const selectedRows = gridRows.filter((row) => selectedRowIds.includes(row.id) && row.id !== "__adding__");
    if (!selectedRows.length) {
      return;
    }

    const summaryText =
      selectedRows.length === 1
        ? `${selectedRows[0].name}(${selectedRows[0].ticker}) 종목을 삭제하시겠습니까?`
        : `${selectedRows.length}개 종목을 삭제하시겠습니까?`;
    if (!confirm(summaryText)) {
      return;
    }

    setProcessingId("__deleting__");
    try {
      for (const row of selectedRows) {
        const params = new URLSearchParams({
          account: summary.account_id,
          ticker: row.ticker.replace("ASX:", ""),
        });
        const response = await fetch(`/api/assets?${params.toString()}`, { method: "DELETE" });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "삭제 실패");
        }
      }
      await onReload();
      toast.success("삭제 완료");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "삭제 실패");
    } finally {
      setProcessingId(null);
    }
  }, [gridRows, onReload, selectedRowIds, summary.account_id, toast]);

  const handleCellValueChanged = useCallback((row: GridRow | undefined, field: string | undefined) => {
    if (!row) {
      return;
    }
    if (isCashGridRow(row)) {
      const nextCashBalance = Math.max(0, Number(row.valuation_krw ?? 0));
      const nextCashTargetRatio = Number(row.target_ratio ?? 0);
      cashDraftRef.current = {
        cashBalanceKrw: nextCashBalance,
        cashTargetRatio: nextCashTargetRatio,
      };
      setDirtyRowIds((previous) => {
        const next = previous.includes(row.id) ? previous : [...previous, row.id];
        dirtyRowIdsRef.current = next;
        return next;
      });
      if (field) {
        const dirtyCellKey = buildDirtyCellKey(row.id, field);
        setDirtyCellKeys((previous) => (previous.includes(dirtyCellKey) ? previous : [...previous, dirtyCellKey]));
      }
      onCashSync(summary.account_id, nextCashBalance, nextCashTargetRatio);
      const timerKey = row.id;
      const currentTimer = childSaveTimersRef.current.get(timerKey);
      if (currentTimer) {
        clearTimeout(currentTimer);
      }
      const nextTimer = setTimeout(async () => {
        childSaveTimersRef.current.delete(timerKey);
        try {
          await processCashUpdate(nextCashBalance, nextCashTargetRatio);
          clearDirtyRowState(timerKey);
          toast.success("현금 저장 완료");
        } catch (error) {
          await onReload();
          toast.error(error instanceof Error ? error.message : "현금 저장에 실패했습니다.");
        }
      }, 700);
      childSaveTimersRef.current.set(timerKey, nextTimer);
      return;
    }
    if (!isEditableHoldingRow(row)) {
      return;
    }

    const nextRows = rowsRef.current.map((currentRow) => {
      if (buildGridRowId(currentRow) !== row.id) {
        return currentRow;
      }
      return {
        ...currentRow,
        quantity: parseEditableQuantity(row.quantity),
        average_buy_price: safeParseFloat(row.average_buy_price),
        target_ratio: Number(row.target_ratio ?? 0),
      };
    });
    rowsRef.current = nextRows;
    setRows(nextRows);
    onRowsSync(summary.account_id, buildSyncedHoldingRows(nextRows, summary));
    setDirtyRowIds((previous) => {
      const next = previous.includes(row.id) ? previous : [...previous, row.id];
      dirtyRowIdsRef.current = next;
      return next;
    });
    if (field) {
      const dirtyCellKey = buildDirtyCellKey(row.id, field);
      setDirtyCellKeys((previous) => (previous.includes(dirtyCellKey) ? previous : [...previous, dirtyCellKey]));
    }
    scheduleSilentRowSave(row.id);
  }, [clearDirtyRowState, isCashGridRow, isEditableHoldingRow, onCashSync, onReload, onRowsSync, processCashUpdate, scheduleSilentRowSave, summary, toast]);

  const columns = useMemo<ColDef<GridRow>[]>(() => [
    {
      colId: "drag",
      headerName: "",
      width: 42,
      maxWidth: 42,
      pinned: "left",
      sortable: false,
      resizable: false,
      suppressMovable: true,
      rowDrag: (params) =>
        Boolean(params.data && params.data.id !== "__adding__" && params.data.ticker !== "IS" && params.data.ticker !== CASH_ROW_TICKER),
      cellClass: "assetsDragCell",
      valueGetter: () => "",
    },
    {
      field: "bucket",
      headerName: "버킷",
      width: 96,
      cellClass: (params) => getBucketCellClass(params.data?.bucket_id ?? 0),
    },
    {
      field: "ticker",
      headerName: "종목코드",
      width: 98,
      cellRenderer: (params: { data?: GridRow; value?: string }) => {
        const row = params.data;
        if (!row) {
          return null;
        }
        if (row.id === "__adding__") {
          return (
            <StableInlineInput
              className="form-control form-control-sm assetsInlineInput assetsInlineInputTicker"
              initialValue={addingRow?.ticker ?? ""}
              disabled={addingRow?.isValidatingTicker || addingRow?.isValidated}
              onChange={(value) =>
                setAddingRow((previous) =>
                  previous
                    ? {
                        ...previous,
                        ticker: value,
                      }
                    : null,
                )
              }
              onSave={handleValidateTicker}
            />
          );
        }
        return (
          row.ticker === CASH_ROW_TICKER ? <span>-</span> : (
            <button
              type="button"
              className="btn btn-link p-0 appCodeText assetsTickerLink"
              onClick={() => moveToTickerDetail(row.ticker)}
            >
              {params.value}
            </button>
          )
        );
      },
    },
    {
      field: "name",
      headerName: "종목명",
      minWidth: 248,
      flex: 1.35,
      cellRenderer: (params: { data?: GridRow; value?: string | null }) => {
        if (params.data?.id === "__adding__") {
          return (
            <div className="assetsNameLookup">
              <span className="assetsNameLookupStatus">
                {addingRow?.isValidated
                  ? String(addingRow.name || "-")
                  : String(addingRow?.name || "종목코드를 입력한 뒤 확인하세요.")}
              </span>
              <button
                className={
                  addingRow?.isValidated
                    ? "btn btn-sm btn-link p-0 assetsInlineLinkButton"
                    : "btn btn-outline-primary btn-sm assetsInlineButton d-inline-flex align-items-center gap-1"
                }
                disabled={addingRow?.isValidatingTicker}
                onMouseDown={(event) => {
                  event.stopPropagation();
                }}
                onClick={(event) => {
                  event.stopPropagation();
                  if (addingRow?.isValidated) {
                    setAddingRow((previous) =>
                      previous
                        ? {
                            ...previous,
                            ticker: "",
                            isValidated: false,
                            name: "",
                          }
                        : null,
                    );
                    return;
                  }
                  void handleValidateTicker();
                }}
              >
                {!addingRow?.isValidated && addingRow?.isValidatingTicker ? (
                  <IconLoader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
                ) : null}
                {addingRow?.isValidated ? "변경" : addingRow?.isValidatingTicker ? "확인중" : "확인"}
              </button>
            </div>
          );
        }

        const value = String(params.value ?? "-");
        return <span className="assetsNameCellText" title={value}>{value}</span>;
      },
    },
    {
      field: "daily_change_pct",
      headerName: "일간(%)",
      width: 92,
      type: "rightAligned",
      cellRenderer: (params: { value?: number | null }) => (
        <span className={getSignedClass(params.value ?? 0)}>
          {params.value === null || params.value === undefined
            ? "-"
            : `${(params.value ?? 0) > 0 ? "+" : ""}${params.value.toFixed(2)}%`}
        </span>
      ),
    },
    {
      field: "current_price",
      headerName: "현재가",
      width: 104,
      type: "rightAligned",
      cellRenderer: (params: { data?: GridRow; value?: string }) => (
        <span>{formatPrice(safeParseFloat(params.value), params.data?.currency || "KRW")}</span>
      ),
    },
    {
      field: "weight_pct",
      headerName: "비중",
      width: 80,
      type: "rightAligned",
      cellRenderer: (params: { data?: GridRow }) => {
        if (!params.data) {
          return "-";
        }

        const weightPct = getPreviewWeightPct(params.data, rowsRef.current, summaryRef.current);
        return (
          <span style={{ color: getWeightTextColor(weightPct, params.data.target_ratio), fontWeight: 700 }}>
            {weightPct.toFixed(1)}%
          </span>
        );
      },
    },
    {
      field: "target_ratio",
      headerName: "목표비중",
      width: 88,
      type: "rightAligned",
      editable: (params) =>
        Boolean(params.data && processingId !== params.data?.id && (isEditableHoldingRow(params.data) || isCashGridRow(params.data))),
      cellClass: (params) => {
        if (!isEditableHoldingRow(params.data) && !isCashGridRow(params.data)) {
          return undefined;
        }
        return isDirtyEditableCell(params.data?.id, "target_ratio")
          ? "assetsEditableCell assetsDirtyCell"
          : "assetsEditableCell";
      },
      valueParser: (params) => {
        const parsed = Number(params.newValue);
        if (Number.isNaN(parsed) || parsed < 0 || parsed > 100) {
          return params.oldValue;
        }
        return parsed;
      },
      cellRenderer: (params: { data?: GridRow; value?: number | null }) => {
        const row = params.data;
        if (!row) {
          return null;
        }
        if (row.id === "__adding__") {
          return (
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              ref={targetRatioRef}
              className="form-control form-control-sm assetsInlineInput"
              defaultValue={addingRow?.target_ratio ?? "0"}
              disabled={!addingRow?.isValidated}
            />
          );
        }
        return (
          <span style={{ color: ASSETS_WEIGHT_TEXT_COLOR, fontWeight: 700 }}>
            {params.value === null || params.value === undefined ? "-" : `${params.value.toFixed(1)}%`}
          </span>
        );
      },
    },
    {
      field: "quantity",
      headerName: "수량",
      width: 80,
      type: "rightAligned",
      editable: (params) => isEditableHoldingRow(params.data) && processingId !== params.data?.id,
      cellClass: (params) => {
        if (!isEditableHoldingRow(params.data)) {
          return undefined;
        }
        return isDirtyEditableCell(params.data?.id, "quantity")
          ? "assetsEditableCell assetsDirtyCell"
          : "assetsEditableCell";
      },
      valueParser: (params) => {
        const parsed = parseInt(parseRawPrice(params.newValue), 10);
        if (Number.isNaN(parsed) || parsed < 0) {
          return params.oldValue;
        }
        return parsed;
      },
      cellRenderer: (params: { data?: GridRow; value?: number }) => {
        const row = params.data;
        if (!row) {
          return null;
        }
        if (row.ticker === CASH_ROW_TICKER) {
          return <span>-</span>;
        }
        if (row.id === "__adding__") {
          return (
            <input
              type="number"
              step="1"
              ref={qtyRef}
              className="form-control form-control-sm assetsInlineInput"
              defaultValue="0"
              disabled={!addingRow?.isValidated}
            />
          );
        }
        return <span>{new Intl.NumberFormat("ko-KR").format(params.value ?? 0)}</span>;
      },
    },
    {
      field: "average_buy_price",
      headerName: "매입 단가",
      width: 112,
      type: "rightAligned",
      editable: (params) => isEditableHoldingRow(params.data) && processingId !== params.data?.id,
      cellClass: (params) => {
        if (!isEditableHoldingRow(params.data)) {
          return undefined;
        }
        return isDirtyEditableCell(params.data?.id, "average_buy_price")
          ? "assetsEditableCell assetsDirtyCell"
          : "assetsEditableCell";
      },
      valueParser: (params) => {
        const parsed = parseFloat(parseRawPrice(params.newValue));
        if (Number.isNaN(parsed) || parsed < 0) {
          return params.oldValue;
        }
        return parsed;
      },
      cellRenderer: (params: { data?: GridRow; value?: string | number }) => {
        const row = params.data;
        if (!row) {
          return null;
        }
        if (row.ticker === CASH_ROW_TICKER) {
          return <span>-</span>;
        }
        if (row.id === "__adding__") {
          return (
            <input
              type="number"
              step="any"
              ref={priceRef}
              className="form-control form-control-sm assetsInlineInput"
              defaultValue="0"
              disabled={!addingRow?.isValidated}
            />
          );
        }
        return <span>{formatPrice(safeParseFloat(params.value), row.currency || "KRW")}</span>;
      },
    },
    {
      field: "return_pct",
      headerName: "수익률",
      width: 88,
      type: "rightAligned",
      cellRenderer: (params: { data?: GridRow; value?: number }) => (
        params.data?.ticker === CASH_ROW_TICKER ? <span>-</span> :
        <span className={getSignedClass(params.value ?? 0)}>
          {(params.value ?? 0) > 0 ? "+" : ""}
          {(params.value ?? 0).toFixed(2)}%
        </span>
      ),
    },
    {
      field: "pnl_krw",
      headerName: "평가손익",
      width: 124,
      type: "rightAligned",
      cellRenderer: (params: { data?: GridRow; value?: number }) => (
        params.data?.ticker === CASH_ROW_TICKER ? <span>-</span> :
        <span className={getSignedClass(params.value ?? 0)}>{formatKrw(params.value ?? 0)}</span>
      ),
    },
    {
      field: "valuation_krw",
      headerName: "평가 금액",
      width: 124,
      type: "rightAligned",
      editable: (params) => Boolean(params.data && params.data.ticker === CASH_ROW_TICKER && !isAusAccount && processingId !== params.data?.id),
      cellClass: (params) => {
        if (params.data?.ticker !== CASH_ROW_TICKER || isAusAccount) {
          return undefined;
        }
        return isDirtyEditableCell(params.data?.id, "valuation_krw")
          ? "assetsEditableCell assetsDirtyCell"
          : "assetsEditableCell";
      },
      valueParser: (params) => {
        const parsed = parseFloat(parseRawPrice(params.newValue));
        if (Number.isNaN(parsed) || parsed < 0) {
          return params.oldValue;
        }
        return parsed;
      },
      cellRenderer: (params: { data?: GridRow }) => (params.data ? formatKrw(getPreviewValuationKrw(params.data)) : "-"),
    },
    { field: "days_held", headerName: "보유일", width: 76 },
  ], [addingRow, handleValidateTicker, isAusAccount, isCashGridRow, isDirtyEditableCell, isEditableHoldingRow, moveToTickerDetail, processingId]);

  return (
    <div className="assetsDetailPanel">
      <div className="appActionHeader">
        <div className="appActionHeaderInner">
          {isAusAccount && (
            <div className="d-flex align-items-center gap-2">
              <label className="mb-0 text-muted small fw-bold">Intl Value</label>
              <input
                type="text"
                className={`form-control form-control-sm ${intlDirtyFields.includes("intl_shares_value") ? "assetsDirtyInput" : ""}`}
                style={{ width: 120, textAlign: "right" }}
                defaultValue={Number(summary.intl_shares_value ?? 0).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                onChange={(event) => {
                  const parsed = parseFloat(event.target.value.replace(/,/g, ""));
                  if (!Number.isNaN(parsed)) {
                    intlDraftRef.current.intlSharesValue = parsed;
                    setIntlDirtyFields((prev) => (prev.includes("intl_shares_value") ? prev : [...prev, "intl_shares_value"]));
                  }
                }}
              />
              <label className="mb-0 text-muted small fw-bold">Intl Change</label>
              <input
                type="text"
                className={`form-control form-control-sm ${intlDirtyFields.includes("intl_shares_change") ? "assetsDirtyInput" : ""}`}
                style={{ width: 120, textAlign: "right" }}
                defaultValue={Number(summary.intl_shares_change ?? 0).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                onChange={(event) => {
                  const parsed = parseFloat(event.target.value.replace(/,/g, ""));
                  if (!Number.isNaN(parsed)) {
                    intlDraftRef.current.intlSharesChange = parsed;
                    setIntlDirtyFields((prev) => (prev.includes("intl_shares_change") ? prev : [...prev, "intl_shares_change"]));
                  }
                }}
              />
              <label className="mb-0 text-muted small fw-bold">AUD Cash</label>
              <input
                type="text"
                className={`form-control form-control-sm ${intlDirtyFields.includes("cash_native") ? "assetsDirtyInput" : ""}`}
                style={{ width: 120, textAlign: "right" }}
                defaultValue={Number(summary.cash_balance_native ?? 0).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                onChange={(event) => {
                  const parsed = parseFloat(event.target.value.replace(/,/g, ""));
                  if (!Number.isNaN(parsed)) {
                    intlDraftRef.current.cashNative = parsed;
                    setIntlDirtyFields((prev) => (prev.includes("cash_native") ? prev : [...prev, "cash_native"]));
                  }
                }}
              />
              <button
                className="btn btn-success btn-sm px-2"
                disabled={intlDirtyFields.length === 0}
                onClick={async () => {
                  try {
                    await processIntlUpdate(
                      intlDraftRef.current.intlSharesValue,
                      intlDraftRef.current.intlSharesChange,
                      intlDraftRef.current.cashNative,
                    );
                    setIntlDirtyFields([]);
                    await onReload();
                    toast.success("호주 계좌 저장 완료");
                  } catch (error) {
                    await onReload();
                    toast.error(error instanceof Error ? error.message : "호주 계좌 저장에 실패했습니다.");
                  }
                }}
              >
                저장
              </button>
            </div>
          )}
          <div className="d-flex align-items-center gap-2 ms-auto">
            <button
              className="btn btn-primary btn-sm px-3 fw-bold"
              onClick={() =>
                setAddingRow({
                  ticker: "",
                  quantity: "",
                  average_buy_price: "",
                  target_ratio: "0",
                  isValidated: false,
                })
              }
              disabled={hasPendingAdd}
            >
              <IconPlus size={16} /> 추가
            </button>
            <button
              className="btn btn-success btn-sm px-3 fw-bold"
              onClick={() => void handleSaveChanges()}
              disabled={!hasPendingSave || processingId === "__adding__" || processingId === "__deleting__"}
            >
              <IconCheck size={16} /> 저장
            </button>
            <button
              className="btn btn-outline-danger btn-sm px-3 fw-bold"
              onClick={() => void handleDeleteSelected()}
              disabled={!hasSelectedRows || processingId === "__adding__" || processingId === "__deleting__"}
            >
              <IconTrash size={16} /> 삭제
            </button>
          </div>
        </div>
      </div>
      <div className="assetsDetailGridWrap">
        <AppAgGrid
          rowData={gridRows}
          columnDefs={columns}
          loading={processingId === "__adding__" || processingId === "__deleting__"}
          minHeight="100%"
          className="assetsAgGrid assetsChildAgGrid"
          theme={assetsGridTheme}
          getRowClass={(params: RowClassParams<GridRow>) => {
            const classes: string[] = [];
            if (params.data?.ticker === "IS") {
              return classes.join(" ");
            }
            if (Number(params.data?.quantity ?? 0) > 0) {
              classes.push("appHeldRow");
            }
            return classes.join(" ");
          }}
          gridOptions={{
            suppressMovableColumns: true,
            ensureDomOrder: true,
            stopEditingWhenCellsLoseFocus: true,
            rowDragManaged: true,
            animateRows: true,
            rowSelection: {
              mode: "multiRow",
              checkboxes: (params) =>
                Boolean(params.data && params.data.id !== "__adding__" && params.data.ticker !== "IS" && params.data.ticker !== CASH_ROW_TICKER),
              headerCheckbox: true,
              hideDisabledCheckboxes: true,
              enableClickSelection: false,
              isRowSelectable: (params) =>
                Boolean(params.data && params.data.id !== "__adding__" && params.data.ticker !== "IS" && params.data.ticker !== CASH_ROW_TICKER),
            },
            selectionColumnDef: {
              width: 52,
              minWidth: 52,
              maxWidth: 52,
              pinned: "left",
              sortable: false,
              resizable: false,
              suppressMovable: true,
              headerName: "",
              cellClass: "assetsSelectCell",
            },
            onSelectionChanged: (params) => {
              setSelectedRowIds(
                params.api
                  .getSelectedRows()
                  .map((row) => row.id)
                  .filter((rowId): rowId is string => Boolean(rowId)),
              );
            },
            onCellEditingStarted: (params) => {
              if (params.data && isEditableHoldingRow(params.data)) {
                setEditingRowId(params.data.id);
              }
            },
            onCellEditingStopped: () => {
              setEditingRowId(null);
            },
            onCellValueChanged: (params) => {
              if (params.newValue === params.oldValue) {
                return;
              }
              handleCellValueChanged(params.data, params.colDef.field);
            },
            onRowDragEnd: (params) => {
              const orderedTickers: string[] = [];
              params.api.forEachNode((node) => {
                const ticker = String(node.data?.ticker || "").trim().toUpperCase();
                if (!ticker || ticker === "IS" || ticker === CASH_ROW_TICKER) {
                  return;
                }
                orderedTickers.push(ticker);
              });
              if (!orderedTickers.length) {
                return;
              }
              setRows((previous) => {
                const nextRows = reorderRowsByTickers(previous, orderedTickers);
                rowsRef.current = nextRows;
                onRowsSync(summary.account_id, buildSyncedHoldingRows(nextRows, summary));
                return nextRows;
              });
              const nextRows = reorderRowsByTickers(rowsRef.current, orderedTickers);
              rowsRef.current = nextRows;
              setIsReorderDirty(true);
              isReorderDirtyRef.current = true;
              scheduleSilentReorderSave(nextRows);
            },
            onGridReady: (params) => {
              gridApiRef.current = params.api;
              if (initialSortState.length > 0) {
                params.api.applyColumnState({
                  state: initialSortState,
                  applyOrder: false,
                });
              }
            },
            onSortChanged: (params) => {
              const nextSortState = params.api
                .getColumnState()
                .filter((column): column is ColumnState => Boolean(column.sort) && Boolean(column.colId))
                .map((column) => ({
                  colId: String(column.colId),
                  sort: column.sort,
                  sortIndex: column.sortIndex,
                }));
              onSortStateChange(summary.account_id, nextSortState);
            },
            getRowId: (params) => String(params.data.id),
            rowClassRules: {
              assetsAddingRow: (params) => params.data?.id === "__adding__",
              assetsEditingRow: (params) => Boolean(params.data?.id && params.data.id === editingRowId),
            },
          }}
        />
      </div>
    </div>
  );
}

export function AssetsManager({ onHeaderSummaryChange }: { onHeaderSummaryChange?: (summary: AssetsHeaderSummary) => void }) {
  const toast = useToast();
  const [allRows, setAllRows] = useState<HoldingsRow[]>([]);
  const [summaries, setSummaries] = useState<AccountSummary[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [parentDirtyCellKeys, setParentDirtyCellKeys] = useState<string[]>([]);
  const [editingParentId, setEditingParentId] = useState<string | null>(null);
  const [previewTargetRatioTotals, setPreviewTargetRatioTotals] = useState<Record<string, number>>({});
  const summariesRef = useRef<AccountSummary[]>([]);
  const parentSaveTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const parentSavingAccountIdsRef = useRef<Set<string>>(new Set());
  const parentQueuedAccountIdsRef = useRef<Set<string>>(new Set());
  const childSortStatesRef = useRef<Record<string, ColumnState[]>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [response, dashResponse] = await Promise.all([
        fetch("/api/assets", { cache: "no-store" }),
        fetch("/api/dashboard", { cache: "no-store" }).catch(() => null),
      ]);
      const payload = (await response.json()) as HoldingsResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "자산 정보를 불러오지 못했습니다.");
      }
      const dashData = dashResponse?.ok ? await dashResponse.json() : null;
      const dashAccounts: Record<string, { cash_ratio: number; net_profit: number; net_profit_pct: number; daily_profit: number; weekly_profit: number }> = {};
      if (dashData?.accounts) {
        for (const a of dashData.accounts) {
          dashAccounts[a.account_id] = {
            cash_ratio: a.cash_ratio ?? 0,
            net_profit: a.net_profit ?? 0,
            net_profit_pct: a.net_profit_pct ?? 0,
            daily_profit: a.daily_profit ?? 0,
            weekly_profit: a.weekly_profit ?? 0,
          };
        }
      }
      const defaultDash = { cash_ratio: 0, net_profit: 0, net_profit_pct: 0, daily_profit: 0, weekly_profit: 0 };
      const mergedSummaries = (payload.account_summaries ?? []).map((s) => ({
        ...s,
        ...(dashAccounts[s.account_id] ?? defaultDash),
      }));
      setAllRows(payload.rows ?? []);
      setSummaries(mergedSummaries);
      setExpandedId((current) => current);
      setPreviewTargetRatioTotals({});
      setParentDirtyCellKeys([]);
      setEditingParentId(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "자산 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    summariesRef.current = summaries;
  }, [summaries]);

  useEffect(() => {
    return () => {
      parentSaveTimersRef.current.forEach((timer) => clearTimeout(timer));
      parentSaveTimersRef.current.clear();
    };
  }, []);

  const groupedRows = useMemo(() => {
    const grouped = new Map<string, HoldingsRow[]>();
    for (const row of allRows) {
      const key = String(row.account_id || "").trim();
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)?.push(row);
    }
    return grouped;
  }, [allRows]);

  const totalAssets = useMemo(
    () => summaries.reduce((sum, summary) => sum + Number(summary.total_assets_krw ?? 0), 0),
    [summaries],
  );
  const totalValuation = useMemo(
    () => summaries.reduce((sum, summary) => sum + Number(summary.valuation_krw ?? 0), 0),
    [summaries],
  );
  const totalCash = useMemo(
    () => summaries.reduce((sum, summary) => sum + Number(summary.cash_balance_krw ?? 0), 0),
    [summaries],
  );
  const totalPrincipal = useMemo(
    () => summaries.reduce((sum, summary) => sum + Number(summary.total_principal ?? 0), 0),
    [summaries],
  );
  const totalHoldingsCount = useMemo(
    () => summaries.reduce((sum, summary) => sum + Number(summary.holdings_count ?? 0), 0),
    [summaries],
  );

  const parentRows = useMemo<ParentGridRow[]>(() => {
    const totalRow: ParentGridRow = {
      id: "__total__",
      rowType: "total",
      name: "합계",
      total_assets_krw: totalAssets,
      valuation_krw: totalValuation,
      total_principal: totalPrincipal,
      cash_edit_value: totalCash,
      target_ratio_total: null,
      holdings_count: totalHoldingsCount,
      cash_ratio: totalAssets > 0 ? (totalCash / totalAssets) * 100 : 0,
      net_profit: totalAssets - totalPrincipal,
      net_profit_pct: totalPrincipal > 0 ? ((totalAssets - totalPrincipal) / totalPrincipal) * 100 : 0,
      daily_profit: summaries.reduce((sum, s) => sum + (s.daily_profit ?? 0), 0),
      weekly_profit: summaries.reduce((sum, s) => sum + (s.weekly_profit ?? 0), 0),
    };

    const detailRows = summaries.flatMap((summary): ParentGridRow[] => {
      const mainRow: ParentGridRow = {
        ...summary,
        id: summary.account_id,
        rowType: "main",
        cash_edit_value:
          String(summary.currency || "KRW").toUpperCase() === "AUD"
            ? Number(summary.cash_balance_native ?? 0)
            : Number(summary.cash_balance_krw ?? 0),
      };

      if (expandedId !== summary.account_id) {
        return [mainRow];
      }

      const detailRow: ParentGridRow = {
        id: `${summary.account_id}__detail`,
        rowType: "detail",
        parentId: summary.account_id,
        summary,
        rows: groupedRows.get(summary.account_id) ?? [],
      };

      return [
        mainRow,
        detailRow,
      ];
    });
    return [totalRow, ...detailRows];
  }, [expandedId, groupedRows, summaries, totalAssets, totalCash, totalHoldingsCount, totalPrincipal, totalValuation]);

  useEffect(() => {
    onHeaderSummaryChange?.({
      totalAssets,
      totalValuation,
      totalCash,
      accountCount: summaries.length,
    });
  }, [onHeaderSummaryChange, summaries.length, totalAssets, totalCash, totalValuation]);

  const isDirtyParentCell = useCallback(
    (rowId: string | undefined, field: string) => Boolean(rowId && parentDirtyCellKeys.includes(buildDirtyCellKey(rowId, field))),
    [parentDirtyCellKeys],
  );

  const clearDirtyParentState = useCallback((accountId: string) => {
    setParentDirtyCellKeys((previous) => previous.filter((key) => !key.startsWith(`${accountId}::`)));
  }, []);

  const silentlySaveParent = useCallback(async (accountId: string) => {
    if (parentSavingAccountIdsRef.current.has(accountId)) {
      parentQueuedAccountIdsRef.current.add(accountId);
      return;
    }

    const summary = summariesRef.current.find((item) => item.account_id === accountId);
    if (!summary) {
      clearDirtyParentState(accountId);
      return;
    }

    parentSavingAccountIdsRef.current.add(accountId);
    try {
      const isAud = String(summary.currency || "KRW").toUpperCase() === "AUD";
      const response = await fetch("/api/assets", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: summary.account_id,
          total_principal: summary.total_principal,
          cash_balance_krw: isAud ? 0 : summary.cash_balance_krw,
          cash_balance_native: isAud ? summary.cash_balance_native : summary.cash_balance_krw,
          cash_currency: summary.cash_currency,
          intl_shares_value: summary.account_id === "aus_account" ? summary.intl_shares_value : null,
          intl_shares_change: summary.account_id === "aus_account" ? summary.intl_shares_change : null,
          cash_target_ratio: summary.cash_target_ratio,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "계좌 저장에 실패했습니다.");
      }
      clearDirtyParentState(accountId);
    } catch (error) {
      await load();
      toast.error(error instanceof Error ? error.message : "계좌 저장에 실패했습니다.");
    } finally {
      parentSavingAccountIdsRef.current.delete(accountId);
      if (parentQueuedAccountIdsRef.current.has(accountId)) {
        parentQueuedAccountIdsRef.current.delete(accountId);
        const nextTimer = setTimeout(() => {
          parentSaveTimersRef.current.delete(accountId);
          void silentlySaveParent(accountId);
        }, 400);
        parentSaveTimersRef.current.set(accountId, nextTimer);
      }
    }
  }, [clearDirtyParentState, load, toast]);

  const scheduleSilentParentSave = useCallback((accountId: string) => {
    const currentTimer = parentSaveTimersRef.current.get(accountId);
    if (currentTimer) {
      clearTimeout(currentTimer);
    }
    const nextTimer = setTimeout(() => {
      parentSaveTimersRef.current.delete(accountId);
      void silentlySaveParent(accountId);
    }, 700);
    parentSaveTimersRef.current.set(accountId, nextTimer);
  }, [silentlySaveParent]);

  const handleParentCellValueChanged = useCallback((row: ParentGridRow | undefined, field: string | undefined) => {
    if (!row || isDetailRow(row) || isTotalRow(row) || !field) {
      return;
    }

    setSummaries((previous) =>
      previous.map((summary) => {
        if (summary.account_id !== row.account_id) {
          return summary;
        }

        const cashEditValue = Number((row as Extract<ParentGridRow, { rowType: "main" }>).cash_edit_value ?? 0);
        const isAud = String(summary.currency || "KRW").toUpperCase() === "AUD";
        return {
          ...summary,
          total_principal: Number(row.total_principal ?? summary.total_principal),
          cash_balance_krw: isAud ? summary.cash_balance_krw : cashEditValue,
          cash_balance_native: isAud ? cashEditValue : summary.cash_balance_native,
          total_assets_krw: summary.valuation_krw + (isAud ? summary.cash_balance_krw : cashEditValue),
        };
      }),
    );
    const dirtyCellKey = buildDirtyCellKey(row.account_id, field);
    setParentDirtyCellKeys((previous) => (previous.includes(dirtyCellKey) ? previous : [...previous, dirtyCellKey]));
    scheduleSilentParentSave(row.account_id);
  }, [scheduleSilentParentSave]);

  const handlePreviewTargetRatioTotalChange = useCallback((accountId: string, total: number) => {
    setPreviewTargetRatioTotals((previous) => {
      if (Math.abs(Number(previous[accountId] ?? NaN) - total) < 0.05) {
        return previous;
      }
      return {
        ...previous,
        [accountId]: total,
      };
    });
  }, []);

  const handleChildRowsSync = useCallback((accountId: string, nextRows: HoldingsRow[]) => {
    setAllRows((previous) => [
      ...previous.filter((row) => row.account_id !== accountId),
      ...nextRows,
    ]);

    const nextValuation = nextRows.reduce((sum, row) => sum + Number(row.valuation_krw ?? 0), 0);
    setSummaries((previous) =>
      previous.map((summary) => {
        if (summary.account_id !== accountId) {
          return summary;
        }
        return {
          ...summary,
          valuation_krw: nextValuation,
          total_assets_krw: nextValuation + Number(summary.cash_balance_krw ?? 0),
          holdings_count: nextRows.filter((r) => r.ticker !== "IS").length,
        };
      }),
    );
  }, []);

  const handleChildSortStateChange = useCallback((accountId: string, state: ColumnState[]) => {
    childSortStatesRef.current = {
      ...childSortStatesRef.current,
      [accountId]: state,
    };
  }, []);

  const DetailRenderer = useCallback(
    (params: { data?: ParentGridRow }) => {
      const data = params.data;
      if (!data || !isDetailRow(data)) {
        return null;
      }
      return (
        <AccountHoldingsDetailPanel
          summary={data.summary}
          initialRows={data.rows}
          initialSortState={childSortStatesRef.current[data.summary.account_id] ?? []}
          onReload={load}
          onRowsSync={handleChildRowsSync}
          onCashSync={(accountId, cashBalanceKrw, cashTargetRatio) => {
            setSummaries((previous) =>
              previous.map((summary) => {
                if (summary.account_id !== accountId) {
                  return summary;
                }
                const currentCashKrw = Number(summary.cash_balance_krw ?? 0);
                const currentCashNative = Number(summary.cash_balance_native ?? 0);
                const nextCashNative =
                  String(summary.currency || "KRW").toUpperCase() === "AUD" && currentCashKrw > 0 && currentCashNative > 0
                    ? (cashBalanceKrw / currentCashKrw) * currentCashNative
                    : summary.cash_balance_native;
                return {
                  ...summary,
                  cash_balance_krw: cashBalanceKrw,
                  cash_balance_native: nextCashNative,
                  cash_target_ratio: cashTargetRatio,
                  total_assets_krw: Number(summary.valuation_krw ?? 0) + cashBalanceKrw,
                };
              }),
            );
          }}
          onPreviewTargetRatioTotalChange={handlePreviewTargetRatioTotalChange}
          onSortStateChange={handleChildSortStateChange}
        />
      );
    },
    [handleChildRowsSync, handleChildSortStateChange, handlePreviewTargetRatioTotalChange, load],
  );

  const parentColumns = useMemo<ColDef<ParentGridRow>[]>(() => [
    {
      field: "name",
      headerName: "계좌",
      minWidth: 220,
      flex: 1.2,
      cellRenderer: (params: { data?: ParentGridRow; value?: string }) => {
        const data = params.data;
        if (!data || isDetailRow(data)) {
          return "";
        }
        if (isTotalRow(data)) {
          return <span className="fw-bold">{data.name}</span>;
        }
        const label = (
          <>
            {data.icon} {params.value}
          </>
        );
        return (
          <div className="snapshotsExpandCell">
            <span className="snapshotsExpandIcon" aria-hidden="true">
              {data.account_id === expandedId ? "▾" : "▸"}
            </span>
            <span>{label}</span>
          </div>
        );
      },
    },
    {
      field: "total_assets_krw",
      headerName: "총 자산",
      minWidth: 132,
      flex: 1,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data) ? formatKrw(params.value ?? 0) : "",
    },
    {
      field: "account_url",
      headerName: "링크",
      minWidth: 48,
      maxWidth: 52,
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params: { data?: ParentGridRow }) => {
        const data = params.data;
        if (!data || isDetailRow(data) || isTotalRow(data)) {
          return "";
        }
        if (!data.account_url) {
          return <span>-</span>;
        }
        return (
          <a
            href={data.account_url}
            target="_blank"
            rel="noreferrer"
            className="assetsInlineLinkButton assetsMoveLinkButton"
            onClick={(event) => {
              event.stopPropagation();
            }}
          >
            이동
          </a>
        );
      },
    },
    {
      field: "total_principal",
      headerName: "총 원금",
      minWidth: 124,
      flex: 1,
      type: "rightAligned",
      editable: (params) => Boolean(params.data && !isDetailRow(params.data) && !isTotalRow(params.data)),
      cellClass: (params) => {
        if (!params.data || isDetailRow(params.data) || isTotalRow(params.data)) {
          return undefined;
        }
        return isDirtyParentCell(params.data.account_id, "total_principal")
          ? "assetsEditableCell assetsDirtyCell"
          : "assetsEditableCell";
      },
      valueParser: (params) => {
        const parsed = parseFloat(parseRawPrice(params.newValue));
        if (Number.isNaN(parsed) || parsed < 0) {
          return params.oldValue;
        }
        return parsed;
      },
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data) ? formatKrw(params.value ?? 0) : "",
    },
    {
      field: "valuation_krw",
      headerName: "평가액",
      minWidth: 132,
      flex: 1,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data) ? formatKrw(params.value ?? 0) : "",
    },
    {
      field: "cash_edit_value",
      headerName: "현금",
      minWidth: 124,
      flex: 1,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) => {
        if (!params.data || isDetailRow(params.data)) {
          return "";
        }
        if (isTotalRow(params.data)) {
          return formatKrw(params.value ?? 0);
        }
        return formatPrice(params.value ?? 0, params.data.currency);
      },
    },
    {
      field: "cash_ratio",
      headerName: "현금 비중",
      minWidth: 90,
      flex: 0.7,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data) ? `${(params.value ?? 0).toFixed(2)}%` : "",
    },
    {
      field: "net_profit",
      headerName: "계좌 손익",
      minWidth: 120,
      flex: 1,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data)
          ? <span className={getSignedClass(params.value ?? 0)}>{formatKrw(params.value ?? 0)}</span>
          : "",
    },
    {
      field: "net_profit_pct",
      headerName: "수익률",
      minWidth: 90,
      flex: 0.7,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data)
          ? <span className={getSignedClass(params.value ?? 0)}>{`${(params.value ?? 0).toFixed(2)}%`}</span>
          : "",
    },
    {
      field: "daily_profit",
      headerName: "금일 손익",
      minWidth: 110,
      flex: 0.9,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data)
          ? <span className={getSignedClass(params.value ?? 0)}>{formatKrw(params.value ?? 0)}</span>
          : "",
    },
    {
      field: "weekly_profit",
      headerName: "금주 손익",
      minWidth: 110,
      flex: 0.9,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data)
          ? <span className={getSignedClass(params.value ?? 0)}>{formatKrw(params.value ?? 0)}</span>
          : "",
    },
    {
      field: "target_ratio_total",
      headerName: "목표비중합",
      minWidth: 108,
      flex: 0.8,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) => {
        if (!params.data || isDetailRow(params.data)) {
          return "";
        }
        if (isTotalRow(params.data)) {
          return "-";
        }
        const previewValue = previewTargetRatioTotals[params.data.account_id];
        const value = Number(previewValue ?? params.value ?? 0);
        const colorClass = Math.abs(value - 100) < 0.05 ? "is-success" : "is-danger";
        return <span className={`appHeaderMetricValue ${colorClass}`}>{value.toFixed(1)}%</span>;
      },
    },
    {
      field: "holdings_count",
      headerName: "종목수",
      minWidth: 76,
      flex: 0.6,
      type: "rightAligned",
      cellRenderer: (params: { data?: ParentGridRow; value?: number }) =>
        params.data && !isDetailRow(params.data) ? formatNumber(params.value) : "",
    },
  ], [expandedId, isDirtyParentCell, previewTargetRatioTotals]);

  const gridOptions = useMemo<GridOptions<ParentGridRow>>(
    () => ({
      suppressMovableColumns: true,
      ensureDomOrder: true,
      stopEditingWhenCellsLoseFocus: true,
      isFullWidthRow: (params) => isDetailRow(params.rowNode.data),
      fullWidthCellRenderer: DetailRenderer,
      getRowHeight: (params) => {
        if (!isDetailRow(params.data)) {
          return 38;
        }
        const rowCount = (params.data.rows?.length ?? 0) + 1;
        return 50 + 34 + rowCount * 42 + 32;
      },
      onCellClicked: (params) => {
        if (!params.data || isDetailRow(params.data) || isTotalRow(params.data)) {
          return;
        }
        if (params.colDef.field !== "name") {
          return;
        }
        const accountId = params.data.account_id;
        setExpandedId((current) => (current === accountId ? null : accountId));
      },
      onCellEditingStarted: (params) => {
        if (params.data && !isDetailRow(params.data) && !isTotalRow(params.data)) {
          setEditingParentId(params.data.account_id);
        }
      },
      onCellEditingStopped: () => {
        setEditingParentId(null);
      },
      onCellValueChanged: (params) => {
        if (params.newValue === params.oldValue) {
          return;
        }
        handleParentCellValueChanged(params.data, params.colDef.field);
      },
      rowClassRules: {
        assetsEditingRow: (params) =>
          Boolean(params.data && !isDetailRow(params.data) && !isTotalRow(params.data) && params.data.account_id === editingParentId),
        snapshotsExpandedMainRow: (params) =>
          Boolean(params.data && !isDetailRow(params.data) && !isTotalRow(params.data) && params.data.account_id === expandedId),
      },
    }),
    [DetailRenderer, editingParentId, expandedId, handleParentCellValueChanged],
  );

  if (loading && !summaries.length) {
    return (
      <div className="appPageStack">
        <div className="appPageLoading">
          <AppLoadingState label="자산 정보를 불러오는 중..." />
        </div>
      </div>
    );
  }

  return (
    <div className="appPageStack appPageStackFill">
      <section className="appSection appSectionFill">
        <div className="card appCard shadow-sm appTableCardFill">
          <div className="card-body p-2 appTableCardBodyFill">
            <AppAgGrid
              rowData={parentRows}
              columnDefs={parentColumns}
              loading={loading}
              minHeight="100%"
              className="assetsAgGrid assetsParentAgGrid"
              theme={assetsGridTheme}
              getRowClass={(params: RowClassParams<ParentGridRow>) => {
                if (isDetailRow(params.data)) {
                  return "assetsDetailFullRow";
                }
                return "";
              }}
              gridOptions={gridOptions}
            />
          </div>
        </div>
      </section>
      <div
        dangerouslySetInnerHTML={{
          __html:
            "<style>.assetsInlineLinkButton{font-weight:700;text-decoration:none;} .css-label{font-size:0.7rem;color:#666;display:block;margin-bottom:2px;} @keyframes spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}</style>",
        }}
      />
    </div>
  );
}
