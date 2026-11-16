// POC6-31 STEP 4 — 구성종목 비교 표시 글(서버 미리보기 '[구성종목 비교]' 묶음 `constituents_pair_exposure.preview_lines`
// 와 같은 낱말 · 같은 반올림). 수치는 서버가 만든 글을 그대로 읽고 표시할 때만 소수 둘째 자리로 반올림한다.
import type { PairCell, PairExposure, PairStock } from "./api/pairExposure";

// 계산 글(%) → 소수 둘째 자리(올림 기준 셋째 자리 5 이상 · 서버 ROUND_HALF_UP 과 같음 · 이진 소수 오차 없음).
export function round2(s: string): string {
  const neg = s.startsWith("-");
  const [i, f = ""] = (neg ? s.slice(1) : s).split(".");
  const f3 = (f + "000").slice(0, 3);
  let n = Number(i + f3.slice(0, 2));
  if (Number(f3[2]) >= 5) n += 1;
  const str = String(n).padStart(3, "0");
  const out = `${str.slice(0, -2)}.${str.slice(-2)}`;
  return neg && n !== 0 ? `-${out}` : out;
}

export function pct2(s: string | null | undefined): string {
  return s === null || s === undefined ? "확인 불가" : `${round2(s)}%`;
}

// 원천 비중 글 → 표시(반올림 없음 · 계산에 쓴 자릿수 그대로 · 소수 둘째 자리까지는 0 을 채움 · 서버 `wtext` 와 같음).
export function wtext(s: string | null | undefined): string {
  if (s === null || s === undefined) return "확인 불가";
  const [head, tail = ""] = s.split(".");
  return `${head}.${tail.padEnd(2, "0")}%`;
}

export function pairText(p: PairCell): string {
  switch (p.state) {
    case "found":
      return wtext(p.weight);
    case "weight_unknown":
      return "편입 · 비중 확인 불가";
    case "zero":
      return "0(확인)";
    case "out_of_range":
      return `저장 범위에서 미확인(${p.stored_rows}행 · 저장 행 합 ${pct2(p.stored_sum)})`;
    case "self":
      return "이 주식 자체";
    case "not_applicable":
      return "해당 없음(개별 주식)";
    case "unconfirmed":
      return `원천 기준일 미확인(${p.asof} 보존 자료)`;
    default:
      return "구성 자료 없음";
  }
}

// 상태 안내(서버 미리보기 글 `constituents_pair_exposure_text` 와 같은 문장).
export const STATUS_TEXT: Record<Exclude<PairExposure["status"], "ok" | "no_candidate_data">, string> = {
  no_etf_list: "확인 불가 — ETF 목록을 읽지 못해 보유 ETF 와 직접 보유를 가를 수 없습니다(겹침 없음이라는 뜻 아님).",
  no_holdings: "등록 보유 없음 — 내 보유 노출을 계산할 대상이 없습니다.",
  holdings_unreadable:
    "보유 목록을 읽지 못했습니다 — 내 보유 노출은 확인 불가(겹침 없음이라는 뜻 아님) · 후보와 고른 보유의 편입 비중만 적음.",
  no_weight_basis:
    "비중 확인 불가 — 시세가 확인된 보유가 없어 분모(현금 제외 보유 평가액)를 정하지 못했습니다 · 후보와 고른 보유의 편입 비중만 적음.",
};

export const AFTER_ADD_TEXT =
  "후보를 더 샀을 때의 예상 비중은 추가 금액과 자금 출처가 있어야 계산할 수 있습니다(지금 확인된 노출만 적음).";

// 짝 칸 중 고른 보유 구성 자료에서 나온 값 — 구성일이 후보와 다르면 참고 표시(서버 `REF_MARK` 와 같은 글 · F12)
export const REF_MARK = "(구성일 다름 · 참고)";
const FROM_HOLDING_SNAPSHOT = new Set(["found", "zero", "out_of_range", "weight_unknown"]);
export function pairCellText(p: PairExposure, cell: PairCell): string {
  return pairText(cell) + (p.pair_dates_differ && FROM_HOLDING_SNAPSHOT.has(cell.state) ? REF_MARK : "");
}

// 확인 범위 — 계산에 들어간 부분 · 빠진 부분(사유별) · 분모 밖. 빠짐 합 = 사유별 합(서버 글 그대로 더함).
export function scopeLines(p: PairExposure): { included: string; missing: string; sum: string } | null {
  const sc = p.scope;
  if (!sc) return null;
  const miss: [typeof sc.no_data, string][] = [
    [sc.other_date, "다른 구성일"],
    [sc.unconfirmed, "원천 기준일 미확인"],
    [sc.no_data, "구성 자료 없음"],
  ];
  const parts = miss.filter(([m]) => m.count > 0).map(([m, label]) => `${label} ${m.count}개 ${pct2(m.weight)}`);
  const missingSum = addDecimals(miss.map(([m]) => m.weight));
  const total = addDecimals([sc.included.weight, sc.direct.weight, missingSum]);
  return {
    included: `계산에 들어감: 보유 ETF ${sc.included.count}개 = 평가액의 ${pct2(sc.included.weight)} · 직접 보유 ${sc.direct.count}개 = ${pct2(sc.direct.weight)}`,
    missing:
      `빠짐 ${pct2(missingSum)}` +
      (parts.length ? `: ${parts.join(" · ")}` : "") +
      (sc.no_weight.count ? ` · 시세 미확인 ${sc.no_weight.count}종목은 분모 밖(부분 평가액 기준)` : ""),
    // 식의 더하는 값은 계산에 쓴 넷째 자리 그대로(따로 반올림하면 보이는 식이 맞지 않음 · 검토 지적 frontend#1)
    sum: `${sc.included.weight}% + ${sc.direct.weight}% + ${missingSum}% = ${total}%(평가 비중은 소수 넷째 자리까지 계산에 씀)`,
  };
}

// 소수 글끼리 정확히 더한다(최대 넷째 자리 · 정수로 바꿔 더함).
export function addDecimals(xs: string[]): string {
  const scale = 4;
  let sum = 0;
  for (const x of xs) {
    const [i, f = ""] = x.split(".");
    sum += Number(i) * 10 ** scale + Number((f + "0000").slice(0, scale)) * (i.startsWith("-") ? -1 : 1);
  }
  const s = String(Math.abs(sum)).padStart(scale + 1, "0");
  const out = `${s.slice(0, -scale)}.${s.slice(-scale)}`.replace(/\.?0+$/, "");
  return `${sum < 0 ? "-" : ""}${out || "0"}`;
}

export function rangeText(p: PairExposure): string {
  const r = p.scope?.ranges;
  if (!r) return "";
  const parts = [
    r.depth ? `30행(요청 깊이 전부 · 그 밖은 미확인) ${r.depth}개` : null,
    r.legacy ? `예전 10행 ${r.legacy}개` : null,
    r.unverified ? `원천 전체 확인 기록 없음(그 밖은 미확인) ${r.unverified}개` : null,
    r.full ? `${r.full_min === r.full_max ? r.full_min : `${r.full_min} ~ ${r.full_max}`}행(원천 전체) ${r.full}개` : null,
  ].filter(Boolean);
  return parts.length ? `합산 보유 ETF별 저장 행: ${parts.join(" · ")}` : "합산 보유 ETF 없음";
}

export function formulaText(s: PairStock): string {
  const e = s.exposure;
  if (!e) return `${s.name} = 내 보유 전체 비중 확인 불가(계산하지 않음)`;
  if (e.value === null || e.raw === null) return `${s.name} = 확인한 구성 없음 → 내 보유 전체 확인 불가`;
  const terms = e.terms.map(
    (t) => `${t.name ?? t.ticker} 평가 비중 ${t.holding_weight}% × 편입 ${t.constituent_weight}% (${t.product}%)`,
  );
  const direct = e.direct.length ? e.direct.map((d) => `직접 보유 ${d.weight}%`) : ["직접 보유 0%"];
  return `${s.name} = ${[...terms, ...direct].join(" + ")} = ${e.raw}% → 합계에서 반올림 ${pct2(e.value)}`;
}

// 후보를 이미 보유 중일 때 — 합계에 들어갔는지와 그 사유(쓰임별 · 서버 `held_text` 와 같은 글 · 검토 지적 backend#2)
const HELD_WHY: Record<string, (asof: string | null) => string> = {
  sum: () => "그 구성도 노출 합계에 들어 있음",
  other_date: (asof) => `후보 구성일 ${asof}이 노출 합계일과 달라 합계 밖(다른 구성일 참고)`,
  no_weight: () => "시세 미확인이라 분모 밖 — 합계에 넣지 않음",
  unconfirmed: () => "원천 기준일 미확인이라 합계 밖",
  no_data: () => "구성 자료 없음이라 합계 밖",
  direct: () => "ETF 목록에 없어 직접 보유로 셈",
};

export function heldText(p: PairExposure): string | null {
  const c = p.candidate;
  if (!c.held) return "후보를 지금 보유하지 않음";
  const weight = c.held_weight !== null ? `(평가 비중 ${pct2(c.held_weight)})` : "";
  const why = HELD_WHY[c.held_use ?? ""]?.(c.asof) ?? "합계 반영 여부 확인 불가";
  return `후보를 이미 보유 중${weight} — ${why}`;
}

// 근거 날짜의 역할별 기준일 세 칸(POC6-31 C26 · 미리보기 · AI 세션 작성 · 다시 열기 공통). 세 칸 모두 없으면 null(예전 기록).
export function constituentDatesText(
  e:
    | {
        candidate_constituents_asof?: string | null;
        holding_constituents_asof?: string | null;
        exposure_asof?: string | null;
      }
    | null
    | undefined,
): string | null {
  if (!e) return null;
  const c = e.candidate_constituents_asof ?? null;
  const h = e.holding_constituents_asof ?? null;
  const x = e.exposure_asof ?? null;
  if (!c && !h && !x) return null;
  return `구성: 후보 ${c ?? "-"} · 고른 보유 ${h ?? "-"} · 노출 합계 ${x ?? "-"}`;
}
