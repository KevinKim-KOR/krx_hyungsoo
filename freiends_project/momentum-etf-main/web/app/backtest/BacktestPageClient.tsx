"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { BacktestBuilder } from "./BacktestBuilder";

type BacktestHeaderSummary = {
  marketLabel: string;
  groupCount: number;
  totalWeight: number;
  resultLabel: string;
};

const DEFAULT_SUMMARY: BacktestHeaderSummary = {
  marketLabel: "한국",
  groupCount: 0,
  totalWeight: 0,
  resultLabel: "준비 중",
};

export function BacktestPageClient() {
  const [summary, setSummary] = useState<BacktestHeaderSummary>(DEFAULT_SUMMARY);

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>마켓:</span>
          <span className="appHeaderMetricValue">{summary.marketLabel}</span>
        </div>
        <div className="appHeaderMetric">
          <span>그룹:</span>
          <span className="appHeaderMetricValue">{new Intl.NumberFormat("ko-KR").format(summary.groupCount)}개</span>
        </div>
        <div className="appHeaderMetric">
          <span>총 비중:</span>
          <span className="appHeaderMetricValue">{summary.totalWeight}%</span>
        </div>
        <div className="appHeaderMetric">
          <span>상태:</span>
          <span className="appHeaderMetricValue">{summary.resultLabel}</span>
        </div>
      </div>
    ),
    [summary],
  );

  return (
    <PageFrame title="백테스트" titleRight={titleRight}>
      <BacktestBuilder onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
