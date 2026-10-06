"use client";

// POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 STEP (2026-06-20).
//
// 지시문 §5 — 현재 운영 기준 카드 + 단일 버튼(POC3-02D-OPS-04 부터 [현재 기준 OCI 전달]).
//
// 표시 항목 (지시문 §5.2):
//   - 현재 적용 기준 (display_label)
//   - OCI 전달 상태 (applied / failed / not_applied / verification_required · OPS-04 전 'OCI 반영')
//   - 마지막 적용 시각 (YYYY-MM-DD HH:MM, 없으면 "—")
//
// 표시 X (지시문 §5.2):
//   param_id / manual_seed / remote path / SSH target / 파일명 /
//   실행 명령 / raw traceback / token / chat_id.
//
// 2026-09-27 사용자 직접 지시(가독성 · 배치만): 한 줄에 몰아 쓰던 값을
//   제목 오른쪽 상태 배지 + 정렬된 행(적용 기준 · 마지막 적용 · OCI 반영)으로
//   나눴다. 값 · 문구 · 시각 형식(YYYY-MM-DD HH:MM, 없으면 "—") · 버튼 · 동작은
//   그대로다. 배지 색은 「OCI 운영·적용」 ① 표와 같은 `.oci-state` 톤을 쓴다.
//
// 2026-10-06 POC3-02D-OPS-04 항목 6(설계자 Q7 b · 사용자 목업 확정): 이 버튼은 OCI 에
//   운영 기준 JSON 을 **전달**만 한다(OCI 러너가 쓰는 활성값은 바꾸지 않는다). 그래서
//   배지 · 행 · 버튼 · 진행 문구를 '적용 · 반영' 에서 '전달' 로 바꿨다. 실제로 쓰이는지는
//   ① 표 '운영 기준 활성' 행이 보인다 — 전달이 끝나면 `onDelivered` 로 ① 을 다시 읽게 한다.

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
      return "전달 완료";
    case "applying":
      return "전달 중";
    case "failed":
      return "전달 실패";
    case "verification_required":
      return "확인 필요";
    case "not_applied":
    default:
      return "미전달";
  }
}

// `.oci-state` 톤 (globals.css). 완료 = ok · 실패/확인 필요 = warn ·
// 진행 중 = info · 미적용 = unknown(회색 — 실패처럼 보이지 않게).
function statusBadgeTone(status: ThreePushParamStatus): string {
  switch (status) {
    case "applied":
      return "ok";
    case "applying":
      return "info";
    case "failed":
    case "verification_required":
      return "warn";
    case "not_applied":
    default:
      return "unknown";
  }
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패 (HTTP ${e.httpStatus})`;
  }
  return "알 수 없는 오류가 발생했습니다.";
}

export default function ThreePushParamCard({
  onDelivered,
}: {
  // 전달 시도가 끝나면 부른다 — ① '운영 기준 활성' 행을 다시 읽게 한다(OCI 재조회 없음).
  onDelivered?: () => void;
} = {}) {
  const [state, setState] = useState<ThreePushParamState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [applying, setApplying] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // 진행 상태 단계 표시 (지시문 §5.4): "운영 기준 생성 중" → "OCI 에 전달 중" →
  // "OCI 전달 확인 중" → "전달 완료"(POC3-02D-OPS-04 문구).
  const [progressStage, setProgressStage] = useState<string | null>(null);
  // POC3-07 (Q4): 표시용 전송 payload SHA-256 (성공 판정 아님, 대조 참고용).
  const [appliedHash, setAppliedHash] = useState<string | null>(null);

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
    setTimeout(() => setProgressStage("OCI 에 전달 중"), 400);
    setTimeout(() => setProgressStage("OCI 전달 확인 중"), 1200);
    try {
      const result = await applyThreePushParamToOci();
      setState(result);
      setAppliedHash(result.content_sha256 ?? null);
      setProgressStage(null);
    } catch (e) {
      setErrorMsg(describeError(e));
      setProgressStage(null);
      // 실패해도 카드의 기존 state 유지 — 사용자는 직전 적용 상태를 볼 수 있다.
      // 지시문 AC-9 — 적용 실패가 기존 PARAM 을 무효화하지 않는다.
      await refresh();
    } finally {
      setApplying(false);
      onDelivered?.();
    }
  }, [applying, refresh, onDelivered]);

  if (loading && !state) {
    return (
      <section aria-labelledby="three-push-param-h" className="tc-card ops-card">
        <div className="ops-card-head">
          <h3 id="three-push-param-h">현재 운영 기준</h3>
        </div>
        <p className="tc-muted tc-small">상태 조회 중...</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="three-push-param-h" className="tc-card ops-card">
      <div className="ops-card-head">
        <h3 id="three-push-param-h">현재 운영 기준</h3>
        {state ? (
          <span className={`oci-state ${statusBadgeTone(state.status)}`}>
            {statusBadgeText(state.status)}
          </span>
        ) : null}
      </div>
      {state ? (
        <div>
          <dl className="ops-kv">
            <dt>적용 기준</dt>
            <dd>
              <strong>{state.display_label}</strong>
            </dd>

            {/* 형식 계약(지시문 §5.2): YYYY-MM-DD HH:MM, 없으면 "—". 다시 바꾸지 않는다. */}
            <dt>마지막 적용</dt>
            <dd>{state.applied_at ?? "—"}</dd>

            <dt>OCI 전달</dt>
            <dd>{state.message}</dd>
          </dl>
          {state.status === "applied" ? (
            <p className="tc-muted tc-small ops-explain">
              실제로 쓰이는지는 위 ① 표 &lsquo;운영 기준 활성&rsquo; 행에서 확인하세요.
            </p>
          ) : null}
          {appliedHash ? (
            <div
              className="ops-note"
              title="전송 내용 식별용 해시 (성공 판정은 OCI 검증)"
            >
              적용 내용 해시 {appliedHash.slice(0, 12)}…
            </div>
          ) : null}
          {state.status === "failed" ? (
            <p className="tc-muted tc-small ops-explain">
              OCI(운영 서버) 연결이 없는 환경에서는 전달이 실패할 수 있습니다.
              이 경우 기존 운영 기준은 그대로 유지되며, 실제 운영 환경에서 다시
              전달하면 됩니다. (화면 오류가 아니라 OCI 전달 단계의 실패입니다.)
            </p>
          ) : null}
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
          {applying ? "전달 진행 중..." : "현재 기준 OCI 전달"}
        </button>
      </div>
    </section>
  );
}
