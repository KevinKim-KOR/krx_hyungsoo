"use client";

// POC2 UI 안전실행 (2026-06-11) — ML evidence 갱신 카드.
//
// 책임 (지시문 §5.1):
// - 마지막 실행 상태 / 시작 / 종료 / 단계별 상태 / 마지막 성공 요약 / 실패 메시지 표시.
// - 'ML evidence 갱신 실행' 버튼 — POST /ml/jobs/evidence-refresh.
// - 실행 중이면 버튼 비활성화 + 5초 간격 polling 으로 자동 갱신.
//
// 본 카드는 baseline 재계산을 직접 하지 않는다. backend background job 만 시작
// 하고 상태를 조회한다. 매수/매도/추천/현금비중/조정장/위험 알림 문구 0건 (§8).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlJobsLatest,
  startMlEvidenceRefresh,
  type MlJobLatestResponse,
  type MlJobState,
  type MlJobStartResponse,
  type MlJobStepState,
} from "@/lib/api";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MlJobLatestResponse };

const DASH = "-";

const STEP_LABELS: Record<keyof MlJobState["steps"], string> = {
  feature_generation: "1) ML feature 생성",
  sanity_check: "2) feature sanity 검증",
  baseline_lookback: "3) baseline 룩백 검증",
};

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function stepBadgeClass(status: string): string {
  if (status === "success") return "ml-readiness-badge ml-readiness-available";
  if (status === "running") return "ml-readiness-badge ml-readiness-partial";
  if (status === "queued") return "ml-readiness-badge ml-readiness-partial";
  if (status === "failed") return "ml-readiness-badge ml-readiness-missing";
  if (status === "skipped") return "ml-readiness-badge ml-readiness-missing";
  return "ml-readiness-badge";
}

function jobBadgeClass(status: string | undefined): string {
  if (status === "success") return "ml-readiness-badge ml-readiness-available";
  if (status === "running") return "ml-readiness-badge ml-readiness-partial";
  if (status === "queued") return "ml-readiness-badge ml-readiness-partial";
  if (status === "failed") return "ml-readiness-badge ml-readiness-missing";
  return "ml-readiness-badge";
}

function isRunning(job: MlJobState | null | undefined): boolean {
  if (!job) return false;
  return job.status === "running" || job.status === "queued";
}

export default function MLEvidenceRefreshCard() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [starting, setStarting] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchMlJobsLatest();
      setState({ phase: "ready", data });
    } catch (e) {
      setState({ phase: "error", message: describeError(e) });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // running 일 때만 5초 polling — 완료되면 자동으로 멈춤.
  useEffect(() => {
    const job = state.phase === "ready" ? state.data.job : null;
    if (isRunning(job)) {
      if (pollTimerRef.current == null) {
        pollTimerRef.current = setInterval(() => {
          load();
        }, 5000);
      }
    } else if (pollTimerRef.current != null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    return () => {
      if (pollTimerRef.current != null) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [state, load]);

  const handleStart = useCallback(async () => {
    setStarting(true);
    setActionMessage(null);
    try {
      const res: MlJobStartResponse = await startMlEvidenceRefresh();
      if (res.status === "already_running") {
        setActionMessage(
          res.message ?? "이미 실행 중인 ML evidence 갱신 job 이 있습니다.",
        );
      } else if (res.status === "accepted") {
        setActionMessage("ML evidence 갱신을 background 로 시작했습니다.");
      } else {
        setActionMessage(res.message ?? "시작 요청 실패");
      }
      await load();
    } catch (e) {
      setActionMessage(describeError(e));
    } finally {
      setStarting(false);
    }
  }, [load]);

  const job = state.phase === "ready" ? state.data.job : null;
  const running = isRunning(job);
  const buttonDisabled = starting || running;

  return (
    <div className="card">
      <h2>ML evidence 갱신</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        현재 ML feature / sanity / baseline 룩백 검증 artifact 를 한 번에
        갱신합니다. 실행은 background 로 시작되며 화면이 멈추지 않습니다. 갱신
        결과는 이 화면 아래 ML Feature Sanity / ML Baseline v0 카드에 자동
        반영됩니다.
      </p>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
        <button type="button" onClick={handleStart} disabled={buttonDisabled}>
          ML evidence 갱신 실행
        </button>
        <button type="button" onClick={load} disabled={starting}>
          상태 다시 불러오기
        </button>
        {running && (
          <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
            실행 중 — 5초마다 자동 갱신됩니다.
          </span>
        )}
      </div>

      {actionMessage && (
        <div className="message info" style={{ marginBottom: 8 }}>
          {actionMessage}
        </div>
      )}

      {state.phase === "loading" && (
        <div className="message info">불러오는 중...</div>
      )}

      {state.phase === "error" && (
        <div className="message error">{state.message}</div>
      )}

      {state.phase === "ready" && state.data.status === "empty" && (
        <div className="message info">
          {state.data.message ??
            "ML evidence 갱신 job 이 아직 한 번도 실행되지 않았습니다."}
        </div>
      )}

      {/* FIX r2 (B-1) — status 파일 손상을 미실행과 구분해 명시 노출. 사용자가
          파일을 직접 확인 또는 삭제 후 재시도해야 한다. */}
      {state.phase === "ready" && state.data.status === "error" && (
        <div className="message error">
          {state.data.message ?? "ml_job_status 파일이 손상되어 읽을 수 없습니다."}
        </div>
      )}

      {state.phase === "ready" && state.data.status === "ok" && job && (
        <JobStatusPanel job={job} />
      )}
    </div>
  );
}

function JobStatusPanel({ job }: { job: MlJobState }) {
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <span className={jobBadgeClass(job.status)}>{job.status}</span>{" "}
        <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
          {" "}
          job_id={job.job_id} · requested_by={job.requested_by}
        </span>
      </div>

      <table className="market-topn-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th style={{ width: 180 }}>항목</th>
            <th>값</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>시작 시각</td>
            <td>{job.started_at ?? DASH}</td>
          </tr>
          <tr>
            <td>종료 시각</td>
            <td>{job.finished_at ?? DASH}</td>
          </tr>
          <tr>
            <td>마지막 heartbeat</td>
            <td>{job.last_heartbeat_at ?? DASH}</td>
          </tr>
          {job.error && (
            <tr>
              <td>실패 메시지</td>
              <td style={{ color: "var(--danger)" }}>{job.error}</td>
            </tr>
          )}
          {job.message && (
            <tr>
              <td>메시지</td>
              <td>{job.message}</td>
            </tr>
          )}
        </tbody>
      </table>

      <h3 style={{ fontSize: "0.95rem", marginTop: 8, marginBottom: 6 }}>
        단계별 상태
      </h3>
      <table className="market-topn-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th style={{ width: 220 }}>단계</th>
            <th style={{ width: 100 }}>상태</th>
            <th style={{ width: 170 }}>시작</th>
            <th style={{ width: 170 }}>종료</th>
            <th>메시지</th>
          </tr>
        </thead>
        <tbody>
          {(Object.keys(STEP_LABELS) as Array<keyof MlJobState["steps"]>).map(
            (key) => {
              const s: MlJobStepState = job.steps[key];
              return (
                <tr key={key}>
                  <td>{STEP_LABELS[key]}</td>
                  <td>
                    <span className={stepBadgeClass(s.status)}>{s.status}</span>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                    {s.started_at ?? DASH}
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                    {s.finished_at ?? DASH}
                  </td>
                  <td style={{ fontSize: "0.8rem" }}>{s.message || DASH}</td>
                </tr>
              );
            },
          )}
        </tbody>
      </table>

      {job.last_success_summary && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            마지막 성공 요약
          </summary>
          <pre
            style={{
              background: "var(--panel-bg, #0c0e15)",
              padding: 8,
              borderRadius: 4,
              fontSize: "0.78rem",
              overflowX: "auto",
              marginTop: 6,
            }}
          >
            {JSON.stringify(job.last_success_summary, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
