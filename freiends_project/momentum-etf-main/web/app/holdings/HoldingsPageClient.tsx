"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { HoldingsManager } from "./HoldingsManager";

type HoldingsHeaderSummary = {
  accountCount: number;
  holdingCount: number;
  totalValuation: number;
};

const DEFAULT_SUMMARY: HoldingsHeaderSummary = {
  accountCount: 0,
  holdingCount: 0,
  totalValuation: 0,
};

function formatKrw(value: number): string {
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

export function HoldingsPageClient() {
  const [summary, setSummary] = useState<HoldingsHeaderSummary>(DEFAULT_SUMMARY);

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>계좌:</span>
          <span className="appHeaderMetricValue">{summary.accountCount}개</span>
        </div>
        <div className="appHeaderMetric">
          <span>종목:</span>
          <span className="appHeaderMetricValue">{summary.holdingCount}개</span>
        </div>
        <div className="appHeaderMetric">
          <span>평가금:</span>
          <span className="appHeaderMetricValue">{formatKrw(summary.totalValuation)}</span>
        </div>
      </div>
    ),
    [summary],
  );

  return (
    <PageFrame title="보유종목" fullHeight fullWidth titleRight={titleRight}>
      <HoldingsManager onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
