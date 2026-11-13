// POC6-28 — 「ETF 비교하기」 화면 문장 · 정렬 · 순서(순수 함수 · 조회 없음).
// PLAN docs/ai_plan/POC6/POC6_28_ETF_COMPARISON_SECTOR_AND_HOLDINGS_PLAN_V1.md §2 · §3 · §5 · 판정 2026-11-11.
import type {
  CompareBasis,
  CompareFilters,
  CompareGroup,
  CompareRegime,
  CompareRow,
  CompareSummaryOk,
  CritStatus,
  EndPrice,
  HoldingLink,
  PriceStateSummary,
  SideOverview,
} from "@/lib/api/etfCompare";

export const BASIS_LABEL: Record<CompareBasis, string> = {
  daily: "1일",
  one_month: "1개월",
  three_month: "3개월",
};

const FILTER_LABEL: [keyof CompareFilters, string][] = [
  ["exclude_inverse", "인버스"],
  ["exclude_leveraged", "레버리지"],
  ["exclude_synthetic", "합성"],
  ["exclude_futures", "선물"],
];

// 'YYYY-MM-DD' → 'M/D'. 모양이 다르면 그대로(지어내지 않음).
export function md(d: string | null | undefined): string {
  if (!d) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  return m ? `${Number(m[2])}/${Number(m[3])}` : d;
}

// 'YYYY-MM-DDTHH:MM:SS+09:00' → 'M/D HH:MM'(서버가 KST 로 보낸 저장 시각).
export function mdhm(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(iso);
  return m ? `${md(m[1])} ${m[2]}:${m[3]}` : iso;
}

// 수익률 · 차이 — 0.00 은 유효값이다(판정 §5). 값 없음은 '—'.
export function pct(v: number | null | undefined, unit: "%" | "%p" = "%"): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}${unit}`;
}

// 보유 내 비중 — 방향이 없는 값이라 부호를 붙이지 않는다.
export function weightText(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(2)}%`;
}

export function filtersText(f: CompareFilters): string {
  const on = FILTER_LABEL.filter(([k]) => f[k]).map(([, l]) => l);
  return on.length ? `${on.join(" · ")} 제외` : "제외 조건 없음";
}

export function basisLine(s: CompareSummaryOk): string {
  const c = s.counts;
  const shown =
    c.shown_top === c.shown_bottom
      ? `상·하위 각 ${c.shown_top}개 표시`
      : `상위 ${c.shown_top} · 하위 ${c.shown_bottom}개 표시`;
  return [
    `${BASIS_LABEL[s.basis]} · ${md(s.period.start)} → ${md(s.period.end)}`,
    filtersText(s.filters),
    `비교한 ETF ${c.population.toLocaleString("ko-KR")}개`,
    `기간이 달라 뺀 ${c.period_differs}개`,
    shown,
  ].join(" · ");
}

// ── 가격 시점(PLAN §3-7 · 판정 §4) ─────────────────────────────────────────
// 종가라고 단정하지 않는다. 저장 시각은 저장 사실이다.
export function endPriceText(e: EndPrice | null | undefined): string {
  if (!e) return "가격 자료 없음";
  if (e.state === "intraday") return `장중 저장값 · ${mdhm(e.fetched_at_kst)} 저장`;
  if (e.state === "after_close") return `마감 뒤 저장(${mdhm(e.fetched_at_kst)} 저장)`;
  return "PC 저장 가격 · 마감값 확인 필요";
}

function range(a: string | null, b: string | null): string {
  if (!a) return "—";
  if (!b || a === b) return mdhm(a);
  const [da, ta] = mdhm(a).split(" ");
  const [db, tb] = mdhm(b).split(" ");
  return da === db ? `${da} ${ta} ~ ${tb}` : `${mdhm(a)} ~ ${mdhm(b)}`;
}

// 여러 종목 상태의 짧은 이름(보유 상세의 후보 근거 줄).
export function priceStateShort(p: PriceStateSummary): string {
  if (p.intraday_count > 0) return "장중 저장값 포함 · 잠정";
  if (p.after_close_count > 0) return p.unknown_count ? "마감 뒤 저장(일부 마감값 확인 필요)" : "마감 뒤 저장";
  return "PC 저장 가격 · 마감값 확인 필요";
}

export function priceStateLine(p: PriceStateSummary): string {
  const head = `${md(p.end_date)} 가격 = `;
  const unknown = p.unknown_count ? ` · 마감값 확인 필요 ${p.unknown_count}개` : "";
  if (p.intraday_count > 0) {
    const after = p.after_close_count ? ` · 마감 뒤 저장 ${p.after_close_count}개` : "";
    return (
      `${head}장중 저장값 포함 · 잠정(장중 ${p.intraday_count.toLocaleString("ko-KR")}개 · ` +
      `${range(p.intraday_fetched_min, p.intraday_fetched_max)} 저장${after}${unknown})`
    );
  }
  if (p.after_close_count > 0) {
    return `${head}마감 뒤 저장(${range(p.after_close_fetched_min, p.after_close_fetched_max)} 저장${unknown})`;
  }
  return `${head}PC 저장 가격 · 마감값 확인 필요`;
}

// ── 시장 국면(PLAN §5 · 표시 순서와 강조만) ──────────────────────────────
export type CardKey = "both" | "holdings" | "top" | "bottom";

export interface RegimeView {
  ok: boolean;
  line: string;
  order: CardKey[];
  emphasis: "distinct_index" | "both_sides" | "holdings" | null;
  holdingsDeclineFirst: boolean;
}

const DEFAULT_ORDER: CardKey[] = ["top", "bottom", "holdings"];

export function regimeView(r: CompareRegime, endDate: string, bothSides: string[]): RegimeView {
  const known = r.code === "bull" || r.code === "neutral" || r.code === "bear";
  if (!known || !r.same_end_date || !r.label) {
    return {
      ok: false,
      line: "시장 판정 확인 필요 · 기본 순서(상위 → 하위 → 보유 겹침)로 보여 줍니다",
      order: DEFAULT_ORDER,
      emphasis: null,
      holdingsDeclineFirst: false,
    };
  }
  const streak = r.streak_days != null ? ` · ${r.streak_days}거래일${r.streak_at_least ? " 이상" : "째"}` : "";
  const provisional = r.price.state === "intraday" ? " (잠정 · 장중 저장값 기준)" : "";
  const head = `시장 판정(국내시장 · KODEX 200 · ${md(r.asof ?? endDate)}): ${r.label}${streak}${provisional}`;
  if (r.code === "bear") {
    return {
      ok: true,
      line: `${head} — 보유와 겹친 항목 · 하위권부터 보여 줍니다`,
      order: ["holdings", "bottom", "top"],
      emphasis: "holdings",
      holdingsDeclineFirst: true,
    };
  }
  if (r.code === "bull") {
    return {
      ok: true,
      line: `${head} — 상위권과 서로 다른 지수 수부터 보여 줍니다`,
      order: DEFAULT_ORDER,
      emphasis: "distinct_index",
      holdingsDeclineFirst: false,
    };
  }
  return {
    ok: true,
    line: bothSides.length
      ? `${head} — 상·하위에 함께 나온 업종부터 보여 줍니다`
      : `${head} — 상·하위에 함께 나온 업종이 없어 상위 → 하위 순으로 보여 줍니다`,
    order: bothSides.length ? ["both", ...DEFAULT_ORDER] : DEFAULT_ORDER,
    emphasis: "both_sides",
    holdingsDeclineFirst: false,
  };
}

// ── [ETF 순위] 정렬(판정 §5 · PLAN §3-6) ──────────────────────────────────
export type SortKey = "sel" | "one_month" | "three_month" | "same" | "drawdown";
export type SortDir = "desc" | "asc";

export const SORT_LABEL: Record<SortKey, string> = {
  sel: "선정 순서",
  one_month: "1개월 수익률",
  three_month: "3개월 수익률",
  same: "1개월 KODEX 200 대비",
  drawdown: "최근 고점 대비(20저장일)",
};

export interface CriterionView {
  status: CritStatus;
  value: number | null;
  unit: "%" | "%p";
  start: string | null;
  end: string | null;
  reason: string | null;
}

export function criterionOf(row: CompareRow, key: SortKey): CriterionView {
  const c = row.criteria;
  switch (key) {
    case "sel":
      return {
        status: "ok",
        value: row.basis_return.value,
        unit: "%",
        start: row.basis_return.start,
        end: row.basis_return.end,
        reason: null,
      };
    case "one_month":
      return { ...c.one_month, unit: "%" };
    case "three_month":
      return { ...c.three_month, unit: "%" };
    case "same":
      return { ...c.same_kodex_1m, unit: "%p" };
    case "drawdown":
      return { ...c.drawdown, unit: "%" };
  }
}

export function comparable(v: CriterionView): boolean {
  return v.status === "ok" && v.value != null && Number.isFinite(v.value);
}

// 비교 가능 행을 값 순(동률 = 선정 순위)으로, 비교 불가 행은 방향과 관계없이 그 뒤에 선정 순위로.
export function sortRows(rows: CompareRow[], key: SortKey, dir: SortDir): CompareRow[] {
  const out = rows.slice();
  if (key === "sel") return out.sort((a, b) => a.rank - b.rank);
  return out.sort((a, b) => {
    const va = criterionOf(a, key);
    const vb = criterionOf(b, key);
    const ca = comparable(va);
    const cb = comparable(vb);
    if (ca !== cb) return ca ? -1 : 1;
    if (!ca) return a.rank - b.rank;
    const d = (va.value as number) - (vb.value as number);
    if (d === 0) return a.rank - b.rank;
    return dir === "asc" ? d : -d;
  });
}

const REASON_TEXT: Record<string, string> = {
  insufficient_history: "20저장일 부족",
  invalid_price: "가격 확인 불가",
  basis_unconfirmed: "가격 기준 연결 확인 불가",
  end_date_unknown: "끝일 확인 불가",
  kodex200_start_price_missing: "KODEX 200 시작일 가격 없음",
  kodex200_end_price_missing: "KODEX 200 끝일 가격 없음",
  candidate_period_unknown: "기간 확인 불가",
  no_period: "기간 계산 불가",
  kodex_window_unknown: "KODEX 200 비교 구간 확인 불가",
};

export function reasonText(v: CriterionView): string {
  if (v.status === "period_differs") {
    return v.start && v.end ? `기간 다름 · ${md(v.start)} → ${md(v.end)}` : "기간 다름";
  }
  return `값 없음 · ${REASON_TEXT[v.reason ?? ""] ?? "자료 없음"}`;
}

function criterionPeriod(s: CompareSummaryOk, key: SortKey): string {
  const p = s.criteria_periods;
  const w =
    key === "sel"
      ? s.period
      : key === "three_month"
        ? p.three_month
        : key === "drawdown"
          ? p.drawdown
          : p.one_month;
  if (!w) return "공통 기간 확인 불가";
  return key === "drawdown" ? `20저장일 ${md(w.start)} ~ ${md(w.end)}` : `${md(w.start)} → ${md(w.end)}`;
}

export function sortLine(
  s: CompareSummaryOk,
  side: "top" | "bottom",
  key: SortKey,
  dir: SortDir,
  rows: CompareRow[],
): string {
  const list = `${BASIS_LABEL[s.basis]} ${side === "top" ? "상위" : "하위"} ${rows.length}`;
  // POC6-29(설계 §4) — 다른 기준으로 정렬하면 '선정 기간 · 표시 순서'를 함께 적는다(예: 1개월 선정 · 3개월 수익률 표시 순서).
  const sortTxt =
    key === "sel"
      ? `선정 순서(${BASIS_LABEL[s.basis]} ${side === "top" ? "높은 순" : "낮은 순"})`
      : `${BASIS_LABEL[s.basis]} 선정 · ${SORT_LABEL[key]} 표시 순서(${dir === "desc" ? "높은 순" : "낮은 순"})`;
  const parts = [list, `정렬 ${sortTxt}`, criterionPeriod(s, key)];
  if (key !== "sel") {
    const ok = rows.filter((r) => comparable(criterionOf(r, key))).length;
    parts.push(`비교 가능 ${ok}`);
    if (rows.length - ok > 0) parts.push(`기간 다름 · 값 없음 ${rows.length - ok}(뒤)`);
  }
  return parts.join(" · ");
}

export function kodexSameNote(s: CompareSummaryOk): string | null {
  const w = s.criteria_periods.one_month;
  const k = s.kodex200.one_month_return_pct;
  if (!w || k == null) return null;
  return (
    `같은 1개월 구간(${md(w.start)} → ${md(w.end)}) KODEX 200 ${pct(k)} · ` +
    "비교 가능한 행에서는 1개월과 순서가 같습니다"
  );
}

// ── 섹터 요약 문장(판정 §3) ───────────────────────────────────────────────
export function kindLabel(g: Pick<CompareGroup, "kind">): string {
  return g.kind === "sector" ? "업종" : g.kind === "index" ? "기초지수" : "미분류";
}

export function countsText(m: Record<string, number>): string {
  return Object.entries(m)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([k, n]) => `${k} ${n}`)
    .join(" · ");
}

export function mixText(ov: SideOverview): string {
  const parts = ov.mix.map((m) => `${m.market} ${m.asset} ${m.count}`);
  if (ov.unclassified_count) parts.push(`공식 기준정보 없음 ${ov.unclassified_count}`);
  return `공식 분류: ${parts.join(" · ")}`;
}

export function sectorLine(ov: SideOverview): string {
  const base = `사업군 분류 ${ov.sector_etf_count}/${ov.total}`;
  return ov.repeated_sector_count === 0 ? `${base} · 공통 업종 확인 어려움` : `${base} · 반복된 업종 먼저`;
}

export function commonText(g: CompareGroup): string {
  const c = g.constituents;
  const scope = `구성 자료 있는 ETF ${c.etf_with_data}/${c.etf_total}`;
  const asof =
    c.asof_min && c.asof_max
      ? c.asof_min === c.asof_max
        ? `구성 기준일 ${md(c.asof_min)}`
        : `구성 기준일 ${md(c.asof_min)} ~ ${md(c.asof_max)}`
      : "";
  if (c.status === "no_sample") return `${scope} — 공통 종목 표본 없음`;
  if (c.status === "single") return `${scope} · ${asof} — 1개뿐이라 공통 종목을 비교할 수 없음`;
  const head = `${scope} · 각 비중 상위 ${c.top_n}종목 · ${asof}`;
  if (c.status === "no_overlap") return `${head} — 2개 이상 ETF에 나온 종목 0건`;
  return `${head} · 숫자 = 그 종목이 나온 ETF 수`;
}

// 목록 전체 AI 질문용 복사문(판정 §3 · 클립보드에서 끝남).
export function aiCopyText(s: CompareSummaryOk, side: "top" | "bottom"): string {
  const rows = side === "top" ? s.top : s.bottom;
  const label = `${BASIS_LABEL[s.basis]} ${side === "top" ? "상위" : "하위"} ${rows.length}개`;
  const noCons = rows.filter((r) => !r.constituents);
  const lines = [
    `[같은 기간 ETF 목록 · ${label} · ${md(s.period.start)} → ${md(s.period.end)}]`,
    `조건: ${filtersText(s.filters)} · 비교한 ETF ${s.counts.population}개 중 · 기간이 달라 뺀 ${s.counts.period_differs}개`,
    `가격 상태: ${priceStateLine(s.price_state)}`,
    "",
  ];
  for (const r of rows) {
    const c = r.classification;
    const where = [c.market, c.asset, c.strategy ? "전략형" : null, c.sector ? `업종 ${c.sector}` : null]
      .filter(Boolean)
      .join(" · ");
    const both = s.in_both.includes(r.ticker) ? " · 상·하위 공통" : "";
    lines.push(
      `${r.rank}. ${r.name ?? r.ticker}(${r.ticker})${both} · 기초지수 ${c.index_name ?? "공식 기준정보 없음"}` +
        `${where ? ` · ${where}` : ""} · ${BASIS_LABEL[s.basis]} ${pct(r.basis_return.value)}`,
    );
    if (r.constituents) {
      const items = r.constituents.items
        .map((i) => `${i.name ?? i.key ?? "?"}${i.weight_pct != null ? ` ${i.weight_pct.toFixed(1)}%` : ""}`)
        .join(", ");
      lines.push(`   구성(${md(r.constituents.asof)} · 비중 상위 ${r.constituents.items.length}): ${items}`);
    }
  }
  lines.push("");
  lines.push(
    noCons.length
      ? `구성 자료 없음 ${noCons.length}개: ${noCons.map((r) => r.name ?? r.ticker).join(", ")}`
      : "구성 자료 없음 0개",
  );
  lines.push("");
  lines.push(
    "질문: 이 목록에서 (1) 여러 ETF에 반복해서 나타나는 근거(기초지수 · 구성종목), " +
      "(2) ETF 이름에서 유추한 가설 — 추정이라고 밝혀 주세요, " +
      "(3) 판단하기에 부족한 자료를 나눠 알려 주세요.",
  );
  return lines.join("\n");
}

// ── 보유 연결(판정 §4 · PLAN §3-4) ────────────────────────────────────────
const OUT_TEXT: Record<string, string> = {
  filter_excluded: "제외 조건(인버스 · 레버리지 · 합성 · 선물)에 해당해 비교 목록 밖",
  no_price: "저장 가격 없음",
  period_differs: "조회 기간과 시작 · 끝 날짜가 달라 비교 목록 밖",
};

export function outReasonText(link: HoldingLink): string {
  if (link.out_reason === "stock") return "개별 주식 — ETF 비교 목록 대상 아님";
  return OUT_TEXT[link.out_reason ?? ""] ?? "비교 목록 밖";
}

// 상·하위 공통(모집단 60 미만에서만 생김 · 검증자 r1 F3) — 양쪽 순위.
export function bothRanks(s: CompareSummaryOk, ticker: string): { top: number; bottom: number } | null {
  if (!s.in_both.includes(ticker)) return null;
  const t = s.top.find((r) => r.ticker === ticker);
  const b = s.bottom.find((r) => r.ticker === ticker);
  return t && b ? { top: t.rank, bottom: b.rank } : null;
}

// 점검 사유 — 직접 하위권 · 그 조회 기간 수익률이 음수일 때만.
export function pointReason(link: HoldingLink | undefined, s: CompareSummaryOk): string | null {
  if (!link || link.side !== "bottom" || !link.basis_return || link.basis_return.value >= 0) return null;
  const br = link.basis_return;
  const intraday = link.end_price?.state === "intraday" ? " · 장중 저장값 기준" : "";
  return (
    `후보 하위 ${link.side_rank}위 · ${BASIS_LABEL[s.basis]} ${pct(br.value)}` +
    `(${md(br.start)} → ${md(br.end)})${intraday}`
  );
}

export function candidateLinkText(link: HoldingLink | undefined, s: CompareSummaryOk): string {
  if (!link) return "후보 비교 자료 없음";
  if (!link.in_population || !link.basis_return) return outReasonText(link);
  const br = link.basis_return;
  const where =
    link.side === "bottom"
      ? link.top_rank != null
        ? `하위 ${link.side_rank}위 · 상위 ${link.top_rank}위(상·하위 공통)`
        : `하위 ${link.side_rank}위`
      : link.side === "top"
        ? `상위 ${link.side_rank}위`
        : "상·하위 30 밖";
  return `${BASIS_LABEL[s.basis]} ${pct(br.value)} · ${md(br.start)} → ${md(br.end)} · ${where}`;
}

export function exposureText(link: HoldingLink): string {
  const e = link.exposure;
  const scope =
    `비교 범위 = 하위 ETF 중 구성 자료 있는 ${e.compared_etf_count}개` +
    (e.compared_asof_min ? `(${md(e.compared_asof_min)}${e.compared_asof_max !== e.compared_asof_min ? ` ~ ${md(e.compared_asof_max)}` : ""})` : "") +
    ` · 각 비중 상위 ${e.top_n}종목`;
  const mine = e.holding_asof ? ` · 이 ETF 구성 ${md(e.holding_asof)}` : "";
  if (e.status === "no_constituents") return "구성종목 자료 없음 — 노출을 비교할 수 없음";
  if (e.status === "no_sample") return "하위 ETF 구성 자료가 없어 노출을 비교할 수 없음";
  if (e.status === "none") return `겹친 구성종목 0건 · ${scope}${mine}`;
  const names = e.overlaps.map((o) => `${o.name}(${o.etfs.length})`).join(" · ");
  return `노출 확인: ${names} · ${scope}${mine} · 숫자 = 겹친 하위 ETF 수`;
}
