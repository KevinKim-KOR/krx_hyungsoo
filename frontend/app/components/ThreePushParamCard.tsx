"use client";

// POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 STEP (2026-06-20).
//
// 지시문 §5 — 현재 운영 기준 카드 + 단일 버튼(POC5-27 부터 [현재 기준 OCI 적용] · 그 전 OPS-04 는 '전달').
//
// 표시 항목 (지시문 §5.2):
//   - 현재 적용 기준 (display_label)
//   - OCI 적용 결과 (active_same / activated / failed / unconfirmed · 예전 기록 delivered_only · POC5-27)
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
// 2026-10-06 POC3-02D-OPS-04 항목 6: 버튼이 OCI JSON 을 **전달**만 해서 '전달' 문구였다.
// 2026-10-20 POC5-27(PLAN 판정 · 사용자 목업 확인): 버튼이 다시 **실제 적용**이다 —
//   [현재 기준 OCI 적용] = OCI 활성값을 먼저 읽고 같으면 바꾸지 않고(일치 · 변경 없음), 다르면
//   PC 값을 그대로 발행 · 활성화한 뒤 다시 읽어 확인한다. 결과 4종(일치 · 변경 없음 / 적용 완료 /
//   적용 실패 / 확인 불가). 차이는 위 ① 표 '운영 기준 활성' 행(기존 비교 영역)에 있다 — 끝나면
//   `onDelivered` 로 ① 을 다시 읽어 적용 때 읽은 값이 보이게 한다(OCI 를 다시 읽지 않는다).

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
    case "active_same":
      return "일치 · 변경 없음";
    case "activated":
      return "적용 완료";
    case "applying":
    case "busy":
      return "적용 중";
    case "failed":
      return "적용 실패";
    case "unconfirmed":
      return "확인 불가";
    case "verification_required":
      return "확인 필요";
    case "delivered_only":
      return "이전 전달 기록";
    case "not_applied":
    default:
      return "미적용";
  }
}

// `.oci-state` 톤 (globals.css). 일치 · 완료 = ok · 실패/확인 필요 = warn · 진행 중 = info ·
// 확인 불가 · 이전 전달 기록 · 미적용 = unknown(회색 — 실패나 불일치처럼 보이지 않게 · 판정 §5).
function statusBadgeTone(status: ThreePushParamStatus): string {
  switch (status) {
    case "active_same":
    case "activated":
      return "ok";
    case "applying":
    case "busy":
      return "info";
    case "failed":
    case "verification_required":
      return "warn";
    case "unconfirmed":
    case "delivered_only":
    case "not_applied":
    default:
      return "unknown";
  }
}

// 백엔드 'unconfirmed' 문구와 같다(새 문구 아님). 적용 요청의 응답을 받지 못했을 때 화면이 쓴다.
const UNCONFIRMED_MESSAGE =
  "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다.";

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
  // 적용 시도가 끝나면 부른다 — ① '운영 기준 활성' 행을 다시 읽게 한다(OCI 재조회 없음).
  onDelivered?: () => void;
} = {}) {
  const [state, setState] = useState<ThreePushParamState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [applying, setApplying] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // 진행 상태 단계 표시 (지시문 §5.4 · POC5-27 문구): "OCI 활성값 읽는 중" → "OCI 에 적용 중" →
  // "다시 읽어 확인 중".
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
    setProgressStage("OCI 활성값 읽는 중");
    // 동기 호출이지만 사용자에게는 단계 진행이 보이도록 표시(시간 기준 표시 · 실제 단계 아님).
    // 응답이 먼저 오면 남은 타이머를 지운다 — 끝난 뒤 '진행 중' 문구가 다시 나타나지 않게.
    const timers = [
      setTimeout(() => setProgressStage("OCI 에 적용 중"), 400),
      setTimeout(() => setProgressStage("다시 읽어 확인 중"), 1200),
    ];
    try {
      const result = await applyThreePushParamToOci();
      setState(result);
      setAppliedHash(result.content_sha256 ?? null);
      setProgressStage(null);
    } catch (e) {
      setErrorMsg(describeError(e));
      setProgressStage(null);
      // POC5-27 r2(검증자 F1 · 설계 §4): 응답을 받지 못했으면(시간 초과 · 연결 끊김 · 서버 오류)
      // 요청이 서버에 닿아 적용이 진행됐을 수 있다 — 이번 결과는 '확인 불가'다. 지난 기록(GET)으로
      // 다시 읽어 덮지 않는다(진행 중이면 GET 은 아직 이전 성공 기록 · 이번 오류 안내도 지워진다).
      // 구성 오류는 요청을 보내기 전 실패라 카드 상태를 그대로 둔다(AC-9 · 기존 PARAM 무효화 없음).
      // r3(검증자 F1-NULL): 이전 상태가 없어도(첫 상태 조회 실패) 같다 — 적용 기준 · 마지막 적용은
      // 모르므로 '—'(카드의 기존 빈 값 표기)로 두고 '확인 불가'를 보인다.
      if (!(e instanceof ApiConfigError)) {
        setState((prev) => ({
          display_label: prev?.display_label ?? "—",
          applied_at: prev?.applied_at ?? null,
          status: "unconfirmed",
          oci_verified: false,
          message: UNCONFIRMED_MESSAGE,
        }));
        setAppliedHash(null);
      }
    } finally {
      timers.forEach(clearTimeout);
      setProgressStage(null);
      setApplying(false);
      onDelivered?.();
    }
  }, [applying, onDelivered]);

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

            <dt>OCI 적용</dt>
            <dd>{state.message}</dd>
          </dl>
          <p className="tc-muted tc-small ops-explain">
            OCI 러너가 이후 실행에서 읽는 기준을 적용합니다. 이미 시작한 실행은 그때 읽은
            기준으로 끝납니다. 지금 OCI 활성값과의 차이는 위 ① 표 &lsquo;운영 기준
            활성&rsquo; 행에 있습니다.
          </p>
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
              OCI 활성값은 바뀌지 않았습니다. 화면 오류가 아니라 OCI 적용 단계의
              실패이며, 다시 누르면 처음부터(실제 활성값 읽기부터) 다시 합니다.
            </p>
          ) : null}
          {state.status === "unconfirmed" ? (
            <p className="tc-muted tc-small ops-explain">
              다시 누르면 먼저 OCI 의 실제 활성값을 읽고, 이미 지금 기준과 같으면 바꾸지
              않습니다. 자동으로 되돌리거나 다시 적용하지 않습니다.
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
