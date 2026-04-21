"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { WeeklyManager } from "./WeeklyManager";

type WeeklyHeaderSummary = {
  activeWeekDate: string;
  rowCount: number;
  dirtyCount: number;
};

const DEFAULT_SUMMARY: WeeklyHeaderSummary = {
  activeWeekDate: "-",
  rowCount: 0,
  dirtyCount: 0,
};

export function WeeklyPageClient() {
  const [summary, setSummary] = useState<WeeklyHeaderSummary>(DEFAULT_SUMMARY);

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>활성 주차:</span>
          <span className="appHeaderMetricValue">{summary.activeWeekDate || "-"}</span>
        </div>
        <div className="appHeaderMetric">
          <span>행:</span>
          <span className="appHeaderMetricValue">{new Intl.NumberFormat("ko-KR").format(summary.rowCount)}</span>
        </div>
        {summary.dirtyCount > 0 ? (
          <div className="appHeaderMetric">
            <span>변경:</span>
            <span className="appHeaderMetricValue is-success">
              {new Intl.NumberFormat("ko-KR").format(summary.dirtyCount)}개
            </span>
          </div>
        ) : null}
      </div>
    ),
    [summary],
  );

  return (
    <PageFrame title="주별" fullHeight fullWidth titleRight={titleRight}>
      <WeeklyManager onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
