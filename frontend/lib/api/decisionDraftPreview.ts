// POST /decision-draft/preview — 선택 종목 판단 근거 미리보기 (2026-07-03 · POC5-23 2026-10-18).
// 저장 없는 임시 요청. 응답은 프론트엔드 메모리에만 유지.

import { request } from "./core";

export type DecisionDraftTargetKind = "holding" | "candidate";

// POC5-23 판정 Q1 (a) — 후보는 화면 목록 조건으로 같은 목록에서 찾는다(없으면 서버 기본 조건).
// POC6-29(판정 Q4-2) — list_source = "common_period" 면 그 화면의 공통 기간 목록(상 · 하위 30)에서 찾고,
//   화면이 본 쪽 · 선정 순위 · 실제 시작일 · 끝일 · 끝일 가격 시점을 서버가 지금 결과와 대조한다(다르면 다시 읽기 안내).
export type DecisionDraftScreen = "candidate_list" | "sector_summary" | "holding_candidate_compare" | "holdings";

export interface DecisionDraftListQuery {
  n?: number;
  basis?: string;
  order?: string;
  exclude_inverse?: boolean;
  exclude_leveraged?: boolean;
  exclude_synthetic?: boolean;
  exclude_futures?: boolean;
  list_source?: "common_period";
  screen?: DecisionDraftScreen;
  side?: "top" | "bottom";
  rank?: number;
  start_date?: string | null;
  end_date?: string | null;
  end_price_state?: string | null;
  // 화면이 본 선정 기간 수익률 — 같은 날 장중 재저장으로 가격만 바뀐 경우도 서버가 '목록이 바뀜'으로 안내.
  basis_value?: number | null;
}

// 보유 미리보기 — B 화면에서 열면 그 화면 조건(기간 · 제외)만 보낸다(후보 목록과의 관계를 그 조건 목록으로 확인 ·
// 판정 Q4-2 둘째 항목). 행 대조 칸(쪽 · 순위 · 날짜)은 후보에만.
function holdingScope(q: DecisionDraftListQuery | undefined): Partial<DecisionDraftListQuery> {
  if (!q || q.list_source !== "common_period") return {};
  const { list_source, screen, basis, exclude_inverse, exclude_leveraged, exclude_synthetic, exclude_futures } = q;
  return { list_source, screen, basis, exclude_inverse, exclude_leveraged, exclude_synthetic, exclude_futures };
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
  flowPeriod?: string, // POC6-01 — 시장 흐름 묶음 기간(화면에서 고른 값 · 없으면 서버 기본 6개월)
): Promise<DecisionDraftPreviewResponse> {
  return request<DecisionDraftPreviewResponse>("POST", "/decision-draft/preview", {
    target_kind,
    ticker,
    ...(target_kind === "candidate" ? listQuery ?? {} : holdingScope(listQuery)),
    ...(flowPeriod ? { flow_period: flowPeriod } : {}),
  });
}
