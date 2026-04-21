"use client";

import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";
import type {
  CellClassParams,
  ColDef,
  GridOptions,
  RowClassParams,
  Theme,
} from "ag-grid-community";

ModuleRegistry.registerModules([AllCommunityModule]);

type AppAgGridProps<TData> = {
  rowData: TData[];
  columnDefs: ColDef<TData>[];
  loading?: boolean;
  minHeight?: string | number;
  className?: string;
  getRowClass?: (params: RowClassParams<TData>) => string;
  getCellClass?: (params: CellClassParams<TData>) => string | string[] | undefined;
  gridOptions?: GridOptions<TData>;
  theme?: Theme | "legacy";
};

export function AppAgGrid<TData>({
  rowData,
  columnDefs,
  loading = false,
  minHeight = "24rem",
  className,
  getRowClass,
  gridOptions,
  theme = "legacy",
}: AppAgGridProps<TData>) {
  const themeClassName = theme === "legacy" ? "ag-theme-quartz appAgGridThemeLegacy" : "appAgGridTheme";
  return (
    <div className={className ? `appAgGridWrap ${className}` : "appAgGridWrap"} style={{ minHeight, height: "100%" }}>
      <div className={themeClassName}>
        <AgGridReact<TData>
          rowData={rowData}
          columnDefs={columnDefs}
          loading={loading}
          theme={theme}
          enableCellTextSelection
          ensureDomOrder
          suppressCellFocus
          rowSelection={{ mode: "singleRow", checkboxes: false, enableClickSelection: false }}
          animateRows={false}
          defaultColDef={{
            sortable: true,
            resizable: true,
          }}
          getRowClass={getRowClass}
          {...gridOptions}
        />
      </div>
    </div>
  );
}
