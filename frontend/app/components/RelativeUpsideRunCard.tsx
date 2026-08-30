"use client";

// POC2 ML 축1 — 상대상승 참고점수 실행 UI 카드 (2026-06-21).
//
// Market Discovery 후보 목록 상단의 작은 카드 1개. CLI 없이 화면에서 점수
// 계산을 실행한다.
//
// 표시 (지시문 — 사용자용 5 항목):
//   - 상태: 미실행 / 계산 중 / 완료 / 실패
//   - 기준일 (asof_date)
//   - 마지막 계산 시각 (generated_at)
//   - 점수 반영 후보 수
//   - GPU 실행 여부
//
// 동작:
//   1. 버튼 클릭 → 기존 relative_upside_score_v0 실행
//   2. 실행 중 버튼 중복 클릭 차단
//
// 2026-08-29 POC3-ML-02 REJECT Closeout:
//   `relative_upside_v0` 은 유효성 검증에서 REJECT 판정을 받았다. 이 카드는
//   **연구용 baseline 재현 경로**로만 남는다. 판정 상태를 카드 안에 명시하고,
//   이 문구와 점수는 ML 화면 밖 어디에도 노출하지 않는다.
//   자동 실행·스케줄러·후보 화면 연결은 추가하지 않는다.
//
// 일반 UI 노출 X (지시문):
//   CUDA device name / loss / epoch / artifact path / raw traceback /
//   shell command / feature vector.

import { useCallback, useState } from "react";
import {
  runRelativeUpsideScore,
  type RelativeUpsideRunResult,
  type RelativeUpsideRunStatus,
} from "@/lib/api/mlRelativeUpside";
import { ApiConfigError, ApiRequestError } from "@/lib/api";

function badgeColor(status: RelativeUpsideRunStatus | "idle" | "running"): string {
  switch (status) {
    case "ok":
      return "#16a34a";
    case "running":
      return "#0284c7";
    case "failed":
      return "#dc2626";
    case "unavailable":
      return "#d97706";
    case "idle":
    default:
      return "#6b7280";
  }
}

function badgeText(status: RelativeUpsideRunStatus | "idle" | "running"): string {
  switch (status) {
    case "ok":
      return "완료";
    case "running":
      return "계산 중";
    case "failed":
      return "실패";
    case "unavailable":
      return "데이터 부족";
    case "idle":
    default:
      return "미실행";
  }
}

function formatGeneratedAt(iso: string | null): string {
  if (!iso) return "—";
  try {
    const dt = new Date(iso);
    // YYYY-MM-DD HH:MM 형식. KST (브라우저 로컬 타임존 기준).
    const yyyy = dt.getFullYear();
    const mm = String(dt.getMonth() + 1).padStart(2, "0");
    const dd = String(dt.getDate()).padStart(2, "0");
    const hh = String(dt.getHours()).padStart(2, "0");
    const mi = String(dt.getMinutes()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  } catch {
    return "—";
  }
}

function describeError(e: unknown): string {
  // 일반 UI 에 raw traceback / network error 원문 노출 0건 (지시문).
  // 사용자용 generic 문구만.
  if (e instanceof ApiConfigError || e instanceof ApiRequestError) {
    return "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다.";
  }
  return "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다.";
}

interface Props {
  // result / errorMessage 는 부모 (MarketDiscoveryView) 가 보유 — onSuccess 의
  // loadTopn() 호출이 부모의 phase 를 loading 으로 바꿔서 본 카드가 unmount/
  // remount 되어도 결과 표시가 유지되도록 lift state up (2026-06-21 운영 회귀
  // 수정).
  result: RelativeUpsideRunResult | null;
  errorMessage: string | null;
  onResult: (result: RelativeUpsideRunResult) => void;
  onError: (message: string) => void;
}

export default function RelativeUpsideRunCard({
  result,
  errorMessage,
  onResult,
  onError,
}: Props) {
  const [running, setRunning] = useState<boolean>(false);

  const handleRun = useCallback(async () => {
    if (running) return;
    setRunning(true);
    try {
      const res = await runRelativeUpsideScore();
      onResult(res);
    } catch (e) {
      onError(describeError(e));
      // 기존 result 는 유지 (지시문 — 실패 시 기존 점수 보존).
    } finally {
      setRunning(false);
    }
  }, [running, onResult, onError]);

  const displayStatus: RelativeUpsideRunStatus | "idle" | "running" = running
    ? "running"
    : result?.status ?? "idle";

  return (
    <section
      aria-labelledby="relative-upside-run-h"
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <h3 id="relative-upside-run-h" style={{ margin: 0 }}>
        상대상승 참고점수 계산
      </h3>
      {/* 2026-08-29 REJECT Closeout — 모델 식별자·판정·용도를 카드 안에 명시한다. */}
      <div
        style={{
          marginTop: 8,
          padding: "8px 10px",
          border: "1px solid #fca5a5",
          borderRadius: 6,
          backgroundColor: "#fef2f2",
          fontSize: "0.85em",
          lineHeight: 1.5,
        }}
      >
        <div>
          <strong>relative_upside_v0</strong>{" "}
          <span
            style={{
              display: "inline-block",
              padding: "1px 6px",
              borderRadius: 4,
              backgroundColor: "#dc2626",
              color: "white",
              fontSize: "0.9em",
            }}
          >
            REJECT
          </span>
        </div>
        <div style={{ marginTop: 4, color: "#7f1d1d" }}>
          연구용 baseline이며 투자 판단에 사용하지 않음
        </div>
      </div>
      <div style={{ marginTop: 12, display: "grid", gap: 6 }}>
        <div>
          <span style={{ color: "#6b7280" }}>상태: </span>
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 4,
              backgroundColor: badgeColor(displayStatus),
              color: "white",
              fontSize: "0.85em",
            }}
          >
            {badgeText(displayStatus)}
          </span>
        </div>
        <div>
          <span style={{ color: "#6b7280" }}>기준일: </span>
          <span>{result?.asof_date ?? "—"}</span>
        </div>
        <div>
          <span style={{ color: "#6b7280" }}>마지막 계산: </span>
          <span>{formatGeneratedAt(result?.generated_at ?? null)}</span>
        </div>
        <div>
          <span style={{ color: "#6b7280" }}>점수 반영: </span>
          <span>
            {result?.scored_candidate_count != null
              ? `${result.scored_candidate_count}개 후보`
              : "—"}
          </span>
        </div>
        <div>
          <span style={{ color: "#6b7280" }}>GPU 실행: </span>
          <span>
            {result?.gpu_execution_used === true
              ? "확인됨"
              : result?.gpu_execution_used === false
                ? "확인되지 않음"
                : "—"}
          </span>
        </div>
        {result?.message ? (
          <div style={{ marginTop: 4, color: "#374151" }}>{result.message}</div>
        ) : null}
        {errorMessage ? (
          <div style={{ marginTop: 4, color: "#dc2626" }}>{errorMessage}</div>
        ) : null}
      </div>
      <div style={{ marginTop: 16 }}>
        <button
          type="button"
          onClick={handleRun}
          disabled={running}
          style={{
            padding: "8px 16px",
            borderRadius: 6,
            border: "none",
            backgroundColor: running ? "#9ca3af" : "#0284c7",
            color: "white",
            cursor: running ? "not-allowed" : "pointer",
          }}
        >
          {running ? "계산 진행 중..." : "상대상승 점수 계산"}
        </button>
      </div>
    </section>
  );
}
