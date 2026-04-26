"use client";

// 현재 run 의 status / draft_payload 표시 + Approve / Reject + 느린 polling.
// 부모(MainPanel) 가 run state 를 controlled 로 관리한다 (run / setRun prop).
// 폼 입력 부분(GenerateDraft) 은 이 컴포넌트에서 분리됨 — POC2 Step 1 운영
// 진입점은 HoldingsClient, 샘플은 SampleDraftQuickButton 이 담당.

import { useCallback, useEffect, useRef } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  approveRun,
  fetchRun,
  isTerminal,
  rejectRun,
  type Run,
  type RunStatus,
} from "@/lib/api";

const POLL_INTERVAL_MS = 12000;
const MAX_POLL_TICKS = 30;

function humanLabel(status: RunStatus): string {
  switch (status) {
    case "PENDING_APPROVAL":
      return "승인 대기";
    case "DELIVERING":
      return "전달 중";
    case "COMPLETED":
      return "전달 완료";
    case "REJECTED":
      return "거절됨";
    case "FAILED":
      return "실패";
  }
}

function describeApiError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    const detail =
      typeof e.body === "string"
        ? e.body
        : e.body && typeof e.body === "object" && "detail" in e.body
          ? String((e.body as Record<string, unknown>).detail)
          : JSON.stringify(e.body);
    return `요청 실패(HTTP ${e.httpStatus}): ${detail}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

// POC2 Step 1A — 사람이 읽는 형식으로 표시.
// holdings 식별 기준은 백엔드 draft_message.is_holdings_draft 와 동일 규약:
// recommendations 첫 항목에 quantity 또는 avg_buy_price 가 있으면 holdings.
// 그 외(샘플 등)는 기존 raw JSON 한 줄 표시 유지.

function isHoldingsRec(r: Record<string, unknown>): boolean {
  return "quantity" in r || "avg_buy_price" in r;
}

function fmtMoney(v: unknown): string | null {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

function fmtQty(v: unknown): string | null {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return n.toLocaleString("ko-KR", { maximumFractionDigits: 4 });
}

function fmtPct(v: unknown): string | null {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return `${n}%`;
}

function HoldingsCard({
  idx,
  item,
}: {
  idx: number;
  item: Record<string, unknown>;
}) {
  // 헤더: "1. RISE 미국은행TOP10 (0013P0)" 또는 "1. 0013P0"
  const ticker = typeof item.ticker === "string" ? item.ticker : "";
  const name = typeof item.name === "string" && item.name ? item.name : "";
  let header: string;
  if (name && ticker && name !== ticker) header = `${idx}. ${name} (${ticker})`;
  else if (ticker) header = `${idx}. ${ticker}`;
  else if (name) header = `${idx}. ${name}`;
  else header = `${idx}. (종목 미상)`;

  // 존재하는 필드만 줄로 표시. payload 에 없으면 생략.
  const lines: Array<[string, string]> = [];
  const qty = fmtQty(item.quantity);
  if (qty !== null) lines.push(["수량", qty]);
  const avg = fmtMoney(item.avg_buy_price);
  if (avg !== null) lines.push(["평균 매입단가", avg]);
  const inv = fmtMoney(item.invested_amount);
  if (inv !== null) lines.push(["매입금액", inv]);
  const w = fmtPct(item.buy_weight_pct);
  if (w !== null) lines.push(["매입비중", w]);
  if (typeof item.action === "string" && item.action) {
    lines.push(["판단", item.action]);
  }
  if (typeof item.reason === "string" && item.reason) {
    lines.push(["사유", item.reason]);
  }

  return (
    <li className="holdings-item">
      <div className="holdings-item-header">{header}</div>
      <ul className="holdings-item-fields">
        {lines.map(([k, v]) => (
          <li key={k}>
            <span className="k">{k}</span>
            <span className="v">{v}</span>
          </li>
        ))}
      </ul>
    </li>
  );
}

function Recommendations({ run }: { run: Run }) {
  const payload = run.draft_payload ?? {};
  const summary = (payload as Record<string, unknown>).summary_text;
  const recs = (payload as Record<string, unknown>).recommendations;
  const note = (payload as Record<string, unknown>).note;

  const hasSummary = typeof summary === "string" && summary.length > 0;
  const hasRecs = Array.isArray(recs) && recs.length > 0;
  const hasNote = typeof note === "string" && note.length > 0;

  if (!hasSummary && !hasRecs && !hasNote && Object.keys(payload).length === 0) {
    return <div className="message info">초안 본문이 없습니다.</div>;
  }

  // recs 첫 항목이 holdings 형태이면 사람이 읽는 카드 리스트로 렌더.
  const recsList = hasRecs
    ? (recs as Array<Record<string, unknown>>)
    : ([] as Array<Record<string, unknown>>);
  const isHoldings =
    recsList.length > 0 &&
    typeof recsList[0] === "object" &&
    recsList[0] !== null &&
    isHoldingsRec(recsList[0]);

  return (
    <div>
      {hasSummary ? (
        <div className="summary-text">{summary as string}</div>
      ) : null}
      {hasNote ? (
        <div className="summary-text" style={{ marginTop: hasSummary ? 8 : 0 }}>
          {note as string}
        </div>
      ) : null}
      {hasRecs && isHoldings ? (
        <ul
          className="holdings-list"
          style={{ marginTop: hasSummary || hasNote ? 10 : 0 }}
        >
          {recsList.map((r, idx) => (
            <HoldingsCard key={idx} idx={idx + 1} item={r} />
          ))}
        </ul>
      ) : null}
      {hasRecs && !isHoldings ? (
        <ul
          className="reco-list"
          style={{ marginTop: hasSummary || hasNote ? 10 : 0 }}
        >
          {recsList.map((r, idx) => (
            <li key={idx}>
              <code>{JSON.stringify(r)}</code>
            </li>
          ))}
        </ul>
      ) : null}
      {!hasSummary && !hasRecs && !hasNote ? (
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      ) : null}
    </div>
  );
}

interface Props {
  run: Run;
  setRun: (run: Run | null) => void;
  loading: boolean;
  setLoading: (b: boolean) => void;
  errorMsg: string | null;
  setErrorMsg: (s: string | null) => void;
}

export default function RunPanel({
  run,
  setRun,
  loading,
  setLoading,
  errorMsg,
  setErrorMsg,
}: Props) {
  const pollTickRef = useRef<number>(0);

  // DELIVERING 만 polling. terminal 도달 시 즉시 중단.
  useEffect(() => {
    if (run.status !== "DELIVERING") {
      pollTickRef.current = 0;
      return;
    }
    const id = window.setInterval(async () => {
      pollTickRef.current += 1;
      if (pollTickRef.current > MAX_POLL_TICKS) {
        window.clearInterval(id);
        setErrorMsg(
          "DELIVERING 상태가 너무 오래 지속됩니다. '상태 새로고침' 을 눌러 확인해 주세요."
        );
        return;
      }
      try {
        const latest = await fetchRun(run.run_id);
        setRun(latest);
      } catch (e) {
        setErrorMsg(describeApiError(e));
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [run, setRun, setErrorMsg]);

  const onApprove = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await approveRun(run.run_id);
      setRun(next);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onReject = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await rejectRun(run.run_id);
      setRun(next);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onRefresh = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const latest = await fetchRun(run.run_id);
      setRun(latest);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onReset = useCallback(() => {
    setRun(null);
    setErrorMsg(null);
    pollTickRef.current = 0;
  }, [setRun, setErrorMsg]);

  const canApproveOrReject = run.status === "PENDING_APPROVAL";
  const showTerminalReset = isTerminal(run.status);

  return (
    <>
      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      <div className="card">
        <h2>2. 현재 진행 상황</h2>
        <div className="status-row">
          <span className={`status-badge status-${run.status}`}>
            {humanLabel(run.status)}
          </span>
          <span className="kv">
            <span className="k">run_id</span>
            <span className="v">
              <code>{run.run_id}</code>
            </span>
          </span>
          <span className="kv">
            <span className="k">asof</span>
            <span className="v">{run.asof}</span>
          </span>
        </div>
        <div className="helper">
          백엔드 status: <code>{run.status}</code>
          {run.status === "DELIVERING" ? " (자동 상태 확인 중, 약 12초 간격)" : ""}
        </div>
      </div>

      <div className="card">
        <h2>3. 초안 본문</h2>
        <Recommendations run={run} />
      </div>

      <div className="card">
        <h2>4. 다음 행동</h2>
        {canApproveOrReject ? (
          <div className="btn-row">
            <button onClick={onApprove} disabled={loading} type="button">
              승인 (Approve)
            </button>
            <button
              className="reject"
              onClick={onReject}
              disabled={loading}
              type="button"
            >
              거절 (Reject)
            </button>
          </div>
        ) : (
          <div className="message info">
            {run.status === "DELIVERING"
              ? "외부 전달이 진행 중입니다. 잠시 후 상태가 자동으로 갱신됩니다."
              : "이 run 은 종결 상태입니다. 새 시도는 새 run_id 로만 가능합니다."}
          </div>
        )}
        <div
          className="btn-row"
          style={{ marginTop: canApproveOrReject ? 12 : 0 }}
        >
          <button
            className="reject"
            onClick={onRefresh}
            disabled={loading}
            type="button"
          >
            상태 새로고침
          </button>
          {showTerminalReset ? (
            <button onClick={onReset} disabled={loading} type="button">
              새 초안 시작
            </button>
          ) : null}
        </div>
      </div>
    </>
  );
}
