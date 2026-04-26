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
      {hasRecs ? (
        <ul
          className="reco-list"
          style={{ marginTop: hasSummary || hasNote ? 10 : 0 }}
        >
          {(recs as Array<Record<string, unknown>>).map((r, idx) => (
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
