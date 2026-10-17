// POC5-19 — 저장 거래량 흐름 문구 · 도움말(설계 V1 §3 · 개정 판정 §4 · 차트 읽기 개정 2026-10-17 §4). 받은 응답만 쓴다.
import type { VolumeTrendEvidence } from "@/lib/api";

export function missingNote(ev: VolumeTrendEvidence): string | null {
  if (!ev.missing_count) return null;
  return `거래량이 비어 있거나 확인이 필요한 날 ${ev.missing_count}개는 빈칸으로 두었습니다(0으로 채우지 않음).`;
}

// 거래량 묶음 · 세부 흐름 ? 의 기간 · 단위 문단 — 판정 Q1: 가격 흐름 · 거래량 칸과 같은, 종가가 확인된 저장일.
export const TREND_HELP_BASIS =
  "세부 흐름의 종가 · 거래량 차트는 기준일을 포함한 최근 최대 20개 저장일(가격 흐름 · 거래량 칸과 같은, 종가가 확인된 저장일)을 같은 가로축으로 씁니다. 종가는 원, 거래량은 주입니다. 20거래일이 빠짐없이 이어졌는지는 따로 확인하지 않습니다. 차트에서 날짜를 고르면(마우스를 올리거나 누르기 · 좌우 화살표) 차트 위 줄에 그날 값을 보입니다.";
// 세부 흐름 창 — 가격은 날짜로 찾는다(개정 2026-10-17 §4) · 평균 · 배수는 기준일 하나의 값.
export const TREND_HELP_PRICE_MATCH =
  "종가 선은 이미 받은 PC 저장 종가에서 같은 날짜의 값을 찾아 그립니다. 그날 종가가 없으면 '종가 자료 없음'으로 두고 선을 잇지 않습니다. 평균 대비 배수는 기준일 하나의 값이며, 고른 과거 날짜의 평균이 아닙니다.";
export const TREND_HELP_SHORT = "저장된 날이 20개보다 적어 있는 만큼만 보입니다.";
export const TREND_HELP_MISSING =
  "거래량이 비어 있거나 확인이 필요한 날은 빈칸으로 두었습니다. 0으로 채우지 않으며, 저장된 0은 0으로 보입니다.";

// 지금 해당하는 제한만(설계 §2 '뜻 → 기간 · 단위 → 지금 해당하는 제한').
export function trendLimits(ev: VolumeTrendEvidence | null | undefined): string[] {
  if (!ev) return [];
  const out: string[] = [];
  if (ev.points.length > 0 && ev.points.length < 20) out.push(TREND_HELP_SHORT);
  if (ev.missing_count) out.push(TREND_HELP_MISSING);
  return out;
}
