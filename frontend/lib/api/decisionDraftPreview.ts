// POST /decision-draft/preview — 선택 종목 판단 근거 미리보기 (2026-07-03 · POC5-23 2026-10-18).
// 저장 없는 임시 요청. 응답은 프론트엔드 메모리에만 유지.

import { request } from "./core";

export type DecisionDraftTargetKind = "holding" | "candidate";

// POC5-23 판정 Q1 (a) — 후보는 화면 목록 조건으로 같은 목록에서 찾는다(없으면 서버 기본 조건).
export interface DecisionDraftListQuery {
  n?: number;
  basis?: string;
  order?: string;
  exclude_inverse?: boolean;
  exclude_leveraged?: boolean;
  exclude_synthetic?: boolean;
  exclude_futures?: boolean;
}

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
  // POC5-23 — 생성 시각(KST · 선택 필드).
  generated_at?: string | null;
  message?: string | null;
}

export async function postDecisionDraftPreview(
  target_kind: DecisionDraftTargetKind,
  ticker: string,
  listQuery?: DecisionDraftListQuery,
): Promise<DecisionDraftPreviewResponse> {
  return request<DecisionDraftPreviewResponse>(
    "POST",
    "/decision-draft/preview",
    { target_kind, ticker, ...(target_kind === "candidate" ? listQuery ?? {} : {}) },
  );
}
