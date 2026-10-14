// POC5-12 — VIX 최신성 안내 문구(정비 큐 · 「ETF 비교하기」 · 「개발·실험용」 공통).
//
// 판정은 PC 서버가 미국 장 마감 기준으로 만든 `vix.freshness` 만 읽는다(화면에서 미국 마감 ·
// 서머타임을 다시 계산하지 않음). 국내 시장 기준일(KODEX200)과 비교하지 않는다.
// - fresh · one_weekday_behind: 안내 없음(평일 1일 차이는 공개 지연 · 평일 휴장 여유)
// - update_check: 'VIX 자료 업데이트 확인 필요(기준일 D)'
// - date_check · 판정 필드 없음: 'VIX 기준일 확인 필요(기준일 D)' — 옛 규칙으로 추측하지 않는다.
// VIX 자료 자체가 없는 경우(unavailable)는 각 화면의 기존 항목이 그대로 다룬다.

import type { MarketRiskVix } from "./api/market";

export interface VixFreshnessNotice {
  state: "update_check" | "date_check";
  text: string;
  reason: string;
}

export function vixFreshnessNotice(
  vix: MarketRiskVix | null | undefined,
): VixFreshnessNotice | null {
  if (!vix || vix.availability !== "available") return null;
  const state = vix.freshness?.state;
  if (state === "fresh" || state === "one_weekday_behind") return null;
  const dateLabel = vix.as_of_date ? `기준일 ${vix.as_of_date}` : "기준일 확인 불가";
  const compare = vix.freshness?.compare_date ?? null;
  if (state === "update_check") {
    const gap =
      typeof vix.freshness?.weekdays_behind === "number"
        ? ` · 그 사이 평일 ${vix.freshness.weekdays_behind}일`
        : "";
    return {
      state,
      text: `VIX 자료 업데이트 확인 필요(${dateLabel})`,
      reason:
        `시장 불안 지표(VIX) 저장 기준일 ${vix.as_of_date ?? "확인 불가"} · ` +
        `미국 장 마감 기준 비교일 ${compare ?? "확인 불가"}${gap}. ` +
        "미국 평일 휴장은 따로 거르지 않으므로 장애로 단정하지 않고 업데이트를 확인할 대상으로 봅니다.",
    };
  }
  return {
    state: "date_check",
    text: `VIX 기준일 확인 필요(${dateLabel})`,
    reason:
      `시장 불안 지표(VIX) 저장 기준일(${vix.as_of_date ?? "확인 불가"})을 ` +
      `미국 장 마감 기준 비교일(${compare ?? "확인 불가"})과 맞춰 볼 수 없습니다.`,
  };
}
