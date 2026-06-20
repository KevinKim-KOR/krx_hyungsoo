"use client";

// POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 STEP (2026-06-20).
//
// 지시문 §5 — 현재 운영 기준 카드 + [현재 기준 OCI 적용] 단일 버튼.
//
// 표시 항목 (지시문 §5.2):
//   - 현재 적용 기준 (display_label)
//   - OCI 반영 상태 (applied / failed / not_applied / verification_required)
//   - 마지막 적용 시각 (YYYY-MM-DD HH:MM, 없으면 "—")
//
// 표시 X (지시문 §5.2):
//   param_id / manual_seed / remote path / SSH target / 파일명 /
//   실행 명령 / raw traceback / token / chat_id.

import { useCallback, useEffect, useState } from "react";
import {
  applyThreePushParamToOci,
  fetchThreePushParamState,
  type ThreePushParamState,
  type ThreePushParamStatus,
} from "@/lib/api/threePushParam";
import { ApiConfigError, ApiRequestError } from "@/lib/api";

function statusBadgeText(status: ThreePushParamStatus): string {
  switch (status) {
    case "applied":
      return "적용 완료";
    case "applying":
      return "적용 중";
    case "failed":
      return "적용 실패";
    case "verification_required":
      return "확인 필요";
    case "not_applied":
    default:
      return "미적용";
  }
}

function statusBadgeColor(status: ThreePushParamStatus): string {
  switch (status) {
    case "applied":
      return "#16a34a"; // green
    case "applying":
      return "#0284c7"; // blue
    case "failed":
      return "#dc2626"; // red
    case "verification_required":
      return "#d97706"; // amber
    case "not_applied":
    default:
      return "#6b7280"; // gray
  }
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패 (HTTP ${e.httpStatus})`;
  }
  return "알 수 없는 오류가 발생했습니다.";
}

export default function ThreePushParamCard() {
  const [state, setState] = useState<ThreePushParamState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [applying, setApplying] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // 진행 상태 단계 표시 (지시문 §5.4): "운영 기준 생성 중" → "OCI 에 적용 중" →
  // "OCI 반영 확인 중" → "적용 완료".
  const [progressStage, setProgressStage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const s = await fetchThreePushParamState();
      setState(s);
    } catch (e) {
      setErrorMsg(describeError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleApply = useCallback(async () => {
    if (applying) return;
    setApplying(true);
    setErrorMsg(null);
    setProgressStage("운영 기준 생성 중");
    // 동기 호출이지만 사용자에게는 단계 진행이 보이도록 표시.
    setTimeout(() => setProgressStage("OCI 에 적용 중"), 400);
    setTimeout(() => setProgressStage("OCI 반영 확인 중"), 1200);
    try {
      const result = await applyThreePushParamToOci();
      setState(result);
      setProgressStage(null);
    } catch (e) {
      setErrorMsg(describeError(e));
      setProgressStage(null);
      // 실패해도 카드의 기존 state 유지 — 사용자는 직전 적용 상태를 볼 수 있다.
      // 지시문 AC-9 — 적용 실패가 기존 PARAM 을 무효화하지 않는다.
      await refresh();
    } finally {
      setApplying(false);
    }
  }, [applying, refresh]);

  if (loading && !state) {
    return (
      <section
        aria-labelledby="three-push-param-h"
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
        }}
      >
        <h3 id="three-push-param-h" style={{ margin: 0 }}>
          현재 운영 기준
        </h3>
        <p style={{ marginTop: 8, color: "#6b7280" }}>상태 조회 중...</p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="three-push-param-h"
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <h3 id="three-push-param-h" style={{ margin: 0 }}>
        현재 운영 기준
      </h3>
      {state ? (
        <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
          <div>
            <span style={{ color: "#6b7280" }}>현재 적용 기준: </span>
            <strong>{state.display_label}</strong>
          </div>
          <div>
            <span style={{ color: "#6b7280" }}>OCI 반영 상태: </span>
            <span
              style={{
                display: "inline-block",
                padding: "2px 8px",
                borderRadius: 4,
                backgroundColor: statusBadgeColor(state.status),
                color: "white",
                fontSize: "0.85em",
              }}
            >
              {statusBadgeText(state.status)}
            </span>
          </div>
          <div>
            <span style={{ color: "#6b7280" }}>마지막 적용 시각: </span>
            <span>{state.applied_at ?? "—"}</span>
          </div>
          <div style={{ color: "#374151", marginTop: 4 }}>{state.message}</div>
        </div>
      ) : null}

      {progressStage ? (
        <p style={{ marginTop: 12, color: "#0284c7" }}>
          진행 중: {progressStage}
        </p>
      ) : null}
      {errorMsg ? (
        <p style={{ marginTop: 12, color: "#dc2626" }}>{errorMsg}</p>
      ) : null}

      {/* 지시문 §5.3 — 버튼은 하나만 둔다. 상태는 카드 마운트 시 자동 조회. */}
      <div style={{ marginTop: 16 }}>
        <button
          type="button"
          onClick={handleApply}
          disabled={applying}
          style={{
            padding: "8px 16px",
            borderRadius: 6,
            border: "none",
            backgroundColor: applying ? "#9ca3af" : "#0284c7",
            color: "white",
            cursor: applying ? "not-allowed" : "pointer",
          }}
        >
          {applying ? "적용 진행 중..." : "현재 기준 OCI 적용"}
        </button>
      </div>
    </section>
  );
}
