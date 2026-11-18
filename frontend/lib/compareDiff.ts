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
// POC6-32 V2(PLAN §3-2 D4 · §9 I-6 · I-20) — 「보유와 후보 비교」 [비교 상세]는 위 규칙 앞에 지수 상태 조건을 하나 더 둔다
// (gatedDiffLine). 서버가 정한 지수 상태가 '같은 공식 기초지수'일 때만 위 규칙대로 차이를 적고, 그 밖(다른 지수 · 같은
// 계열 · 기준 미확인)이면 다섯 줄 모두 차이 요약을 쓰지 않고 지수 사유 + 위 규칙이 찾은 사유(값 없음 · 기간 다름 · 가격
// 시점 확인 필요 · 가격 상태 다름)를 함께 적는다. 위 규칙(diffLine)의 글 · 순서는 그대로다.
//
// 사유 낱말(저장 이력 부족 등)은 화면의 같은 사유 함수를 받아 쓴다(lib 는 화면 파일을 가져오지 않는다).

import type { PriceStateCode } from "@/lib/api/etfCompare";
import type { DetailPeriod, EtfDetailItem } from "@/lib/api/etfDetail";
import type { OfficialPairState } from "@/lib/api/etfOfficial";
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

// 위 판정 순서의 결과 하나(글을 만들기 전). diffLine 과 gatedDiffLine 이 같은 판정을 쓴다(순서는 이 함수 한 곳).
type Verdict =
  | { t: "no_detail"; detail: string }
  | { t: "missing"; detail: string }
  | { t: "period"; h: DiffPeriod; c: DiffPeriod }
  | { t: "unconfirmed"; range: string; who: string }
  | { t: "state"; range: string; hs: "intraday" | "after_close"; cs: "intraday" | "after_close" }
  | { t: "diff"; range: string; d: number; provisional: boolean };

function judge(key: DiffPeriodKey, hold: DiffSide | null, cand: DiffSide | null, reasonText: (code: string | null) => string): Verdict {
  if (!hold || !cand) {
    const who = [hold ? null : "보유 상세 수치 없음", cand ? null : "후보 상세 수치 없음"].filter((x): x is string => !!x);
    return { t: "no_detail", detail: who.join(" / ") };
  }
  const sides: [string, DiffSide][] = [
    ["보유", hold],
    ["후보", cand],
  ];

  const missing = sides.filter(([, s]) => isMissing(key, s.period));
  if (missing.length > 0) {
    return { t: "missing", detail: missing.map(([who, s]) => `${who} 값 없음 · ${reasonText(s.period.reason)}`).join(" / ") };
  }

  const h = hold.period;
  const c = cand.period;
  if (!samePeriod(key, h, c)) return { t: "period", h, c };

  const range = rangeText(key, h);
  const hs = confirmedState(hold);
  const cs = confirmedState(cand);
  if (!hs || !cs) {
    const who = sides.filter(([, s]) => !confirmedState(s)).map(([w]) => w);
    return { t: "unconfirmed", range, who: who.join(" · ") };
  }
  if (hs !== cs) return { t: "state", range, hs, cs };

  const d = hundredths(c.value as number) - hundredths(h.value as number);
  return { t: "diff", range, d, provisional: hs === "intraday" };
}

export function diffLine(
  key: DiffPeriodKey,
  hold: DiffSide | null,
  cand: DiffSide | null,
  reasonText: (code: string | null) => string,
): DiffLine {
  const label = DIFF_LABEL[key];
  const notCompared = (text: string): DiffLine => ({ kind: "not_compared", text, diffPctp: null });
  const v = judge(key, hold, cand, reasonText);
  switch (v.t) {
    case "no_detail":
    case "missing":
      return notCompared(`${label}: 비교하지 않음 — ${v.detail}`);
    case "period":
      return notCompared(`${label}: 기간이 달라 비교하지 않음(보유 ${rangeText(key, v.h)} · 후보 ${rangeText(key, v.c)})`);
    case "unconfirmed":
      return notCompared(`${label}(${v.range}): 비교하지 않음 — 가격 시점 확인 필요(${v.who})`);
    case "state":
      return notCompared(`${label}(${v.range}): 가격 상태가 달라 비교하지 않음(보유 ${STATE_WORD[v.hs]} · 후보 ${STATE_WORD[v.cs]})`);
    case "diff":
      return {
        kind: v.provisional ? "provisional" : "compared",
        text: `${v.provisional ? "잠정 비교 · " : ""}${label}(${v.range} · 같은 기간): ${resultText(key, v.d)}${
          v.provisional ? "(두 쪽 모두 장중 저장값)" : ""
        }`,
        diffPctp: v.d / 100,
      };
  }
}

// ── POC6-32 V2 — 지수 상태 조건(PLAN §3-2 D4 · §9 I-6 · I-20) ─────────────────────────────

// 차이 요약을 쓰지 않는 지수 상태의 짧은 사유(줄마다 · 자세한 사유는 화면의 지수 상태 한 줄).
export const GATE_WORD: Record<Exclude<OfficialPairState, "same">, string> = {
  different: "지수 다름",
  same_family: "지수 다름(같은 계열)",
  unconfirmed: "기준 미확인",
};

// 위 규칙이 찾은 사유(지수 사유 뒤에 붙임) · 차이를 적을 수 있었으면 null.
function ruleReason(key: DiffPeriodKey, v: Verdict): string | null {
  switch (v.t) {
    case "no_detail":
    case "missing":
      return v.detail;
    case "period":
      return `기간 다름(보유 ${rangeText(key, v.h)} · 후보 ${rangeText(key, v.c)})`;
    case "unconfirmed":
      return `가격 시점 확인 필요(${v.who})`;
    case "state":
      return `가격 상태 다름(보유 ${STATE_WORD[v.hs]} · 후보 ${STATE_WORD[v.cs]})`;
    case "diff":
      return null;
  }
}

// 지수 상태가 '같은 공식 기초지수'(same)일 때만 diffLine 그대로. 그 밖이면 차이(%p)를 만들지 않고
// '{항목}: 차이 요약 안 함 — {지수 사유}[ · {위 규칙 사유}]'(5줄 모두 같은 조건 · I-20).
export function gatedDiffLine(
  key: DiffPeriodKey,
  hold: DiffSide | null,
  cand: DiffSide | null,
  reasonText: (code: string | null) => string,
  gate: OfficialPairState,
): DiffLine {
  if (gate === "same") return diffLine(key, hold, cand, reasonText);
  const extra = ruleReason(key, judge(key, hold, cand, reasonText));
  return {
    kind: "not_compared",
    text: `${DIFF_LABEL[key]}: 차이 요약 안 함 — ${GATE_WORD[gate]}${extra ? ` · ${extra}` : ""}`,
    diffPctp: null,
  };
}
