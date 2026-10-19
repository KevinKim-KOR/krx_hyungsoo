// POC5-25 — '20저장일 종가 고점 대비'(현재 PC 저장 종가 · 응답 `stored_drawdown_20` 만 읽는다).
//
// 값 = 그 종목 마지막 저장 종가 ÷ 그날 포함 최근 저장 종가 20개 중 최고 종가 − 1(%).
// 옛 점수 스냅샷 `drawdown_20d`(날짜 없음)로 대신 채우지 않는다. 두 화면 · 정렬이 이 파일 하나를 쓴다.
import type { MarketCandidate, StoredDrawdown } from "./api";

export const DD_LABEL = "20저장일 종가 고점 대비";

export const DD_REASON: Record<string, string> = {
  end_date_unknown: "기준일 확인 불가",
  insufficient_history: "저장 종가 20개 미만",
  invalid_price: "기간 안 비정상 종가",
  basis_unconfirmed: "가격 기준 확인 필요",
};

export type DdView =
  | {
      kind: "ok";
      value: number;
      start: string | null;
      end: string | null;
      peakDate: string | null;
      peakClose: number | null;
    }
  | { kind: "none"; reason: string };

export function ddView(c: MarketCandidate | undefined): DdView {
  const d: StoredDrawdown | null | undefined = c?.stored_drawdown_20;
  if (!d) return { kind: "none", reason: "자료 없음" };
  if (d.status === "ok" && d.value_pct != null) {
    return {
      kind: "ok",
      value: d.value_pct,
      start: d.start_date ?? null,
      end: d.end_date ?? null,
      peakDate: d.peak_date ?? null,
      peakClose: d.peak_close ?? null,
    };
  }
  return { kind: "none", reason: DD_REASON[d.reason ?? ""] ?? "자료 없음" };
}

// 사용자 정렬 값 — 값 없음은 null(정렬에서 방향과 무관하게 맨 뒤).
export function ddSortValue(c: MarketCandidate | undefined): number | null {
  const v = ddView(c);
  return v.kind === "ok" ? v.value : null;
}

const win = (v: DdView) => (v.kind === "ok" && v.start && v.end ? `${v.start} ~ ${v.end}` : null);

export interface DdGroup {
  total: number;
  ok: number;
  windows: string[];
  ends: string[];
}

export function ddGroup(candidates: MarketCandidate[]): DdGroup {
  const ws = new Set<string>();
  const es = new Set<string>();
  let ok = 0;
  for (const c of candidates) {
    const v = ddView(c);
    const w = win(v);
    if (w && v.kind === "ok" && v.end) {
      ok += 1;
      ws.add(w);
      es.add(v.end);
    }
  }
  return { total: candidates.length, ok, windows: [...ws].sort(), ends: [...es].sort() };
}

// 목록 위 한 줄 — 값이 있는 후보의 기간이 모두 같을 때만 '모두 같음'.
export function ddSummary(g: DdGroup): string {
  const missing = g.total - g.ok;
  const tail = missing > 0 ? ` · 값 없음 ${missing}개` : "";
  if (g.ok === 0) return `값 없음${g.total > 0 ? ` ${g.total}개` : ""}`;
  if (g.windows.length === 1)
    return `${g.windows[0]} 저장 종가 20개 · 표시 후보 ${g.ok}개 모두 같음${tail}`;
  // 다수 날짜를 기준으로 삼지 않는다(POC5-21 규칙) — 서로 다른 끝일을 모두 적고 기간은 값 아래에.
  return `종목별 기간 다름 · 끝일 ${g.ends.join(" · ")} · 기간은 값 아래${tail}`;
}

// 값 아래 짧은 표시 — 고점 날짜 · 공통 기간과 다를 때만 그 기간.
export function ddNote(v: DdView, g: DdGroup): string | null {
  if (v.kind !== "ok") return null;
  const parts: string[] = [];
  const w = win(v);
  if (w && !(g.windows.length === 1 && g.windows[0] === w)) parts.push(w);
  if (v.peakDate) parts.push(`고점 ${v.peakDate}`);
  return parts.length ? parts.join(" · ") : null;
}

// 값 글자 — 화면의 기존 % 함수 그대로 · 고점과 같은 0 만 '+' 없이(정의상 양수가 없어 '+0.00%' 는 뜻이 어긋남).
export function ddPct(value: number, fmt: (x: number) => string): string {
  const t = fmt(value);
  return value === 0 ? t.replace(/^\+/, "") : t;
}

// 상세 한 줄 — 값 · 기간 · 고점(날짜 · 종가).
export function ddDetail(v: DdView, fmt: (x: number) => string): string {
  if (v.kind !== "ok") return v.reason;
  const pct = ddPct(v.value, fmt);
  const peak =
    v.peakDate != null
      ? ` · 고점 ${v.peakDate}${v.peakClose != null ? ` ${v.peakClose.toLocaleString("ko-KR")}` : ""}`
      : "";
  return `${pct} (${v.start ?? "-"} ~ ${v.end ?? "-"}${peak})`;
}

// 고점과 같으면 0% — 정의상 양수가 없으므로 0 은 중립 색(음수만 하락 색).
export function ddColor(v: DdView, negColor: (x: number) => string): string {
  if (v.kind !== "ok") return "var(--muted)";
  return v.value < 0 ? negColor(v.value) : "var(--fg)";
}

export const DD_HELP: string[] = [
  "20저장일 종가 고점 대비 = 그 종목의 마지막 저장 종가 ÷ 그날을 포함한 최근 저장 종가 20개 중 가장 높은 종가 − 1. 고점과 같으면 0%.",
  "예: 20개 중 최고 종가 120 · 마지막 종가 90 → −25%. 장중 고가가 아닌 종가이고, 20개는 달력 20일 · 공식 거래일 20일이 아니라 저장된 종가 20개입니다.",
  "값이 없는 경우: 저장 종가 20개 미만 · 기간 안 비정상 종가 · 가격 기준 확인 필요(저장 change 와 종가 변화 불일치 등). 더 오래된 종가로 채우지 않습니다.",
  "기간 중 최대 낙폭(MDD) · 보유 손익률 · 앞으로의 하락 가능성 · 위험 등급이 아닙니다. 예전 '고점 대비'(2026-08-27 점수 스냅샷 값 · 날짜 없음)와 다른 값입니다.",
];
