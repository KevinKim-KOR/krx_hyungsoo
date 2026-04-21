"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { SnapshotsManager } from "./SnapshotsManager";

type SnapshotsHeaderSummary = {
  snapshotCount: number;
  latestDate: string;
};

const DEFAULT_SUMMARY: SnapshotsHeaderSummary = {
  snapshotCount: 0,
  latestDate: "-",
};

export function SnapshotsPageClient() {
  const [summary, setSummary] = useState<SnapshotsHeaderSummary>(DEFAULT_SUMMARY);

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>최신:</span>
          <span className="appHeaderMetricValue">{summary.latestDate}</span>
        </div>
        <div className="appHeaderMetric">
          <span>총 날짜:</span>
          <span className="appHeaderMetricValue">{new Intl.NumberFormat("ko-KR").format(summary.snapshotCount)}개</span>
        </div>
      </div>
    ),
    [summary],
  );

  return (
    <PageFrame title="스냅샷" titleRight={titleRight}>
      <SnapshotsManager onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
