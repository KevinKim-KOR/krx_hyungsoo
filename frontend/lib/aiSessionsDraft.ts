// Context Bridge — Market Discovery → AI Sessions draft 전달 유틸.
//
// 정책 (지시문 §5.2):
// - 서버 draft 저장소를 만들지 않는다.
// - sessionStorage 사용 (브라우저 새로고침으로 사라져도 본 STEP 에서 허용).
// - 영구 기록은 POST /decision/sessions 호출 후 decision_evidence.sqlite 에 저장.
//
// draft 는 "전달 중인 임시 컨텍스트" 의미. AI Sessions 의 새 기록 저장 탭에
// 도착하면 store 호출 후 명시 clear.

import type {
  DecisionCandidateSnapshot,
  DecisionFilters,
} from "./api";

// 2026-05-22 — market_context_snapshot 필드 추가로 schema v2 로 승격.
// v1 draft 는 새로고침되면 사라지고 본 STEP 의 sessionStorage 정책상 마이그레이션
// 불필요 — key 만 v2 로 바꿔 호환 모호함 차단.
const STORAGE_KEY = "krx_alertor.ai_sessions.draft.v2";

export interface AISessionsDraft {
  asof: string;
  filters: DecisionFilters;
  candidate_snapshot: DecisionCandidateSnapshot[];
  question_text: string;
  linked_market_refresh_id: string | null;
  // draft 생성 시각 — 디버깅 / 사용자에게 "언제 넘긴 후보냐" 안내용.
  draft_created_at: string;
  // 2026-05-22 — Market Regime & Benchmark Context. null 또는 빈 dict 허용.
  market_context_snapshot?: Record<string, unknown> | null;
}

function safeStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function saveAISessionsDraft(draft: AISessionsDraft): void {
  const s = safeStorage();
  if (!s) return;
  s.setItem(STORAGE_KEY, JSON.stringify(draft));
}

export function loadAISessionsDraft(): AISessionsDraft | null {
  const s = safeStorage();
  if (!s) return null;
  const raw = s.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as AISessionsDraft;
    // 필수 필드 누락 시 무시 (스키마 변경 호환).
    if (
      !parsed ||
      typeof parsed.asof !== "string" ||
      !Array.isArray(parsed.candidate_snapshot) ||
      !parsed.filters
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearAISessionsDraft(): void {
  const s = safeStorage();
  if (!s) return;
  s.removeItem(STORAGE_KEY);
}
