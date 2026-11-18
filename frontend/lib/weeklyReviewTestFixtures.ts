// POC6-32 — 「주간 ETF 점검」 화면 시험 고정 응답(GET /weekly/etf-check 모양).
// 서버 조립 함수 출력 그대로(11/16 공개 시장 자료 · 합성 공통 시장 근거 · 합성 보유 사례 · V2 형식 합성 AI 답) — 만든 방법은 JSON 의 _note.
import raw from "./weeklyReviewTestFixtures.json";
import type { WeeklyReviewOk } from "./api/weeklyReview";

// 고른 ETF 없음 · 마지막 기록 없음(첫 사용)
export const WEEKLY_NONE = raw.none as unknown as WeeklyReviewOk;
// 476070 을 고름(합성 보유 겹침) · 마지막 기록 없음
export const WEEKLY_SELECTED = raw.selected as unknown as WeeklyReviewOk;
// 476070 을 고름 · 이 한 장에서 저장한 기록 1건(합성 답 3개)
export const WEEKLY_SAVED = raw.saved as unknown as WeeklyReviewOk;

export function weeklyFor(selected: string | null): WeeklyReviewOk {
  return selected ? WEEKLY_SELECTED : WEEKLY_NONE;
}
