"use client";

// POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 STEP (2026-06-20).
//
// 지시문 §5 — 현재 운영 기준 카드 + 단일 버튼(POC5-27 부터 [현재 기준 OCI 적용] · 그 전 OPS-04 는 '전달').
//
// 표시 X (지시문 §5.2):
//   param_id / manual_seed / remote path / SSH target / 파일명 /
//   실행 명령 / raw traceback / token / chat_id.
//
// 2026-09-27 사용자 직접 지시(가독성 · 배치만): 한 줄에 몰아 쓰던 값을 제목 오른쪽 배지 +
//   정렬된 행으로 나눴다. 배지 색은 「OCI 운영·적용」 ① 표와 같은 `.oci-state` 톤을 쓴다.
//
// 2026-10-06 POC3-02D-OPS-04 항목 6: 버튼이 OCI JSON 을 **전달**만 해서 '전달' 문구였다.
// 2026-10-20 POC5-27(PLAN 판정 · 사용자 목업 확인): 버튼이 다시 **실제 적용**이다 —
//   [현재 기준 OCI 적용] = OCI 활성값을 먼저 읽고 같으면 바꾸지 않고, 다르면
//   PC 값을 그대로 발행 · 활성화한 뒤 다시 읽어 확인한다. 끝나면 `onDelivered` 로 ① 을
//   다시 읽게 한다(OCI 를 다시 읽지 않는다).
//
// 2026-11-19 POC6-34(PLAN 판정 Q4 · PLAN O5 ~ O7 · I-9 ~ I-12): 'OCI 활성값 마지막 확인'과
//   '마지막 적용 요청 및 결과'를 가른다.
//   - 머리 배지 = 지금 적용할 일. GET /oci/startup-status 의 'param_active' 행 상태와
//     `param_read_at` 으로 정한다(일치 + 시각 → 변경 없음 · 다름 + 시각 → 변경 있음 · 그 밖 → 확인 불가).
//     차이 건수는 쓰지 않는다(구조 필드 없음 · ① 행 글에만 있음).
//   - 응답 출처(I-8): 부모가 `ociStatus`(① 이 받은 같은 응답)를 넘기면 그것만 쓰고 따로 부르지
//     않는다 — ① '운영 기준 활성' 행과 머리 배지가 늘 같은 응답을 가리킨다. 넘기지 않으면(칸 자체가
//     없으면) 카드가 마운트될 때와 적용 시도가 끝났을 때 직접 부른다. 어느 쪽이든 PC 백엔드 메모리
//     값이고 OCI 를 다시 읽지 않는다.
//   - 옛 머리 배지(적용 요청 결과)는 '마지막 적용 요청 {applied_at} · 결과 {낱말}' 줄로 옮겼다.
//     '마지막 적용 요청'의 형식(YYYY-MM-DD HH:MM, 없으면 "—")은 지시문 §5.2 그대로다.
//   - 버튼은 '확인값 기준으로 적용할 변경 없음'일 때만 [자세히 보기 (필요할 때 다시 적용)](기본 닫힘)
//     안에 둔다. 그 밖에는 지금 자리다. 버튼 동작 · 진행 문구 · 오류 문구 · 확인 창 없음은 그대로다.
//
// 2026-11-19 POC6-34 r1(검증자 R1-F2): 적용 요청의 응답을 받지 못하면 이번 시도를 따로 보인다.
//   서버 기록(`state`)은 덮지 않고 이번 시도만 `lostAttemptAt` 에 둔다. 다음 적용 응답을 받으면
//   지운다. 지난 기록(GET)을 다시 읽어 덮지 않는 POC5-27 계약 · 구성 오류(요청 전 실패) 때 그대로
//   두는 계약은 같다.
// 2026-11-19 POC6-34 RESULT 판정 C3(줄 이름 보완): 응답을 받지 못했거나 HTTP 오류 응답이라 결과를
//   확인할 수 없는 시도는 줄 이름이 '최근 적용 시도'다 — 값 = 버튼 누른 시각(한국 시각
//   YYYY-MM-DD HH:MM) · '결과 확인 불가(응답을 받지 못함)' 또는 '결과 확인 불가(서버가 오류로 응답 ·
//   HTTP n)'. 그 바로 아래('요청 결과' 앞)에 '이전에 확인한 서버 요청 기록' 줄 = 마지막으로 확인된
//   서버 기록의 요청 종료 시각 · 결과 낱말(서버 기록에 요청 기록 · 시각이 없으면 줄 없음). 이전 시각에
//   이번 결과를 붙이지 않는다. 연달아 응답을 못 받아도 이 줄의 출처는 같다(사이의 시도가 아니라
//   마지막으로 확인된 서버 기록). 정상 서버 기록은 그대로 '마지막 적용 요청' + 서버 종료 시각이다.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyThreePushParamToOci,
  fetchThreePushParamState,
  type ThreePushParamState,
  type ThreePushParamStatus,
} from "@/lib/api/threePushParam";
import {
  ApiConfigError,
  ApiRequestError,
  fetchOciStartupStatus,
  type OciStartupStatus,
} from "@/lib/api";
import { fmtKst } from "./OciStatusView";

// 마지막 적용 요청의 결과 낱말(I-11). 옛 머리 배지 낱말을 옮겼다 — active_same 만 '이미 일치'.
function resultWord(status: ThreePushParamStatus): string {
  switch (status) {
    case "active_same":
      return "이미 일치";
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

// '마지막 적용 요청' 값. 요청 기록이 없으면(not_applied) '요청 기록 없음'.
function lastRequestText(s: ThreePushParamState): string {
  if (s.status === "not_applied") return "요청 기록 없음";
  return `${s.applied_at ?? "—"} · 결과 ${resultWord(s.status)}`;
}

// R1-F2 — 응답을 받지 못한 이번 시도의 결과 글.
const LOST_RESULT_TEXT = "결과 확인 불가(응답을 받지 못함)";
// r1 검증 V-1 — 서버가 오류로 응답한 경우(HTTP 코드 있음). 결과는 여전히 모르지만 '응답 없음'은 아니다.
function lostResultText(httpStatus: number | null): string {
  return httpStatus && httpStatus > 0
    ? `결과 확인 불가(서버가 오류로 응답 · HTTP ${httpStatus})`
    : LOST_RESULT_TEXT;
}

/** 이번 시도 시각(한국 시각 · 서버 `applied_at` 과 같은 YYYY-MM-DD HH:MM 표기). */
function kstMinute(d: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d);
  const p = (t: string) => parts.find((x) => x.type === t)?.value ?? "";
  return `${p("year")}-${p("month")}-${p("day")} ${p("hour")}:${p("minute")}`;
}

/** '이전에 확인한 서버 요청 기록' 값 — 마지막으로 확인된 서버 기록에 요청 기록과 시각이 있을 때만. */
function previousRecordText(s: ThreePushParamState | null): string | null {
  if (!s || s.status === "not_applied" || !s.applied_at) return null;
  return `${s.applied_at} · 결과 ${resultWord(s.status)}`;
}

// ── 머리 배지: 지금 적용할 일(Q4 · O5 · I-9) ─────────────────────────────────────

/** undefined = 응답 전 · null = 조회 실패 */
export type OciStatusInput = OciStartupStatus | null | undefined;
export type ParamVerdict = "checking" | "none" | "changes" | "unknown";

const VERDICT_TEXT: Record<ParamVerdict, string> = {
  checking: "적용할 변경 확인 중…",
  none: "확인값 기준으로 적용할 변경 없음",
  changes: "적용할 변경 있음",
  unknown: "적용할 변경 확인 불가",
};
const VERDICT_TONE: Record<ParamVerdict, string> = {
  checking: "unknown",
  none: "ok",
  changes: "warn",
  unknown: "unknown",
};

// 백엔드는 UTC ISO(isoformat · 시간대 포함)로 준다. 문자열인지가 아니라 실제로 읽히는지 본다.
const ISO_FULL = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function isStatusObject(oci: OciStatusInput): oci is OciStartupStatus {
  return typeof oci === "object" && oci !== null;
}

/** OCI 활성값을 읽은 시각(한국 시각 · ① 부제와 같은 표기). 없거나 못 읽으면 null. */
function paramReadAt(oci: OciStatusInput): string | null {
  if (!isStatusObject(oci)) return null;
  const raw: unknown = oci.param_read_at;
  if (typeof raw !== "string" || !ISO_FULL.test(raw)) return null;
  return fmtKst(raw, true);
}

/** 'param_active' 행 상태 + 읽은 시각으로 지금 적용할 일을 정한다. */
export function paramVerdict(oci: OciStatusInput): ParamVerdict {
  if (oci === undefined) return "checking";
  if (!isStatusObject(oci)) return "unknown";
  if (paramReadAt(oci) === null) return "unknown";
  const jobs: unknown = oci.jobs;
  if (!Array.isArray(jobs)) return "unknown";
  const rows = jobs.filter(
    (j): j is { job: string; status: unknown } =>
      typeof j === "object" && j !== null && (j as { job?: unknown }).job === "param_active",
  );
  // 행이 없거나 둘 이상이면(응답 이상) 판정하지 않는다.
  if (rows.length !== 1) return "unknown";
  if (rows[0].status === "SUCCESS") return "none";
  if (rows[0].status === "STALE") return "changes";
  return "unknown";
}

/** 'OCI 활성값 마지막 확인' 값(I-10). */
function paramReadLine(oci: OciStatusInput): string {
  if (oci === undefined) return "확인 중…";
  const at = paramReadAt(oci);
  if (at === null || !isStatusObject(oci)) return "확인 불가";
  if (oci.param_source === "startup") return `${at} · 마지막 OCI 점검 때 읽음`;
  if (oci.param_source === "apply") return `${at} · 적용 요청 때 읽음`;
  return at;
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

type ThreePushParamCardProps = {
  // 적용 시도가 끝나면 부른다 — ① '운영 기준 활성' 행을 다시 읽게 한다(OCI 재조회 없음).
  onDelivered?: () => void;
  // POC6-34 I-8 — ① 이 받은 GET /oci/startup-status 응답(undefined = 응답 전 · null = 조회 실패).
  // 이 칸을 넘기면(값이 undefined 여도) 카드는 따로 부르지 않는다.
  ociStatus?: OciStatusInput;
};

export default function ThreePushParamCard(props: ThreePushParamCardProps = {}) {
  const { onDelivered } = props;
  const sharedOci = Object.prototype.hasOwnProperty.call(props, "ociStatus");
  const [state, setState] = useState<ThreePushParamState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [applying, setApplying] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // 진행 상태 단계 표시 (지시문 §5.4 · POC5-27 문구): "OCI 활성값 읽는 중" → "OCI 에 적용 중" →
  // "다시 읽어 확인 중".
  const [progressStage, setProgressStage] = useState<string | null>(null);
  // POC3-07 (Q4): 표시용 전송 payload SHA-256 (성공 판정 아님, 대조 참고용).
  const [appliedHash, setAppliedHash] = useState<string | null>(null);
  // R1-F2 — 응답을 받지 못한 이번 시도의 버튼 누른 시각. 있으면 `state` 는 이전 서버 기록이다.
  const [lostAttemptAt, setLostAttemptAt] = useState<string | null>(null);
  // r1 검증 V-1 — 그 시도가 HTTP 오류 응답으로 끝났으면 코드(응답 자체가 없으면 null).
  const [lostAttemptHttp, setLostAttemptHttp] = useState<number | null>(null);
  // POC6-34 — 카드가 직접 부른 GET /oci/startup-status 응답(undefined = 응답 전 · null = 조회 실패).
  // 부모가 `ociStatus` 를 넘기면 쓰지 않는다.
  const [ownOciStatus, setOwnOciStatus] = useState<OciStatusInput>(undefined);
  const ociStatus = sharedOci ? props.ociStatus : ownOciStatus;
  // 늦게 온 이전 응답이 새 응답을 덮지 않게 한다(마운트 조회가 적용 뒤 조회보다 늦게 끝나는 경우).
  const ociSeq = useRef(0);

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

  // 다시 읽는 동안은 '확인 중'이다 — 적용 전에 받은 판정을 적용 뒤 판정처럼 보이지 않게 한다.
  // 조회가 실패하면 앞선 값을 남기지 않고 '확인 불가'(null)로 둔다.
  const loadOciStatus = useCallback(async () => {
    const seq = ++ociSeq.current;
    setOwnOciStatus(undefined);
    try {
      const s = await fetchOciStartupStatus();
      if (seq === ociSeq.current) setOwnOciStatus(s ?? null);
    } catch {
      if (seq === ociSeq.current) setOwnOciStatus(null);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (sharedOci) return; // ① 의 같은 응답을 쓴다(따로 부르지 않음)
    loadOciStatus();
    return () => {
      ociSeq.current += 1; // 사라진 뒤 도착한 응답은 버린다
    };
  }, [sharedOci, loadOciStatus]);

  const handleApply = useCallback(async () => {
    if (applying) return;
    // 이번 시도 시각은 응답이 아니라 버튼을 누른 때다(응답이 없으면 서버 시각도 없다).
    const pressedAt = kstMinute(new Date());
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
      setLostAttemptAt(null); // 응답을 받았다 — 응답 없는 시도 표시는 지운다
      setLostAttemptHttp(null);
      setAppliedHash(result.content_sha256 ?? null);
      setProgressStage(null);
    } catch (e) {
      setErrorMsg(describeError(e));
      setProgressStage(null);
      // POC5-27 r2(검증자 F1 · 설계 §4): 응답을 받지 못했으면(시간 초과 · 연결 끊김 · 서버 오류)
      // 요청이 서버에 닿아 적용이 진행됐을 수 있다 — 이번 결과는 '확인 불가'다. 지난 기록(GET)으로
      // 다시 읽어 덮지 않는다(진행 중이면 GET 은 아직 이전 성공 기록 · 이번 오류 안내도 지워진다).
      // 구성 오류는 요청을 보내기 전 실패라 카드 상태를 그대로 둔다(AC-9 · 기존 PARAM 무효화 없음).
      // r3(검증자 F1-NULL): 이전 상태가 없어도(첫 상태 조회 실패) 같다 — 적용 기준은 모르므로
      // '—'(카드의 기존 빈 값 표기)로 두고 '확인 불가'를 보인다.
      // POC6-34 r1(R1-F2): 이전 서버 기록(`state`)은 그대로 두고 이번 시도 시각만 따로 둔다 — 이전
      // 시각에 이번 결과를 붙이지 않는다. 이어서 또 응답이 없으면 '최근 적용 시도' 시각만 바뀌고,
      // '이전에 확인한 서버 요청 기록'은 마지막으로 확인된 서버 기록 그대로다(RESULT 판정 C3).
      if (!(e instanceof ApiConfigError)) {
        setLostAttemptAt(pressedAt);
        setLostAttemptHttp(e instanceof ApiRequestError && e.httpStatus > 0 ? e.httpStatus : null);
        setAppliedHash(null);
      }
    } finally {
      timers.forEach(clearTimeout);
      setProgressStage(null);
      setApplying(false);
      // POC6-34 — 적용 시도가 끝나면 OCI 활성값 확인 시각 · 상태를 다시 읽는다(OCI 재조회 없음).
      // 부모의 같은 응답을 쓰면 부모가 ① 을 다시 읽을 때(onDelivered) 함께 바뀐다.
      if (!sharedOci) loadOciStatus();
      onDelivered?.();
    }
  }, [applying, onDelivered, loadOciStatus, sharedOci]);

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

  const verdict = paramVerdict(ociStatus);
  // R1-F2 — 응답을 받지 못한 이번 시도가 있으면 줄 값은 이번 시도 것이고, `state` 는 이전 서버 기록이다.
  const lost = lostAttemptAt !== null;
  const hasRecord = state !== null || lost;
  const shownStatus = lost ? "unconfirmed" : state?.status;
  // RESULT 판정 C3 — 결과를 확인할 수 없는 이번 시도는 '최근 적용 시도', 서버 기록은 '마지막 적용 요청'.
  const requestLabel = lost ? "최근 적용 시도" : "마지막 적용 요청";
  const lastRequestLine = lost
    ? `${lostAttemptAt} · ${lostResultText(lostAttemptHttp)}`
    : state
      ? lastRequestText(state)
      : "";
  const requestMessage = lost ? UNCONFIRMED_MESSAGE : (state?.message ?? "");
  const previousRecord = lost ? previousRecordText(state) : null;
  // 지시문 §5.3 — 버튼은 하나만 둔다. 자리만 판정에 따라 바뀐다(I-12).
  const applyButton = (
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
  );

  return (
    <section aria-labelledby="three-push-param-h" className="tc-card ops-card">
      <div className="ops-card-head">
        <h3 id="three-push-param-h">현재 운영 기준</h3>
        <span className={`oci-state ${VERDICT_TONE[verdict]}`}>{VERDICT_TEXT[verdict]}</span>
      </div>
      <dl className="ops-kv">
        {hasRecord ? (
          <>
            <dt>적용 기준</dt>
            <dd>
              <strong>{state?.display_label ?? "—"}</strong>
            </dd>
          </>
        ) : null}

        <dt>OCI 활성값 마지막 확인</dt>
        <dd>{paramReadLine(ociStatus)}</dd>

        {hasRecord ? (
          <>
            {/* 형식 계약(지시문 §5.2): YYYY-MM-DD HH:MM, 없으면 "—". 다시 바꾸지 않는다. */}
            <dt>{requestLabel}</dt>
            <dd>{lastRequestLine}</dd>

            {/* RESULT 판정 C3 — 이번 시도 줄 바로 아래('요청 결과' 앞). */}
            {previousRecord ? (
              <>
                <dt>이전에 확인한 서버 요청 기록</dt>
                <dd>{previousRecord}</dd>
              </>
            ) : null}

            <dt>요청 결과</dt>
            <dd>{requestMessage}</dd>
          </>
        ) : null}
      </dl>
      {hasRecord ? (
        <div>
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
          {shownStatus === "failed" ? (
            <p className="tc-muted tc-small ops-explain">
              OCI 활성값은 바뀌지 않았습니다. 화면 오류가 아니라 OCI 적용 단계의
              실패이며, 다시 누르면 처음부터(실제 활성값 읽기부터) 다시 합니다.
            </p>
          ) : null}
          {shownStatus === "unconfirmed" ? (
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

      {verdict === "none" ? (
        <details className="ops-details" style={{ marginTop: 12 }}>
          <summary>자세히 보기 (필요할 때 다시 적용)</summary>
          <p className="tc-muted tc-small ops-explain">
            확인값 기준으로 지금 적용할 변경은 없습니다. 다시 적용하면 먼저 OCI 활성값을
            읽고, 같으면 OCI 에 쓰지 않습니다.
          </p>
          <div style={{ marginTop: 8 }}>{applyButton}</div>
        </details>
      ) : (
        <div style={{ marginTop: 16 }}>{applyButton}</div>
      )}
    </section>
  );
}
