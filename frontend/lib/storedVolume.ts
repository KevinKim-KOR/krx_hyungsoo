// POC5-09 — 저장 거래량 확인 근거 표시(「확인 근거」 종목 상세 · 「오늘의 투자 점검」 KODEX200 공용).
// 계산은 backend(app/stored_volume_evidence.py)가 원래 숫자로 하고, 여기서는 표시할 때만
// 반올림한다(평균 · 배수 소수 둘째 자리 · 거래량 단위 = 주). 저장된 거래량 자체는 줄이지 않는다(POC5-19 검증 r1).
// 값을 지어내지 않는다.
import type { StoredVolumeEvidence } from "@/lib/api";
import { fmtExact } from "./chartScale";

export const VOLUME_HELP =
  "기준일 거래량을 그 앞 20개 저장일 평균과 비교한 배수입니다. 거래가 많고 적음만 보여 주며, 오르내림의 원인이나 매매 신호가 아닙니다.";
export const KODEX200_VOLUME_HELP =
  VOLUME_HELP + " KODEX 200 ETF 한 종목의 거래량이며 코스피 시장 전체 거래량이 아닙니다.";
export const NO_VOLUME_TEXT = "거래량 자료 없음";

const TWO = { minimumFractionDigits: 2, maximumFractionDigits: 2 } as const;

export type VolumeCell = { label: string; value: string };

// 네 칸: 기준일 · 거래량 · 직전 20개 저장일 평균 · 평균 대비.
// 배수 사유 우선순위(판정 §9-2) = backend ratio_status: 기준일 거래량 없음 → 자료 부족 → 평균 0.
export function volumeCells(ev: StoredVolumeEvidence): VolumeCell[] {
  // 저장된 거래량은 줄이지 않는다(POC5-19 검증 r1 — 0 이 아닌 소수가 '0주'로 보이지 않게 · 평균 · 배수는 소수 둘째 자리 그대로).
  const volume = ev.volume != null ? `${fmtExact(ev.volume)}주` : "자료 없음";
  const avg =
    ev.avg_status === "ok" && ev.avg_prev20 != null
      ? `${ev.avg_prev20.toLocaleString("ko-KR", TWO)}주`
      : `자료 부족 (${ev.valid_count}/${ev.window_size})`;
  const RATIO_TEXT: Record<StoredVolumeEvidence["ratio_status"], string> = {
    ok: ev.ratio != null ? `${ev.ratio.toLocaleString("ko-KR", TWO)}배` : "자료 없음",
    volume_missing: "자료 없음",
    avg_insufficient: "자료 부족",
    avg_zero: "계산 불가",
  };
  return [
    { label: "기준일", value: ev.asof_date ?? "자료 없음" },
    { label: "거래량", value: volume },
    { label: `직전 ${ev.window_size}개 저장일 평균`, value: avg },
    { label: "평균 대비", value: RATIO_TEXT[ev.ratio_status] },
  ];
}

// 설명 줄 두 부분: 출처 · 비교 구간(시작 ~ 끝 · 유효 N/20).
export function volumeSourceParts(ev: StoredVolumeEvidence): [string, string] {
  const source = `출처 ${ev.source ?? "확인 불가"}`;
  const window =
    ev.window_date_count > 0 && ev.window_start_date && ev.window_end_date
      ? `비교 구간 ${ev.window_start_date} ~ ${ev.window_end_date}`
      : "비교 구간 없음";
  return [source, `${window} · 유효 ${ev.valid_count}/${ev.window_size}`];
}

// 거래량 기준일이 PC 비교 기준일과 다르면 구분한다(판정 §9-4-4). 더 이르면 과거 저장 자료,
// 더 늦으면 그 사실만 적는다(날짜 문자열 YYYY-MM-DD 비교).
export function pastVolumeNote(
  ev: StoredVolumeEvidence,
  referenceDate: string | null | undefined,
): string | null {
  if (!referenceDate || !ev.asof_date || ev.asof_date === referenceDate) return null;
  if (ev.asof_date < referenceDate) {
    return `과거 저장 자료 · PC 비교 기준일은 ${referenceDate}`;
  }
  return `PC 비교 기준일(${referenceDate})보다 늦은 날짜의 자료`;
}
