"use client";

import { useEffect, useMemo, useState } from "react";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { ColDef, GridOptions, RowClassParams } from "ag-grid-community";

import { AppAgGrid } from "../components/AppAgGrid";

type SnapshotAccountItem = {
  account_id: string;
  account_name: string;
  order: number;
  total_assets: number;
  total_principal: number;
  cash_balance: number;
  valuation_krw: number;
};

type SnapshotListItem = {
  id: string;
  snapshot_date: string;
  total_assets: number;
  total_principal: number;
  cash_balance: number;
  valuation_krw: number;
  accounts: SnapshotAccountItem[];
};

type SnapshotListResponse = {
  snapshots?: SnapshotListItem[];
  error?: string;
};

type SnapshotMainRow = SnapshotListItem & { id: string; rowType: "main" };
type SnapshotDetailRow = {
  id: string;
  rowType: "detail";
  parentId: string;
  snapshot_date: string;
  accounts: SnapshotAccountItem[];
};
type SnapshotGridRow = SnapshotMainRow | SnapshotDetailRow;

function formatKrw(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(Math.round(value));
}

function formatSnapshotDate(value: string): string {
  const text = String(value || "").trim();
  if (!text) {
    return "-";
  }
  const date = new Date(`${text}T00:00:00+09:00`);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  return `${text} (${weekdays[date.getDay()]})`;
}

function isDetailRow(row: SnapshotGridRow | undefined): row is SnapshotDetailRow {
  return row?.rowType === "detail";
}

function SnapshotDetailPanel(params: { data?: SnapshotGridRow }) {
  const data = params.data;
  if (!data || !isDetailRow(data)) {
    return null;
  }

  return (
    <div className="snapshotsDetailPanel">
      <div className="snapshotsDetailPanelHeader">
        <span className="tableMuted">계좌별 상세</span>
      </div>
      <div className="snapshotsDetailTableWrap">
        <table className="snapshotsDetailTable">
          <thead>
            <tr>
              <th>계좌</th>
              <th className="tableAlignRight">총 자산</th>
              <th className="tableAlignRight">원금</th>
              <th className="tableAlignRight">현금</th>
              <th className="tableAlignRight">평가액</th>
            </tr>
          </thead>
          <tbody>
            {data.accounts.map((account) => (
              <tr key={`${data.parentId}-${account.account_id}`}>
                <td>{account.account_name}</td>
                <td className="tableAlignRight">{formatKrw(account.total_assets)}</td>
                <td className="tableAlignRight">{formatKrw(account.total_principal)}</td>
                <td className="tableAlignRight">{formatKrw(account.cash_balance)}</td>
                <td className="tableAlignRight">{formatKrw(account.valuation_krw)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const appGridTheme = themeQuartz
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

export function SnapshotsManager({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: { snapshotCount: number; latestDate: string }) => void;
}) {
  const [snapshots, setSnapshots] = useState<SnapshotListItem[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch("/api/snapshots", { cache: "no-store" });
        const payload = (await response.json()) as SnapshotListResponse;
        if (!response.ok) {
          throw new Error(payload.error ?? "스냅샷 목록을 불러오지 못했습니다.");
        }

        if (!alive) {
          return;
        }

        const nextSnapshots = payload.snapshots ?? [];
        setSnapshots(nextSnapshots);
        setExpandedId((current) => current ?? nextSnapshots[0]?.id ?? null);
      } catch (loadError) {
        if (alive) {
          setError(loadError instanceof Error ? loadError.message : "스냅샷 목록을 불러오지 못했습니다.");
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      alive = false;
    };
  }, []);

  const listRows = useMemo<SnapshotGridRow[]>(
    () =>
      snapshots.flatMap((snapshot) => {
        const mainRow: SnapshotMainRow = { ...snapshot, id: snapshot.id, rowType: "main" };
        if (snapshot.id !== expandedId) {
          return [mainRow];
        }

        const detailRow: SnapshotDetailRow = {
          id: `${snapshot.id}__detail`,
          rowType: "detail",
          parentId: snapshot.id,
          snapshot_date: snapshot.snapshot_date,
          accounts: snapshot.accounts,
        };
        return [mainRow, detailRow];
      }),
    [expandedId, snapshots],
  );

  useEffect(() => {
    onHeaderSummaryChange?.({
      snapshotCount: snapshots.length,
      latestDate: snapshots[0]?.snapshot_date ?? "-",
    });
  }, [onHeaderSummaryChange, snapshots]);

  const listColumns = useMemo<ColDef<SnapshotGridRow>[]>(
    () => [
      {
        field: "snapshot_date",
        headerName: "날짜",
        minWidth: 220,
        flex: 1.1,
        cellRenderer: (params: { data?: SnapshotGridRow; value?: string }) => {
          const data = params.data;
          if (!data || isDetailRow(data)) {
            return "";
          }

          return (
            <div className="snapshotsExpandCell">
              <span className="snapshotsExpandIcon" aria-hidden="true">
                {data.id === expandedId ? "▾" : "▸"}
              </span>
              <span>{formatSnapshotDate(params.value ?? "")}</span>
            </div>
          );
        },
      },
      {
        field: "total_assets",
        headerName: "총 자산",
        minWidth: 120,
        flex: 1,
        type: "rightAligned",
        cellRenderer: (params: { data?: SnapshotGridRow; value: number }) =>
          params.data && !isDetailRow(params.data) ? formatKrw(params.value) : "",
      },
      {
        field: "total_principal",
        headerName: "원금",
        minWidth: 120,
        flex: 1,
        type: "rightAligned",
        cellRenderer: (params: { data?: SnapshotGridRow; value: number }) =>
          params.data && !isDetailRow(params.data) ? formatKrw(params.value) : "",
      },
      {
        field: "cash_balance",
        headerName: "현금",
        minWidth: 120,
        flex: 1,
        type: "rightAligned",
        cellRenderer: (params: { data?: SnapshotGridRow; value: number }) =>
          params.data && !isDetailRow(params.data) ? formatKrw(params.value) : "",
      },
      {
        field: "valuation_krw",
        headerName: "평가액",
        minWidth: 120,
        flex: 1,
        type: "rightAligned",
        cellRenderer: (params: { data?: SnapshotGridRow; value: number }) =>
          params.data && !isDetailRow(params.data) ? formatKrw(params.value) : "",
      },
    ],
    [expandedId],
  );

  const gridOptions = useMemo<GridOptions<SnapshotGridRow>>(
    () => ({
      suppressMovableColumns: true,
      domLayout: "autoHeight",
      isFullWidthRow: (params) => isDetailRow(params.rowNode.data),
      fullWidthCellRenderer: SnapshotDetailPanel,
      getRowHeight: (params) => {
        if (!isDetailRow(params.data)) {
          return 38;
        }
        return 58 + (params.data.accounts.length + 1) * 38;
      },
      onRowClicked: (params) => {
        const data = params.data;
        if (!data || isDetailRow(data)) {
          return;
        }
        setExpandedId((current) => (current === data.id ? null : data.id));
      },
    }),
    [],
  );

  return (
    <div className="appPageStack">
      {error ? (
        <div className="appBannerStack">
          <div className="bannerError">{error}</div>
        </div>
      ) : null}
      <section className="appSection">
        <div className="card appCard">
          <div className="card-body appCardBody">
            <div className="tableFooterMeta mb-2">날짜 row를 클릭하면 계좌별 상세가 펼쳐집니다.</div>
            <AppAgGrid
              rowData={listRows}
              columnDefs={listColumns}
              loading={loading}
              minHeight="22rem"
              theme={appGridTheme}
              getRowClass={(params: RowClassParams<SnapshotGridRow>) =>
                isDetailRow(params.data)
                  ? "snapshotsDetailFullRow"
                  : params.data?.id === expandedId
                    ? "tableRowSelected snapshotsExpandedMainRow"
                    : ""
              }
              gridOptions={gridOptions}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
