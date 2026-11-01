"use client";

// POC6-14 — 「ML 실험」 맨 위 「전향 ML 비교 · 연구」 카드(설계 V1 · PLAN 판정 2026-10-30 · 사용자 목업 확인 2026-10-30).
//
// 06 전향 기록을 GET /ml/forward-comparison 으로 읽기만 한다(실행 · 학습 · 보고 생성 · 매수/매도 판단 0).
// 기존 「ML 실험」 카드 부품(helper · ml-readiness-badge · market-topn-table · message)과 기존 ? 도움말(HelpPopover).
// 기준일 바꾸기 · 다시 불러오기 중 늦게 온 이전 응답은 버린다(요청 순번). [복사] = 지금 화면에 그린 응답에서만.

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchForwardComparison,
  type ForwardComparisonResponse,
  type ForwardRow,
} from "@/lib/api";
import HelpPopover from "../holdings_risk_evidence/HelpPopover";
import ForwardCompareReport from "./ForwardCompareReport";
import {
  HELP_PARAGRAPHS,
  METHODS,
  actualLong,
  actualShort,
  cardNotices,
  copyText,
  kstTime,
  methodLong,
  methodShort,
  runTime,
  spanText,
} from "./forwardText";

type Load =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: ForwardComparisonResponse };

const NUM: React.CSSProperties = { textAlign: "right", fontVariantNumeric: "tabular-nums" };
const LINE: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "4px 10px",
  alignItems: "center",
  fontSize: 14,
  margin: "6px 0 4px",
};
const MUTED: React.CSSProperties = { color: "var(--muted)" };
const PROBLEM = new Set(["DUE_DATA_MISSING", "PENDING_CALENDAR", "DATA_CHECK_REQUIRED", "CHECK_REQUIRED"]);

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    if (e.httpStatus === 404) return "선택한 기준일 기록 없음 — 다시 불러오기로 목록을 새로 읽어 주세요";
    return `불러오기 실패: ${e.message}`;
  }
  return `불러오기 실패: ${(e as Error)?.message ?? String(e)}`;
}

export default function ForwardComparisonCard() {
  const [state, setState] = useState<Load>({ phase: "loading" });
  const [open, setOpen] = useState<string | null>(null);
  const [copy, setCopy] = useState<{ ticker: string; ok: boolean } | null>(null);
  const seq = useRef(0);

  const run = useCallback((d: string | null) => {
    const mine = ++seq.current;
    fetchForwardComparison(d ?? undefined).then(
      (data) => {
        if (mine === seq.current) setState({ phase: "ready", data });
      },
      (e: unknown) => {
        if (mine === seq.current) setState({ phase: "error", message: describeError(e) });
      },
    );
  }, []);

  useEffect(() => {
    run(null);
  }, [run]);

  const reload = useCallback(
    (d: string | null) => {
      setState({ phase: "loading" });
      setOpen(null);
      setCopy(null);
      run(d);
    },
    [run],
  );

  const doCopy = useCallback((data: ForwardComparisonResponse, row: ForwardRow) => {
    const text = copyText(data, row);
    if (!navigator.clipboard?.writeText) {
      setCopy({ ticker: row.ticker, ok: false });
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => setCopy({ ticker: row.ticker, ok: true }),
      () => setCopy({ ticker: row.ticker, ok: false }),
    );
  }, []);

  const current = state.phase === "ready" ? (state.data.selected_D ?? null) : null;

  return (
    <div className="card">
      <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        전향 ML 비교 · 연구
        <HelpPopover label="전향 ML 비교 · 연구 도움말" paragraphs={HELP_PARAGRAPHS} />
      </h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        POC6-06 고정 연구 표본의 전향 D20 예측(네 방법)과 저장된 성숙 결과 · 비교 보고를 읽기만 합니다. 학습 · 예측
        · 보고 생성 · 매수/매도 판단 0건. 기록은 맥북 정기 실행(06 run)으로만 쌓입니다.
      </p>
      {state.phase === "loading" && <div className="message info">불러오는 중...</div>}
      {state.phase === "error" && (
        <>
          <div className="message error">{state.message}</div>
          <button onClick={() => reload(null)}>다시 불러오기</button>
        </>
      )}
      {state.phase === "ready" && (
        <Body
          data={state.data}
          open={open}
          copy={copy}
          onToggle={(t) => {
            setOpen((cur) => (cur === t ? null : t));
            setCopy(null);
          }}
          onSelect={(d) => reload(d)}
          onReload={() => reload(current)}
          onCopy={doCopy}
        />
      )}
    </div>
  );
}

function Body({
  data,
  open,
  copy,
  onToggle,
  onSelect,
  onReload,
  onCopy,
}: {
  data: ForwardComparisonResponse;
  open: string | null;
  copy: { ticker: string; ok: boolean } | null;
  onToggle: (ticker: string) => void;
  onSelect: (d: string) => void;
  onReload: () => void;
  onCopy: (data: ForwardComparisonResponse, row: ForwardRow) => void;
}) {
  const label = <span className="ml-readiness-badge ml-readiness-missing">{data.label}</span>;
  if (data.status !== "OK") {
    const o = data.other;
    const box =
      data.status === "NO_RECORDS" ? (
        <div className="message info">
          공개 확인된 연구 기록 없음 — {data.message ?? "기록 없음"}
          {o && o.unconfirmed_forward_records + o.diagnostic_entries + o.supplementary_entries > 0
            ? ` · 마감 뒤 확인 ${o.unconfirmed_forward_records}개 · 진단 ${o.diagnostic_entries}행 · 부가 ${o.supplementary_entries}행은 성과 · 표본에 넣지 않습니다.`
            : ""}{" "}
          이 화면은 실행 · 소급을 하지 않습니다.
        </div>
      ) : (
        <div className="message error">
          불러오기 실패 · 확인 필요 — {data.message ?? "사유 미기록"}. 숫자를 보여 주지 않습니다.
        </div>
      );
    return (
      <>
        <div style={LINE}>{label}</div>
        {box}
        <button onClick={onReload}>다시 불러오기</button>
      </>
    );
  }
  const b = data.basis!;
  const rows = data.rows ?? [];
  const mv = b.model_versions;
  const rr = b.record_runs;
  const mt = b.maturity;
  const matText = !mt
    ? "이 기준일의 성숙 평가 상태 기록이 아직 없습니다"
    : mt.runs.length === 1
      ? `${runTime(mt.runs[0])} 회차`
      : `여러 회차(${mt.runs.length}) · ${spanText(mt.at)}`;
  return (
    <>
      <div style={LINE}>
        {label}
        <span>
          고정 연구 표본 <b>{data.cohort?.size ?? "미확인"}</b>종 · 공개 확인된 기준일 <b>{data.dates?.length ?? 0}</b>개
        </span>
      </div>
      <div style={{ ...LINE, margin: "10px 0 4px", gap: 10 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
          기준일
          <select
            value={data.selected_D ?? ""}
            onChange={(e) => onSelect(e.target.value)}
            style={{ height: 40, fontSize: 14, padding: "0 10px" }}
          >
            {(data.dates ?? []).map((x) => (
              <option key={x.D} value={x.D}>
                {x.D} ({x.primary_rows}종)
              </option>
            ))}
          </select>
        </label>
        <button onClick={onReload}>다시 불러오기</button>
      </div>
      <div style={LINE}>
        <span>
          <span style={MUTED}>기준일</span> <b>{data.selected_D}</b>
        </span>
        <span>
          · <span style={MUTED}>공개 확인</span> <b>{spanText(b.visible_by)}</b>
        </span>
        <span>
          · <span style={MUTED}>입력 확정</span> <b>{spanText(b.input_cutoff)}</b>
        </span>
        <span>
          · <span style={MUTED}>기록 회차</span>{" "}
          <b>{rr.length === 1 ? `${runTime(rr[0])} 회차` : `여러 회차(${rr.length}) — 행 상세에서 확인`}</b>
        </span>
        <span>
          · <span style={MUTED}>모델 판</span>{" "}
          <b>{mv.length === 1 ? mv[0] : `여러 판(${mv.length}) — 행 상세에서 확인`}</b>
        </span>
        <span>
          · <span style={MUTED}>결과 상태 출처</span> <b>{matText}</b>
        </span>
      </div>
      {/* 카드 경고도 복사문과 같은 함수(cardNotices)에서 */}
      {cardNotices(data).map((n) => (
        <div key={n.text} className={`message ${n.level}`}>
          {n.text}
        </div>
      ))}
      <div style={{ overflowX: "auto" }}>
        <table className="market-topn-table">
          <thead>
            <tr>
              <th rowSpan={2} aria-label="펼치기" />
              <th rowSpan={2}>종목</th>
              <th colSpan={4} style={{ textAlign: "center" }}>
                D20 예측(%) · 범위 제한 뒤
              </th>
              <th rowSpan={2} style={NUM}>
                실제 D20(%)
                <br />· 결과 상태
              </th>
            </tr>
            <tr>
              {METHODS.map(([k, name]) => (
                <th key={k} style={NUM}>
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <RowView
                key={r.ticker}
                data={data}
                row={r}
                isOpen={open === r.ticker}
                copy={copy?.ticker === r.ticker ? copy : null}
                onToggle={onToggle}
                onCopy={onCopy}
              />
            ))}
          </tbody>
        </table>
      </div>
      <p className="helper">
        D20 = 다음 20거래일 종가 중 가장 깊은 하락(0 이하) · 연구 추정 · 매매 수익률 아님 · 정렬 = 티커 순. 행을 누르면 그
        아래에 근거와 [복사]가 열립니다.
      </p>
      <ForwardCompareReport data={data} />
    </>
  );
}

function RowView({
  data,
  row,
  isOpen,
  copy,
  onToggle,
  onCopy,
}: {
  data: ForwardComparisonResponse;
  row: ForwardRow;
  isOpen: boolean;
  copy: { ticker: string; ok: boolean } | null;
  onToggle: (ticker: string) => void;
  onCopy: (data: ForwardComparisonResponse, row: ForwardRow) => void;
}) {
  const name = (
    <td>
      <b style={{ fontVariantNumeric: "tabular-nums" }}>{row.ticker}</b>
      <span style={{ display: "block", color: "var(--muted)", fontSize: 12 }}>{row.name ?? "이름 미확인"}</span>
    </td>
  );
  if (!row.primary) {
    return (
      <tr>
        <td style={{ width: 28, textAlign: "center", color: "var(--muted)" }}>·</td>
        {name}
        <td colSpan={5} style={{ color: "var(--muted)", fontSize: 12 }}>
          이 기준일 주 기록 없음{row.why ? ` — 입력 상태 ${row.why}` : ""}
        </td>
      </tr>
    );
  }
  const a = row.actual;
  const det = row.detail!;
  return (
    <Fragment>
      <tr
        onClick={() => onToggle(row.ticker)}
        style={{ cursor: "pointer", background: isOpen ? "rgba(37, 99, 235, 0.06)" : undefined }}
      >
        <td style={{ width: 28, textAlign: "center" }}>
          <button
            type="button"
            className="link-button"
            aria-expanded={isOpen}
            aria-label={`${row.ticker} 상세`}
            onClick={(e) => {
              e.stopPropagation();
              onToggle(row.ticker);
            }}
            style={{ width: 40, height: 40, minHeight: 40, padding: 0, margin: "-8px 0", background: "transparent", color: "var(--muted)" }}
          >
            {isOpen ? "▾" : "▸"}
          </button>
        </td>
        {name}
        {METHODS.map(([k]) => {
          const m = row.methods?.[k];
          return (
            <td key={k} style={NUM}>
              {m && m.status !== "OK" ? (
                <span className="ml-readiness-badge ml-readiness-partial">{methodShort(m)}</span>
              ) : (
                <>
                  {methodShort(m)}
                  {m?.retried_at && (
                    <span style={{ display: "block", color: "var(--muted)", fontSize: 11 }}>재시도로 채움</span>
                  )}
                </>
              )}
            </td>
          );
        })}
        <td style={{ ...NUM, minWidth: 118 }}>
          {a?.state === "MATURED" ? (
            actualShort(a)
          ) : (
            <span className={`ml-readiness-badge ${PROBLEM.has(a?.state ?? "") ? "ml-readiness-partial" : "ml-readiness-missing"}`}>
              {actualShort(a)}
            </span>
          )}
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={7} style={{ background: "var(--bg)", padding: "12px 14px" }}>
            <div
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 8 }}
            >
              <b>
                {row.ticker} {row.name ?? ""} · 기준일 {data.selected_D}
              </b>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button type="button" className="btn-md" onClick={() => onCopy(data, row)}>
                  복사
                </button>
                {copy && (
                  <span style={{ color: copy.ok ? "var(--ok)" : "var(--danger)", fontSize: 13, fontWeight: 600 }}>
                    {copy.ok ? "복사했습니다" : "복사하지 못했습니다"}
                  </span>
                )}
              </span>
            </div>
            <dl
              style={{ display: "grid", gridTemplateColumns: "max-content minmax(0, 1fr)", gap: "4px 14px", fontSize: 13, margin: 0 }}
            >
              <dt style={MUTED}>기록 회차</dt>
              <dd style={{ margin: 0 }}>
                {det.run_id} · 쓰기 시작 {kstTime(det.write_started_at)}
              </dd>
              <dt style={MUTED}>공개 확인</dt>
              <dd style={{ margin: 0 }}>
                {kstTime(det.visible_by)} (마감 {kstTime(det.close_cutoff_at).slice(0, 16)} 전)
              </dd>
              <dt style={MUTED}>입력 확정</dt>
              <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                {kstTime(det.input_cutoff)} · OCI 수집 {kstTime(det.input.observed_at)} · 보관{" "}
                {kstTime(det.input.available_at)} · 묶음 {(det.input.object ?? "미확인").slice(0, 12)}…
              </dd>
              <dt style={MUTED}>모델 판</dt>
              <dd style={{ margin: 0 }}>{det.model_version}</dd>
              {METHODS.map(([k, label]) => (
                <Fragment key={k}>
                  <dt style={MUTED}>{label}</dt>
                  <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{methodLong(row.methods?.[k])}</dd>
                </Fragment>
              ))}
              <dt style={MUTED}>실제 D20</dt>
              <dd style={{ margin: 0 }}>{actualLong(a)}</dd>
            </dl>
          </td>
        </tr>
      )}
    </Fragment>
  );
}
