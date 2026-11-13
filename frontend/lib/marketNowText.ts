// POC6-29 보완 R1(RESULT 판정 §1 · 보완 PLAN 판정 Q-R1 · Q-R3 · Q-R6) — 「시장 흐름」 맨 위 '지금 시장'.
// - 빠른 시세 3칸(네이버 · 원천 표기 시각 · 조회 시각 · 장중/마감 · 실패 때 마지막 성공 값 · 기록 없으면 '시세 미확인').
// - 흐름 문장: 국면과 근거 · VIX · 수급 · 환율 · 유가를 자료별 기준일과 함께 잇는다. 새 계산 · 점수 없음 — 응답 칸
//   (시장 판정 · VIX · 시장 흐름)을 그대로 문장으로 옮긴다. 문장에 넣은 원/달러 · WTI 사건은 아래 '최근 큰 변화'에서 뺀다.
import type { MarketRiskVix } from "./api/market";
import type { MarketContext } from "./api/marketEvidence";
import type { FlowEvent, FlowPriceObs, MarketFlowContext } from "./api/marketFlow";
import type { QuickQuoteItem } from "./api/quickQuotes";
import { kstDate } from "./todayFreshness";
import {
  eventSentence,
  foreignView,
  hasStructuredEvents,
  md,
  netWord,
  num2,
  parseIsoInstant,
  priceObs,
  signedPct,
  withUnit,
  wonAbs,
} from "./todayMarketLines";
import { vixFreshnessNotice } from "./vixFreshness";

// 'M/D HH:MM'(한국 시각) — 시각으로 읽을 수 없으면 받은 글자 그대로.
export function kstMdHm(iso: string | null | undefined): string {
  if (!iso) return "확인 불가";
  const d = parseIsoInstant(iso);
  if (!d) return iso;
  const hm = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
  return `${md(kstDate(iso))} ${hm}`;
}

// ── 빠른 시세 3칸 ─────────────────────────────────────────────────────────────

const QUICK_REASON: Record<string, string> = {
  http_error: "연결 실패",
  timeout: "응답 시간 초과",
  bad_value: "값을 읽지 못함",
  missing_time: "시세 시각 없음",
};

export function quickReasonText(r: string | null | undefined): string {
  return (r && QUICK_REASON[r]) || "원인 미상";
}

export interface QuoteView {
  label: string;
  badge: string | null;
  value: string | null;
  change: string | null;
  // 방향(색) — 0 · 없음 = null
  dir: "up" | "down" | null;
  time: string | null;
  fetched: string | null;
  note: string | null;
  warn: boolean;
}

function marketBadge(s: string | null): string {
  return s === "OPEN" ? "장중" : s === "CLOSE" ? "마감" : "장 상태 확인 필요";
}

export function quoteView(it: QuickQuoteItem): QuoteView {
  const q = it.quote;
  const failed = it.last_attempt?.status === "failed";
  if (!q) {
    return {
      label: it.name,
      badge: null,
      value: null,
      change: null,
      dir: null,
      time: null,
      fetched: null,
      note: failed
        ? `시세 미확인 · 받지 못했습니다(${quickReasonText(it.last_attempt?.reason)} · ${kstMdHm(it.last_attempt?.at)})`
        : "시세 미확인 · [최신 자료 갱신]을 누르면 받습니다",
      warn: failed,
    };
  }
  const stock = it.kind === "stock";
  const amount = (v: number) => (stock ? `${Math.round(v).toLocaleString("ko-KR")}원` : num2(v));
  const change =
    q.change == null
      ? null
      : `${q.change > 0 ? "+" : q.change < 0 ? "-" : ""}${amount(Math.abs(q.change))}` +
        (q.change_pct == null ? "" : ` (${signedPct(q.change_pct)})`);
  return {
    label: it.name,
    badge: marketBadge(q.market_status),
    value: amount(q.value),
    change,
    dir: q.change == null || q.change === 0 ? null : q.change > 0 ? "up" : "down",
    time: `시세 시각 ${kstMdHm(q.source_time)}`,
    // '변동 없음'은 저장값이 이전 성공 그대로 — 새로 확인한 시각(last_attempt.at)을 적고 그 사실을 붙인다.
    fetched:
      it.last_attempt?.status === "unchanged"
        ? `조회 ${kstMdHm(it.last_attempt.at)} · 시세 변동 없음`
        : `조회 ${kstMdHm(q.fetched_at)}`,
    note: failed
      ? `마지막 조회 실패(${quickReasonText(it.last_attempt?.reason)} · ${kstMdHm(it.last_attempt?.at)}) · 위 값은 이전에 받은 시세입니다`
      : null,
    warn: failed,
  };
}

// ── 흐름 문장 ─────────────────────────────────────────────────────────────────

export interface NowSentence {
  key: "regime" | "vix" | "flows" | "fxwti" | "kospi";
  text: string;
  // 자료 기준(날짜 · 저장 시각) — 문장 끝 작은 글자
  basis: string | null;
  // 늦은 자료(기존 최신성 판정) — 배지
  stale: string | null;
}

// 시장 판정이 실제로 쓴 KODEX 200 끝일 — 같은 이력의 마지막 행(POC5-21 `return_end_date`) · 없으면 KODEX200 기준일(`asof`).
// 저장 시점(장중 · 마감 뒤)은 이 날짜의 행일 때만 붙인다(검증자 F4 — 따로 받은 상세 응답의 다른 날을 붙이지 않음).
export function regimeBasisDate(ctx: MarketContext | null): string | null {
  return ctx?.kodex200?.return_end_date ?? ctx?.asof ?? null;
}

// 판정이 쓴 끝일 종가(같은 계산의 `kodex200.close`). 같은 날 가격을 다시 저장하면(장중 → 마감 뒤) 날짜만으로는 어느
// 저장값인지 모른다 — 상세의 저장 시점은 날짜와 이 종가가 모두 같을 때만 붙인다(검증자 F7).
export function regimeBasisClose(ctx: MarketContext | null): number | null {
  const k = ctx?.kodex200;
  return k && k.status === "ok" && typeof k.close === "number" && Number.isFinite(k.close) ? k.close : null;
}

// 같은 저장값인가 — 날짜가 같고 종가가 같을 때만(어느 한쪽이라도 모르면 같다고 하지 않음).
export function sameStoredPrice(
  a: { date: string | null; close: number | null },
  b: { date: string | null; close: number | null },
): boolean {
  return !!a.date && a.date === b.date && a.close != null && b.close != null && Math.abs(a.close - b.close) < 0.005;
}

export function regimeSentence(
  ctx: MarketContext | null,
  label: string,
  kodexBasis: string | null,
): NowSentence | null {
  if (!ctx) return null;
  const date = regimeBasisDate(ctx);
  const s = ctx.regime_streak;
  const streak = s && s.streak_days != null ? `(${s.streak_days}거래일째${s.at_least ? " 이상" : ""})` : "";
  const reasons = (ctx.regime_reasons ?? []).filter((r) => typeof r === "string" && r.trim() !== "");
  return {
    key: "regime",
    text: `국내 시장은 ${label}${streak}입니다.` + (reasons.length > 0 ? ` 판정 근거: ${reasons.join(" · ")}.` : ""),
    basis: kodexBasis ?? (date ? `KODEX 200 ${md(date)} 가격 기준(저장 시점 확인 필요)` : "KODEX 200 기준일 확인 불가"),
    stale: null,
  };
}

// 숫자 뒤 '(으)로' — 끝 숫자를 읽은 소리가 받침(ㄹ 제외)으로 끝나면 '으로'(0 영 · 3 삼 · 6 육), 아니면 '로'
// (1 일 · 7 칠 · 8 팔 = ㄹ 받침 · 2 · 4 · 5 · 9 = 받침 없음). 2026-11-14 운영 화면 'VIX … 18.70로' 정정.
export function roAfterNumber(numText: string): string {
  return /[036]$/.test(numText) ? "으로" : "로";
}

export function vixSentence(vix: MarketRiskVix | null | undefined): NowSentence | null {
  if (!vix || vix.availability !== "available" || vix.close == null) return null;
  const c = vix.change_1d_pct;
  // 설계자 정리(2026-11-13 · 마감 뒤) — 'VIX는 17.49로 전일보다 10.12% 낮아졌습니다'처럼 읽히게(값 · 변화 그대로).
  const v = num2(vix.close);
  const text =
    c == null || !Number.isFinite(c)
      ? `VIX(미국 변동성)는 ${v}입니다.`
      : c === 0
        ? `VIX(미국 변동성)는 ${v}${roAfterNumber(v)} 전일과 같습니다.`
        : `VIX(미국 변동성)는 ${v}${roAfterNumber(v)} 전일보다 ${Math.abs(c).toFixed(2)}% ${c > 0 ? "높아졌습니다" : "낮아졌습니다"}.`;
  const notice = vixFreshnessNotice(vix);
  return {
    key: "vix",
    text,
    basis: `${md(vix.as_of_date)} 미국`,
    stale: notice ? notice.text : null,
  };
}

function staleOfFresh(flow: MarketFlowContext, key: string): string | null {
  const it = flow.freshness?.items?.find((x) => x.key === key);
  if (!it) return null;
  if (it.state === "late") return `${it.behind != null ? `${it.behind}거래일` : ""} 늦음`.trim();
  if (it.state === "check") return "기준 확인 필요";
  return null;
}

export function flowsSentence(flow: MarketFlowContext | null): NowSentence | null {
  if (!flow) return null;
  if (!flow.has_flows) {
    return { key: "flows", text: "투자자별 수급 자료가 없습니다.", basis: null, stale: staleOfFresh(flow, "flows") };
  }
  const fv = foreignView(flow);
  const parts: string[] = [];
  const r = fv.recent;
  const p = fv.previous;
  if (r && r.avg != null) {
    const prev =
      p && p.avg != null ? `(직전 20거래일 ${wonAbs(p.avg)} ${netWord(p.avg)}${fv.trend ? ` · ${fv.trend}` : ""})` : "";
    parts.push(`외국인은 최근 20거래일(${md(r.from)} ~ ${md(r.to)}) 하루 평균 ${wonAbs(r.avg)} ${netWord(r.avg)}입니다${prev}.`);
  }
  const inst = flow.windows?.r60?.institution ?? null;
  if (inst) parts.push(`기관은 최근 60거래일(${md(inst.from)} ~ ${md(inst.to)}) ${wonAbs(inst.sum)} ${netWord(inst.sum)}입니다.`);
  if (parts.length === 0) return null;
  const last = flow.freshness?.items?.find((x) => x.key === "flows")?.last_date ?? r?.to ?? null;
  return {
    key: "flows",
    text: parts.join(" "),
    basis: last ? `${md(last)}까지` : null,
    stale: staleOfFresh(flow, "flows"),
  };
}

function priceClause(name: string, josa: string, o: FlowPriceObs | null, unit: string): string | null {
  if (!o) return null;
  const d = o.d1
    ? `(직전 대비 ${o.d1.diff > 0 ? "+" : o.d1.diff < 0 ? "-" : ""}${withUnit(Math.abs(o.d1.diff), unit)})`
    : "";
  return `${name}${josa} ${md(o.date)} ${withUnit(o.value, unit)}${d}`;
}

// 원/달러 · WTI — 값 문장 + 각 자료의 가장 최근 사건 1건씩(최대 2건 · 발생일 포함 · 아래 목록에서 뺄 사건).
// withEvents = false — 아침 요약은 값만(과거 사건은 최근 변화 줄 · 날짜별 상세에서 · 설계자 정리 2026-11-13).
export function fxwtiSentence(
  flow: MarketFlowContext | null,
  withEvents = true,
): { sentence: NowSentence | null; merged: FlowEvent[] } {
  if (!flow) return { sentence: null, merged: [] };
  const u = priceClause("원/달러", "는", priceObs(flow, "usdkrw"), "원");
  const w = priceClause("WTI", "는", priceObs(flow, "wti"), "달러");
  const merged: FlowEvent[] = [];
  if (withEvents && hasStructuredEvents(flow)) {
    for (const key of ["usdkrw", "wti"] as const) {
      const e = (flow.events ?? []).find((x) => x.key === key);
      if (e) merged.push(e);
    }
  }
  const head = [u, w].filter((x): x is string => !!x);
  if (head.length === 0 && merged.length === 0) return { sentence: null, merged: [] };
  const text =
    (head.length > 0 ? `${head.join(", ")}입니다.` : "") +
    merged.map((e) => ` ${eventSentence(e)}.`).join("");
  return {
    sentence: { key: "fxwti", text: text.trim(), basis: null, stale: staleOfFresh(flow, "usdkrw") ? `원/달러 ${staleOfFresh(flow, "usdkrw")}` : null },
    merged,
  };
}

// ── ⓪ 빠른 시세 결과 줄(보완 PLAN 판정 '구현에서 확인할 세 가지' 1) ──────────────────

const QUICK_NAME: Record<string, string> = { KOSPI: "코스피", KOSDAQ: "코스닥", "069500": "KODEX 200" };

export function quickResultLine(
  step: { status: string; items?: Partial<Record<string, { status: string; reason?: string | null }>>; message?: string | null },
  items: QuickQuoteItem[] | null,
): { text: string; warn: boolean } {
  const byCode = new Map((items ?? []).map((it) => [it.code as string, it]));
  const name = (c: string) => byCode.get(c)?.name ?? QUICK_NAME[c] ?? c;
  const entries = Object.entries(step.items ?? {}).filter((e): e is [string, { status: string; reason?: string | null }] => !!e[1]);
  if (entries.length === 0) {
    return {
      text: `⓪ 빠른 시세를 받지 못했습니다${step.message ? `(${step.message})` : ""} · 보유 · 시장 단계는 이어서 진행합니다`,
      warn: true,
    };
  }
  const parts: string[] = [];
  const updated = entries.filter(([, v]) => v.status === "updated").map(([c]) => c);
  if (updated.length > 0) {
    const qs = updated.map((c) => byCode.get(c)?.quote).filter((q): q is NonNullable<typeof q> => !!q);
    const latest = qs.map((q) => q.source_time).sort().at(-1);
    const states = Array.from(new Set(qs.map((q) => marketBadge(q.market_status))));
    parts.push(
      `${updated.map(name).join(" · ")} 새 시세 받음` +
        (latest ? `(시세 시각 ${kstMdHm(latest)}${states.length === 1 ? ` · ${states[0]}` : ""})` : ""),
    );
  }
  const same = entries.filter(([, v]) => v.status === "unchanged").map(([c]) => c);
  if (same.length > 0) parts.push(`${same.map(name).join(" · ")} 조회 성공 · 시세 변동 없음`);
  const failed = entries.filter(([, v]) => v.status === "failed");
  for (const [c, v] of failed) {
    const q = byCode.get(c)?.quote ?? null;
    parts.push(
      `${name(c)} 받지 못함(${quickReasonText(v.reason)}) — ` +
        (q ? `마지막 시세 ${kstMdHm(q.source_time)} 표시` : "시세 미확인"),
    );
  }
  return { text: `⓪ ${parts.join(" · ")}`, warn: failed.length > 0 || step.status === "failed" };
}
