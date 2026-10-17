// POC5-19 개정(차트 읽기 · 2026-10-17) — 차트 세 곳(KOSPI · 종목 가격 · 거래량)의 공통 눈금 계산.
// 값 눈금: 실제 입력값을 덮는 '보기 좋은' 간격 3~5개(최솟값 · 최댓값이 눈금 범위 안에 드러남).
// 거래량은 0 에서 시작. 일정한 값 · 전부 0 이어도 범위가 0 이 되지 않게 한다.
// 날짜 눈금: 저장일 순서의 양끝 + 중간(폭에 맞춰 개수). 첫 눈금과 연도가 바뀌는 눈금은 연도까지.

export type ChartUnit = "원" | "pt" | "주";

export interface ValueAxis {
  lo: number;
  hi: number;
  ticks: number[];
}

function niceStep(raw: number): number {
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const m = raw / p;
  const k = m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10;
  return k * p;
}

const clean = (v: number) => Number(v.toPrecision(12));

export function valueAxis(
  values: number[],
  opts: { zeroBase?: boolean; integer?: boolean; target?: number } = {},
): ValueAxis {
  const finite = values.filter((v) => Number.isFinite(v));
  let min = finite.length ? Math.min(...finite) : 0;
  let max = finite.length ? Math.max(...finite) : 0;
  if (opts.zeroBase) min = Math.min(0, min);
  if (max === min) {
    if (max === 0) max = 1;
    else {
      const pad = Math.abs(max) * 0.01;
      min -= pad;
      max += pad;
    }
  }
  let step = niceStep((max - min) / (opts.target ?? 3));
  if (opts.integer) step = Math.max(step, 1);
  const lo = opts.zeroBase ? 0 : clean(Math.floor(min / step) * step);
  const hi = clean(Math.ceil(max / step) * step);
  const ticks: number[] = [];
  for (let k = 0; lo + k * step <= hi + step / 2; k++) ticks.push(clean(lo + k * step));
  return { lo, hi: hi > lo ? hi : lo + step, ticks };
}

export function dateTickIndices(n: number, count = 5): number[] {
  if (n <= 0) return [];
  if (n <= count) return Array.from({ length: n }, (_, i) => i);
  const out: number[] = [];
  for (let k = 0; k < count; k++) {
    const i = Math.round((k * (n - 1)) / (count - 1));
    if (!out.includes(i)) out.push(i);
  }
  return out;
}

export function dateTickLabels(dates: string[], idx: number[]): string[] {
  let prevYear: string | null = null;
  return idx.map((i) => {
    const d = dates[i];
    const y = d.slice(0, 4);
    const label = prevYear === null || y !== prevYear ? d : d.slice(5);
    prevYear = y;
    return label;
  });
}

const trim = (s: string) => s.replace(/\.0$/, "");

// 축 눈금(짧게) — 거래량은 만 · 억 단위로 줄인다. 단위는 늘 붙인다.
export function fmtTick(v: number, unit: ChartUnit): string {
  if (unit === "주") {
    if (v >= 1e8) return `${trim((v / 1e8).toFixed(1))}억주`;
    if (v >= 1e4) return `${trim((v / 1e4).toFixed(1))}만주`;
    return `${v.toLocaleString("ko-KR")}주`;
  }
  return `${v.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}${unit}`;
}

// 저장된 원래 값을 줄이지 않고 보인다(차트 고른 값 줄 · 거래량 칸 공통 · POC5-19 검증 r1).
// 정수는 그대로, 소수는 여섯째 자리까지, 1 보다 작은 0 아닌 값은 유효 숫자 6개 — 0 이 아닌 값이 '0'으로 보여
// 저장된 0 과 구분되지 않는 일이 없게 한다(반올림 · 정수화 금지).
export function fmtExact(v: number, minFrac = 0): string {
  if (v !== 0 && Math.abs(v) < 1) {
    return v.toLocaleString("ko-KR", { maximumSignificantDigits: 6 });
  }
  return v.toLocaleString("ko-KR", {
    minimumFractionDigits: minFrac,
    maximumFractionDigits: Math.max(6, minFrac),
  });
}

// 고른 날의 실제 값(충분한 정밀도 · 줄이지 않음 · 코스피는 소수 둘째 자리까지는 늘 보임).
export function fmtValue(v: number, unit: ChartUnit): string {
  return `${fmtExact(v, unit === "pt" ? 2 : 0)}${unit}`;
}
