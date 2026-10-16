// POC5-16 — 가격 흔들림(변동성) 표시 문구 · 도움말(설계 V1 §4 · §5 · PLAN 판정 2026-10-16 §3 · §4 · §5).
// 받은 응답(backend app/pc_price_volatility.py)만 쓴다. 새 계산 · 조회 없음.
import type {
  PriceVolatilityEvidence,
  PriceVolatilityReason,
  PriceVolatilityWindow,
} from "@/lib/api";

export const COMPARISON_TEXT: Record<"higher" | "lower" | "same", string> = {
  higher: "직전보다 커짐",
  lower: "직전보다 작아짐",
  same: "직전과 같음",
};

// 판정 §4 — 경계는 '가격 기준 변화'가 아니라 '가격 기준 확인 필요'(change 누락 · 출처 재전환도 포함).
export const REASON_TEXT: Record<PriceVolatilityReason, string> = {
  insufficient_history: "자료 부족",
  invalid_price: "가격 확인 필요",
  basis_unconfirmed: "가격 기준 확인 필요",
};

export function cellValue(
  w: PriceVolatilityWindow | null,
  reason: PriceVolatilityReason | null,
): string {
  if (w) return `${w.value_pct.toFixed(2)}%`;
  return reason ? REASON_TEXT[reason] : "확인 불가";
}

// 값을 보이지 않는 상태(칸 · 비교 · 기간 줄 없음).
export function hidesValues(ev: PriceVolatilityEvidence): boolean {
  return ev.status === "date_mismatch" || ev.status === "reference_unavailable";
}

// 짧은 사유 — 지금 해당할 때만 · 접혀 있어도 보인다(판정 §5 · PLAN Q4 (a)).
// 판정 §3 — 거른 날짜(E)는 '최근 저장일'이 아니라 '마지막 유효 가격일'.
export function volatilityNote(
  ev: PriceVolatilityEvidence,
  flowDate: string | null,
): string | null {
  if (ev.status === "reference_unavailable") {
    return "PC 가격 흐름 기준일을 확인할 수 없어 값을 보이지 않습니다.";
  }
  if (ev.status === "date_mismatch") {
    return `이 종목의 마지막 유효 가격일(${ev.end_date ?? "확인 불가"})이 PC 가격 흐름 기준일(${flowDate ?? "확인 불가"})과 달라 값을 보이지 않습니다.`;
  }
  if (ev.status === "unavailable") return "최근 · 직전 20구간 모두 계산하지 못했습니다.";
  if (ev.status === "recent_only") return "직전 20구간은 계산하지 못해 비교하지 않습니다.";
  if (ev.status === "previous_only") return "최근 20구간은 계산하지 못해 비교하지 않습니다.";
  return null;
}

export function periodLine(ev: PriceVolatilityEvidence): string {
  const parts: string[] = [];
  if (ev.recent) parts.push(`최근 ${ev.recent.start_date} ~ ${ev.recent.end_date}`);
  if (ev.previous) parts.push(`직전 ${ev.previous.start_date} ~ ${ev.previous.end_date}`);
  // 두 기간 모두 없으면 실제 확인 가능한 날짜(마지막 유효 가격일)를 보인다(설계 §4).
  if (!parts.length && ev.end_date) parts.push(`마지막 유효 가격일 ${ev.end_date}`);
  return [...parts, "PC 저장 종가"].join(" · ");
}

export const VOL_HELP_MEANING =
  "위아래 가격 변화가 얼마나 들쑥날쑥했는지 보여 줍니다. 하락 폭을 뜻하는 값은 아닙니다. ‘직전보다 커짐’은 최근 20구간의 흔들림이 그 앞 20구간보다 크다는 뜻입니다.";
export const VOL_HELP_BASIS =
  "PC 저장 종가로 만든 20개 가격 변화(다음 종가 ÷ 직전 종가 − 1)의 표준편차(분모 20 · 연율화하지 않음)를 %로 보입니다. 직전 20구간은 그 바로 앞 20개 변화이고, 두 구간은 경계 종가 하나만 같이 씁니다. 비교와 ‘같음’은 소수 둘째 자리 값 기준입니다. 실시간 시세가 아닌 PC 저장 종가 기준입니다.";
export const VOL_HELP_INSUFFICIENT =
  "저장 종가가 부족한 기간은 계산하지 않았습니다(최근은 21개, 직전까지는 41개 필요).";
export const VOL_HELP_INVALID =
  "기간 안 저장 종가에 확인이 필요한 값이 있어 그 기간은 계산하지 않았습니다. 다른 날 가격으로 채우지 않습니다.";
export const VOL_HELP_BASIS_UNCONFIRMED =
  "기간 안에 가격 연속성을 확인할 수 없는 날(저장된 변화율과 종가 변화 불일치 · 변화율 누락 · 출처 재전환)이 있어 그 기간은 계산하지 않았습니다. 실제 가격 기준이 바뀌었다고 단정하는 뜻은 아닙니다.";
export const VOL_HELP_DATE =
  "이 종목의 마지막 유효 가격일이 PC 가격 흐름 기준일과 달라, 기준일이 다른 기간의 값을 현재 비교값처럼 보이지 않게 값을 숨겼습니다.";
export const VOL_HELP_REF =
  "PC 가격 흐름 기준일을 확인할 수 없어, 최신 자료인지 알 수 없는 값을 숨겼습니다.";

// 순서 = 뜻 → 계산 기준 → 지금 해당하는 제한만(설계 §5).
export function volatilityHelp(ev: PriceVolatilityEvidence): string[] {
  const out = [VOL_HELP_MEANING, VOL_HELP_BASIS];
  if (ev.status === "reference_unavailable") return [...out, VOL_HELP_REF];
  if (ev.status === "date_mismatch") return [...out, VOL_HELP_DATE];
  const reasons = [ev.recent_reason, ev.previous_reason];
  if (reasons.includes("insufficient_history")) out.push(VOL_HELP_INSUFFICIENT);
  if (reasons.includes("invalid_price")) out.push(VOL_HELP_INVALID);
  if (reasons.includes("basis_unconfirmed")) out.push(VOL_HELP_BASIS_UNCONFIRMED);
  return out;
}
