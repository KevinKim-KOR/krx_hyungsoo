"use client";

// 승인 루프 클라이언트 컴포넌트.
// 사용자 이벤트(Generate Draft / Approve / Reject)와 DELIVERING 상태의
// 제한적 polling 을 담당한다. 백엔드 status 값을 그대로 표시하며
// 프론트 전용 가공 상태를 만들지 않는다 (KS-1).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  approveRun,
  fetchRun,
  generateDraft,
  isTerminal,
  rejectRun,
  type Run,
  type RunStatus,
} from "@/lib/api";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_TICKS = 30; // 약 45초. 넘으면 polling 중단 (BACKLOG 로 추적)

// 사용자가 직접 입력한 draft 본문을 서버로 넘기기 위한 가벼운 파싱 도우미.
// sample_draft 레이어에서 필수 키 검증이 이뤄지므로 이곳은 단순 JSON 파싱만 담당.
function parseRecommendations(input: string): unknown {
  const trimmed = input.trim();
  if (!trimmed) {
    throw new Error("recommendations JSON 을 입력해 주세요.");
  }
  return JSON.parse(trimmed);
}

type InputState = {
  title: string;
  note: string;
  recommendations: string;
};

const INITIAL_INPUT: InputState = {
  title: "",
  note: "",
  recommendations: "",
};

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

function Recommendations({ run }: { run: Run }) {
  const payload = run.draft_payload ?? {};
  const summary = (payload as Record<string, unknown>).summary_text;
  const recs = (payload as Record<string, unknown>).recommendations;

  const hasSummary = typeof summary === "string" && summary.length > 0;
  const hasRecs = Array.isArray(recs) && recs.length > 0;

  if (!hasSummary && !hasRecs && Object.keys(payload).length === 0) {
    return <div className="message info">초안 본문이 없습니다.</div>;
  }

  return (
    <div>
      {hasSummary ? (
        <div className="summary-text">{summary as string}</div>
      ) : null}
      {hasRecs ? (
        <ul className="reco-list" style={{ marginTop: hasSummary ? 10 : 0 }}>
          {(recs as Array<Record<string, unknown>>).map((r, idx) => (
            <li key={idx}>
              <code>{JSON.stringify(r)}</code>
            </li>
          ))}
        </ul>
      ) : null}
      {!hasSummary && !hasRecs ? (
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      ) : null}
    </div>
  );
}

export default function ApprovalLoopClient() {
  const [run, setRun] = useState<Run | null>(null);
  const [input, setInput] = useState<InputState>(INITIAL_INPUT);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pollTickRef = useRef<number>(0);

  const handleApiError = useCallback((e: unknown) => {
    if (e instanceof ApiConfigError) {
      setErrorMsg(`구성 오류: ${e.message}`);
      return;
    }
    if (e instanceof ApiRequestError) {
      setErrorMsg(
        `요청 실패(HTTP ${e.httpStatus}): ${
          typeof e.body === "string" ? e.body : JSON.stringify(e.body)
        }`
      );
      return;
    }
    setErrorMsg(`알 수 없는 오류: ${(e as Error).message}`);
  }, []);

  // DELIVERING 상태에서만 polling. terminal 도달 시 즉시 중단.
  useEffect(() => {
    if (!run || run.status !== "DELIVERING") {
      pollTickRef.current = 0;
      return;
    }
    const id = window.setInterval(async () => {
      pollTickRef.current += 1;
      if (pollTickRef.current > MAX_POLL_TICKS) {
        window.clearInterval(id);
        setErrorMsg(
          "DELIVERING 상태가 너무 오래 지속됩니다. 아래 '상태 새로고침' 을 눌러 확인해 주세요."
        );
        return;
      }
      try {
        const latest = await fetchRun(run.run_id);
        setRun(latest);
      } catch (e) {
        handleApiError(e);
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [run, handleApiError]);

  const onGenerate = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const payload: Record<string, unknown> = {};
      if (input.title.trim()) payload.title = input.title.trim();
      if (input.note.trim()) payload.note = input.note.trim();
      if (input.recommendations.trim()) {
        try {
          payload.recommendations = parseRecommendations(input.recommendations);
        } catch (e) {
          setErrorMsg(
            `recommendations JSON 파싱 실패: ${(e as Error).message}`
          );
          setLoading(false);
          return;
        }
      }
      const next = await generateDraft(payload);
      setRun(next);
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [input, handleApiError]);

  const onApprove = useCallback(async () => {
    if (!run) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await approveRun(run.run_id);
      setRun(next);
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [run, handleApiError]);

  const onReject = useCallback(async () => {
    if (!run) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await rejectRun(run.run_id);
      setRun(next);
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [run, handleApiError]);

  const onRefresh = useCallback(async () => {
    if (!run) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const latest = await fetchRun(run.run_id);
      setRun(latest);
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [run, handleApiError]);

  const onReset = useCallback(() => {
    setRun(null);
    setInput(INITIAL_INPUT);
    setErrorMsg(null);
    pollTickRef.current = 0;
  }, []);

  const canApproveOrReject = run?.status === "PENDING_APPROVAL";
  const showTerminalReset = run !== null && isTerminal(run.status);

  return (
    <main>
      <h1>POC 1단계 승인 루프</h1>
      <p className="subtitle">
        AI 가 초안을 만들면, 사람이 승인/거절하고 외부로 전달합니다.
      </p>

      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      {!run ? (
        <div className="card">
          <h2>1. 새 초안 만들기</h2>
          <label>제목 (title)</label>
          <input
            type="text"
            value={input.title}
            onChange={(e) =>
              setInput((p) => ({ ...p, title: e.target.value }))
            }
            placeholder="예: ETF 모멘텀 추천 초안"
            disabled={loading}
          />
          <label>메모 (note)</label>
          <textarea
            value={input.note}
            onChange={(e) =>
              setInput((p) => ({ ...p, note: e.target.value }))
            }
            placeholder="사람이 읽고 판단할 본문"
            disabled={loading}
          />
          <label>추천 목록 (recommendations, JSON 배열)</label>
          <textarea
            value={input.recommendations}
            onChange={(e) =>
              setInput((p) => ({ ...p, recommendations: e.target.value }))
            }
            placeholder='[{"ticker":"069500","score":0.75,"action":"HOLD"}]'
            disabled={loading}
          />
          <div className="helper">
            필수 항목(title / note / recommendations) 중 하나라도 누락되면
            서버가 FAILED 로 저장합니다.
          </div>
          <div style={{ marginTop: 16 }}>
            <button onClick={onGenerate} disabled={loading}>
              {loading ? "생성 중..." : "초안 만들기"}
            </button>
          </div>
        </div>
      ) : (
        <>
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
              백엔드 status 값:{" "}
              <code>{run.status}</code>
              {run.status === "DELIVERING" ? " (자동 상태 확인 중)" : ""}
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
                <button onClick={onApprove} disabled={loading}>
                  승인 (Approve)
                </button>
                <button
                  className="reject"
                  onClick={onReject}
                  disabled={loading}
                >
                  거절 (Reject)
                </button>
              </div>
            ) : (
              <div className="message info">
                {run.status === "DELIVERING"
                  ? "외부 전달이 진행 중입니다. 잠시 후 상태가 자동으로 갱신됩니다."
                  : "이 run 은 종결 상태입니다. 새 시도는 아래 '새 초안 시작' 으로 새 run_id 를 만들어야 합니다."}
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
              >
                상태 새로고침
              </button>
              {showTerminalReset ? (
                <button onClick={onReset} disabled={loading}>
                  새 초안 시작
                </button>
              ) : null}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
