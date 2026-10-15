// POC5-13 — 시장 국면 + 보유 'PC 최근 20저장일 하락 구간' 요약 조립(받은 두 응답만 · 새 조회 0).
// 「확인 근거」 요약 블록과 「오늘의 투자 점검」 보유 칸 띠가 같은 함수를 쓴다.
// - 종목 수 = ticker 기준(같은 종목 여러 계좌 = 1종목).
// - 비중 = 정상 GET /holdings/enriched 를 기존 종목 합산 함수(aggregateHoldingsByTicker)로 합친
//   평가 비중 원값의 합. 근거 응답의 평가금액은 쓰지 않는다(판정 §7 '평가 비중').
// - 구간 판정은 backend(app/pc_price_basis.py · OCI classify_decline)가 한다. 여기서 다시 판정하지 않는다.
import type { HoldingsMarketEvidenceResponse, PriceBasis } from "@/lib/api";
import { regimeLabelKo } from "../today/todayHelpers";
import type { RiskEvidenceRow } from "./helpers";

export const DECLINE_ORDER = ["D10_PLUS", "D8_10", "D5_8"] as const;
export type DeclineState = (typeof DECLINE_ORDER)[number];
export const DECLINE_SHORT: Record<DeclineState, string> = {
  D10_PLUS: "10% 이상",
  D8_10: "8~10%",
  D5_8: "5~8%",
};
export const PARTIAL_EVAL_TEXT = "확인된 평가금액 기준 · 일부 평가 자료 미확인";

export interface DeclineSummary {
  total: number; // 종목 수
  judgeable: number; // 구간 판정 가능 종목 수
  inBand: number; // 세 구간 중 하나에 든 종목 수
  inBandShare: number | null; // 보유 평가 비중 원값(%) · null = 확인 불가
  bands: { state: DeclineState; count: number; share: number | null }[];
  evalPartial: boolean; // 평가금액 합산값이 비어 있는 종목이 있음
  regime: string | null; // 시장 국면 문구(날짜 없음 · 판정 §7 '날짜')
  flowDate: string | null; // PC 가격 흐름 기준일(price_basis.reference_date)
}

// 평가 비중 원값 합. 평가금액이 하나도 없으면(분모 0 포함) 확인 불가 — 0% 로 채우지 않는다.
// 그 묶음의 종목이 모두 평가 미확인이어도 확인 불가다(미확인 평가금액을 0 으로 보이지 않음).
function shareOf(rows: RiskEvidenceRow[], anyWeight: boolean): number | null {
  if (!anyWeight) return null;
  if (rows.length > 0 && rows.every((r) => r.market_weight_pct === null)) return null;
  return rows.reduce((a, r) => a + (r.market_weight_pct ?? 0), 0);
}

function regimeText(evidence: HoldingsMarketEvidenceResponse): string | null {
  const mp = evidence.judgment_summary?.market_position as
    | {
        available?: boolean;
        regime_code?: string | null;
        regime_label?: string | null;
        regime_streak_days?: number | null;
        regime_streak_at_least?: boolean;
      }
    | null
    | undefined;
  if (!mp?.available) return null;
  const streak =
    typeof mp.regime_streak_days === "number"
      ? ` · ${mp.regime_streak_days}거래일째${mp.regime_streak_at_least ? " 이상" : ""}`
      : "";
  return `${regimeLabelKo(mp.regime_code, mp.regime_label)}${streak}`;
}

export function buildDeclineSummary(
  rows: RiskEvidenceRow[],
  evidence: HoldingsMarketEvidenceResponse,
): DeclineSummary {
  const anyWeight = rows.some((r) => r.market_weight_pct !== null);
  const inBandRows = rows.filter((r) => r.decline_band?.state);
  return {
    total: rows.length,
    judgeable: rows.filter((r) => r.decline_band?.judgeable).length,
    inBand: inBandRows.length,
    inBandShare: shareOf(inBandRows, anyWeight),
    bands: DECLINE_ORDER.map((st) => {
      const rs = rows.filter((r) => r.decline_band?.state === st);
      return { state: st, count: rs.length, share: shareOf(rs, anyWeight) };
    }),
    evalPartial: rows.some((r) => r.eval_amount === null),
    regime: regimeText(evidence),
    flowDate: evidence.price_basis?.reference_date ?? null,
  };
}

export const fmtShare = (v: number | null): string =>
  v === null ? "확인 불가" : `${v.toFixed(1)}%`;

// 상세의 'PC 20저장일 하락 구간' 줄 — 실제 기간 · 판정에 쓴 값 · 판정하지 않은 이유.
// 비교 기간 사유는 이 줄의 20저장일 기간이 KODEX200 20일 기간과 다를 때만 붙인다(5 · 10일만 다른 종목은
// 20일 KODEX200 대비 값이 남아 있음 — 그 사유는 '자료 확인 안내'가 보인다 · evidenceGuidance 와 같은 비교).
export function declineDetailText(r: RiskEvidenceRow, basis: PriceBasis | null): string {
  const b = r.decline_band;
  const pd = r.price_dates;
  const flowDate = basis?.reference_date ?? null;
  const period =
    pd?.start_date_20d && pd?.end_date ? ` · 기간 ${pd.start_date_20d} ~ ${pd.end_date}` : "";
  const wm =
    pd?.comparison === "window_mismatch" &&
    pd.start_date_20d !== (basis?.kodex200_start_date_20d ?? null)
      ? "(KODEX200 비교 기간과 달라 상대 비교는 비워 둠)"
      : "";
  if (b?.judgeable && typeof b.return_20d_pct_1dp === "number") {
    const v = `20저장일 변화 ${b.return_20d_pct_1dp.toFixed(1)}%(판정에 쓴 소수 첫째 자리 값)`;
    return b.state
      ? `${b.label} · ${v}${period}${wm} · PC 저장 종가`
      : `해당 없음 · ${v}${period}${wm}`;
  }
  if (r.evidence_conflict) {
    return "판정하지 않음 — 계좌 간 가격 흐름 값이 달라 확인이 필요합니다.";
  }
  if (b?.unjudged_reason === "date_mismatch") {
    return `판정하지 않음 — 이 종목의 최근 저장일(${pd?.end_date ?? "확인 불가"})이 PC 가격 흐름 기준일(${flowDate ?? "확인 불가"})과 다릅니다(자료 확인 필요).`;
  }
  if (b?.unjudged_reason === "insufficient_history") {
    return "판정하지 않음 — 이 종목이나 KODEX200 의 저장 종가가 21개보다 적어 20저장일 변화를 계산할 수 없습니다(자료 확인 필요).";
  }
  return "판정하지 않음 — 20저장일 변화 값을 확인할 수 없습니다(자료 확인 필요).";
}
