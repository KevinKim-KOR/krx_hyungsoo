// POC5-UI-04 — 종목 가격 차트 기간 선택(설계 docs/ai_design/POC5/POC5-19_RESULT_DECISION_AND_PRICE_CHART_PERIOD_DESIGN_2026-10-17.md §3).
// 기준 D = 받은 종목 가격 시계열의 마지막 저장 날짜(오늘 · 시장 최신일 아님). 3 · 6개월 · 1년 = D 에서 달력 개월을 뺀 날 ~ D
// (그 달에 같은 날이 없으면 그 달 말일 · 경계 포함). 날짜는 'YYYY-MM-DD' 문자열로만 계산한다(시각대 변환 없음).
// 원본 배열은 바꾸지 않고, 그릴 배열만 새로 잘라 돌려준다(공유 조회 결과 · 세부 흐름 창의 날짜 대응 자료 보존).

export type PricePeriod = "3M" | "6M" | "1Y" | "ALL";

export const PRICE_PERIODS: ReadonlyArray<[PricePeriod, string]> = [
  ["3M", "3개월"],
  ["6M", "6개월"],
  ["1Y", "1년"],
  ["ALL", "전체"],
];

export const DEFAULT_PRICE_PERIOD: PricePeriod = "3M";

const MONTHS: Record<Exclude<PricePeriod, "ALL">, number> = { "3M": 3, "6M": 6, "1Y": 12 };

const pad = (n: number) => String(n).padStart(2, "0");

// D 에서 달력 n개월 전. 그 달에 같은 날이 없으면 그 달 말일(예: 05-31 의 3개월 전 = 02-28 · 윤년 02-29).
export function minusMonths(d: string, n: number): string {
  const y = Number(d.slice(0, 4));
  const m = Number(d.slice(5, 7));
  const day = Number(d.slice(8, 10));
  const total = y * 12 + (m - 1) - n;
  const ty = Math.floor(total / 12);
  const tm = (total % 12) + 1;
  const last = new Date(Date.UTC(ty, tm, 0)).getUTCDate(); // tm 월의 말일(UTC · 시각대 영향 없음)
  return `${ty}-${pad(tm)}-${pad(Math.min(day, last))}`;
}

export function periodStart(end: string, p: PricePeriod): string | null {
  return p === "ALL" ? null : minusMonths(end, MONTHS[p]);
}

// 날짜 오름차순 시계열에서 기간 창만(경계 포함). '전체'와 빈 시계열은 원본 그대로.
export function periodWindow<T extends { date: string }>(series: readonly T[], p: PricePeriod): T[] {
  if (series.length === 0) return [];
  const end = series[series.length - 1].date;
  const start = periodStart(end, p);
  if (start === null) return series.slice();
  return series.filter((x) => x.date >= start && x.date <= end);
}
