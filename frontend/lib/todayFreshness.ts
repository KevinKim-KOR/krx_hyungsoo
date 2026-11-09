// POC6-27 — 「오늘의 투자 점검」 자료별 최신성(설계 §2 · PLAN 쟁점 2 · 판정 §3 Q4 · Q5 · §4).
//
// 기대 기준일은 서버가 정한다(`/market/flow-context` 의 freshness.expected_kr = 국내 직전 거래일 ·
// 기존 trading_day_lag 함수). 이 파일은 그 날짜와 각 자료의 마지막 날짜를 비교만 한다(새 기대일 계산 없음).
// - 코스피: 기존 화면 판정(kospiStatusView · 정확 일치) 그대로.
// - 외국인 수급 · 원/달러: 서버 freshness.items 그대로(원/달러는 '국내 직전 거래일 대비' 기준과 실제 관측일을 나눠 적음).
// - WTI: 판정하지 않는다(관측일만 · 판정 §4) — 이 목록에 넣지 않는다.
// - KODEX200 시장 판정 · 보유 근거 가격 기준일: 기대일 이상이면 최신.
// - 보유 현재가: 네이버 체결 시각(price_asof · localTradedAt)인 행만 KST 날짜로 비교, 그 밖은 '기준 확인 필요'.
// NAV · 구성종목 · 연구 · VIX 는 조건으로 쓰지 않는다(「자료 확인」 · 기존 정비 기준).
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import { kospiStatusView } from "@/lib/kospiStatus";
import { isRealDate, josa, md, parseIsoInstant } from "@/lib/todayMarketLines";

export type FreshState = "fresh" | "late" | "check";
// 이 자료를 새로 받는 이 화면의 동작(상단 버튼과 같은 작업).
export type FreshAction = "market" | "holdings" | "reload" | null;

export interface FreshRow {
  key: string;
  label: string;
  lastDate: string | null;
  expected: string | null;
  basis: string | null;
  state: FreshState;
  behind: number | null;
  reason: string;
  action: FreshAction;
}

export interface FreshSources {
  market: MarketTopNResponse | null;
  marketPhase: "idle" | "loading" | "success" | "error";
  flow: MarketFlowContext | null;
  flowFailed: boolean;
  holdings: EnrichedHoldingsResult | null;
  holdingsFailed: boolean;
  evidence: HoldingsMarketEvidenceResponse | null;
  evidenceFailed: boolean;
}

export function krBasisText(b: string | null | undefined): string {
  return b === "weekday_fallback" ? "국내 직전 거래일 · 평일 기준(달력 없음)" : "국내 직전 거래일";
}

// 날짜(YYYY-MM-DD) · ISO 시각 → KST 날짜 · 실제 날짜 · 시각으로 읽을 수 없으면 null(검증자 r1 F2 — 모양만 보지 않음).
export function kstDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return isRealDate(iso) ? iso : null;
  const d = parseIsoInstant(iso);
  if (!d) return null;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

function compareRow(
  key: string,
  label: string,
  last: string | null | undefined,
  expected: string | null,
  basis: string,
  action: FreshAction,
): FreshRow {
  const base = { key, label, lastDate: last ?? null, expected, basis, behind: null, action };
  if (!last) return { ...base, state: "check", reason: "자료 없음" };
  if (!isRealDate(last)) return { ...base, state: "check", reason: "날짜 확인 불가" };
  if (!isRealDate(expected)) return { ...base, state: "check", reason: "기대 기준일 확인 불가" };
  if (last >= expected) return { ...base, state: "fresh", reason: "" };
  return { ...base, state: "late", reason: `${basis} ${expected} 보다 이전` };
}

function kospiRow(src: FreshSources, expected: string | null, basis: string): FreshRow | null {
  const kospi = src.market?.market_context?.kospi ?? null;
  const kv = kospiStatusView(kospi, src.marketPhase);
  if (kv.loading) return null;
  const base = {
    key: "kospi",
    label: "코스피",
    lastDate: kospi?.as_of_date ?? null,
    expected,
    basis,
    action: "market" as const,
  };
  if (kv.state === "ok" || kv.state === "holiday") {
    return { ...base, state: "fresh", behind: null, reason: "" };
  }
  if (kv.state === "stale") {
    const lag = kospi?.trading_day_lag;
    return {
      ...base,
      state: "late",
      behind: typeof lag === "number" && lag > 0 ? lag : null,
      reason: kv.reason ?? "KOSPI 자료가 기대 기준일보다 이전",
    };
  }
  return { ...base, state: "check", behind: null, reason: kv.reason ?? "KOSPI 상태 확인 불가" };
}

function flowRows(src: FreshSources): FreshRow[] {
  const labels: [string, string][] = [
    ["flows", "외국인 수급"],
    ["usdkrw", "원/달러"],
  ];
  if (!src.flow) {
    if (!src.flowFailed) return []; // 아직 불러오는 중 — 받은 뒤 판정한다(F3)
    return labels.map(([key, label]) => ({
      key,
      label,
      lastDate: null,
      expected: null,
      basis: null,
      state: "check" as const,
      behind: null,
      reason: "시장 흐름 자료를 불러오지 못함",
      action: "reload" as const,
    }));
  }
  const fr = src.flow.freshness;
  if (!fr) {
    return labels.map(([key, label]) => ({
      key,
      label,
      lastDate: src.flow?.status?.find((s) => s.key === key)?.E ?? null,
      expected: null,
      basis: null,
      state: "check" as const,
      behind: null,
      reason: "기준일 판정 자료 없음(서버 응답에 없음)",
      action: "market" as const,
    }));
  }
  const basis = krBasisText(fr.expected_kr_basis);
  return labels.map(([key, label]) => {
    const it = fr.items?.find((x) => x.key === key);
    if (!it || it.state === "observed") {
      return {
        key,
        label,
        lastDate: it?.last_date ?? null,
        expected: fr.expected_kr,
        basis,
        state: "check" as const,
        behind: null,
        reason: "기준일 판정 자료 없음",
        action: "market" as const,
      };
    }
    // 원/달러는 '국내 직전 거래일 대비' 기준과 실제 관측일(런던 날짜)을 나눠 적는다(판정 Q4).
    const shownBasis = key === "usdkrw" ? `${basis} 대비` : basis;
    return {
      key,
      label,
      lastDate: it.last_date,
      expected: it.expected ?? fr.expected_kr,
      basis: shownBasis,
      state: it.state,
      behind: it.behind,
      reason: it.reason ?? "",
      action: "market" as const,
    };
  });
}

function holdingsRow(src: FreshSources, expected: string | null, basis: string): FreshRow {
  const base = { key: "holdings_price", label: "보유 현재가", expected, basis, action: "holdings" as const };
  if (!src.holdings) {
    return {
      ...base,
      lastDate: null,
      state: "check",
      behind: null,
      reason: "보유 자료를 불러오지 못함",
      action: "reload",
    };
  }
  const seen = new Set<string>();
  let late = 0;
  let missing = 0;
  let unknown = 0;
  let earliest: string | null = null;
  for (const it of src.holdings.items) {
    if (seen.has(it.ticker)) continue;
    seen.add(it.ticker);
    if (it.current_price == null) {
      missing += 1;
      continue;
    }
    const d = it.price_source === "naver" ? kstDate(it.price_asof) : null;
    if (!d) {
      unknown += 1;
      continue;
    }
    if (earliest === null || d < earliest) earliest = d;
    if (expected && d < expected) late += 1;
  }
  const parts = [
    late > 0 ? `${expected} 이전 시세 ${late}종목` : null,
    missing > 0 ? `시세 없음 ${missing}종목` : null,
    unknown > 0 ? `관측 시각 확인 불가 ${unknown}종목` : null,
  ].filter((x): x is string => !!x);
  if (seen.size === 0) return { ...base, lastDate: null, state: "fresh", behind: null, reason: "" };
  if (!expected) return { ...base, lastDate: earliest, state: "check", behind: null, reason: "기대 기준일 확인 불가" };
  const state: FreshState = late > 0 ? "late" : missing + unknown > 0 ? "check" : "fresh";
  return { ...base, lastDate: earliest, state, behind: null, reason: parts.join(" · ") };
}

// scope: reload = [요약 다시 읽기](6개 자료 + 시장 판정 · 코스피 스냅샷) · copy = [AI용 시장 정보 복사](시장 자료).
export function freshnessRows(src: FreshSources, scope: "reload" | "copy"): FreshRow[] {
  // 기대일은 시장 흐름 응답이 정한다 — 그 응답을 아직 불러오는 중이면 기대일에 기대는 줄은 받은 뒤 판정한다(F3).
  const flowLoading = !src.flow && !src.flowFailed;
  // 서버 기대일도 실제 날짜일 때만 기대일로 쓴다(깨졌으면 비교하는 줄이 '기대 기준일 확인 불가' · F2).
  const expectedRaw = src.flow?.freshness?.expected_kr ?? null;
  const expected = isRealDate(expectedRaw) ? expectedRaw : null;
  const basis = krBasisText(src.flow?.freshness?.expected_kr_basis);
  const rows: FreshRow[] = [];
  const k = kospiRow(src, expected, basis);
  if (k) rows.push(k);
  if (!flowLoading && (src.marketPhase === "success" || src.marketPhase === "error")) {
    rows.push(
      src.market?.market_context
        ? compareRow("regime", "시장 판정(KODEX 200)", src.market.market_context.asof, expected, basis, "market")
        : {
            key: "regime",
            label: "시장 판정(KODEX 200)",
            lastDate: null,
            expected,
            basis,
            state: "check",
            behind: null,
            reason: "시장 판정 자료 없음",
            action: null,
          },
    );
  }
  rows.push(...flowRows(src));
  if (scope === "reload" && !flowLoading) {
    // 불러오는 중인 보유 · 보유 근거는 줄을 만들지 않는다(받은 뒤 판정 · F3).
    if (src.holdings || src.holdingsFailed) rows.push(holdingsRow(src, expected, basis));
    if (src.evidence) {
      rows.push(
        compareRow(
          "evidence_basis",
          "보유 근거 가격 기준일",
          src.evidence.price_basis?.reference_date ?? null,
          expected,
          basis,
          "market",
        ),
      );
    } else if (src.evidenceFailed) {
      rows.push({
        key: "evidence_basis",
        label: "보유 근거 가격 기준일",
        lastDate: null,
        expected,
        basis,
        state: "check",
        behind: null,
        reason: "보유 근거 자료를 불러오지 못함",
        action: "reload",
      });
    }
  }
  return rows;
}

// 시장 갱신 뒤에도 기대일보다 늦은 자료 — '갱신 후에도 코스피·원/달러는 11/6 기준입니다. 화면 기대일은 11/9입니다.'
// (설계자 2026-11-10 · 기준일 판정은 그대로 · 날짜가 여럿이면 '코스피는 11/6 · 외국인 수급은 11/5 기준입니다.')
export function staleAfterRefreshText(rows: FreshRow[]): string | null {
  const late = rows.filter((r) => r.state === "late" && r.lastDate);
  if (late.length === 0) return null;
  const groups: { date: string; labels: string[] }[] = [];
  for (const r of late) {
    const g = groups.find((x) => x.date === r.lastDate);
    if (g) g.labels.push(r.label);
    else groups.push({ date: r.lastDate as string, labels: [r.label] });
  }
  const body = groups.map((g) => `${josa(g.labels.join("·"), "은", "는")} ${md(g.date)}`).join(" · ");
  const expected = late.find((r) => r.expected)?.expected ?? null;
  return `갱신 후에도 ${body} 기준입니다.` + (expected ? ` 화면 기대일은 ${md(expected)}입니다.` : "");
}

// 시장 갱신 상태의 실패 — ETF 가격 실패 건수는 서버 칸(price_fail_count)에서 · 서버 요약 문구에서 그 부분을 뺀 나머지는 그대로
// (요약은 ' · '로 이어 붙인 문구이고 ETF 가격 부분이 맨 앞 · 건수가 같을 때만 그 앞부분을 뺀다 — 다른 실패 문구를 잃지 않음).
export function refreshFailureLines(
  st: { price_fail_count?: number | null; error_summary?: string | null } | null,
): { etf: string | null; other: string | null } {
  const n = typeof st?.price_fail_count === "number" && st.price_fail_count > 0 ? st.price_fail_count : null;
  const summary = st?.error_summary?.trim() || null;
  const etf = n != null ? `ETF 가격 ${n}건은 이번에 갱신하지 못했습니다.` : null;
  if (!summary) return { etf, other: null };
  const head = n != null ? `price_partial_failure: fail=${n}` : null;
  const rest = head && summary.startsWith(head) ? summary.slice(head.length).replace(/^\s*·\s*/, "") : summary;
  if (!rest) return { etf, other: null };
  return { etf, other: `${etf ? "그 밖의 확인 필요" : "확인 필요"}: ${rest}` };
}

export function needsAttention(rows: FreshRow[]): FreshRow[] {
  return rows.filter((r) => r.state !== "fresh");
}

// 접힌 줄 요약(판정 §2) — 모두 같은 거래일 수만큼 늦으면 'N건 · K거래일 늦음', 섞이면 '늦음 N건 · 기준 확인 필요 M건'.
export function freshnessSummary(rows: FreshRow[]): string {
  const late = rows.filter((r) => r.state === "late");
  const check = rows.filter((r) => r.state === "check");
  if (late.length === 0 && check.length === 0) return "";
  const k = late[0]?.behind ?? null;
  if (check.length === 0 && k != null && late.every((r) => r.behind === k)) {
    return `${late.length}건 · ${k}거래일 늦음`;
  }
  return [late.length ? `늦음 ${late.length}건` : null, check.length ? `기준 확인 필요 ${check.length}건` : null]
    .filter(Boolean)
    .join(" · ");
}

// 한 줄 설명(확인 창 · 펼친 카드): '마지막 11/5 · 기대 11/6(국내 직전 거래일) · 1거래일 늦음'.
export function freshnessLine(r: FreshRow): string {
  const parts = [
    `${r.key === "usdkrw" ? "실제 관측일(런던 날짜)" : "마지막"} ${r.lastDate ?? "확인 불가"}`,
    r.expected ? `기대 ${r.expected}${r.basis ? `(${r.basis})` : ""}` : null,
    r.state === "late" ? (r.behind != null ? `${r.behind}거래일 늦음` : "늦음") : r.state === "check" ? "기준 확인 필요" : null,
    r.reason && r.state !== "fresh" && !(r.state === "late" && r.behind != null) ? r.reason : null,
  ];
  return parts.filter(Boolean).join(" · ");
}
