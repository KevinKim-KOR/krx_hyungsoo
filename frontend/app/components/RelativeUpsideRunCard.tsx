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
// 2026-11-01 POC6-15(설계자 PLAN 판정 §3 · §4 · 목업 3 사용자 확인):
//   순서 = 제목 → 결론 한 줄(미채택 · 연구용) → [참고점수 계산] · 요청 오류 → 상태 줄 → 접힌 개발 정보.
//   버튼의 핸들러 · 막힘 조건(계산 중) · 색은 그대로이고 자리만 위로 옮겼다.
//   모델 이름 `relative_upside_v0` · 판정 원문 REJECT · 응답 원래 값은 접힌 '자세한 정보(개발 정보)'로 옮겼다.
//   응답이 모르는 상태 값을 주면 원래 값을 그대로 보인다(이전에는 '미실행'으로 보였다).
//   마지막 계산 시각 = 시간대가 붙은 ISO 면 한국 시각(분까지) · 아니면 받은 글자 그대로.
//
// 일반 UI 노출 X (지시문):
//   CUDA device name / loss / epoch / artifact path / raw traceback /
//   shell command / feature vector.

import { useCallback, useState } from "react";
import {
  runRelativeUpsideScore,
  type RelativeUpsideRunResult,
} from "@/lib/api/mlRelativeUpside";
import { ApiConfigError, ApiRequestError } from "@/lib/api";
import { CardConclusion, DevDetails, fmtCount, kstText } from "./MLCardParts";

interface StatusView {
  badge: string;
  color: string;
  note: string | null;
}

// 상태 줄의 배지 글자 · 색 · 덧붙임. 계산 중 → 응답 없음 → 응답 상태 값 순서로 정한다.
// 응답이 모르는 상태 값이면 원래 값을 배지에 그대로 둔다(임의 해석 없음).
// 응답은 받았는데 상태 값이 없으면(null · 빠짐) '아직 계산 안 함'과 합치지 않는다.
function statusView(running: boolean, result: RelativeUpsideRunResult | null): StatusView {
  if (running) return { badge: "계산 중", color: "#0284c7", note: null };
  if (result == null) return { badge: "아직 계산 안 함", color: "#6b7280", note: null };
  const status: unknown = result.status;
  switch (status) {
    case "ok":
      return { badge: "완료", color: "#16a34a", note: null };
    case "failed":
      // 응답에 실패 원인이 오지 않는다(백엔드 고정 문장) — 원인을 지어내지 않는다.
      return { badge: "실패", color: "#dc2626", note: "원인 확인 필요" };
    case "unavailable":
      // 2026-11-02 RESULT 판정 §3: unavailable 은 파일 손상 · 실행 기록 없음 · 자료 부족 · 후보 0건을 함께 뜻함 → 원인을 단정하지 않는 말(사유는 아래 응답 문장)
      return { badge: "결과를 사용할 수 없음", color: "#d97706", note: null };
    default:
      return {
        badge:
          status == null
            ? "응답에 없음"
            : status === ""
              ? "빈 값"
              : typeof status === "string"
                ? status
                : JSON.stringify(status),
        color: "#6b7280",
        note: "알 수 없는 상태 · 확인 필요",
      };
  }
}

function formatGeneratedAt(iso: string | null): string {
  if (!iso) return "—";
  // 시간대가 붙은 ISO 만 한국 시각 'YYYY-MM-DD HH:MM'. 그 밖의 값은 받은 글자 그대로.
  return kstText(iso, false) ?? iso;
}

function describeError(e: unknown): string {
  // 일반 UI 에 raw traceback / network error 원문 노출 0건 (지시문).
  // 사용자용 generic 문구만.
  if (e instanceof ApiConfigError || e instanceof ApiRequestError) {
    return "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다.";
  }
  return "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다.";
}

// 개발 정보 칸에 응답 원래 값을 보일 필드(응답 6필드 · 백엔드 response_model 그대로).
const RAW_FIELDS: (keyof RelativeUpsideRunResult)[] = [
  "status",
  "asof_date",
  "generated_at",
  "scored_candidate_count",
  "gpu_execution_used",
  "message",
];

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

  const view = statusView(running, result);

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
      <h2 id="relative-upside-run-h" style={{ fontSize: 16, margin: "0 0 12px 0" }}>
        상대 상승 참고점수(이전 실험)
      </h2>
      {/* 2026-08-29 REJECT 판정(당시 결론) · 용도 — 기본 화면 맨 위. 원래 식별자는 개발 정보에. */}
      <CardConclusion tone="bad" label="미채택">
        2026-08-29 판정 · 연구용 기준선 · 투자 판단에 쓰지 않음
      </CardConclusion>
      <div className="ml-card-controls">
        <button
          type="button"
          onClick={handleRun}
          disabled={running}
          style={{
            borderRadius: 6,
            border: "none",
            backgroundColor: running ? "#9ca3af" : "#0284c7",
            color: "white",
            cursor: running ? "not-allowed" : "pointer",
          }}
        >
          {running ? "계산 진행 중..." : "참고점수 계산"}
        </button>
      </div>
      {errorMessage ? (
        <div className="message error" data-testid="ru-request-error">
          계산 요청 오류 · 원인 확인 필요 — {errorMessage}
        </div>
      ) : null}
      <div
        data-testid="ru-status-line"
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "4px 12px",
          fontSize: 14,
        }}
      >
        <span>
          <span style={{ color: "#6b7280" }}>상태 </span>
          <span
            data-testid="ru-status"
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 4,
              backgroundColor: view.color,
              color: "white",
              fontSize: "0.85em",
            }}
          >
            {view.badge}
          </span>
          {view.note ? <span style={{ marginLeft: 6 }}>{view.note}</span> : null}
        </span>
        <span>
          <span style={{ color: "#6b7280" }}>기준일 </span>
          <span>{result?.asof_date ?? "—"}</span>
        </span>
        <span>
          <span style={{ color: "#6b7280" }}>마지막 계산 </span>
          <span>{formatGeneratedAt(result?.generated_at ?? null)}</span>
        </span>
        <span>
          <span style={{ color: "#6b7280" }}>점수 반영 </span>
          <span>
            {result?.scored_candidate_count != null
              ? `${fmtCount(result.scored_candidate_count)}개 후보`
              : "—"}
          </span>
        </span>
        <span>
          <span style={{ color: "#6b7280" }}>GPU 계산 </span>
          <span>
            {result?.gpu_execution_used === true
              ? "확인됨"
              : result?.gpu_execution_used === false
                ? "확인되지 않음"
                : "—"}
          </span>
        </span>
      </div>
      {result?.message ? (
        <div style={{ marginTop: 8, color: "#374151", fontSize: 14 }}>{result.message}</div>
      ) : null}
      <DevDetails>
        <div>모델 이름 relative_upside_v0 · 판정 REJECT(2026-08-29 POC3-ML-02)</div>
        {result ? (
          <div style={{ marginTop: 6 }}>
            <div>응답 원래 값(POST /market/relative-upside/run)</div>
            {RAW_FIELDS.map((k) => (
              <div key={k}>
                {k} = {result[k] === undefined ? "(응답에 없음)" : JSON.stringify(result[k])}
              </div>
            ))}
          </div>
        ) : null}
      </DevDetails>
    </section>
  );
}
