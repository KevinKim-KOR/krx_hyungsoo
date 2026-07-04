// POST /decision-draft/preview — 선택 ETF 임시 판단 근거 미리보기 (2026-07-03).
// 저장 없는 임시 요청. 응답은 프론트엔드 메모리에만 유지.

import { request } from "./core";

export type DecisionDraftTargetKind = "holding" | "candidate";

export interface DecisionDraftPreviewEvidenceAsOf {
  target_as_of_date: string | null;
  kodex200_as_of_date: string | null;
  vix_as_of_date: string | null;
}

export interface DecisionDraftPreviewResponse {
  status: "ok" | "error";
  target_kind?: DecisionDraftTargetKind | null;
  ticker?: string | null;
  preview_text?: string | null;
  evidence_as_of?: DecisionDraftPreviewEvidenceAsOf | null;
  message?: string | null;
}

export async function postDecisionDraftPreview(
  target_kind: DecisionDraftTargetKind,
  ticker: string,
): Promise<DecisionDraftPreviewResponse> {
  return request<DecisionDraftPreviewResponse>(
    "POST",
    "/decision-draft/preview",
    { target_kind, ticker },
  );
}
