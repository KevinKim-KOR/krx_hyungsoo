// POC6-29 보완 R3(PLAN §9-3 · 목업 R3 · 보완 PLAN 판정 2026-11-12 '구현에서 확인할 세 가지' 3)
// — 「보유와 후보 비교」 기본 비교의 차이 줄(순수 함수 · 조회 없음).
// 보완 2차 S3(PLAN §10-6 · 목업 S3 · S 판정 Q-S6) — 1 · 3개월에 최근 5 · 20구간 · 고점 대비를 같은 규칙으로 넓혔다.
//
// 차이(%p)는 아래가 모두 맞을 때만 적는다.
//   1) 두 쪽 값이 모두 있음(상세 응답 값 · 시작일 · 끝일)
//      - 기간 수익률(1 · 3개월 · 최근 5 · 20구간) = 상태 ok 일 때만 값이 있다(기간 다름은 서버가 값을 비운다).
//      - 고점 대비 = 서버가 KODEX 200 창과 달라도(기간 다름) 그 종목 20저장일 창 값을 준다(행 상세와 같은 값).
//   2) 실제 시작일과 끝일이 둘 다 같음
//      - 기간 수익률 = 두 쪽 모두 ok 이고 시작 · 끝일이 같음(기존 그대로).
//      - 고점 대비 = 두 종목의 20저장일 창 시작일 · 끝일이 같음(Q-S6).
//   3) 끝일 가격 상태가 두 쪽 모두 확인됨(장중 저장 · 마감 뒤 저장 · 그 가격 날짜 = 기간 끝일)이고 서로 같음
// 둘 다 장중 저장값이면 '잠정 비교'로 적는다. 하나라도 어긋나면 비교하지 않고 그 사유를,
// 수치 · 상태를 확인할 수 없으면 자료 상태를 적는다. 0 으로 채우지 않는다 · 새 점수 · 등급 없음.
// 판정 순서: 상세 수치 없음 → 값 없음 → 기간 다름 → 가격 시점 확인 필요 → 가격 상태 다름 → 차이.
// 차이 = 화면에 보이는 소수 둘째 자리 값끼리 뺀 값(후보 − 보유). 고점 대비 값은 0 이하라
// 후보 − 보유 > 0 이면 후보 하락폭이 작다.
//
// 사유 낱말(저장 이력 부족 등)은 화면의 같은 사유 함수를 받아 쓴다(lib 는 화면 파일을 가져오지 않는다).

import type { PriceStateCode } from "@/lib/api/etfCompare";
import type { DetailPeriod, EtfDetailItem } from "@/lib/api/etfDetail";
import { md } from "@/lib/etfCompare";

export type DiffPeriodKey = "m1" | "m3" | "w5" | "w20" | "drawdown";

export const DIFF_LABEL: Record<DiffPeriodKey, string> = {
  m1: "1개월",
  m3: "3개월",
  w5: "최근 5구간",
  w20: "최근 20구간",
  drawdown: "고점 대비",
};

// 비교에 쓰는 칸 — 기간 수익률(DetailPeriod) · 최근 고점 대비(DetailDrawdown) 공통 부분.
export type DiffPeriod = Pick<DetailPeriod, "status" | "value" | "start" | "end" | "reason">;

export interface DiffSide {
  period: DiffPeriod;
  // 그 종목 끝일 행의 가격 상태 · 가격 날짜(상세 응답 end_price).
  priceState: PriceStateCode | null;
  priceDate: string | null;
}

// compared = 차이를 적음 · provisional = 둘 다 장중 저장값이라 잠정 비교 · not_compared = 비교하지 않음(사유 · 자료 상태).
export type DiffKind = "compared" | "provisional" | "not_compared";

export interface DiffLine {
  kind: DiffKind;
  text: string;
  // 후보 − 보유(%p · 화면에 보이는 소수 둘째 자리 값끼리). 비교하지 않으면 null(0 아님).
  diffPctp: number | null;
}

const STATE_WORD: Record<"intraday" | "after_close", string> = { intraday: "장중", after_close: "마감 뒤" };

export function diffSideOf(it: EtfDetailItem | null | undefined, key: DiffPeriodKey): DiffSide | null {
  if (!it) return null;
  const period: DiffPeriod = key === "drawdown" ? it.drawdown : it[key];
  return { period, priceState: it.end_price?.state ?? null, priceDate: it.end_price?.date ?? null };
}

// 날짜 — 끝일과 연도가 다르면 연도까지(행 상세와 같은 표기).
function dateText(d: string | null | undefined, ref?: string | null): string {
  if (!d) return "—";
  return !ref || d.slice(0, 4) === ref.slice(0, 4) ? md(d) : d;
}

function rangeText(key: DiffPeriodKey, p: DiffPeriod): string {
  return `${key === "drawdown" ? "20저장일 " : ""}${dateText(p.start, p.end)} → ${dateText(p.end)}`;
}

function hasValue(p: DiffPeriod): boolean {
  return p.value != null && Number.isFinite(p.value) && !!p.start && !!p.end;
}

// 비교에 쓸 수 있는 값인가 — 기간 수익률은 ok 일 때만 · 고점 대비는 자료 없음이 아니면(그 종목 창 값).
function usable(key: DiffPeriodKey, p: DiffPeriod): boolean {
  if (key === "drawdown") return p.status !== "missing" && hasValue(p);
  return p.status === "ok" && hasValue(p);
}

// 값 없음으로 적을 쪽 — 기간 수익률의 '기간 다름'은 값이 비어 있어도 기간 사유로 적는다(기존 그대로).
function isMissing(key: DiffPeriodKey, p: DiffPeriod): boolean {
  if (key === "drawdown") return !usable(key, p);
  return p.status !== "period_differs" && !usable(key, p);
}

function samePeriod(key: DiffPeriodKey, h: DiffPeriod, c: DiffPeriod): boolean {
  const sameDates = h.start === c.start && h.end === c.end;
  if (key === "drawdown") return sameDates;
  return h.status === "ok" && c.status === "ok" && sameDates;
}

// 확인된 가격 상태 — 장중 · 마감 뒤이고 그 가격 날짜가 이 기간 끝일일 때만(아니면 확인 필요).
function confirmedState(s: DiffSide): "intraday" | "after_close" | null {
  if (s.priceState !== "intraday" && s.priceState !== "after_close") return null;
  return s.priceDate && s.priceDate === s.period.end ? s.priceState : null;
}

// 화면에 보이는 값(소수 둘째 자리)끼리 뺀다 — 보이는 두 숫자와 차이 줄이 서로 맞게.
function hundredths(v: number): number {
  return Math.round(Number(v.toFixed(2)) * 100);
}

function resultText(key: DiffPeriodKey, d: number): string {
  const size = `${(Math.abs(d) / 100).toFixed(2)}%p`;
  if (key === "drawdown") return d === 0 ? "하락폭 같음" : `후보 하락폭이 ${size} ${d > 0 ? "작음" : "큼"}`;
  return d === 0 ? "같음" : `${d > 0 ? "후보" : "보유"}가 ${size} 높음`;
}

export function diffLine(
  key: DiffPeriodKey,
  hold: DiffSide | null,
  cand: DiffSide | null,
  reasonText: (code: string | null) => string,
): DiffLine {
  const label = DIFF_LABEL[key];
  const notCompared = (detail: string): DiffLine => ({ kind: "not_compared", text: `${label}: 비교하지 않음 — ${detail}`, diffPctp: null });

  if (!hold || !cand) {
    return notCompared(
      [hold ? null : "보유 상세 수치 없음", cand ? null : "후보 상세 수치 없음"].filter((x): x is string => !!x).join(" / "),
    );
  }
  const sides: [string, DiffSide][] = [
    ["보유", hold],
    ["후보", cand],
  ];

  const missing = sides.filter(([, s]) => isMissing(key, s.period));
  if (missing.length > 0) {
    return notCompared(missing.map(([who, s]) => `${who} 값 없음 · ${reasonText(s.period.reason)}`).join(" / "));
  }

  const h = hold.period;
  const c = cand.period;
  if (!samePeriod(key, h, c)) {
    return {
      kind: "not_compared",
      text: `${label}: 기간이 달라 비교하지 않음(보유 ${rangeText(key, h)} · 후보 ${rangeText(key, c)})`,
      diffPctp: null,
    };
  }

  const range = rangeText(key, h);
  const hs = confirmedState(hold);
  const cs = confirmedState(cand);
  if (!hs || !cs) {
    const who = sides.filter(([, s]) => !confirmedState(s)).map(([w]) => w);
    return { kind: "not_compared", text: `${label}(${range}): 비교하지 않음 — 가격 시점 확인 필요(${who.join(" · ")})`, diffPctp: null };
  }
  if (hs !== cs) {
    return {
      kind: "not_compared",
      text: `${label}(${range}): 가격 상태가 달라 비교하지 않음(보유 ${STATE_WORD[hs]} · 후보 ${STATE_WORD[cs]})`,
      diffPctp: null,
    };
  }

  const d = hundredths(c.value as number) - hundredths(h.value as number);
  const provisional = hs === "intraday";
  return {
    kind: provisional ? "provisional" : "compared",
    text: `${provisional ? "잠정 비교 · " : ""}${label}(${range} · 같은 기간): ${resultText(key, d)}${provisional ? "(두 쪽 모두 장중 저장값)" : ""}`,
    diffPctp: d / 100,
  };
}
