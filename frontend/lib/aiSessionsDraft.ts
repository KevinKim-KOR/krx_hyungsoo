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
// 2026-05-27 — constituent_snapshot / overlap_snapshot 추가로 schema v3 승격.
// 새로고침 시 draft 가 사라지는 정책상 in-place 호환 불필요. key 변경으로 모호함 차단.
const STORAGE_KEY = "krx_alertor.ai_sessions.draft.v3";

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
  // 2026-05-27 — ETF Constituents & Overlap snapshots. ETF Exposure → AI Sessions
  // 흐름에서 채워진다. Market Discovery 직접 흐름에서는 비어있음 (null).
  constituent_snapshot?: Record<string, unknown> | null;
  overlap_snapshot?: Record<string, unknown> | null;
  // 2026-06-01 — Market Discovery Evidence Closeout 1차. 단기 흐름 + 데이터 품질
  // 스냅샷. Market Discovery 시점에 응답의 candidates 에서 추출.
  short_term_momentum_snapshot?: Record<string, unknown> | null;
  data_quality_snapshot?: Record<string, unknown> | null;
  // 2026-06-11 — ML Baseline Evidence Draft Integration. 저장된 ML baseline v0
  // 룩백 report snapshot. 기본은 null (Market Discovery 직접 흐름에서는 비어있음).
  // AISessionsCreateTab 가 GET /ml/baseline-v0/latest 결과를 옮겨 담는다.
  ml_baseline_evidence_snapshot?: Record<string, unknown> | null;
  // POC5-24 — 저장 시 source_screen(없으면 기존 "market_discovery"). 「보유와 비교」 판단 근거 미리보기에서
  // 넘긴 초안은 "holdings_compare_preview"(선택 종목 1건 · 질문 = 미리보기 원문 · ML 자동 보충 안 함).
  source_screen?: string;
}

export const SELECTED_PREVIEW_SOURCE = "holdings_compare_preview";

// POC5-24 — 선택 근거 모드 = 화면 값 · 후보 1건 · selected_preview 객체가 모두 맞을 때만(백엔드
// app/decision_selected_preview.is_selected_preview_record 와 같은 판정 · 일반 후보 1건 기록은 아님).
export function isSelectedPreviewRecord(
  sourceScreen: string | undefined | null,
  candidates: DecisionCandidateSnapshot[] | undefined | null,
): boolean {
  return (
    sourceScreen === SELECTED_PREVIEW_SOURCE &&
    Array.isArray(candidates) &&
    candidates.length === 1 &&
    candidates[0]?.selected_preview != null &&
    typeof candidates[0].selected_preview === "object"
  );
}

// 지금 남아 있는 초안이 어디서 왔는지 한 줄(덮어쓰기 확인용 · 판단 없음) + 넘긴 시각(KST · 없으면 생략).
// 「ETF 구성종목」 초안은 구성종목 · 중복 칸을 늘 넣는다(분석 전이면 null) · 「요즘 잘 오르는 ETF」 초안에는 그 칸이 없다.
export function describeDraftOrigin(d: AISessionsDraft): string {
  let origin: string;
  if (isSelectedPreviewRecord(d.source_screen, d.candidate_snapshot)) {
    const c = d.candidate_snapshot[0];
    origin = `「보유와 비교」 판단 근거 미리보기 · ${c?.name ?? c?.ticker ?? "-"}`;
  } else if ("constituent_snapshot" in d || "overlap_snapshot" in d) {
    origin = `「ETF 구성종목」 · 후보 ${d.candidate_snapshot.length}개`;
  } else {
    origin = `「요즘 잘 오르는 ETF」 · 후보 ${d.candidate_snapshot.length}개`;
  }
  const at = typeof d.draft_created_at === "string" && d.draft_created_at.trim();
  return at ? `${origin} · ${kstDateTimeLabel(d.draft_created_at)}` : origin;
}

// 시간대가 없는 값은 KST 로 본다(백엔드 app/decision_selected_preview.kst_date_of 와 같은 규칙) ·
// 앞뒤 공백 무시 · 날짜만이면 그날 00:00 KST · 'YYYY-MM-DD HH:MM' 사이 공백은 T 로.
function withKstOffset(raw: string): string {
  let s = raw.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return `${s}T00:00:00+09:00`;
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(s)) s = s.replace(" ", "T");
  if (/T\d{2}:\d{2}/.test(s) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(s)) return `${s}+09:00`;
  return s;
}

// POC5-24 — 시각을 Asia/Seoul(KST) 기준으로 읽는다(브라우저 시간대와 무관 · 해석 못 하면 null).
function kstParts(iso: string | null | undefined): Record<string, string> | null {
  if (!iso) return null;
  const d = new Date(withKstOffset(iso));
  if (Number.isNaN(d.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d);
  return Object.fromEntries(parts.map((x) => [x.type, x.value]));
}

// 'YYYY-MM-DD HH:MM'(KST) · 해석 못 하면 원문 그대로(저장 문자열은 바꾸지 않는다).
export function kstDateTimeLabel(iso: string): string {
  const p = kstParts(iso);
  return p ? `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}` : iso;
}

// 'YYYY-MM-DD'(KST) · 해석 못 하면 null.
export function kstDateOf(iso: string | null | undefined): string | null {
  const p = kstParts(iso);
  return p ? `${p.year}-${p.month}-${p.day}` : null;
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
