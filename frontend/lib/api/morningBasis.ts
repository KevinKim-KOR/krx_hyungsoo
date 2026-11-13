// POC6-29 보완 2차(PLAN §10-1 · §10-5 · S 판정 Q-S4 · §3) — 아침 요약 기준(`GET /market/morning-basis` · 저장값만).
// 아침 요약 · 갱신 끝 줄 · 근거 접기 ③ 은 이 응답 하나로 준비 상태를 판단한다(화면 곳곳에서 따로 조합하지 않음).
import { request } from "./core";
import type { MarketContext } from "./marketEvidence";

export type MorningKey = "kospi" | "kodex200" | "flows" | "vix" | "usdkrw" | "wti";

export interface MorningAttempt {
  at: string; // KST ISO
  via: "full" | "prevday";
  status: string;
  text: string | null;
}

export interface MorningItem {
  key: MorningKey;
  label: string;
  required: boolean;
  stored_date: string | null;
  expected_date: string | null;
  met: boolean;
  // 국내 = fresh · late · check / VIX = fresh · one_weekday_behind · update_check · date_check / WTI = observed
  state: string;
  behind: number | null;
  source: string | null;
  received_at: string | null; // KST ISO
  reason: string | null; // 미충족 사유(확인된 결과만)
  last_attempt: MorningAttempt | null;
  basis_row?: { date: string; close: number; state: "intraday" | "after_close" | "unknown" } | null;
}

export interface MorningRegime {
  status: "ok" | "unconfirmed";
  basis_date: string | null; // 실제로 사용한 산출 기준일
  reason: string | null;
  context: MarketContext | null;
}

// 당일 판정(형수님 결정 2026-11-13 · 검증자 F8) — 저장된 KODEX 200 이력 전체로 기존 산식 + 그 판정이 쓴 끝 행의 저장 시점.
// 판정 값과 저장 시점이 서버의 같은 한 번 읽기에서 온다(따로 받은 가격 상세와 맞추지 않음).
export interface TodayRegime extends MorningRegime {
  basis_row: {
    date: string;
    close: number;
    state: "intraday" | "after_close" | "unknown";
    fetched_at_kst: string | null;
  } | null;
}

export interface MorningBasisResponse {
  status: "ok" | "invalid";
  message: string | null;
  today: string;
  expected_date: string | null;
  ready: boolean;
  missing: MorningKey[];
  items: MorningItem[];
  morning_regime: MorningRegime | null;
  // 칸 없음(옛 서버) · null(읽기 실패) = 화면이 시장 판정 응답의 판정 · 날짜만 쓴다(저장 시점 없음)
  today_regime?: TodayRegime | null;
  // 설계자 V3 D1 — 판정 점수 산식의 경계값(기존 판정 상수 그대로 · [?] 설명 문장이 읽음)
  score_rule?: { return_20d_pct: number; return_60d_pct: number; bull_min: number; bear_max: number } | null;
  full_refresh: { cooldown_remaining_seconds: number; next_available_at: string | null } | null;
}

export const MORNING_BASIS_KEY = "market:morning-basis";

export function fetchMorningBasis(): Promise<MorningBasisResponse> {
  return request<MorningBasisResponse>("GET", "/market/morning-basis");
}
