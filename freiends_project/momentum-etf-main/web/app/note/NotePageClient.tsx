"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { NoteManager } from "./NoteManager";

type NoteHeaderSummary = {
  accountLabel: string;
  saveLabel: string;
};

const DEFAULT_SUMMARY: NoteHeaderSummary = {
  accountLabel: "-",
  saveLabel: "아직 저장된 메모가 없습니다.",
};

export function NotePageClient() {
  const [summary, setSummary] = useState<NoteHeaderSummary>(DEFAULT_SUMMARY);

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>계좌:</span>
          <span className="appHeaderMetricValue">{summary.accountLabel}</span>
        </div>
        <div className="appHeaderMetric">
          <span>상태:</span>
          <span className="appHeaderMetricValue">{summary.saveLabel}</span>
        </div>
      </div>
    ),
    [summary],
  );

  return (
    <PageFrame title="계좌 메모" titleRight={titleRight}>
      <NoteManager onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
