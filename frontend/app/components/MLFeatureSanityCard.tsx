"use client";

// POC2 ML Feature Sanity Check (2026-06-08) — DataStatusView 의 ML readiness 아래
// 표시되는 sanity 요약 카드.
//
// 책임 (지시문 §4.7):
// - GET /ml/feature-sanity/latest 1회 조회 (외부 source 호출 X / 재계산 X).
// - sanity_status / latest asof / checked ticker / warning/error 수 요약.
// - 샘플 ETF 5~10건의 return/excess/volatility/drawdown/NAV 괴리율 표시.
// - 본 카드는 데이터 품질 표시 영역. 매수·매도 / 위험 threshold / 조정장 판정 0건.

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlFeatureSanityLatest,
  type MlFeatureSanityResponse,
  type MlSanitySampleRow,
  type MlSanityStatus,
} from "@/lib/api";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MlFeatureSanityResponse };

const DASH = "-";

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function statusBadgeClass(status: MlSanityStatus | undefined): string {
  if (status === "ok") return "ml-readiness-badge ml-readiness-available";
  if (status === "warn") return "ml-readiness-badge ml-readiness-partial";
  if (status === "error") return "ml-readiness-badge ml-readiness-missing";
  return "ml-readiness-badge ml-readiness-missing";
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return value.toFixed(4);
}

export default function MLFeatureSanityCard() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMlFeatureSanityLatest()
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
      <h2>ML feature sanity check</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        본 카드는 ML baseline v0 입력 직전의 데이터 품질 검산 결과입니다 — coverage
        / 계산 정합성 / NAV join / 조정장 전조 proxy null 비율 4종. ML 모델 / 위험
        threshold / 매수·매도 판단 0건. 갱신은 CLI{" "}
        <code>python scripts/check_ml_feature_sanity.py</code>로만 수행됩니다.
      </p>
      {state.phase === "loading" && (
        <div className="message info">불러오는 중...</div>
      )}
      {state.phase === "error" && (
        <div className="message error">{state.message}</div>
      )}
      {state.phase === "ready" && <SanityBody data={state.data} />}
    </div>
  );
}

function SanityBody({ data }: { data: MlFeatureSanityResponse }) {
  if (data.status === "error") {
    return (
      <div className="message error">
        sanity snapshot 파일이 손상되어 읽을 수 없습니다.{" "}
        {data.message ? (
          <div style={{ marginTop: 4 }}>{data.message}</div>
        ) : null}
      </div>
    );
  }
  if (data.status === "empty" || !data.snapshot) {
    return (
      <div className="message info">
        sanity snapshot 미생성. 좌측 CLI 안내 메시지를 따라 1회 실행하면 본 영역에
        검산 결과가 표시됩니다.{" "}
        {data.message ? (
          <div style={{ marginTop: 4, color: "var(--muted)" }}>
            {data.message}
          </div>
        ) : null}
      </div>
    );
  }
  const snap = data.snapshot;
  const cov = snap.coverage_checks;
  const calc = snap.calculation_checks;
  const nav = snap.nav_join_checks;
  const risk = snap.risk_proxy_checks;

  return (
    <>
      <p style={{ marginBottom: 8 }}>
        <span className={statusBadgeClass(snap.sanity_status)}>
          {snap.sanity_status}
        </span>{" "}
        · latest asof <strong>{snap.feature_asof_range.end ?? DASH}</strong> ·
        거래일 <strong>{snap.feature_asof_range.trading_days ?? DASH}</strong> ·
        ETF row <strong>{snap.etf_feature_row_count.toLocaleString()}</strong> ·
        market risk row <strong>{snap.market_risk_row_count}</strong> · 검산
        ticker <strong>{snap.checked_ticker_count}</strong> · warning{" "}
        <strong>{snap.warnings.length}</strong> · error{" "}
        <strong>{snap.errors.length}</strong>
      </p>
      <table
        className="market-topn-table"
        style={{ marginBottom: 12 }}
      >
        <thead>
          <tr>
            <th>sub-check</th>
            <th style={{ width: 100 }}>status</th>
            <th>주요 지표</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>coverage</td>
            <td>
              <span className={statusBadgeClass(cov?.status as MlSanityStatus)}>
                {String(cov?.status ?? DASH)}
              </span>
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              asof {snap.feature_asof_range.start ?? DASH} →{" "}
              {snap.feature_asof_range.end ?? DASH} · latest match readiness:{" "}
              {String(cov?.["latest_asof_matches_readiness"] ?? DASH)}
            </td>
          </tr>
          <tr>
            <td>calculation</td>
            <td>
              <span className={statusBadgeClass(calc?.status as MlSanityStatus)}>
                {String(calc?.status ?? DASH)}
              </span>
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              warning {(calc?.warnings ?? []).length} · error{" "}
              {(calc?.errors ?? []).length} · 검산 필드{" "}
              {Array.isArray(calc?.["checked_fields"])
                ? (calc?.["checked_fields"] as unknown[]).length
                : DASH}
              종
            </td>
          </tr>
          <tr>
            <td>nav join</td>
            <td>
              <span className={statusBadgeClass(nav?.status as MlSanityStatus)}>
                {String(nav?.status ?? DASH)}
              </span>
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              future_nav_join_count{" "}
              <strong>{String(nav?.["future_nav_join_count"] ?? DASH)}</strong> ·
              unavailable_ratio{" "}
              {String(nav?.["unavailable_ratio"] ?? DASH)} · same_asof{" "}
              {String(nav?.["same_asof_count"] ?? DASH)} · past_latest{" "}
              {String(nav?.["past_latest_count"] ?? DASH)}
            </td>
          </tr>
          <tr>
            <td>risk proxy</td>
            <td>
              <span className={statusBadgeClass(risk?.status as MlSanityStatus)}>
                {String(risk?.status ?? DASH)}
              </span>
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              all-null asof <strong>{String(risk?.["all_null_asof_count"] ?? DASH)}</strong>
              {" "}· warning {(risk?.warnings ?? []).length}
            </td>
          </tr>
        </tbody>
      </table>
      <SampleTable rows={snap.sample_rows} />
      {snap.warnings.length > 0 && (
        <details
          style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--warn)" }}
        >
          <summary>전체 warning {snap.warnings.length}건</summary>
          <ul style={{ marginTop: 4 }}>
            {snap.warnings.slice(0, 50).map((w, i) => (
              <li key={`w-${i}`}>{w}</li>
            ))}
            {snap.warnings.length > 50 && (
              <li>... ({snap.warnings.length - 50}건 추가)</li>
            )}
          </ul>
        </details>
      )}
      {snap.errors.length > 0 && (
        <details
          style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--danger)" }}
          open
        >
          <summary>전체 error {snap.errors.length}건</summary>
          <ul style={{ marginTop: 4 }}>
            {snap.errors.slice(0, 50).map((e, i) => (
              <li key={`e-${i}`}>{e}</li>
            ))}
            {snap.errors.length > 50 && (
              <li>... ({snap.errors.length - 50}건 추가)</li>
            )}
          </ul>
        </details>
      )}
      <p
        className="helper"
        style={{ marginTop: 8, fontSize: "0.78rem" }}
      >
        generated_at: {snap.generated_at} · snapshot: <code>{data.snapshot_path}</code>
      </p>
    </>
  );
}

function SampleTable({ rows }: { rows: MlSanitySampleRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="helper" style={{ fontSize: "0.85rem" }}>
        샘플 ETF 0건 — coverage check 가 ok 가 아닌 상태일 수 있습니다.
      </div>
    );
  }
  return (
    <>
      <h3
        style={{
          fontSize: "0.9rem",
          margin: "8px 0 4px 0",
          color: "var(--muted)",
        }}
      >
        샘플 ETF (latest asof)
      </h3>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th style={{ width: 80 }}>ticker</th>
            <th>name</th>
            <th style={{ textAlign: "right" }}>5d</th>
            <th style={{ textAlign: "right" }}>20d</th>
            <th style={{ textAlign: "right" }}>excess 20d</th>
            <th style={{ textAlign: "right" }}>vol 20d</th>
            <th style={{ textAlign: "right" }}>dd 20d</th>
            <th style={{ textAlign: "right" }}>NAV 괴리</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker}>
              <td>
                <code>{r.ticker}</code>
              </td>
              <td>{r.name ?? DASH}</td>
              <td style={{ textAlign: "right" }}>{fmtPct(r.return_5d)}</td>
              <td style={{ textAlign: "right" }}>{fmtPct(r.return_20d)}</td>
              <td style={{ textAlign: "right" }}>
                {fmtPct(r.excess_return_20d_vs_kodex200)}
              </td>
              <td style={{ textAlign: "right" }}>{fmtNum(r.volatility_20d)}</td>
              <td style={{ textAlign: "right" }}>{fmtPct(r.drawdown_20d)}</td>
              <td style={{ textAlign: "right" }}>
                {fmtPct(r.nav_discount_rate_pct)}
                {r.nav_status && r.nav_status !== "ok" ? (
                  <span
                    style={{ fontSize: "0.75rem", color: "var(--muted)" }}
                  >
                    {" "}
                    ({r.nav_status})
                  </span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
