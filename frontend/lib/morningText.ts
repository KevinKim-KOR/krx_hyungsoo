// POC6-29 보완 2차(PLAN §10-1 · §10-2 · §10-4 · S 판정 §1 · §3 · Q-S4) — 아침 요약 · 오늘 시장 변화 머리 · ③ 결과 줄.
// 준비 상태 · 사유는 아침 기준 응답(`GET /market/morning-basis`) 그대로 옮긴다(화면이 따로 판정하지 않음 · 새 계산 없음).
import type { MarketContext } from "./api/marketEvidence";
import type { MorningBasisResponse, MorningItem, TodayRegime } from "./api/morningBasis";
import type { QuickQuoteItem } from "./api/quickQuotes";
import type { QueryState } from "./api/queryCache";
import type { PrevdayItem, RefreshAllPrevdayStep } from "./api/refreshAll";
import type { ShortFlowInvestor, ShortFlowsResponse } from "./api/shortFlows";
import { kstMdHm, regimeBasisDate, type NowSentence } from "./marketNowText";
import { josa, md, netWord, wonAbs } from "./todayMarketLines";

// 한 줄 안의 짧은 이름(판정서 예: '코스피 공식 종가 · 수급은 11/9까지')
const SHORT: Record<string, string> = {
  kospi: "코스피 공식 종가",
  kodex200: "KODEX 200",
  flows: "수급",
  vix: "VIX",
  usdkrw: "원/달러",
  wti: "WTI",
};

export interface Readiness {
  // true = 준비됨 · false = 미완료 · null = 판단 못 함(불러오는 중 · 읽기 실패)
  ok: boolean | null;
  head: string;
  reasons: string[];
}

export function readiness(mb: MorningBasisResponse | null): Readiness {
  if (!mb) return { ok: null, head: "아침 요약 기준 불러오는 중", reasons: [] };
  if (mb.status !== "ok" || !mb.expected_date) {
    return { ok: null, head: mb.message ?? "아침 요약 기준을 확인하지 못했습니다", reasons: [] };
  }
  const miss = mb.items.filter((i) => i.required && !i.met);
  if (miss.length === 0) {
    return { ok: true, head: "필수 자료 준비됨 · 코스피 공식 종가 · KODEX 200 판정 근거 · 투자자 수급", reasons: [] };
  }
  // 같은 날짜까지인 자료를 한 묶음으로(저장일 오름차순 · 날짜 없음 = 자료 없음)
  const byDate = new Map<string, string[]>();
  for (const i of miss) {
    if (i.key === "kodex200") continue;
    const k = i.stored_date ?? "";
    byDate.set(k, [...(byDate.get(k) ?? []), SHORT[i.key]]);
  }
  const parts = [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([d, labels]) => {
      const names = labels.slice(0, -1).concat(josa(labels[labels.length - 1], "은", "는"));
      return d ? `${names.join(" · ")} ${md(d)}까지` : `${labels.join(" · ")} 자료 없음`;
    });
  if (miss.some((i) => i.key === "kodex200")) parts.push("KODEX 200 근거 미확인");
  return {
    ok: false,
    head: `전일 자료 미완료 · ${parts.join(" · ")}`,
    reasons: miss.filter((i) => i.reason).map(reasonOf),
  };
}

function reasonOf(i: MorningItem): string {
  // KODEX 200 사유는 이름을 이미 담고 있다(서버 문장 그대로).
  return i.key === "kodex200" ? (i.reason ?? "") : `${SHORT[i.key]}: ${i.reason}`;
}

// 갱신 끝 줄 — 다시 읽은 아침 기준 그대로(요약과 같은 판단 · Q-S4).
export function endLine(mb: MorningBasisResponse | null): { text: string; warn: boolean } {
  const r = readiness(mb);
  if (r.ok === null || !mb?.expected_date) return { text: `아침 요약 기준 확인 불가 — ${r.head}`, warn: true };
  const head = `아침 요약 기준 ${md(mb.expected_date)}`;
  if (r.ok) return { text: `${head} · 필수 자료 모두 준비됨`, warn: false };
  const rest = r.head.replace(/^전일 자료 미완료 · /, "");
  return { text: `${head} · 남은 예외: ${rest}${r.reasons.length ? ` — ${r.reasons.join(" / ")}` : ""}`, warn: true };
}

// 아침 판정 — 기준일까지의 저장 이력으로 계산한 기존 산식 결과(서버) · 근거가 확인되지 않으면 미확인(S 판정 §3).
// 설계자 정리(2026-11-13 · 마감 뒤): 시장 판단(굵게) + KODEX 200 핵심 근거(20거래일 · 20 · 60일선 위치)를 먼저 ·
// 60거래일 수익률은 판정 표에서(요약에는 쓰지 않음) · 문장은 응답 칸 그대로(새 계산 없음).
export function morningVerdict(
  mb: MorningBasisResponse | null,
  labelKo: (c: MarketContext) => string,
): { head: string; detail: string | null; ok: boolean } {
  const r = mb?.morning_regime ?? null;
  if (r && r.status === "ok" && r.context) {
    const c = r.context;
    const s = c.regime_streak;
    const streak = s?.streak_days != null ? ` ${s.streak_days}거래일째${s.at_least ? " 이상" : ""}` : "";
    return { head: `국내 시장은 ${labelKo(c)}${streak}입니다.`, detail: kodexEvidence(c), ok: true };
  }
  return { head: `아침 판정 미확인 — ${r?.reason ?? "기준일 근거를 확인하지 못했습니다"}`, detail: null, ok: false };
}

function kodexEvidence(c: MarketContext): string | null {
  const k = c.kodex200;
  if (!k || k.status !== "ok") return null;
  const r = k.return_20d_pct;
  const has = typeof r === "number" && Number.isFinite(r);
  const word = (p: "above" | "below" | null | undefined) => (p === "above" ? "위" : p === "below" ? "아래" : null);
  const a = word(k.ma20_position);
  const b = word(k.ma60_position);
  const ma = a && b ? (a === b ? `20일선과 60일선 ${a}에 있습니다` : `20일선 ${a}, 60일선 ${b}에 있습니다`) : null;
  const move = (end: "고" | "습니다") =>
    r === 0 ? `최근 20거래일간 변동이 없었${end}` : `최근 20거래일간 ${Math.abs(r as number).toFixed(2)}% ${(r as number) > 0 ? "상승" : "하락"}했${end}`;
  if (has && ma) return `KODEX 200은 ${move("고")}, ${ma}.`;
  if (has) return `KODEX 200은 ${move("습니다")}.`;
  if (ma) return `KODEX 200은 ${ma}.`;
  return null;
}

// 아침 요약 끝 줄(설계자 정리 2026-11-13 · 형수님 선택) — 빠진 필수 자료만 짧게('코스피 공식 종가 · 수급은 11/11까지 있습니다.') ·
// 원인 · 확인 시각은 [자료 상태 보기] 안(reasons) · 모두 준비되면 짧게 한 줄 · 판단은 서버 그대로(readiness 와 같은 묶음).
export function morningStatus(
  mb: MorningBasisResponse | null,
  phase: QueryState<MorningBasisResponse>["phase"],
): { text: string; tone: "ok" | "warn" | "muted"; reasons: string[] } {
  if (phase === "error") return { text: "아침 요약 기준을 불러오지 못했습니다(PC 서버 확인)", tone: "warn", reasons: [] };
  const r = readiness(mb);
  if (r.ok === null) return { text: r.head, tone: mb ? "warn" : "muted", reasons: [] };
  if (r.ok) return { text: "필수 자료 준비됨(코스피 공식 종가 · KODEX 200 · 수급)", tone: "ok", reasons: [] };
  const miss = (mb?.items ?? []).filter((i) => i.required && !i.met);
  const byDate = new Map<string, string[]>();
  for (const i of miss) {
    if (i.key === "kodex200") continue;
    const k = i.stored_date ?? "";
    byDate.set(k, [...(byDate.get(k) ?? []), SHORT[i.key]]);
  }
  const parts = [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([d, labels]) => {
      const names = labels.slice(0, -1).concat(josa(labels[labels.length - 1], "은", "는"));
      return d ? `${names.join(" · ")} ${md(d)}까지 있습니다.` : `${labels.join(" · ")} 자료가 없습니다.`;
    });
  if (miss.some((i) => i.key === "kodex200")) parts.push("KODEX 200 판정 근거는 확인되지 않았습니다.");
  return { text: parts.join(" "), tone: "warn", reasons: r.reasons };
}

// 당일 판정의 출처(형수님 결정 2026-11-13 · 검증자 F8) — 아침 기준 응답의 today_regime: 판정 값과 그 판정이 쓴 끝 행의
// 저장 시점이 서버의 같은 한 번 읽기에서 온다. 그 칸이 없거나(아침 기준 읽기 전 · 실패 · 옛 서버) 하면 시장 판정 응답의
// 판정과 그 날짜만 쓴다(row = null → 저장 시점을 붙이지 않음 · 따로 받은 가격 상세로 채우지 않음).
// 검증자 F10 — 다시 읽기에 실패해 남아 있는 이전 응답(stale)도 출처로 쓰지 않는다(갱신 뒤 이전 당일 판정 · 저장 시점이
// 지금 판정처럼 남지 않게 · 이전 응답이라는 안내는 카드 아래 줄).
export interface TodayBasis {
  ctx: MarketContext | null;
  date: string | null;
  row: TodayRegime["basis_row"];
  // 아침 기준 응답이 당일 판정을 확인하지 못한 사유(판정 칸 없음)
  missing: string | null;
}

// 두 응답 모두 쓸 수 없을 때의 사유도 여기 한 곳에서 정한다(상자 · 표 '당일' 줄 · AI용 복사가 같은 문장 · 설계자 V3 §3).
export function todayBasis(
  morning: QueryState<MorningBasisResponse>,
  marketCtx: MarketContext | null,
  marketPhase: QueryState<unknown>["phase"] = "success",
): TodayBasis {
  const mb = morning.phase === "success" && !morning.stale ? morning.data : null;
  const tr = mb?.status === "ok" ? (mb.today_regime ?? null) : null;
  if (tr) {
    return tr.status === "ok" && tr.context
      ? { ctx: tr.context, date: tr.basis_date, row: tr.basis_row, missing: null }
      : { ctx: null, date: tr.basis_date, row: tr.basis_row, missing: `당일 판정 미확인 — ${tr.reason ?? "근거 확인 불가"}` };
  }
  if (marketCtx) return { ctx: marketCtx, date: regimeBasisDate(marketCtx), row: null, missing: null };
  const missing =
    marketPhase === "error"
      ? "당일 판정을 불러오지 못했습니다"
      : marketPhase === "success"
        ? "당일 판정 확인 불가(시장 판정 자료 없음)"
        : null; // 불러오는 중
  return { ctx: null, date: null, row: null, missing };
}

// ── 설계자 RESULT 재판정 V3(2026-11-13) D1 · D2 ────────────────────────────────────────

// D1 — 그 행 판정과 같은 응답의 regime_score('-4점' · '0점' · '+2점') · 없으면 '확인 불가'.
export function scoreText(ctx: MarketContext | null): string {
  const s = ctx?.regime_score;
  return typeof s === "number" && Number.isFinite(s) ? `${s > 0 ? "+" : ""}${s}점` : "확인 불가";
}

// D1 — 제목 옆 [?] 의 산식 설명(경계값은 서버가 준 기존 판정 상수 · 화면에 숫자를 따로 두지 않음) + 이동평균 거리의 한계
// (예전 코스피 구역 'ⓘ 이 값의 한계' 문장 · D3 로 그 구역이 빠져 여기로 옮김).
export function scoreRuleText(rule: MorningBasisResponse["score_rule"], loading = false): string {
  const limit =
    "이동평균 거리는 급격한 하락이나 반등에 늦게 반응할 수 있으며, 미래의 추세 전환을 예측하는 값은 아닙니다.";
  if (!rule) return `${loading ? "점수 산식을 불러오는 중입니다." : "점수 산식을 불러오지 못했습니다(아침 요약 기준 읽기 실패)."} ${limit}`;
  const p = (v: number) => `${v}%`;
  const n = (v: number) => `${v > 0 ? "+" : ""}${v}점`;
  return (
    `점수 = KODEX 200 네 조건의 합(-4점 ~ +4점). ` +
    `20거래일 수익률 +${p(rule.return_20d_pct)} 이상 +1 · -${p(rule.return_20d_pct)} 이하 -1 · 그 사이 0 / ` +
    `60거래일 수익률 +${p(rule.return_60d_pct)} 이상 +1 · -${p(rule.return_60d_pct)} 이하 -1 · 그 사이 0 / ` +
    `현재가가 20일 이동평균 위 +1 · 같거나 아래 -1 / 60일 이동평균도 같은 방식. ` +
    `${n(rule.bull_min)} 이상 상승장 · ${n(rule.bear_max)} 이하 하락장 · 그 사이 보합장. ${limit}`
  );
}

// D2 — 아침 · 당일 두 판정이 같은 유효 응답(아침 기준 응답 · 지금 성공)의 같은 KODEX 200 마감 뒤 저장 행을 쓰는가.
// 같으면 그 행(표 '아침·당일 공통' 한 행 · 상자는 기준만) · 다르거나 확인할 수 없으면 null(각각 표시).
export function commonClosedRow(morning: QueryState<MorningBasisResponse>): TodayRegime["basis_row"] {
  const mb = morning.phase === "success" && !morning.stale && morning.data.status === "ok" ? morning.data : null;
  const mr = mb?.morning_regime ?? null;
  const tr = mb?.today_regime ?? null;
  const k = itemOf(mb, "kodex200")?.basis_row ?? null;
  const t = tr?.basis_row ?? null;
  if (!mr || mr.status !== "ok" || !tr || tr.status !== "ok" || !k || !t || !mr.basis_date) return null;
  const same =
    t.date === mr.basis_date &&
    k.date === mr.basis_date &&
    t.state === "after_close" &&
    k.state === "after_close" &&
    Math.abs(t.close - k.close) < 0.005;
  return same ? t : null;
}

export function itemOf(mb: MorningBasisResponse | null, key: MorningItem["key"]): MorningItem | null {
  return mb?.items.find((i) => i.key === key) ?? null;
}

// ── 수급 5거래일(근거 표 단기 흐름 · 아침 요약 수급 문장) ───────────────────────

export function investorOf(sf: ShortFlowsResponse | null, key: ShortFlowInvestor["key"]): ShortFlowInvestor | null {
  return sf?.status === "ok" ? (sf.investors.find((i) => i.key === key) ?? null) : null;
}

export function shortFlowText(inv: ShortFlowInvestor | null): string {
  if (!inv) return "확인 불가";
  if (!inv.recent5) return inv.note ?? "5거래일 자료 부족";
  const s = inv.recent5.sum;
  return `최근 5거래일 ${wonAbs(s)} ${netWord(s)}${inv.trend ? ` · ${inv.trend}` : ""}`;
}

export function flowsMorning(sf: ShortFlowsResponse | null): NowSentence | null {
  const f = investorOf(sf, "foreign");
  if (!f || !sf?.end_date) return null;
  const text = f.recent5
    ? `외국인은 최근 5거래일(${md(f.recent5.from)} ~ ${md(f.recent5.to)}) ${wonAbs(f.recent5.sum)} ${netWord(f.recent5.sum)}입니다` +
      (f.trend ? `(${f.trend}).` : ".")
    : `외국인 최근 5거래일 — ${f.note ?? "5거래일 자료 부족"}.`;
  return { key: "flows", text, basis: `${md(sf.end_date)}까지`, stale: null };
}

// ── 오늘 시장 변화 머리(공통 시점은 한 번 · 다른 칸만 그 칸에 · §10-2) ───────────────

function quoteKey(it: QuickQuoteItem): string | null {
  const q = it.quote;
  if (!q || it.last_attempt?.status === "failed") return null;
  return `${q.trade_date}|${q.market_status ?? ""}`;
}

export function quoteHeader(items: QuickQuoteItem[] | null): { head: string | null; differs: Set<string> } {
  const list = items ?? [];
  const keys = list.map(quoteKey).filter((k): k is string => !!k);
  if (keys.length === 0) return { head: null, differs: new Set(list.map((i) => i.code)) };
  const count = new Map<string, number>();
  for (const k of keys) count.set(k, (count.get(k) ?? 0) + 1);
  const main = [...count.entries()].sort((a, b) => b[1] - a[1])[0][0];
  const differs = new Set(list.filter((i) => quoteKey(i) !== main).map((i) => i.code));
  const [date, status] = main.split("|");
  const same = list.filter((i) => !differs.has(i.code));
  const last = same
    .map((i) => i.last_attempt?.at ?? i.quote?.fetched_at ?? "")
    .filter(Boolean)
    .sort()
    .at(-1);
  const state = status === "OPEN" ? "장중" : status === "CLOSE" ? "마감" : "장 상태 확인 필요";
  return { head: `${md(date)} ${state} · 네이버 시세 · 마지막 조회 ${kstMdHm(last ?? null)}`, differs };
}

// ── ③ 전일 자료 보충 결과 줄(§10-4) ───────────────────────────────────────────

const PREVDAY_ORDER = ["kospi", "flows", "vix", "usdkrw", "wti"] as const;

function prevdayPart(key: string, it: PrevdayItem): { text: string; warn: boolean } | null {
  const name = SHORT[key] ?? it.label;
  switch (it.status) {
    case "already":
      return { text: `${name} ${md(it.before)} 이미 있음`, warn: false };
    case "fetched":
    case "applied":
      return {
        text:
          `${name} ${it.before ? md(it.before) : "없음"} → ${md(it.after)} ${it.status === "applied" ? "반영" : "받음"}` +
          (it.via === "local" ? "(PC 보관본)" : "") +
          (it.reason ? `(일부 확인 필요: ${it.reason})` : ""),
        warn: false,
      };
    case "unchanged":
      return { text: `${name} ${md(it.before)} 그대로(${it.reason ?? "새 자료 없음"})`, warn: true };
    case "failed":
      return { text: `${name} 받지 못함(${it.reason ?? "원인 미상"}) · ${md(it.before)}까지`, warn: true };
    default:
      return null; // skipped(원/달러가 최신이라 WTI 를 따로 받지 않음) · pending
  }
}

export function prevdayLine(step: RefreshAllPrevdayStep | null | undefined): { text: string; warn: boolean } | null {
  if (!step || step.status === "pending") return null;
  if (step.status === "running") {
    return { text: "③ 전일 자료 보충 중...(코스피 공식 종가 · 수급 · 해외 지표 중 모자란 것만)", warn: false };
  }
  if (step.status === "skipped") return { text: `③ 전일 자료 보충 안 함 — ${step.reason ?? "사유 미상"}`, warn: false };
  if (step.status === "failed") return { text: `③ 전일 자료 보충 실패 — ${step.reason ?? "원인 미상"}`, warn: true };
  const parts = PREVDAY_ORDER.map((k) => {
    const it = step.items?.[k];
    return it ? prevdayPart(k, it) : null;
  }).filter((p): p is { text: string; warn: boolean } => !!p);
  const head = `③ 전일 자료(${step.expected_date ? `${md(step.expected_date)} 기준` : "기준일 확인 불가"})`;
  return {
    text: `${head} — ${parts.length ? parts.map((p) => p.text).join(" · ") : "보충할 항목 없음"}${step.reason ? ` · ${step.reason}` : ""}`,
    warn: parts.some((p) => p.warn) || !!step.reason,
  };
}
