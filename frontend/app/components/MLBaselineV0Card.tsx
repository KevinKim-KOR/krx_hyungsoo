"use client";

// POC2 ML Baseline v0 룩백 검증 카드 (2026-06-11) — DataStatusView 하단 표시.
//
// 책임 (지시문 §12):
// - GET /ml/baseline-v0/latest 1회 조회 (외부 source 호출 X / 재계산 X).
// - 후보 발굴 baseline / 위험 패턴 baseline 의 룩백 검증 결과 요약.
// - 지시문 §12 금지 문구 (매수 후보 / 매도 후보 / 현금비중 확대 / 조정장 확정 /
//   위험 알림) 화면 표시 0건. 허용 문구 (후보 발굴 baseline 검증 결과 /
//   위험 패턴 baseline 검증 결과 / high-risk group 의 이후 drawdown 비교) 만 사용.

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlBaselineV0Latest,
  type MlBaselineStatus,
  type MlBaselineV0Response,
} from "@/lib/api";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MlBaselineV0Response };

const DASH = "-";

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function statusBadgeClass(status: MlBaselineStatus | undefined): string {
  if (status === "ok") return "ml-readiness-badge ml-readiness-available";
  if (status === "warn") return "ml-readiness-badge ml-readiness-partial";
  if (status === "insufficient_history") {
    return "ml-readiness-badge ml-readiness-partial";
  }
  if (status === "error") return "ml-readiness-badge ml-readiness-missing";
  return "ml-readiness-badge ml-readiness-missing";
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function fmtFloat(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return value.toFixed(digits);
}

export default function MLBaselineV0Card() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMlBaselineV0Latest()
      .then((data) => {
        if (!cancelled) setState({ phase: "ready", data });
      })
      .catch((e) => {
        if (!cancelled) setState({ phase: "error", message: describeError(e) });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="card">
      <h2>ML baseline v0 룩백 검증</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        본 카드는 현재 feature dataset 이 과거 구간에서 (1) 후보 발굴 baseline
        검증 결과 / (2) 위험 패턴 baseline 검증 결과를 룩백으로 확인한 영역입니다.
        과거 구간에서 high-risk group 의 이후 drawdown 이 더 컸는지 확인하는
        baseline 입니다. 갱신은 CLI{" "}
        <code>python scripts/run_ml_baseline_v0.py</code> 로만 수행됩니다.
      </p>
      {state.phase === "loading" && (
        <div className="message info">불러오는 중…</div>
      )}
      {state.phase === "error" && (
        <div className="message error">{state.message}</div>
      )}
      {state.phase === "ready" && <BaselineBody data={state.data} />}
    </div>
  );
}

function BaselineBody({ data }: { data: MlBaselineV0Response }) {
  if (data.status === "error") {
    return (
      <div className="message error">
        baseline report 파일이 손상되어 읽을 수 없습니다.
        {data.message ? <div style={{ marginTop: 4 }}>{data.message}</div> : null}
      </div>
    );
  }
  if (data.status === "empty" || !data.report) {
    return (
      <div className="message info">
        baseline 룩백 report 미생성. 좌측 CLI 안내 메시지를 따라 1회 실행하면 본
        영역에 후보 발굴 baseline / 위험 패턴 baseline 룩백 검증 결과가 표시됩니다.
        {data.message ? (
          <div style={{ marginTop: 4, color: "var(--muted)" }}>{data.message}</div>
        ) : null}
      </div>
    );
  }
  const rpt = data.report;
  const cand = rpt.candidate_baseline;
  const risk = rpt.risk_baseline;
  const leak = rpt.leakage_checks;

  return (
    <>
      <p style={{ marginBottom: 8 }}>
        <span className={statusBadgeClass(rpt.status)}>{rpt.status}</span> · feature
        기간 <strong>{rpt.feature_asof_range.start ?? DASH}</strong>~
        <strong>{rpt.feature_asof_range.end ?? DASH}</strong> (거래일{" "}
        <strong>{rpt.feature_asof_range.trading_days ?? DASH}</strong>) · 평가 가능
        거래일 <strong>{rpt.evaluated_asof_range.evaluated_days ?? DASH}</strong>
      </p>

      <h3 style={{ marginTop: 12 }}>후보 발굴 baseline 검증 결과</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>지표</th>
            <th>5d</th>
            <th>10d</th>
            <th>20d</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>top group 평균 future return</td>
            <td>{fmtPct(cand.top_group_avg_future_return?.["5d"])}</td>
            <td>{fmtPct(cand.top_group_avg_future_return?.["10d"])}</td>
            <td>{fmtPct(cand.top_group_avg_future_return?.["20d"])}</td>
          </tr>
          <tr>
            <td>top group 평균 future excess (vs KODEX200)</td>
            <td>{fmtPct(cand.top_group_avg_future_excess_return?.["5d"])}</td>
            <td>{fmtPct(cand.top_group_avg_future_excess_return?.["10d"])}</td>
            <td>{fmtPct(cand.top_group_avg_future_excess_return?.["20d"])}</td>
          </tr>
          <tr>
            <td>universe median future return</td>
            <td>{fmtPct(cand.universe_median_future_return?.["5d"])}</td>
            <td>{fmtPct(cand.universe_median_future_return?.["10d"])}</td>
            <td>{fmtPct(cand.universe_median_future_return?.["20d"])}</td>
          </tr>
          <tr>
            <td>hit rate (excess &gt; 0)</td>
            <td>{fmtFloat(cand.hit_rate?.["5d"])}</td>
            <td>{fmtFloat(cand.hit_rate?.["10d"])}</td>
            <td>{fmtFloat(cand.hit_rate?.["20d"])}</td>
          </tr>
          <tr>
            <td>rank correlation</td>
            <td>{fmtFloat(cand.rank_correlation?.["5d"])}</td>
            <td>{fmtFloat(cand.rank_correlation?.["10d"])}</td>
            <td>{fmtFloat(cand.rank_correlation?.["20d"])}</td>
          </tr>
          <tr>
            <td>단순 baseline: return_20d top quintile avg future return</td>
            <td>
              {fmtPct(
                cand.simple_baselines?.[
                  "simple_return_20d_top_quintile_avg_future_return"
                ]?.["5d"],
              )}
            </td>
            <td>
              {fmtPct(
                cand.simple_baselines?.[
                  "simple_return_20d_top_quintile_avg_future_return"
                ]?.["10d"],
              )}
            </td>
            <td>
              {fmtPct(
                cand.simple_baselines?.[
                  "simple_return_20d_top_quintile_avg_future_return"
                ]?.["20d"],
              )}
            </td>
          </tr>
          <tr>
            <td>단순 baseline: excess_20d top quintile avg future return</td>
            <td>
              {fmtPct(
                cand.simple_baselines?.[
                  "simple_excess_20d_vs_kodex200_top_quintile_avg_future_return"
                ]?.["5d"],
              )}
            </td>
            <td>
              {fmtPct(
                cand.simple_baselines?.[
                  "simple_excess_20d_vs_kodex200_top_quintile_avg_future_return"
                ]?.["10d"],
              )}
            </td>
            <td>
              {fmtPct(
                cand.simple_baselines?.[
                  "simple_excess_20d_vs_kodex200_top_quintile_avg_future_return"
                ]?.["20d"],
              )}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="helper" style={{ marginTop: 4 }}>
        top group = composite rank v0 상위 {(cand.top_group_quantile * 100).toFixed(0)}
        % (사용자 결정). 단순 baseline 2종 = 단순 return_20d / excess_20d
        top quintile (지시문 §7.4). 평가 거래일 {cand.evaluated_days} / ticker{" "}
        {cand.evaluated_ticker_count}.
      </p>

      <h3 style={{ marginTop: 16 }}>위험 패턴 baseline 검증 결과</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>구간</th>
            <th>future KODEX200 return 3d</th>
            <th>5d</th>
            <th>10d</th>
            <th>future market drawdown 5d</th>
            <th>10d</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>high-risk group (상위 1/3 composite)</td>
            <td>{fmtPct(risk.high_risk_group_future_return?.["3d"])}</td>
            <td>{fmtPct(risk.high_risk_group_future_return?.["5d"])}</td>
            <td>{fmtPct(risk.high_risk_group_future_return?.["10d"])}</td>
            <td>{fmtPct(risk.high_risk_group_future_drawdown?.["5d"])}</td>
            <td>{fmtPct(risk.high_risk_group_future_drawdown?.["10d"])}</td>
          </tr>
          <tr>
            <td>low-risk group (하위 1/3)</td>
            <td>{fmtPct(risk.low_risk_group_future_return?.["3d"])}</td>
            <td>{fmtPct(risk.low_risk_group_future_return?.["5d"])}</td>
            <td>{fmtPct(risk.low_risk_group_future_return?.["10d"])}</td>
            <td>{fmtPct(risk.low_risk_group_future_drawdown?.["5d"])}</td>
            <td>{fmtPct(risk.low_risk_group_future_drawdown?.["10d"])}</td>
          </tr>
        </tbody>
      </table>
      <p className="helper" style={{ marginTop: 4 }}>
        과거 구간에서 high-risk group 의 이후 drawdown 이 low-risk 대비 더 컸는지
        확인하는 baseline 입니다. 평가 거래일 {risk.evaluated_days}. universe
        down ratio 5d: high {fmtFloat(risk.high_risk_group_future_down_ratio_5d)}{" "}
        vs low {fmtFloat(risk.low_risk_group_future_down_ratio_5d)}.
      </p>

      <h4 style={{ marginTop: 12 }}>
        단순 baseline 비교 (지시문 §8.4 — composite 와 별도)
      </h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>단순 기준 (top tercile)</th>
            <th>high group future market drawdown 10d</th>
            <th>low group future market drawdown 10d</th>
            <th>high group future KODEX200 return 5d</th>
            <th>low group future KODEX200 return 5d</th>
          </tr>
        </thead>
        <tbody>
          {(
            [
              ["kodex200_return_5d", "5일 시장 수익률 기준 (작을수록 위험)"],
              [
                "drawdown_20d_market_proxy",
                "20일 drawdown 기준 (작을수록 위험)",
              ],
              [
                "etf_universe_down_ratio",
                "시장폭 악화 기준 (down ratio 클수록 위험)",
              ],
            ] as Array<[string, string]>
          ).map(([axis, label]) => {
            const row = risk.simple_baselines?.[axis] as
              | Record<string, number | null>
              | undefined;
            return (
              <tr key={axis}>
                <td>{label}</td>
                <td>
                  {fmtPct(row?.["high_risk_future_market_drawdown_10d"])}
                </td>
                <td>{fmtPct(row?.["low_risk_future_market_drawdown_10d"])}</td>
                <td>
                  {fmtPct(row?.["high_risk_future_kodex200_return_5d"])}
                </td>
                <td>{fmtPct(row?.["low_risk_future_kodex200_return_5d"])}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <details style={{ marginTop: 12 }}>
        <summary>leakage / coverage 검증 세부</summary>
        <ul style={{ marginTop: 4 }}>
          <li>
            future data leakage detected:{" "}
            <strong>
              {String(leak.feature_future_data_leakage_detected)}
            </strong>
          </li>
          <li>
            horizon tail excluded:{" "}
            <strong>{String(leak.target_horizon_short_tail_excluded)}</strong>
          </li>
          <li>
            time order preserved:{" "}
            <strong>{String(leak.time_order_preserved)}</strong>
          </li>
          <li>candidate tail asof count: {leak.candidate_tail_asof_count}</li>
          <li>risk tail asof count: {leak.risk_tail_asof_count}</li>
        </ul>
        {(rpt.warnings?.length ?? 0) > 0 && (
          <div style={{ marginTop: 8 }}>
            <strong>warnings ({rpt.warnings.length}):</strong>
            <ul>
              {rpt.warnings.slice(0, 30).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
        {(rpt.errors?.length ?? 0) > 0 && (
          <div style={{ marginTop: 8 }}>
            <strong>errors ({rpt.errors.length}):</strong>
            <ul>
              {rpt.errors.slice(0, 30).map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}
      </details>
    </>
  );
}
