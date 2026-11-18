"use client";

// POC6-32 V2(PLAN §4-4 · AC3 · 판정 Q5 · Q6) — 「AI 투자 세션」 주간 기록 상세의 '당시 검토'.
// 저장한 값만 그린다: 시장 자료 다시 계산 · 지금 자료 조회 없음 · 이후 자료 갱신은 이 기록을 바꾸지 않는다.
// 요청은 하나뿐 — `GET /weekly/etf-check/records/{id}/review`(저장한 질문 · 답 원문을 「주간 ETF 점검」 ④ 와 같은 해석기로
// 나눔 · PLAN I-14 · 읽기 전용). 나눈 결과 = AI 별 최신 확인 · 확인 항목 줄(확인 시각 · 없으면 '확인 시각 미기재') ·
// 후보마다 상태 · 인용 근거 · 이유 · 다음 확인 · AI 끼리 대조(today/WeeklyRecord WeeklyAnswers 를 같이 씀).
// 읽는 칸(주간 화면이 넘긴 초안 → 저장 · 자유 칸 · 표 변경 없음 · PLAN §4-3 · §9 I-13):
// - created_at(저장 시각) · asof(원자료 기준일) · candidate_snapshot(후보 30 · 1 · 3개월 · 같은 기간 KODEX 200 실제 기간)
// - data_quality_snapshot = condition(검토 조건 줄) · selected(+ returns = ③ R2 결과) · common_periods · period_differs_values ·
//   lack · price_states(30행 · KODEX 200 끝 가격 날짜 · 상태) · evidence_list
// - 국내시장(KODEX 200) 대비(PLAN I-8 · I-32 · 검토 F2 · F5): 고른 후보 = 저장한 R2 결과 그대로(잠정 비교 · 대비 안 함 사유 ·
//   문구) · 30행 = 저장 비교 칸 + 저장한 가격 상태로 I-8(끝일 · 상태가 같을 때만 · 모름 · 다름 = 대비 안 함 · 둘 다 장중 =
//   잠정). 가격 상태를 저장하지 않은 기록은 '가격 상태 대조 기록 없음'을 붙인다(지금 값으로 채우지 않음).
// - constituent_snapshot = product(공식 기준정보) · constituents(구성 요약) · overlap_snapshot = 보유 겹침 · 확인 범위
// - AI 답 원문(GPT · Gemini · Claude) — 나눈 결과 아래 접힌 칸(원문 그대로).
// 칸이 없거나 모양이 다르면 그 칸만 '당시 기록에 없음'(다른 칸은 그대로 · 지금 값으로 채우지 않음).

import { useEffect, useState } from "react";
import { ApiRequestError } from "@/lib/api/core";
import type { DecisionCandidateSnapshot, DecisionSessionDetail } from "@/lib/api/decisionSessions";
import { fetchWeeklyRecordReview, type WeeklyLastRecord } from "@/lib/api/weeklyReview";
import { kstDateTimeLabel, verdictText } from "@/lib/aiSessionsDraft";
import { md, signedPct } from "@/lib/weeklyReview";
import { WeeklyAnswers } from "../today/WeeklyRecord";

type Obj = Record<string, unknown>;
type PeriodKey = "one_month" | "three_month";

const NONE = "당시 기록에 없음";
const AIS: { key: "gpt_answer_text" | "gemini_answer_text" | "claude_answer_text"; label: string }[] = [
  { key: "gpt_answer_text", label: "GPT" },
  { key: "gemini_answer_text", label: "Gemini" },
  { key: "claude_answer_text", label: "Claude" },
];
// 같은 기간 KODEX 200 비교를 못 한 사유(저장 코드 → 쉬운 한국어 · 모르는 코드는 '대비 안 함').
const REASON: Record<string, string> = {
  candidate_period_unknown: "후보 기간 확인 불가",
  kodex200_start_price_missing: "KODEX 200 시작 가격 없음",
  kodex200_end_price_missing: "KODEX 200 끝 가격 없음",
};
const PERIOD_CODE: Record<PeriodKey, string> = { one_month: "1m", three_month: "3m" };
const PERIOD_LABEL: Record<string, string> = { "1m": "1개월", "3m": "3개월" };
const NO_PRICE_CHECK = "가격 상태 대조 기록 없음";
const PRICE_DIFFERS = "대비 안 함(가격 상태 다름/모름)";

function obj(v: unknown): Obj | null {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function strs(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && x.trim().length > 0) : [];
}

function objs(v: unknown): Obj[] {
  return Array.isArray(v) ? v.map(obj).filter((x): x is Obj => x !== null) : [];
}

function pct(v: number | null): string {
  return v !== null ? `${v.toFixed(2)}%` : "확인 불가";
}

function pp(v: number): string {
  const s = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${s}${Math.abs(v).toFixed(2)}%p`;
}

function span(start: string | null, end: string | null): string {
  return start || end ? `${md(start)} → ${md(end)}` : "기간 확인 불가";
}

interface Differs {
  value: number | null;
  start: string | null;
  end: string | null;
}

interface PeriodView {
  value: number | null;
  start: string | null;
  end: string | null;
  differs: boolean;
  kodex: number | null;
  diff: number | null;
  provisional: boolean;
  note: string;
}

// 저장한 끝 가격(날짜 · 상태) — 30행(티커별) · KODEX 200. 칸이 없으면 null(대조 기록 없음).
interface EndPrice {
  date: string | null;
  state: string;
}
interface PriceStates {
  rows: Map<string, EndPrice>;
  kodex: EndPrice | null;
}

function endPrice(v: unknown): EndPrice | null {
  const o = obj(v);
  return o ? { date: str(o.date), state: str(o.state) ?? "unknown" } : null;
}

function priceStatesOf(v: unknown): PriceStates | null {
  const o = obj(v);
  if (!o) return null;
  const rows = new Map<string, EndPrice>();
  for (const [t, p] of Object.entries(obj(o.rows) ?? {})) {
    const e = endPrice(p);
    if (e) rows.set(t, e);
  }
  return { rows, kodex: endPrice(o.kodex200) };
}

// PLAN I-8 — 두 끝 가격의 날짜가 기간 끝과 같고 상태가 확인돼 같을 때만 대비(둘 다 장중 = 잠정) · 아니면 대비 안 함.
function priceGate(row: EndPrice | undefined, kodex: EndPrice | null, end: string | null): "ok" | "provisional" | "no" {
  if (!row || !kodex || !end || row.date !== end || kodex.date !== end) return "no";
  if (row.state === "unknown" || row.state !== kodex.state) return "no";
  return row.state === "intraday" ? "provisional" : "ok";
}

// 한 후보 · 한 기간 — 저장 행의 값 · 실제 기간 · 같은 기간 KODEX 200(기간 다름이면 데이터 품질 칸의 값 · 실제 기간 · 대비 안 함).
// 가격 상태를 저장한 기록이면 저장 비교 칸이 ok 여도 I-8 을 다시 적용한다(ps = null · 대조 기록 없음 = 저장 비교 그대로).
function periodView(
  c: DecisionCandidateSnapshot,
  key: PeriodKey,
  differs: Map<string, Differs>,
  ps: PriceStates | null,
): PeriodView {
  const item = c.same_period_kodex200?.[key] ?? null;
  const own = key === "one_month" ? c.one_month_return_pct : c.three_month_return_pct;
  const d = differs.get(`${c.ticker ?? ""}|${PERIOD_CODE[key]}`) ?? null;
  const value = num(own) ?? d?.value ?? null;
  const saved = !d && value !== null && item?.status === "ok" && num(item.kodex200_return_pct) !== null;
  const gate = saved && ps ? priceGate(ps.rows.get(c.ticker ?? ""), ps.kodex, str(item?.end_date)) : "ok";
  const ok = saved && gate !== "no";
  let note = "";
  if (d) note = "기간 다름 · 국내시장 대비 안 함";
  else if (value === null) note = "값 없음";
  else if (!item) note = NONE;
  else if (saved && !ok) note = PRICE_DIFFERS;
  else if (!ok) note = REASON[item.reason ?? ""] ?? "대비 안 함";
  return {
    value,
    start: d?.start ?? str(item?.start_date) ?? null,
    end: d?.end ?? str(item?.end_date) ?? null,
    differs: d !== null,
    kodex: ok ? num(item?.kodex200_return_pct) : null,
    diff: ok ? num(item?.diff_pctp) : null,
    provisional: ok && gate === "provisional",
    note,
  };
}

function kodexText(p: PeriodView): string {
  if (p.kodex === null) return p.note;
  return `${signedPct(p.kodex)}${p.diff !== null ? ` · 차 ${pp(p.diff)}` : ""}${p.provisional ? " · 잠정" : ""}`;
}

// 고른 후보의 저장 R2 한 줄(③ 화면과 같은 모양 — 비교했으면 국내시장 값 · 문구 · 아니면 문구(대비 안 함 사유 포함)).
function savedReturnLine(x: Obj): string {
  const m = obj(x.market);
  const differs = x.status === "period_differs" ? " · 기간 다름" : "";
  const vs = m?.comparable === true ? `${signedPct(num(m.value_pct))} · ${str(x.phrase) ?? "-"}` : (str(x.phrase) ?? "확인 불가");
  const label = PERIOD_LABEL[str(x.period) ?? ""] ?? "기간 확인 불가";
  return `${label} ${signedPct(num(x.value_pct))}(${span(str(x.start), str(x.end))}${differs}) · 같은 기간 국내시장(KODEX 200) ${vs}`;
}

function KodexHead({ ps }: { ps: PriceStates | null }) {
  return (
    <th>
      같은 기간 KODEX 200
      {ps ? null : <div className="wrs-sub">{NO_PRICE_CHECK}</div>}
    </th>
  );
}

function ValueCell({ p, common }: { p: PeriodView; common: Obj | null }) {
  return (
    <>
      <div>{signedPct(p.value)}</div>
      <div className="wrs-sub">
        {span(p.start, p.end)}
        {p.differs
          ? ` · 기간 다름${common ? `(공통 ${span(str(common.start), str(common.end))})` : ""}`
          : ""}
      </div>
    </>
  );
}

function productLines(product: Obj | null): string[] {
  if (!product) return [`상품 정보 — ${NONE}`];
  const csv = obj(product.csv);
  const file = str(csv?.asof) ? ` (KRX 공식 기준정보 ${str(csv?.asof)} 파일)` : "";
  if (product.found !== true) {
    const why = str(product.missing_reason) ?? "공식 기준정보에 없음";
    return [product.kind === "stock" ? why : `${why} — 확인 불가${file}`];
  }
  const v = (k: string) => str(product[k]) ?? "확인 불가";
  const feeRaw = str(product.fee_pct);
  const fee = feeRaw !== null && Number.isFinite(Number(feeRaw)) ? `${Number(feeRaw)}%` : (feeRaw ?? "확인 불가");
  return [
    `공식 기초지수 ${v("index_name")} · 지수산출기관 ${v("index_provider")} · 투자 대상 ${v("market")} · ${v("asset")}`,
    `상품 구조 ${v("multiple")} · ${v("replication")} · 총보수 ${fee}${file}`,
  ];
}

function constituentLines(cons: Obj | null): string[] {
  if (!cons) return [`구성 요약 — ${NONE}`];
  const out: string[] = [];
  const top = objs(cons.top_stocks);
  if (top.length > 0) {
    const names = top.map((t) => `${str(t.name) ?? "-"} ${pct(num(t.weight_pct))}`);
    out.push(`주요 편입(주식) ${names.join(" · ")} → 상위 ${top.length}개 합 ${pct(num(cons.top3_sum_pct))}`);
  }
  out.push(str(cons.line) ?? str(cons.state_label) ?? `구성 상태 — ${NONE}`);
  return out;
}

type Parsed = { phase: "loading" } | { phase: "error"; message: string } | { phase: "ok"; view: WeeklyLastRecord };

// 읽기 실패 사유 — 서버 한국어 detail(404 · 503) 그대로 · 그 밖(네트워크 등)은 일반 안내(영어 오류 글은 보이지 않음).
function failText(e: unknown): string {
  const body = e instanceof ApiRequestError ? e.body : null;
  const detail = body && typeof body === "object" ? (body as Obj).detail : null;
  return typeof detail === "string" && detail.trim() ? detail : "서버에 연결하지 못했습니다";
}

// 저장 원문을 나눈 결과(기록 id 하나 · 늦게 온 앞 기록 응답은 버림).
function useParsedAnswers(id: string): Parsed {
  const [st, setSt] = useState<{ id: string; parsed: Parsed }>({ id, parsed: { phase: "loading" } });
  useEffect(() => {
    let alive = true;
    fetchWeeklyRecordReview(id).then(
      (view) => alive && setSt({ id, parsed: { phase: "ok", view } }),
      (e: unknown) => alive && setSt({ id, parsed: { phase: "error", message: failText(e) } }),
    );
    return () => {
      alive = false;
    };
  }, [id]);
  return st.id === id ? st.parsed : { phase: "loading" };
}

function ParsedAnswers({ parsed }: { parsed: Parsed }) {
  if (parsed.phase === "loading") return <div className="wrs-sub">저장한 답을 나누어 읽는 중입니다</div>;
  if (parsed.phase === "error")
    return <div className="wrs-warn">저장한 답을 나누어 읽지 못했습니다 — {parsed.message} · 아래 원문 참고</div>;
  const v = parsed.view;
  if (v.status !== "ok" || !v.compare)
    return <div className="wrs-warn">{v.message ?? "요약 확인 필요"} · 아래 원문 참고</div>;
  return <WeeklyAnswers cmp={v.compare} />;
}

export default function WeeklyReviewSnapshot({ detail }: { detail: DecisionSessionDetail }) {
  const parsed = useParsedAnswers(detail.id);
  const dq = obj(detail.data_quality_snapshot);
  const cs = obj(detail.constituent_snapshot);
  const ov = obj(detail.overlap_snapshot);
  const cond = obj(dq?.condition);
  const common = obj(dq?.common_periods);
  const sel = obj(dq?.selected) ?? obj(cs?.selected);
  const selTicker = str(sel?.ticker);
  const ps = priceStatesOf(dq?.price_states);
  const savedReturns = objs(sel?.returns);

  const differs = new Map<string, Differs>();
  for (const d of objs(dq?.period_differs_values)) {
    const t = str(d.ticker);
    const per = str(d.period);
    if (t && per) differs.set(`${t}|${per}`, { value: num(d.value_pct), start: str(d.start), end: str(d.end) });
  }
  const lack = new Map<string, string[]>();
  for (const l of objs(dq?.lack)) {
    const t = str(l.ticker);
    if (t) lack.set(t, strs(l.lack));
  }
  const evList = dq?.evidence_list;
  const evidence: unknown[] | null = Array.isArray(evList) ? evList : null;
  const answered = AIS.filter((a) => (detail[a.key] ?? "").trim().length > 0);
  const missing = AIS.filter((a) => !answered.includes(a));
  const selRow = selTicker ? detail.candidate_snapshot.find((c) => c.ticker === selTicker) ?? null : null;
  const verdict = verdictText(detail.source_screen, detail.user_verdict);

  return (
    <div className="wrs" data-testid="wrs">
      <div className="wrs-head" data-testid="wrs-head">
        저장 {kstDateTimeLabel(detail.created_at)} · 원자료 기준일 {detail.asof} · 고른 후보{" "}
        {sel ? `${str(sel.name) ?? "-"}(${selTicker ?? "-"})` : "없음"} · 사용자 판단 {verdict} · AI 답{" "}
        {answered.length}개{answered.length === 1 ? "(한 의견)" : ""}
      </div>
      <div className="wrs-note">
        당시 검토 — 저장한 값만 보입니다(다시 계산 · 지금 자료 조회 없음 · 이후 자료 갱신은 이 기록을 바꾸지 않음) · 저장
        시각과 원자료 기준일은 다른 값 · 오늘 시세 · 수집 시각은 이 기록에 남은 값만(아래 인용 근거 · 접힌 시장 근거 칸)
      </div>

      <section className="wrs-sec" data-testid="wrs-cond">
        <div className="wrs-title">검토 조건</div>
        <div>{str(cond?.line) ?? `${NONE} — 아래 질문 원문 첫 줄 참고`}</div>
        {common ? (
          <div className="wrs-sub">
            공통 기간 1개월 {span(str(obj(common.one_month)?.start), str(obj(common.one_month)?.end))} · 3개월{" "}
            {span(str(obj(common.three_month)?.start), str(obj(common.three_month)?.end))}
          </div>
        ) : null}
      </section>

      <details className="wrs-box wrs-fold" open data-testid="wrs-candidates">
        <summary>
          후보 {detail.candidate_snapshot.length}개 — 순위 · 1 · 3개월 · 같은 기간 국내시장(KODEX 200) · 실제 기간
        </summary>
        <div className="wr-table-wrap">
          <table className="wr-table">
            <thead>
              <tr>
                <th>순위</th>
                <th>ETF</th>
                <th>1개월(실제 기간)</th>
                <KodexHead ps={ps} />
                <th>3개월(실제 기간)</th>
                <KodexHead ps={ps} />
              </tr>
            </thead>
            <tbody>
              {detail.candidate_snapshot.map((c, i) => {
                const p1 = periodView(c, "one_month", differs, ps);
                const p3 = periodView(c, "three_month", differs, ps);
                const picked = selTicker !== null && c.ticker === selTicker;
                const lk = lack.get(c.ticker ?? "") ?? [];
                return (
                  <tr
                    key={`${c.ticker ?? "x"}-${i}`}
                    data-ticker={c.ticker ?? ""}
                    className={picked ? "wr-picked wrs-picked" : undefined}
                  >
                    <td className="wr-num">{c.rank ?? i + 1}</td>
                    <td>
                      {c.name ?? "-"} <span className="wrs-sub">{c.ticker ?? "-"}</span>
                      {picked ? <div className="wrs-sub">✓ 고른 후보</div> : null}
                      {lk.length > 0 ? <div className="wrs-lack">자료 부족: {lk.join(" · ")}</div> : null}
                    </td>
                    <td className="wr-num">
                      <ValueCell p={p1} common={obj(common?.one_month)} />
                    </td>
                    <td>{kodexText(p1)}</td>
                    <td className="wr-num">
                      <ValueCell p={p3} common={obj(common?.three_month)} />
                    </td>
                    <td>{kodexText(p3)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>

      <section className="wrs-sec" data-testid="wrs-selected">
        <div className="wrs-title">고른 후보 — 어떤 상품인가 · 실제로 올랐나</div>
        {sel ? (
          <>
            <div>
              <b>
                {str(sel.name) ?? "-"}({selTicker ?? "-"})
              </b>
              {num(sel.rank) !== null ? ` · 1개월 상위 ${num(sel.rank)}위` : ""}
            </div>
            {productLines(obj(cs?.product)).map((l, i) => (
              <div key={i}>{l}</div>
            ))}
            {constituentLines(obj(cs?.constituents)).map((l, i) => (
              <div key={i} className="wrs-sub">
                {l}
              </div>
            ))}
            {savedReturns.length > 0 ? (
              savedReturns.map((x, i) => (
                <div key={i} data-testid="wrs-selected-return">
                  {savedReturnLine(x)}
                </div>
              ))
            ) : selRow ? (
              (["one_month", "three_month"] as PeriodKey[]).map((k) => {
                const p = periodView(selRow, k, differs, ps);
                return (
                  <div key={k}>
                    {k === "one_month" ? "1개월" : "3개월"} {signedPct(p.value)}({span(p.start, p.end)}
                    {p.differs ? " · 기간 다름" : ""}) · 같은 기간 국내시장(KODEX 200) {kodexText(p)}
                    {ps ? "" : ` · ${NO_PRICE_CHECK}`}
                  </div>
                );
              })
            ) : (
              <div className="wrs-sub">1 · 3개월 — 고른 후보가 저장한 후보 목록에 없음</div>
            )}
          </>
        ) : (
          <div className="wrs-sub">고른 후보 없음(목록만 넘긴 기록)</div>
        )}
      </section>

      <section className="wrs-sec" data-testid="wrs-overlap">
        <div className="wrs-title">내 보유에 무엇이 겹치나 · 확인 범위</div>
        {ov && Object.keys(ov).length > 0 ? (
          <>
            {strs(ov.warn_lines).map((l, i) => (
              <div key={i} className="wrs-warn">
                {l}
              </div>
            ))}
            {strs(ov.lines).map((l, i) => (
              <div key={i}>{l}</div>
            ))}
            {str(ov.date_line) ? <div className="wrs-sub">{str(ov.date_line)}</div> : null}
            <div className="wrs-sub">내 보유 평가액 기준 노출 — 후보끼리 중복률과 다른 값</div>
          </>
        ) : (
          <div className="wrs-sub">{NONE}(겹침을 저장하지 않은 기록)</div>
        )}
      </section>

      <section className="wrs-sec" data-testid="wrs-evidence">
        <div className="wrs-title">인용 근거(저장한 근거 목록)</div>
        {evidence === null ? (
          <div className="wrs-sub">{NONE} — 아래 질문 원문 참고</div>
        ) : evidence.length === 0 ? (
          <div className="wrs-sub">저장한 근거 목록이 비어 있음 — 아래 질문 원문 참고</div>
        ) : (
          evidence.map((raw, i) => {
            const e = obj(raw);
            const no = num(e?.no);
            const text = typeof raw === "string" ? raw : (str(e?.text) ?? "-");
            return <div key={i}>{no !== null ? `[근거 ${no}] ${text}` : text}</div>;
          })
        )}
      </section>

      <section className="wrs-sec" data-testid="wrs-ai">
        <div className="wrs-title">AI 추가 확인 · 의견 대조</div>
        <div className="wrs-sub" data-testid="wrs-ai-note">
          저장한 질문 · 답 원문을 다시 읽어 나눈 결과입니다(시장 자료 다시 계산 없음 · 해석 규칙이 바뀌면 나눈 모양도 바뀔 수
          있음 · 원문은 아래 접힌 칸) · AI 가 답에 적은 확인 시각 · 출처는 위 저장 시각과 다른 값 · AI 의견이며 결정이 아닙니다
        </div>
        <div data-testid="wrs-ai-parsed">
          <ParsedAnswers parsed={parsed} />
        </div>
        {answered.map((a) => (
          <details key={a.key} className="wrs-fold" data-ai={a.label}>
            <summary>{a.label} 답 원문</summary>
            <pre className="decision-pre">{detail[a.key]}</pre>
          </details>
        ))}
        {missing.length > 0 ? <div className="wrs-sub">답 없음: {missing.map((a) => a.label).join(" · ")}</div> : null}
      </section>

      <section className="wrs-sec" data-testid="wrs-verdict">
        <div className="wrs-title">사용자 판단</div>
        <div>
          <b>{verdict}</b>
        </div>
        <div>메모 {detail.user_memo.trim() ? detail.user_memo : <span className="wrs-sub">비어 있음</span>}</div>
        <div>
          다음 확인{" "}
          {detail.next_checks.length > 0 ? (
            detail.next_checks.join(" · ")
          ) : (
            <span className="wrs-sub">비어 있음</span>
          )}
        </div>
        <div className="wrs-sub">메모 · 다음 확인이 비어 있어도 판단 기록은 유효합니다</div>
      </section>
    </div>
  );
}
