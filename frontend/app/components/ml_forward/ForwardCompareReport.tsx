"use client";

// POC6-14 — 「전향 ML 비교 · 연구」 카드의 누적 비교(저장된 06 보고를 그대로 · 선택한 기준일의 성적이 아님).
// 보고 상태(PLAN 판정 §5): 선택 D 를 기록한 회차의 보고가 있음 / 아직 없음 / 읽지 못함을 나눈다.
// MAE · 작게 추정한 정도 = 보고의 %p 그대로(다시 계산 · 곱하기 없음) · 비교마다 분모가 달라 순위로 합치지 않는다.

import type { ForwardComparisonResponse, ForwardMethodKey } from "@/lib/api";
import { METHODS, fmtSizePp, kstTime, reportNotices } from "./forwardText";

const NUM: React.CSSProperties = { textAlign: "right", fontVariantNumeric: "tabular-nums" };
const SUB: React.CSSProperties = { display: "block", color: "var(--muted)", fontSize: 12 };

const COMPARISONS: [string, string, ForwardMethodKey[]][] = [
  ["HGB_vs_MEDIAN_RIDGE", "HGB · 중앙값 · Ridge", ["MEDIAN", "RIDGE", "HGB"]],
  ["MLP_CPU_vs_MEDIAN_RIDGE", "MLP(CPU) · 중앙값 · Ridge", ["MEDIAN", "RIDGE", "MLP_CPU"]],
  ["ALL_FOUR", "네 방법 공통", ["MEDIAN", "RIDGE", "HGB", "MLP_CPU"]],
];

// 행이 있는 비교의 값 — null 이면 '-' 가 아니라 확인 필요(06 은 공통 행이 있으면 모든 방법에 값을 쓴다 · r2 F3)
function Filled({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined) return <span style={{ color: "var(--danger)" }}>값 확인 필요</span>;
  return <>{fmtSizePp(v)}</>;
}

function count(v: unknown): string {
  return typeof v === "number" ? String(v) : "미확인";
}

export default function ForwardCompareReport({ data }: { data: ForwardComparisonResponse }) {
  const rep = data.report;
  return (
    <section aria-label="누적 비교">
      <h3 style={{ marginTop: 16 }}>
        누적 비교 — 저장된 보고{" "}
        <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 400 }}>
          (선택한 기준일의 성적이 아님)
        </span>
      </h3>
      {/* 경고 문구는 복사문과 같은 함수(reportNotices)에서 — 화면에 보인 경고는 복사에도 남는다 */}
      {reportNotices(data).map((n) =>
        n.level === "ok" ? (
          <div key={n.text} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14, margin: "6px 0" }}>
            <span className="ml-readiness-badge ml-readiness-available">보고 있음</span>
            <span>{n.text}</span>
          </div>
        ) : (
          <div key={n.text} className={`message ${n.level}`}>
            {n.text}
          </div>
        ),
      )}
      {rep && rep.state !== "NONE" && rep.generated_at ? <ReportBody data={data} /> : null}
    </section>
  );
}

function ReportBody({ data }: { data: ForwardComparisonResponse }) {
  const rep = data.report!;
  const c = rep.counts ?? {};
  const p = rep.predicted_dates;
  const m = rep.matured_dates;
  const by = (c.predicted_by_method ?? {}) as Partial<Record<ForwardMethodKey, number>>;
  const deepRows = COMPARISONS.filter(([key]) => (rep.comparisons?.[key]?.deep.rows ?? 0) > 0);
  return (
    <>
      <p className="helper" style={{ display: "flex", flexWrap: "wrap", gap: "2px 16px" }}>
        <span>보고 {rep.id ?? "미확인"}</span>
        <span>생성 {kstTime(rep.generated_at)}</span>
        <span>
          예측 포함 기준일 {p?.count ?? 0}개{p?.count ? `(${p.first} ~ ${p.last})` : ""}
        </span>
        <span>
          성숙 비교 기준일 {m?.count ? `${m.count}개(${m.first} ~ ${m.last})` : "0개 — 아직 없음"}
        </span>
        <span>
          주 기록 · 성숙 · 대기/미확보 {count(c.primary_records)} · {count(c.matured)} ·{" "}
          {count(c.pending_or_missing)}
        </span>
      </p>
      <div style={{ overflowX: "auto" }}>
        <table className="market-topn-table">
          <thead>
            <tr>
              <th>날짜 균형 MAE(%p) · 같은 행 비교</th>
              {METHODS.map(([k, label]) => (
                <th key={k} style={NUM}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARISONS.map(([key, label, ms]) => {
              const x = rep.comparisons?.[key];
              if (!x || typeof x.rows !== "number" || x.rows <= 0) {
                // 비교 행 0 = 정상 미성숙 · 항목 · 행 수가 없으면 구조 확인 필요(빈 비교로 바꾸지 않음 · r1 F1)
                const empty = typeof x?.rows === "number" && x.rows === 0;
                return (
                  <tr key={key}>
                    <td>
                      {label}
                      <span style={SUB}>비교 행 {x?.rows ?? "미확인"}</span>
                    </td>
                    <td colSpan={4} style={{ color: empty ? "var(--muted)" : "var(--danger)" }}>
                      {empty ? "아직 비교할 결과 없음" : "비교 항목 확인 필요"}
                    </td>
                  </tr>
                );
              }
              return (
                <tr key={key}>
                  <td>
                    {label}
                    <span style={SUB}>
                      비교 행 {x.rows} · 날짜 {x.dates} · 종목 {x.tickers} · 빠진 행 {x.excluded_rows}
                    </span>
                  </td>
                  {METHODS.map(([k]) => (
                    <td key={k} style={NUM}>
                      {ms.includes(k) ? <Filled v={x.mae_pp[k]} /> : "—"}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {deepRows.length > 0 && (
        <div style={{ overflowX: "auto", marginTop: 8 }}>
          <table className="market-topn-table">
            <thead>
              <tr>
                <th>큰 하락 행에서 작게 추정한 정도(%p · 보조)</th>
                {METHODS.map(([k, label]) => (
                  <th key={k} style={NUM}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {deepRows.map(([key, label, ms]) => {
                const dp = rep.comparisons![key].deep;
                return (
                  <tr key={key}>
                    <td>
                      {label}
                      <span style={SUB}>D20 ≤ −8% 행 {dp.rows}</span>
                    </td>
                    {METHODS.map(([k]) => (
                      <td key={k} style={NUM}>
                        {ms.includes(k) ? <Filled v={dp.under_estimate_pp[k]} /> : "—"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="helper">
        {METHODS.map(([k, label]) => `${label} 예측 ${count(by[k])}`).join(" · ")} | 마감 뒤 확인(성과 제외){" "}
        {count(c.unconfirmed_forward_records)} · 진단 {count(c.diagnostic_entries)} · 부가{" "}
        {count(c.supplementary_entries)}
      </p>
      <p className="helper">
        MAE = 날짜마다 공통 행의 |예측 − 실제| 평균(%p)을 다시 날짜 평균. 비교마다 분모가 달라 한 줄 순위로 합치지
        않습니다.
      </p>
    </>
  );
}
