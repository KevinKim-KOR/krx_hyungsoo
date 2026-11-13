"use client";

// POC6-29(PLAN §2-7 · 판정 Q4-1) — 종목 상세 수치(행 상세 · [표] · 「보유와 후보 비교」 공통 표시).
// 값 · 단위 · 사용 날짜는 응답 그대로(같은 종목 · 같은 자료 시점이면 화면마다 같은 글자).
// 계산된 0 = '+0.00%' 이 아니라 '0.00%' 그대로 · 자료 없음 · 기간 다름 · 개별 주식 NAV 해당 없음은 서로 다른 글자.

import { etfDetailKey, fetchEtfDetail, type DetailPeriod, type EtfDetailItem, type EtfDetailResponse } from "@/lib/api/etfDetail";
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import { md, pct } from "@/lib/etfCompare";
import { directionColor } from "./helpers";

// 고를 종목이 아직 없으면(목록 · 보유를 받는 중) 조회하지 않는다(빈 종목 요청 없음 · phase = idle).
export function useEtfDetail(tickers: readonly string[]): QueryState<EtfDetailResponse> & { reload: () => void } {
  return useSharedQuery<EtfDetailResponse>(etfDetailKey(tickers), () => fetchEtfDetail(tickers), { lazy: tickers.length === 0 });
}

export function detailOf(q: QueryState<EtfDetailResponse>, ticker: string): EtfDetailItem | null {
  if (q.phase !== "success" || q.data.status !== "ok") return null;
  return q.data.items.find((it) => it.ticker === ticker) ?? null;
}

// 날짜 — 기준 날짜(그 종목 마지막 저장일 등)와 연도가 다르면 연도까지(12개월 시작일이 'M/D → M/D' 로 같아 보이지 않게).
export function dd(d: string | null | undefined, ref?: string | null): string {
  if (!d) return "—";
  return !ref || d.slice(0, 4) === ref.slice(0, 4) ? md(d) : d;
}

const REASON: Record<string, string> = {
  no_rows: "저장 가격 없음",
  no_start_row: "시작일 가격 없음",
  insufficient_history: "저장 이력 부족",
  invalid_price: "비정상 가격",
  end_differs: "끝일 다름",
  start_differs: "시작일 다름",
  kodex_window_unknown: "KODEX 200 구간 확인 불가",
  basis_unconfirmed: "가격 기준 확인 필요",
  end_date_unknown: "기준일 확인 불가",
  kodex200_start_price_missing: "KODEX 200 시작일 가격 없음",
  kodex200_end_price_missing: "KODEX 200 끝일 가격 없음",
};

export function reasonOf(code: string | null | undefined): string {
  if (!code) return "자료 없음";
  return REASON[code] ?? code;
}

// 기간 수익률 한 칸 — ok: 값(날짜) · 기간 다름: 실제 날짜 · 자료 없음: 사유.
export function periodText(p: DetailPeriod | null | undefined, withDates = true): string {
  if (!p) return "—";
  const ref = p.end;
  if (p.status === "ok") return withDates ? `${pct(p.value)} (${dd(p.start, ref)} → ${dd(p.end)})` : pct(p.value);
  if (p.status === "period_differs")
    return `기간 다름 · 실제 ${dd(p.start, ref)} → ${dd(p.end)}${p.reason ? ` · ${reasonOf(p.reason)}` : ""}`;
  return `값 없음 · ${reasonOf(p.reason)}`;
}

function Val({ p }: { p: DetailPeriod }) {
  return (
    <span style={{ color: p.status === "ok" ? directionColor(p.value) : "var(--muted)" }}>{periodText(p)}</span>
  );
}

function won(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}

const FLAG: Record<string, string> = {
  discount_check_needed: "괴리 확인 필요(3% 이상)",
  discount_warning: "괴리 주의(5% 이상)",
};

export function navText(it: EtfDetailItem): string {
  const n = it.nav;
  if (n.status === "not_applicable") return "기준가(NAV) · 괴리율: 해당 없음(개별 주식)";
  if (n.status === "missing") return "시장가 · 기준가(NAV) · 괴리율: 저장된 자료 없음";
  return (
    `${won(n.market_price)} · ${won(n.nav)} · ${pct(n.discount_rate_pct)} · ${dd(n.asof)} 자료` +
    (n.flag ? ` · ${FLAG[n.flag] ?? n.flag}` : "")
  );
}

export function excessText(it: EtfDetailItem): string {
  const e = it.excess20;
  if (e.status === "ok")
    return `${pct(e.value_pctp, "%p")} (이 종목 ${pct(e.etf_return_pct)} · KODEX 200 ${pct(e.kodex200_return_pct)} · 같은 ${dd(
      e.start,
    )} → ${dd(e.end)})`;
  if (e.status === "period_differs")
    return (
      `기간 다름 · 이 종목 ${dd(e.start, e.end)} → ${dd(e.end)}` +
      (e.kodex200_start ? ` · KODEX 200 ${dd(e.kodex200_start, e.kodex200_end)} → ${dd(e.kodex200_end)}` : "")
    );
  return `값 없음 · ${reasonOf(e.reason)}`;
}

// 최근 고점 대비 한 줄(행 상세 · 「보유와 후보 비교」 같은 문장 · 기간 다름 · 값 없음 구분 — 검토 지적).
export function drawdownText(it: EtfDetailItem): string {
  const d = it.drawdown;
  if (d.status === "missing") return `값 없음 · ${reasonOf(d.reason)}`;
  return `20저장일 ${dd(d.start)} ~ ${dd(d.end)} · 고점 ${dd(d.peak_date)} ${won(d.peak_close)} → ${pct(d.value)}${
    d.status === "period_differs" ? " · 기간 다름" : ""
  }`;
}

// 행 상세 · 비교 화면의 수치 줄들(<dl> 안에 넣는다).
// 「보유」 행은 최근 5 · 20구간 · 20구간 KODEX 200 차이를 하락 판정과 같은 응답(price_flow · POC6-28 F4)으로 이미 보이므로
// 그 두 줄을 뺀다(omitWindows) — 같은 값이 다른 시점 응답으로 두 번 보이지 않게.
export function DetailLines({ it, omitWindows = false }: { it: EtfDetailItem; omitWindows?: boolean }) {
  const s1 = it.same_kodex.one_month;
  const s3 = it.same_kodex.three_month;
  const same = (s: typeof s1, label: string) =>
    s.status === "ok"
      ? `${label} ${pct(s.value, "%p")}(KODEX 200 ${pct(s.kodex200_return_pct)} · 같은 ${dd(s.start, s.end)} → ${dd(s.end)})`
      : `${label} ${s.status === "period_differs" ? "기간 다름" : `값 없음 · ${reasonOf(s.reason)}`}`;
  return (
    <>
      <dt>1 · 3 · 6 · 12개월</dt>
      <dd data-testid="dn-months">
        1개월 <Val p={it.m1} /> · 3개월 <Val p={it.m3} /> · 6개월 <Val p={it.m6} /> · 12개월 <Val p={it.m12} />
      </dd>
      {!omitWindows && (
        <>
          <dt>일간 · 최근 5 · 20구간</dt>
          <dd data-testid="dn-windows">
            일간 <Val p={it.daily} /> · 5구간 <Val p={it.w5} /> · 20구간 <Val p={it.w20} />
          </dd>
          <dt>20구간 KODEX 200 차이</dt>
          <dd
            data-testid="dn-excess"
            style={{ color: it.excess20.status === "ok" ? directionColor(it.excess20.value_pctp) : undefined }}
          >
            {excessText(it)}
          </dd>
        </>
      )}
      <dt>KODEX 200 동일 기간</dt>
      <dd data-testid="dn-same">
        {same(s1, "1개월")} · {same(s3, "3개월")}
      </dd>
      <dt>최근 고점 대비</dt>
      <dd data-testid="dn-drawdown">{drawdownText(it)}</dd>
      <dt>시장가 · 기준가(NAV) · 괴리율</dt>
      <dd data-testid="dn-nav">{navText(it)}</dd>
    </>
  );
}

// 상세를 읽는 중 · 실패 · 없음 한 줄(행 상세 · 비교 공통).
export function detailStateText(q: QueryState<EtfDetailResponse>, ticker: string): string | null {
  if (q.phase === "loading" || q.phase === "idle") return "상세 수치 확인 중...";
  if (q.phase === "error") return "상세 수치 조회 실패 — [다시 불러오기]로 다시 시도하세요.";
  if (q.data.status !== "ok") return q.data.message ?? "상세 수치를 만들 수 없습니다.";
  if (!q.data.items.some((it) => it.ticker === ticker)) return "이 종목의 상세 수치가 응답에 없습니다.";
  return null;
}
