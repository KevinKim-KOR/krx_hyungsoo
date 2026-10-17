// POC5-19 — 근거 묶음 · 세부 흐름 창 머리의 짧은 표시(받은 근거 응답 · 기존 문구만 · 새 계산 없음).
// 세부 흐름 창 첫 부분 = 세 근거의 실제 기준일 + 핵심 값 한 줄씩(개정 2026-10-17 §2).
import type { HoldingsMarketEvidenceItem, PriceBasis } from "@/lib/api";
import { NO_VOLUME_TEXT, pastVolumeNote, volumeCells } from "@/lib/storedVolume";
import { declineDetailText } from "./declineSummary";
import type { RiskEvidenceRow } from "./helpers";
import { COMPARISON_TEXT, cellValue, hidesValues, volatilityNote } from "./priceVolatility";

export function pct(v: number | null): string {
  return v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
export function pctp(v: number | null): string {
  return v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%p`;
}

// 하락 구간 짧은 값: 구간 이름 / '해당 없음' / 판정하지 않는 사유(기존 문장).
export function bandShortText(row: RiskEvidenceRow, basis: PriceBasis | null): string {
  const band = row.decline_band;
  if (!band?.judgeable) return declineDetailText(row, basis);
  return band.state ? (band.label ?? "") : "해당 없음";
}

export interface StripLine {
  key: "price" | "volume" | "volatility";
  title: string;
  date: string;
  text: string;
  note: string | null;
}

export function evidenceStrip(
  row: RiskEvidenceRow,
  item: HoldingsMarketEvidenceItem | null,
  basis: PriceBasis | null,
): StripLine[] {
  const flowDate = basis?.reference_date ?? null;
  const stale = row.price_dates?.comparison === "date_mismatch";
  const price = stale
    ? declineDetailText(row, basis)
    : [
        `5일 ${pct(row.return_5d_pct)}`,
        `20일 ${pct(row.return_20d_pct)}`,
        `KODEX200 대비 20일 ${pctp(row.excess_vs_kodex200_20d_pctp)}`,
        `하락 구간 ${bandShortText(row, basis)}`,
      ].join(" · ");
  const sv = item?.stored_volume;
  const cells = sv && sv.status !== "no_price_data" ? volumeCells(sv) : null;
  const volume = cells ? `${cells[1].value} · ${cells[3].label} ${cells[3].value}` : NO_VOLUME_TEXT;
  const pv = item?.price_volatility;
  const vol = !pv
    ? "확인 불가"
    : hidesValues(pv)
      ? (volatilityNote(pv, flowDate) ?? "확인 불가")
      : [
          `최근 20구간 ${cellValue(pv.recent, pv.recent_reason)}`,
          `직전 20구간 ${cellValue(pv.previous, pv.previous_reason)}`,
          pv.comparison ? COMPARISON_TEXT[pv.comparison] : volatilityNote(pv, flowDate),
        ]
          .filter(Boolean)
          .join(" · ");
  return [
    { key: "price", title: "가격 흐름", date: row.price_dates?.end_date ?? "확인 불가", text: price, note: null },
    {
      key: "volume",
      title: "거래량",
      date: sv?.asof_date ?? "확인 불가",
      text: volume,
      note: sv ? pastVolumeNote(sv, flowDate) : null,
    },
    { key: "volatility", title: "가격 흔들림", date: pv?.end_date ?? "확인 불가", text: vol, note: null },
  ];
}
