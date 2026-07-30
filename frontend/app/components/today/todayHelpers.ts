// POC3-01 오늘의 투자 점검 — 표시 헬퍼 + 상태 라벨.
//
// 설계서 §7(사용자 언어) · §4.4(상태 구분) · §9(가독성) 준수:
// - 내부 용어(후보/Evidence/Workbench/Unavailable/Pending)를 화면에 노출하지 않는다.
// - "0건 / 자료 없음 / 개발 중 / 업데이트 실패" 는 서로 다른 의미이므로 별도 상태로 둔다.
// - 임시 숫자로 빈칸을 채우지 않는다 (값 없음은 상태로 표현).

// 항목 상태 (설계서 §4.4 표). 화면 표현은 컴포넌트가 결정.
export type ItemState =
  | "available" // 기능·데이터 모두 제공 (실제 값 + 기준일)
  | "no_data" // 기능은 있으나 자료 없음
  | "stale" // 자료가 오래됨 (업데이트 필요)
  | "in_development" // 기능 자체 미구현 (개발 중)
  | "failed"; // 실행 실패

export const ITEM_STATE_LABEL: Record<ItemState, string> = {
  available: "",
  no_data: "자료 없음",
  stale: "업데이트 필요",
  in_development: "개발 중",
  failed: "업데이트 실패",
};

// 수익률/변화율 (소수 둘째, 부호 명시). 값 없음은 "-" (임시 숫자 아님).
export function fmtPct(v: number | null | undefined): string {
  if (v == null) return "-";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

// 지수/가격 (천 단위). 값 없음은 "-".
export function fmtIndex(v: number | null | undefined): string {
  if (v == null) return "-";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

// timestamp → 한국시간 가독. 순수 날짜(YYYY-MM-DD)는 그대로, ISO datetime 은 KST.
// raw ISO 원문을 화면에 노출하지 않는다 (파싱 불가 시 "확인 불가").
// 값 없음은 "-"(정상 위장) 가 아니라 "자료 없음" 으로 정직 표시 (AC-9 상태 구분).
export function fmtKstDate(s: string | null | undefined): string {
  if (!s) return "자료 없음";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const d = new Date(s);
  if (isNaN(d.getTime())) return "확인 불가";
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")} KST`;
}

// 국면 코드 → 사용자 표현. 벤치마크명은 별도 라벨에서 명시하므로 여기선 국면만.
export function regimeLabelKo(
  code: string | null | undefined,
  label: string | null | undefined,
): string {
  // 백엔드가 이미 한국어 라벨(상승장/보합장/하락장/판정불가)을 준다.
  if (label && label.trim()) return label;
  switch (code) {
    case "bull":
      return "상승장";
    case "bear":
      return "하락장";
    case "neutral":
      return "보합장";
    default:
      return "판정불가";
  }
}

// MA 기준선 대비 거리 문구 — "KODEX200 MA20 대비 +x.x%" (단일 "전환까지 거리" 금지).
// 값 결측은 "-" 가 아니라 "자료 없음" 으로 정직 표시 (B-1: 0/정상 위장 금지).
export function maDistanceText(
  which: "MA20" | "MA60",
  distancePct: number | null | undefined,
  position: "above" | "below" | null | undefined,
): string {
  if (distancePct == null) return `KODEX200 ${which} 대비 자료 없음`;
  const dir = position === "above" ? "위" : position === "below" ? "아래" : "";
  return `KODEX200 ${which} 대비 ${fmtPct(distancePct)}${dir ? ` (${dir})` : ""}`;
}
