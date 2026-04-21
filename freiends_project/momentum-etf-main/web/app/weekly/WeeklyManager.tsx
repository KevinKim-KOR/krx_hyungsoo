"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef } from "ag-grid-community";
import { IconCheck } from "@tabler/icons-react";

import { AppAgGrid } from "../components/AppAgGrid";
import { useToast } from "../components/ToastProvider";

type WeeklyEditableField = {
  key: string;
  label: string;
  type: "int" | "float" | "text";
};

type WeeklyRow = {
  week_date: string;
  week_date_display: string;
  withdrawal_personal: number;
  withdrawal_mom: number;
  nh_principal_interest: number;
  total_expense: number;
  deposit_withdrawal: number;
  total_principal: number;
  total_assets: number;
  purchase_amount: number;
  valuation_amount: number;
  profit_loss: number;
  cumulative_profit: number;
  weekly_profit: number;
  weekly_return_pct: number;
  cumulative_return_pct: number;
  memo: string;
  exchange_rate: number;
  exchange_rate_change_pct: number;
  bucket_pct_momentum: number;
  bucket_pct_market: number;
  bucket_pct_dividend: number;
  bucket_pct_alternative: number;
  bucket_pct_cash: number;
  total_stocks: number;
  profit_count: number;
  loss_count: number;
  updated_at: string | null;
};

type WeeklyResponse = {
  active_week_date?: string;
  rows?: WeeklyRow[];
  editable_fields?: WeeklyEditableField[];
  read_only_keys?: string[];
  core_hidden_keys?: string[];
  error?: string;
};

type WeeklyGridRow = WeeklyRow & {
  id: string;
};

type ViewMode = "core" | "full";

const MONEY_KEYS = new Set([
  "withdrawal_personal",
  "withdrawal_mom",
  "nh_principal_interest",
  "total_expense",
  "deposit_withdrawal",
  "total_principal",
  "total_assets",
  "purchase_amount",
  "valuation_amount",
  "profit_loss",
  "cumulative_profit",
  "weekly_profit",
]);

const PERCENT_KEYS = new Set([
  "weekly_return_pct",
  "cumulative_return_pct",
  "exchange_rate_change_pct",
  "bucket_pct_momentum",
  "bucket_pct_market",
  "bucket_pct_dividend",
  "bucket_pct_alternative",
  "bucket_pct_cash",
]);

const COLUMN_DEFS = [
  { key: "week_date_display", label: "종료일" },
  { key: "memo", label: "비고" },
  { key: "withdrawal_personal", label: "개인 인출" },
  { key: "withdrawal_mom", label: "엄마" },
  { key: "nh_principal_interest", label: "농협원리금" },
  { key: "total_expense", label: "지출 합계" },
  { key: "deposit_withdrawal", label: "입출금" },
  { key: "total_principal", label: "총 원금" },
  { key: "total_assets", label: "총 자산" },
  { key: "purchase_amount", label: "매입 금액" },
  { key: "valuation_amount", label: "평가 금액" },
  { key: "profit_loss", label: "평가 손익" },
  { key: "cumulative_profit", label: "누적 손익" },
  { key: "weekly_profit", label: "금주 손익" },
  { key: "weekly_return_pct", label: "주수익률" },
  { key: "cumulative_return_pct", label: "누적 수익률" },
  { key: "exchange_rate_change_pct", label: "환율(변동)" },
  { key: "exchange_rate", label: "환율" },
  { key: "bucket_pct_momentum", label: "1. 모멘텀" },
  { key: "bucket_pct_market", label: "2. 시장지수" },
  { key: "bucket_pct_dividend", label: "3. 배당방어" },
  { key: "bucket_pct_alternative", label: "4. 대체헷지" },
  { key: "bucket_pct_cash", label: "5. 현금" },
  { key: "total_stocks", label: "총 종목 수" },
  { key: "profit_count", label: "수익 종목 수" },
  { key: "loss_count", label: "손실 종목 수" },
] as const;

const weeklyGridTheme = themeQuartz
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

function formatMoney(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(Math.round(value));
}

function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

function formatExchangeRate(value: number): string {
  return value.toFixed(2);
}

function getSignedClass(value: number): string {
  if (!Number.isFinite(value) || value === 0) {
    return "";
  }
  return value > 0 ? "metricPositive" : "metricNegative";
}

function formatCellValue(row: WeeklyRow, key: (typeof COLUMN_DEFS)[number]["key"]): string {
  const value = row[key as keyof WeeklyRow];
  if (key === "week_date_display" || key === "memo") {
    return String(value ?? "-");
  }
  if (key === "exchange_rate") {
    return formatExchangeRate(Number(value ?? 0));
  }
  if (PERCENT_KEYS.has(key)) {
    return formatPercent(Number(value ?? 0));
  }
  return formatMoney(Number(value ?? 0));
}

function getColumnCellClass(key: string, value: number | string): string {
  const classes: string[] = [];
  if (key === "week_date_display") {
    classes.push("weeklyDateCell");
  }
  if (key === "memo") {
    classes.push("weeklyMemoCell");
  }
  if (MONEY_KEYS.has(key) || PERCENT_KEYS.has(key) || key === "exchange_rate") {
    classes.push("tableAlignRight");
  }
  if (typeof value === "number" && (key === "profit_loss" || key === "cumulative_profit" || key === "weekly_profit" || PERCENT_KEYS.has(key))) {
    const signedClass = getSignedClass(value);
    if (signedClass) {
      classes.push(signedClass);
    }
  }
  return classes.join(" ");
}

function buildDirtyCellKey(rowId: string, field: string): string {
  return `${rowId}::${field}`;
}

function parseWeeklyCellValue(field: WeeklyEditableField | undefined, newValue: unknown, oldValue: unknown) {
  if (!field) {
    return newValue;
  }
  if (field.type === "text") {
    return String(newValue ?? "");
  }
  const parsed = Number(newValue);
  if (!Number.isFinite(parsed)) {
    return oldValue;
  }
  if (field.type === "int") {
    return Math.trunc(parsed);
  }
  return parsed;
}

function getWeeklyColumnWidth(key: (typeof COLUMN_DEFS)[number]["key"]): { width?: number; minWidth: number; flex?: number } {
  if (key === "week_date_display") {
    return { width: 112, minWidth: 112 };
  }
  if (key === "memo") {
    return { width: 156, minWidth: 140, flex: 1 };
  }
  if (
    key === "total_principal" ||
    key === "total_assets" ||
    key === "purchase_amount" ||
    key === "valuation_amount" ||
    key === "profit_loss" ||
    key === "cumulative_profit" ||
    key === "weekly_profit"
  ) {
    return { width: 102, minWidth: 98 };
  }
  if (key === "exchange_rate") {
    return { width: 82, minWidth: 82 };
  }
  if (key === "exchange_rate_change_pct") {
    return { width: 94, minWidth: 94 };
  }
  if (key === "total_stocks" || key === "profit_count" || key === "loss_count") {
    return { width: 84, minWidth: 80 };
  }
  if (
    key === "withdrawal_mom" ||
    key === "total_expense" ||
    key === "deposit_withdrawal" ||
    key === "weekly_return_pct" ||
    key === "bucket_pct_cash"
  ) {
    return { width: 88, minWidth: 84 };
  }
  if (key === "cumulative_return_pct") {
    return { width: 96, minWidth: 92 };
  }
  if (
    key === "bucket_pct_momentum" ||
    key === "bucket_pct_market" ||
    key === "bucket_pct_dividend" ||
    key === "bucket_pct_alternative"
  ) {
    return { width: 96, minWidth: 92 };
  }
  if (PERCENT_KEYS.has(key)) {
    return { width: 84, minWidth: 80 };
  }
  if (MONEY_KEYS.has(key)) {
    return { width: 88, minWidth: 84 };
  }
  return { width: 78, minWidth: 72 };
}

export function WeeklyManager({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: { activeWeekDate: string; rowCount: number; dirtyCount: number }) => void;
}) {
  const [rows, setRows] = useState<WeeklyRow[]>([]);
  const [editableFields, setEditableFields] = useState<WeeklyEditableField[]>([]);
  const [readOnlyKeys, setReadOnlyKeys] = useState<Set<string>>(new Set());
  const [activeWeekDate, setActiveWeekDate] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("core");
  const [coreHiddenKeys, setCoreHiddenKeys] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dirtyRowIds, setDirtyRowIds] = useState<string[]>([]);
  const [dirtyCellKeys, setDirtyCellKeys] = useState<string[]>([]);
  const [isPending, startTransition] = useTransition();
  const toast = useToast();

  async function load(options?: { silent?: boolean }) {
    const silent = options?.silent ?? false;
    if (!silent) {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await fetch("/api/weekly", { cache: "no-store" });
      const payload = (await response.json()) as WeeklyResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "주별 데이터를 불러오지 못했습니다.");
      }
      setRows(payload.rows ?? []);
      setEditableFields(payload.editable_fields ?? []);
      setReadOnlyKeys(new Set(payload.read_only_keys ?? []));
      setCoreHiddenKeys(payload.core_hidden_keys ?? []);
      setActiveWeekDate(payload.active_week_date ?? "");
      setDirtyRowIds([]);
      setDirtyCellKeys([]);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "주별 데이터를 불러오지 못했습니다.");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const visibleColumns = useMemo(() => {
    if (viewMode === "full") {
      return COLUMN_DEFS;
    }
    return COLUMN_DEFS.filter((column) => !coreHiddenKeys.includes(column.key));
  }, [coreHiddenKeys, viewMode]);

  const gridRows = useMemo<WeeklyGridRow[]>(
    () =>
      rows.map((row) => ({
        ...row,
        id: row.week_date,
      })),
    [rows],
  );

  useEffect(() => {
    onHeaderSummaryChange?.({
      activeWeekDate: activeWeekDate || "-",
      rowCount: rows.length,
      dirtyCount: dirtyRowIds.length,
    });
  }, [activeWeekDate, dirtyRowIds.length, onHeaderSummaryChange, rows.length]);

  const editableFieldMap = useMemo(
    () => new Map(editableFields.map((field) => [field.key, field])),
    [editableFields],
  );

  const gridColumns = useMemo<ColDef<WeeklyGridRow>[]>(
    () => [
      ...visibleColumns.map<ColDef<WeeklyGridRow>>((column) => ({
        ...getWeeklyColumnWidth(column.key),
        field: column.key,
        headerName: column.label,
        type:
          MONEY_KEYS.has(column.key) || PERCENT_KEYS.has(column.key) || column.key === "exchange_rate"
            ? "rightAligned"
            : undefined,
        sortable: false,
        editable: () => editableFieldMap.has(column.key) && !readOnlyKeys.has(column.key),
        valueParser: (params) =>
          parseWeeklyCellValue(
            editableFieldMap.get(column.key),
            params.newValue,
            params.oldValue,
          ),
        cellClass: (params) => {
          const classes = getColumnCellClass(column.key, params.value as number | string);
          const editableClasses =
            editableFieldMap.has(column.key) && !readOnlyKeys.has(column.key)
              ? dirtyCellKeys.includes(buildDirtyCellKey(params.data?.id ?? "", column.key))
                ? " weeklyEditableCell weeklyDirtyCell"
                : " weeklyEditableCell"
              : "";
          return `${classes}${editableClasses}`.trim();
        },
        cellRenderer: (params: { data?: WeeklyGridRow; value?: unknown }) => (
          <span title={column.key === "memo" ? String(params.value ?? "") : undefined}>
            {params.data ? formatCellValue(params.data, column.key) : "-"}
          </span>
        ),
      })),
    ],
    [dirtyCellKeys, editableFieldMap, readOnlyKeys, visibleColumns],
  );

  function handleAggregate() {
    startTransition(async () => {
      try {
        setError(null);
        const response = await fetch("/api/weekly", { method: "POST" });
        const payload = (await response.json()) as { week_date?: string; error?: string };
        if (!response.ok) {
          throw new Error(payload.error ?? "이번주 데이터 집계에 실패했습니다.");
        }
        await load({ silent: true });
        toast.success(`[자산-주별] ${payload.week_date ?? activeWeekDate} 집계 완료`);
      } catch (aggregateError) {
        setError(aggregateError instanceof Error ? aggregateError.message : "이번주 데이터 집계에 실패했습니다.");
      }
    });
  }

  function handleSave() {
    if (dirtyRowIds.length === 0) {
      return;
    }

    startTransition(async () => {
      try {
        setError(null);
        const dirtyRows = rows.filter((row) => dirtyRowIds.includes(row.week_date));
        for (const row of dirtyRows) {
          const response = await fetch("/api/weekly", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              week_date: row.week_date,
              ...Object.fromEntries(
                editableFields
                  .filter((field) => !readOnlyKeys.has(field.key))
                  .map((field) => [field.key, row[field.key as keyof WeeklyRow]]),
              ),
            }),
          });
          const payload = (await response.json()) as { error?: string };
          if (!response.ok) {
            throw new Error(payload.error ?? "주별 데이터 저장에 실패했습니다.");
          }
        }
        await load({ silent: true });
        toast.success("[자산-주별] 변경사항 저장 완료");
      } catch (saveError) {
        setError(saveError instanceof Error ? saveError.message : "주별 데이터 저장에 실패했습니다.");
      }
    });
  }

  return (
    <div className="appPageStack appPageStackFill">
      {error ? (
        <div className="appBannerStack">
          {error ? <div className="bannerError">{error}</div> : null}
        </div>
      ) : null}

      <section className="appSection appSectionFill">
        <div className="card appCard appTableCardFill">
          <div className="card-header">
            <div className="appMainHeader">
              <div className="appMainHeaderLeft weeklyMainHeaderLeft">
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">보기 방식</span>
                  <div className="appSegmentedToggle" role="group" aria-label="주별 보기 방식">
                    <button
                      type="button"
                      className={viewMode === "core" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setViewMode("core")}
                    >
                      핵심만 보기
                    </button>
                    <button
                      type="button"
                      className={viewMode === "full" ? "btn appSegmentedToggleButton is-active" : "btn appSegmentedToggleButton"}
                      onClick={() => setViewMode("full")}
                    >
                      전체 보기
                    </button>
                  </div>
                </label>
                <label className="appLabeledField">
                  <span className="appLabeledFieldLabel">집계</span>
                  <button
                    type="button"
                    className="btn btn-success btn-sm px-3 fw-bold"
                    onClick={handleAggregate}
                    disabled={isPending}
                  >
                    {isPending ? "집계 중..." : "이번주 데이터 집계"}
                  </button>
                </label>
              </div>
            </div>
          </div>
          <div className="card-header appActionHeader bg-light-subtle border-top">
            <div className="appActionHeaderInner">
              <button
                type="button"
                className="btn btn-success btn-sm px-3 fw-bold d-flex align-items-center gap-1"
                onClick={handleSave}
                disabled={isPending || dirtyRowIds.length === 0}
              >
                <IconCheck size={16} />
                <span>저장</span>
              </button>
            </div>
          </div>
          <div className="card-body appCardBodyTight appTableCardBodyFill">
            <AppAgGrid<WeeklyGridRow>
              rowData={gridRows}
              columnDefs={gridColumns}
              loading={loading || isPending}
              minHeight="100%"
              className="weeklyAgGrid"
              theme={weeklyGridTheme}
              getRowClass={(params) => (params.data?.week_date === activeWeekDate ? "tableRowSelected" : "")}
              gridOptions={{
                suppressMovableColumns: true,
                onCellValueChanged: (params: {
                  data?: WeeklyGridRow;
                  colDef: { field?: string };
                  newValue?: unknown;
                  oldValue?: unknown;
                }) => {
                  if (!params.data || !params.colDef.field || params.newValue === params.oldValue) {
                    return;
                  }
                  const rowId = params.data.id;
                  const field = params.colDef.field;
                  setRows((current) =>
                    current.map((row) =>
                      row.week_date === rowId
                        ? {
                            ...row,
                            [field]: params.data?.[field as keyof WeeklyGridRow] ?? row[field as keyof WeeklyRow],
                          }
                        : row,
                    ),
                  );
                  setDirtyRowIds((prev) => (prev.includes(rowId) ? prev : [...prev, rowId]));
                  const dirtyCellKey = buildDirtyCellKey(rowId, field);
                  setDirtyCellKeys((prev) => (prev.includes(dirtyCellKey) ? prev : [...prev, dirtyCellKey]));
                },
              }}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
