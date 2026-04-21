"use client";

import { useEffect, useState, useTransition } from "react";
import { iconSetQuartzBold, themeQuartz } from "ag-grid-community";
import type { CellStyle, ColDef } from "ag-grid-community";

import { AppAgGrid } from "../components/AppAgGrid";
import { useToast } from "../components/ToastProvider";

type SystemSummaryRow = {
  category: string;
  count: number;
  target: string;
};

type SystemScheduleRow = {
  key: string;
  job: string;
  target: string;
  cadence: string;
  command: string;
};

type SystemJobKey =
  | "cache_refresh"
  | "market_hours_analysis"
  | "metadata_updater"
  | "asset_summary";

type SystemResponse = {
  summary_rows?: SystemSummaryRow[];
  schedule_rows?: SystemScheduleRow[];
  schedule_note?: string;
  running_jobs?: string[];
  error?: string;
};

type SystemSummaryGridRow = SystemSummaryRow & { id: string };
type SystemScheduleGridRow = SystemScheduleRow & {
  id: string;
  running: boolean;
  anyRunning: boolean;
};

function formatCount(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
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

const summaryColumns: ColDef<SystemSummaryGridRow>[] = [
  {
    field: "count",
    headerName: "순서",
    minWidth: 72,
    width: 72,
    type: "rightAligned",
    cellRenderer: (params: { value: number }) => formatCount(params.value),
  },
  { field: "target", headerName: "계좌 ID", minWidth: 200, flex: 1 },
  { field: "category", headerName: "계좌", minWidth: 200, flex: 1.2 },
];

const scheduleColumns: ColDef<SystemScheduleGridRow>[] = [
  { field: "job", headerName: "작업", minWidth: 140, width: 180 },
  { field: "target", headerName: "대상", minWidth: 120, width: 140 },
  { field: "cadence", headerName: "자동 주기", minWidth: 140, width: 180 },
  {
    field: "command",
    headerName: "실행 명령 (클릭하여 백그라운드 실행)",
    minWidth: 320,
    flex: 1.6,
    cellStyle: (params): CellStyle => {
      const row = params.data as SystemScheduleGridRow | undefined;
      if (!row) return { cursor: "default" };
      if (row.running) return { cursor: "default", backgroundColor: "#fff8e1" };
      if (row.anyRunning) return { cursor: "not-allowed", color: "#9aa4b1" };
      return { cursor: "pointer" };
    },
    tooltipValueGetter: (params) => {
      const row = params.data as SystemScheduleGridRow | undefined;
      if (!row) return "";
      if (row.running) return "현재 실행 중입니다.";
      if (row.anyRunning) return "다른 배치가 실행 중이라 시작할 수 없습니다.";
      return `클릭 시 "${row.job}" 배치를 백그라운드로 실행합니다.`;
    },
    cellRenderer: (params: { value: string; data?: SystemScheduleGridRow }) => (
      <span className="appCodeText">
        {params.data?.running ? "▶ 실행 중... " : ""}
        {params.value}
      </span>
    ),
  },
];

export function SystemManager({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: { accountCount: number; scheduleCount: number }) => void;
}) {
  const [summaryRows, setSummaryRows] = useState<SystemSummaryRow[]>([]);
  const [scheduleRows, setScheduleRows] = useState<SystemScheduleRow[]>([]);
  const [scheduleNote, setScheduleNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningJobs, setRunningJobs] = useState<string[]>([]);
  const [, startTransition] = useTransition();
  const toast = useToast();
  const runningSet = new Set(runningJobs);
  const anyRunning = runningSet.size > 0;
  const summaryGridRows: SystemSummaryGridRow[] = summaryRows.map((row) => ({ ...row, id: row.category }));
  const scheduleGridRows: SystemScheduleGridRow[] = scheduleRows.map((row) => ({
    ...row,
    id: row.key,
    running: runningSet.has(row.key),
    anyRunning,
  }));

  useEffect(() => {
    onHeaderSummaryChange?.({
      accountCount: summaryRows.length,
      scheduleCount: scheduleRows.length,
    });
  }, [onHeaderSummaryChange, scheduleRows.length, summaryRows.length]);

  useEffect(() => {
    let alive = true;

    async function load(initial: boolean) {
      try {
        if (initial) setLoading(true);
        const response = await fetch("/api/system", { cache: "no-store" });
        const payload = (await response.json()) as SystemResponse;
        if (!response.ok) {
          throw new Error(payload.error ?? "시스템정보 데이터를 불러오지 못했습니다.");
        }

        if (!alive) return;

        setSummaryRows(payload.summary_rows ?? []);
        setScheduleRows(payload.schedule_rows ?? []);
        setScheduleNote(payload.schedule_note ?? "");
        setRunningJobs(payload.running_jobs ?? []);
        if (initial) setError(null);
      } catch (loadError) {
        if (alive && initial) {
          setError(loadError instanceof Error ? loadError.message : "시스템정보 데이터를 불러오지 못했습니다.");
        }
      } finally {
        if (alive && initial) setLoading(false);
      }
    }

    load(true);
    const intervalId = window.setInterval(() => load(false), 3000);
    return () => {
      alive = false;
      window.clearInterval(intervalId);
    };
  }, []);

  function handleTriggerJob(action: SystemJobKey, label: string) {
    if (runningSet.has(action)) {
      // 이미 이 배치가 실행 중인 경우 — 조용히 무시 (표시만 확인하라는 의미)
      return;
    }
    if (anyRunning) {
      toast.error("다른 배치가 실행 중입니다. 완료 후 다시 시도해주세요.");
      return;
    }
    startTransition(async () => {
      setError(null);
      // 낙관적 UI: 즉시 running 표시 → 다음 폴링에서 서버 상태로 교체됨
      setRunningJobs((prev) => (prev.includes(action) ? prev : [...prev, action]));
      try {
        const response = await fetch("/api/system", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        });
        const payload = (await response.json()) as { message?: string; error?: string };
        if (!response.ok) {
          // 트리거 실패 시 낙관적 표시 롤백
          setRunningJobs((prev) => prev.filter((k) => k !== action));
          throw new Error(payload.error ?? "배치 실행에 실패했습니다.");
        }
        toast.success(String(payload.message ?? `[배치] ${label} 실행 시작`));
      } catch (actionError) {
        const msg = actionError instanceof Error ? actionError.message : "배치 실행에 실패했습니다.";
        setError(msg);
        toast.error(msg);
      }
    });
  }

  return (
    <div className="appPageStack">
      {error ? (
        <div className="appBannerStack">
          <div className="bannerError">{error}</div>
        </div>
      ) : null}

      <section className="appSection">
        <div className="card appCard">
          <div className="card-header">
            <div className="appMainHeader">
              <div className="appMainHeaderLeft">
                <span className="appHeaderMetricValue">배치</span>
              </div>
            </div>
          </div>
          <div className="card-body appCardBodyTight">
            <AppAgGrid
              rowData={scheduleGridRows}
              columnDefs={scheduleColumns}
              loading={loading}
              minHeight="18rem"
              theme={appGridTheme}
              gridOptions={{
                suppressMovableColumns: true,
                domLayout: "autoHeight",
                onCellClicked: (event) => {
                  if (event.colDef.field !== "command") return;
                  const row = event.data as SystemScheduleGridRow | undefined;
                  if (!row?.key) return;
                  handleTriggerJob(row.key as SystemJobKey, row.job);
                },
              }}
            />
            {scheduleNote ? <div className="tableFooterMeta">{scheduleNote}</div> : null}
          </div>
        </div>
      </section>

      <section className="appSection">
        <div className="card appCard">
          <div className="card-header">
            <div className="appMainHeader">
              <div className="appMainHeaderLeft">
                <span className="appHeaderMetricValue">계좌 요약</span>
              </div>
            </div>
          </div>
          <div className="card-body appCardBodyTight">
            <AppAgGrid
              rowData={summaryGridRows}
              columnDefs={summaryColumns}
              loading={loading}
              minHeight="18rem"
              theme={appGridTheme}
              gridOptions={{ suppressMovableColumns: true, domLayout: "autoHeight" }}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
