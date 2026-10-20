"use client";
// POC6-01 — 「요즘 잘 오르는 ETF」 시장 정보 영역의 시장 흐름(수급 · 환율 · 유가 · 사용자 목업 확인 2026-10-20).
// 읽는 순서(설계 §4): 기간 요약 · 최근 큰 변화 → 같은 날짜 가로축 차트 4개 → 가능한 해석 → 자료 기준일 · 한계.
// 계산한 숫자 · 문장 줄(사건 없음 · 확인 못 한 자료 · 해석 메모 포함)은 서버 응답 그대로(복사문 · 미리보기와 같은
// 글). 화면이 직접 쓰는 것은 같은 status 로 만든 '늦음' 요약 · 수급 차트 자료 없음 안내 · 차트 눈금 · 고른 날 읽기
// 줄뿐이다. 기간 버튼은 받은 자료를 다시 자를 뿐 다시
// 조회하지 않는다. 고른 기간은 공유 저장소(`lib/marketFlowPeriod`)에 둬 복사문 · 미리보기 · 해석이 같은 기간을 쓴다.
import { useMemo, useState } from "react";

import FlowTimeChart, { valueAt, type FlowLine } from "@/app/components/charts/FlowTimeChart";
import HelpPopover from "@/app/components/holdings_risk_evidence/HelpPopover";
import { FLOW_PERIODS, type FlowInvestor, type FlowPoint, type MarketFlowContext } from "@/lib/api/marketFlow";
import { setMarketFlowPeriod, useMarketFlowPeriod } from "@/lib/marketFlowPeriod";

import { useMarketFlowContext } from "./useMarketFlowContext";

const TITLE = "시장 흐름 — 수급 · 환율 · 유가";
const INV: [FlowInvestor, string, string][] = [
  ["foreign", "외국인", "#dc2626"],
  ["individual", "개인", "#2563eb"],
  ["institution", "기관계", "#059669"],
  ["other_corp", "기타법인", "#9ca3af"],
];
const MARK_KEY: Record<string, string> = { 코스피: "kospi", "원/달러": "usdkrw", WTI: "wti", 외국인: "foreign", 기관계: "institution" };
const md = (d: string) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
const fmt0 = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const fmt2 = (v: number) => v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
// 서버 `won()` 과 같은 규칙: 1조 이상 = 조원(소수 1자리) · 그 아래 = 억원 정수(-0 없음).
const won = (v: number) => {
  if (Math.abs(v) >= 1e12) return `${(v / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조원`;
  const e = Math.round(v / 1e8);
  return `${(e === 0 ? 0 : e).toLocaleString("ko-KR")}억원`;
};
// 저장 시각(UTC ISO) → 한국 시각 'M/D HH:MM'.
const kst = (iso: string | null) => {
  const t = iso ? Date.parse(iso) : NaN;
  if (Number.isNaN(t)) return "—";
  const k = new Date(t + 9 * 3_600_000).toISOString();
  return `${md(k.slice(0, 10))} ${k.slice(11, 16)}`;
};

export const MARKET_FLOW_HELP = [
  "기간 요약의 끝일 D = 코스피와 투자자별 수급이 함께 확인된 마지막 거래일입니다. 누적 순매수는 기간 시작 직전을 0 으로 두고 기간 안 모든 날을 더합니다(첫 거래일 포함 · 빠진 날은 0 으로 채우지 않고 '부분 집계').",
  "최근 큰 변화는 자료마다 가장 최근의 완료된 일별 값으로 계산합니다. '변화 확대' = 직전 대비 변화가 그 이전 20회 변화 크기 평균의 3배 이상 · '직전 20개 관측 범위 위/아래' = 이전 20개 값의 최고보다 높거나 최저보다 낮음. 3배 · 20개는 이 화면의 관측 표시 기준이며 검증된 위험 · 수익 임계치가 아닙니다. 장중 움직임은 보지 않습니다.",
  "수급 = 키움 REST(KRX 코스피 종합 · 억원 단위 반올림 · 순매수만 · 외국인은 내국인대우외국인 제외 · 기관계 = 기관 세부 합). 원/달러 = Yahoo KRW=X 일봉 종가(런던 날짜) · WTI = Yahoo CL=F 근월물 선물 일봉 종가(뉴욕 날짜 · 만기 교체가 변화에 들어갈 수 있음 · 공식 정산가 아님). 한국 15:30 값이 아니며, 같은 날짜 라벨이어도 관측 시각은 다릅니다.",
  "외국인 순매도는 주식 매매 통계입니다. 같은 금액이 해외로 나갔다는 뜻이 아니며(채권 · 예금에 남을 수 있음), 외국인 순매도와 개인 순매수의 차이를 '부족액'으로 보지 않습니다.",
];

function cumulative(points: FlowPoint[], boundary: string, end: string): FlowPoint[] {
  let s = 0;
  return points.filter((p) => p[0] > boundary && p[0] <= end).map((p) => ((s += p[1]), [p[0], s] as FlowPoint));
}

function fromBoundary(points: FlowPoint[] | undefined, boundary: string): FlowPoint[] {
  if (!points) return [];
  const before = points.filter((q) => q[0] <= boundary).slice(-1);
  return [...before, ...points.filter((q) => q[0] > boundary)];
}

function Section({ data }: { data: MarketFlowContext }) {
  const period = useMarketFlowPeriod();
  const p = data.periods[period];
  const D = data.D as string;
  const view = useMemo(() => {
    if (!p) return null;
    const s = data.series;
    const ends = [s.kospi?.E, s.usdkrw?.E, s.wti?.E, s.flows?.E].filter((e): e is string => !!e).sort();
    const domain: [string, string] = [p.boundary, ends[ends.length - 1] ?? D];
    const flows: FlowLine[] = data.has_flows
      ? INV.map(([k, label, color]) => ({ key: k, label, color, points: cumulative(s.flows?.investors[k] ?? [], p.boundary, D) }))
      : [];
    const kospi = fromBoundary(s.kospi?.points, p.boundary);
    return {
      domain,
      kospi,
      fx: fromBoundary(s.usdkrw?.points, p.boundary),
      wti: fromBoundary(s.wti?.points, p.boundary),
      flows,
      steps: kospi.map((q) => q[0]).filter((d) => d > p.boundary),
      marks: data.events.filter((e) => e.date > p.boundary).map((e) => ({ date: e.date, key: MARK_KEY[e.series] ?? e.series })),
    };
  }, [data, p, D]);
  const [picked, setPicked] = useState<string | null>(null);
  if (!p || !view) return null;
  const sel = picked && picked > p.boundary ? picked : D;
  const snap = (iso: string) => {
    const cands = view.steps;
    if (!cands.length) return;
    const best = cands.reduce((a, b) => (Math.abs(Date.parse(b) - Date.parse(iso)) < Math.abs(Date.parse(a) - Date.parse(iso)) ? b : a));
    setPicked(best);
  };
  const step = (delta: -1 | 1) => {
    const i = view.steps.indexOf(sel);
    const next = view.steps[Math.min(Math.max((i < 0 ? view.steps.length - 1 : i) + delta, 0), view.steps.length - 1)];
    if (next) setPicked(next);
  };
  const read = (label: string, pts: FlowPoint[], f: (v: number) => string) => {
    const hit = valueAt(pts, sel);
    return hit ? `${label} ${f(hit[1])}${hit[0] !== sel ? `(${md(hit[0])})` : ""}` : `${label} 값 없음`;
  };
  const charts = { onPick: snap, onStep: step, selected: sel, domain: view.domain, marks: view.marks };
  return (
    <>
      <div className="mf-period">
        기간 {p.start ?? p.boundary} ~ {p.end} · 끝일 D {md(D)}(코스피 · 수급이 함께 확인된 마지막 거래일)
      </div>
      <div className="mf-top">
        <div className="mf-box">
          <div className="mf-box-title">기간 요약 · {p.label}</div>
          {p.lines.map((l) => (
            <div key={l} className="mf-line">
              {l}
            </div>
          ))}
          <div className="mf-sub">최근 20 · 60 거래일(D 기준 · 기간 선택과 무관)</div>
          {data.windows.lines.map((l) => (
            <div key={l} className="mf-line">
              {l}
            </div>
          ))}
        </div>
        <div className="mf-box">
          <div className="mf-box-title">최근 큰 변화 · 완료된 일별 값 · 자료마다 최신일</div>
          {data.short_lines.map((r) => (
            <div key={r.text} className="mf-line">
              {r.text}
              {r.flags.map((f) => (
                <span
                  key={f}
                  className={f === "비교 자료 부족" ? "mf-flag mf-flag-na" : f.startsWith("늦음") ? "mf-flag mf-flag-late" : "mf-flag"}
                >
                  {f}
                </span>
              ))}
            </div>
          ))}
          <div className="mf-sub">최근 5개 관측에서 생긴 일</div>
          {data.events.map((e) => (
            <div key={`${e.series}-${e.kind}-${e.date}`} className="mf-event">
              {e.text}
            </div>
          ))}
          {/* '큰 변화 없음'은 모든 자료를 비교했을 때만(서버 문장) · 아니면 확인 못 한 자료와 사유 */}
          {data.events.length === 0 && data.event_check.empty_text ? (
            <div
              className={data.event_check.unchecked.length ? "mf-event tc-warn" : "mf-event tc-muted"}
              data-testid="market-flow-events-empty"
            >
              {data.event_check.empty_text}
            </div>
          ) : null}
          {data.events.length > 0 && data.event_check.unchecked_text ? (
            <div className="mf-event tc-warn" data-testid="market-flow-events-unchecked">
              {data.event_check.unchecked_text}
            </div>
          ) : null}
        </div>
      </div>
      <div className="rc-readout" data-testid="market-flow-readout">
        <span className="rc-readout-date">{sel}</span> ·{" "}
        {[
          read("코스피", view.kospi, fmt2),
          ...(data.has_flows ? view.flows.map((l) => read(l.label, l.points, won)) : []),
          read("원/달러", view.fx, (v) => `${fmt2(v)}원`),
          read("WTI", view.wti, (v) => `${fmt2(v)}달러`),
        ].join(" · ")}
      </div>
      <div className="mf-charts">
        <FlowTimeChart title="코스피(pt)" lines={[{ key: "kospi", label: "코스피", color: "#2563eb", points: view.kospi }]} fmt={fmt0} testId="mf-chart-kospi" {...charts} />
        {data.has_flows ? (
          <FlowTimeChart
            title={`투자자별 누적 순매수(조원 · 억원 · 기간 시작 직전 = 0 · 끝 ${md(D)})`}
            lines={view.flows}
            fmt={won}
            zeroLine
            height={150}
            testId="mf-chart-flows"
            {...charts}
          />
        ) : (
          <p className="tc-muted tc-small">투자자별 누적 순매수 — 자료 없음(시장 갱신 뒤 다시 확인 · 키움 인증 · 등록 IP)</p>
        )}
        <FlowTimeChart title="원/달러(1달러당 원 · Yahoo 런던 날짜 일봉)" lines={[{ key: "usdkrw", label: "원/달러", color: "#7c3aed", points: view.fx }]} fmt={(v) => `${fmt0(v)}원`} testId="mf-chart-usdkrw" {...charts} />
        <FlowTimeChart title="WTI(달러/배럴 · 근월물 선물 · 뉴욕 날짜 일봉)" lines={[{ key: "wti", label: "WTI", color: "#b45309", points: view.wti }]} fmt={(v) => `${fmt0(v)}달러`} testId="mf-chart-wti" {...charts} />
      </div>
    </>
  );
}

export default function MarketFlowCard() {
  const q = useMarketFlowContext();
  const period = useMarketFlowPeriod();
  const data = q.phase === "success" ? q.data : null;
  const stale = data && data.D ? data.status.filter((s) => s.E && s.E < (data.D as string)) : [];
  const interp = data?.interpretation[period] ?? { rows: [], notes: [] };
  const periodLabel = FLOW_PERIODS.find(([k]) => k === period)?.[1] ?? period;
  return (
    <section className="card mf-card" data-testid="market-flow-card">
      <div className="mf-head">
        <h2>{TITLE}</h2>
        <div className="holdings-sort-seg" role="group" aria-label="시장 흐름 기간">
          {FLOW_PERIODS.map(([k, label]) => (
            <button key={k} type="button" className={period === k ? "on" : ""} aria-pressed={period === k} onClick={() => setMarketFlowPeriod(k)}>
              {label}
            </button>
          ))}
        </div>
        <HelpPopover label="시장 흐름 읽는 법" paragraphs={MARKET_FLOW_HELP} />
      </div>
      {q.phase === "loading" || q.phase === "idle" ? <p className="tc-muted">시장 흐름 불러오는 중...</p> : null}
      {q.phase === "error" ? <p className="tc-danger">시장 흐름 자료를 불러오지 못했습니다.</p> : null}
      {data && q.phase === "success" && q.stale ? <p className="tc-warn tc-small">⚠ 이전 조회값(다시 읽기 실패)</p> : null}
      {data && !data.D ? <p className="tc-muted">{data.today_lines[0]}</p> : null}
      {data && data.D ? (
        <>
          <Section data={data} />
          <div className="mf-box mf-interp">
            <div className="mf-box-title">가능한 해석 — {periodLabel} 기준 · 확정이 아님</div>
            {interp.rows.map(([obs, cand, other]) => (
              <div key={obs} className="mf-interp-row">
                <div>
                  <b>관측</b> {obs}
                </div>
                <div>
                  <b>가능성</b> {cand}
                </div>
                <div className="tc-muted">
                  <b>다른 설명 · 한계</b> {other}
                </div>
              </div>
            ))}
            {/* 확인 못 한 조합(입력 없음 · 부분 집계) · 해당 규칙 없음 — 서버 문장 그대로 */}
            {interp.notes.map((n) => (
              <div key={n} className={n.startsWith("확인 못 한") ? "tc-warn tc-small" : "tc-muted tc-small"}>
                {n}
              </div>
            ))}
          </div>
          <div className="mf-status">
            <div>
              자료 기준일:{" "}
              {data.status.map((s) => `${s.label} ${s.E ? md(s.E) : "없음"}(수집 ${kst(s.collected_at)})`).join(" · ")}
              {stale.length ? (
                <span className="tc-warn">
                  {" "}
                  · 늦음: {stale.map((s) => `${s.label} ${md(s.E as string)}`).join(" · ")}(D {md(data.D)} 보다 이전)
                </span>
              ) : null}
            </div>
            <div>수급 거래대금 대비 비율 — 키움 응답에 거래대금이 없어 표시하지 않음 · 장중 움직임은 보지 않음(완료된 일별 값만)</div>
          </div>
        </>
      ) : null}
    </section>
  );
}
