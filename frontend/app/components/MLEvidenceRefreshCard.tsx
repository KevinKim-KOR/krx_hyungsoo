"use client";

// POC2 UI 안전실행 (2026-06-11) — 이전 자료와 실험 다시 만들기 카드(옛 이름 'ML evidence 갱신').
//
// 2026-11-01 POC6-15(판정 §3 · §4 · PLAN §8-2 · §8-3 · 목업 3):
// - 순서 = 제목 → 현재 결론 한 줄 → 버튼 → 짧은 설명 → 단계 표 → 접힌 '자세한 정보(개발 정보)'.
// - 화면 글자는 쉬운 한국어. 작업 번호 · 요청 위치 · 신호(heartbeat) 시각 · 단계 원문 · 파일 경로 ·
//   마지막 성공 요약 원문은 접힌 개발 정보 안으로 옮겼다. 실패 · 시각 · 점검 결과는 결론과 본문에 그대로 둔다.
// - 알려진 고정 문장(단계 요약 JSON · 실패 문장 3종 · 빈 기록 · 손상 안내)만 쉬운 말로 요약하고,
//   틀에 안 맞는 문장 · 모르는 상태 값은 원문을 그대로 보이며 실패면 '원인 확인 필요'를 붙인다.
// - 바꾸지 않은 것: 조회(처음 1번) · 시작 요청 · 실행 중 5초 다시 읽기 · 두 버튼의 동작과 막힘 조건.
//
// 책임 (지시문 §5.1):
// - 마지막 실행 상태 / 시작 / 종료 / 단계별 상태 / 실패 내용 표시.
// - '이전 자료와 실험 다시 만들기' 버튼 — POST /ml/jobs/evidence-refresh.
// - 실행 중이면 버튼 비활성화 + 5초 간격 polling 으로 자동 갱신.
//
// 본 카드는 baseline 재계산을 직접 하지 않는다. backend background job 만 시작
// 하고 상태를 조회한다. 매수/매도/추천/현금비중/조정장/위험 알림 문구 0건 (§8).

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
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
import {
  CardConclusion,
  DevDetails,
  fmtCount,
  kstText,
  toneBadgeClass,
  type ConclusionTone,
} from "./MLCardParts";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MlJobLatestResponse };

// 시작 요청 결과 안내 — text = 버튼 옆에 보이는 쉬운 말 · raw = 응답 원문(개발 정보).
type ActionNote = { text: string; raw: string | null };

type StepKey = keyof MlJobState["steps"];

const DASH = "-";

const STEP_NAMES: Record<StepKey, string> = {
  feature_generation: "이전 학습용 값 만들기",
  sanity_check: "자료 점검",
  baseline_lookback: "Baseline 되돌아보기 검증",
};

const STEP_LABELS: Record<StepKey, string> = {
  feature_generation: `1) ${STEP_NAMES.feature_generation}`,
  sanity_check: `2) ${STEP_NAMES.sanity_check}`,
  baseline_lookback: `3) ${STEP_NAMES.baseline_lookback}`,
};

const STEP_KEYS = Object.keys(STEP_LABELS) as StepKey[];

// 백엔드 고정 문장(app/api_ml_jobs.py · app/ml_job_runner.py) — 같은 문장일 때만 쉬운 말로 바꾼다.
const ALREADY_RUNNING_RAW = "ML evidence refresh is already running";
const EMPTY_RAW_PREFIX = "ML evidence 갱신 job 이 아직 한 번도 실행되지 않았습니다.";
const CORRUPT_RAW_PREFIX = "ml_job_status 파일이 손상되어 읽을 수 없습니다";
// 시작 요청(POST)이 손상 때문에 거절될 때의 고정 문장(JobStatusCorruptedError · 파일 경로가 들어 있음).
const START_CORRUPT_RAW_PREFIX = "ml_job_status 파일 손상 (";
const SKIPPED_RAW = "이전 단계 실패";
const FEATURE_ZERO_RE =
  /^feature generation upsert 0건 — etf=(-?\d+) market=(-?\d+)\. 두 산출물 모두 필수이며 DB 가 비어있거나 universe coverage 0 이다$/;
const SANITY_ERROR_RE = /^sanity_status=error \/ errors=(\d+) warnings=(\d+)$/;
const BASELINE_ERROR_RE = /^baseline status=error \/ errors=(\d+) warnings=(\d+)$/;

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function isRunning(job: MlJobState | null | undefined): boolean {
  if (!job) return false;
  return job.status === "running" || job.status === "queued";
}

// ── 표시용 작은 함수(값을 바꾸지 않는다 · 새 판정 없음) ─────────────────────────

function stepStatusView(status: string | undefined): { tone: ConclusionTone; text: string } {
  if (status === "success") return { tone: "ok", text: "완료" };
  if (status === "running") return { tone: "warn", text: "실행 중" };
  if (status === "queued") return { tone: "warn", text: "대기" };
  if (status === "failed") return { tone: "bad", text: "실패" };
  if (status === "skipped") return { tone: "muted", text: "건너뜀" };
  if (status == null) return { tone: "muted", text: "기록 없음" };
  return { tone: "muted", text: `${status} (확인 필요)` };
}

function sanityWord(s: string): string {
  if (s === "ok") return "정상";
  if (s === "warn") return "주의";
  if (s === "error") return "오류";
  return `${s}(확인 필요)`;
}

function baselineWord(s: string): string {
  // ok = 보고가 있음(Baseline 카드 배지 '보고 있음'과 같은 말 · 2026-11-02 RESULT 판정 §3 — 모든 점검 정상이 아님)
  if (s === "ok") return "있음";
  if (s === "warn") return "주의";
  if (s === "insufficient_history") return "자료 부족";
  if (s === "error") return "오류";
  return `${s}(확인 필요)`;
}

function parseObject(text: string): Record<string, unknown> | null {
  try {
    const v: unknown = JSON.parse(text);
    return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

const isInt = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);
const isStrOrNull = (v: unknown): v is string | null => v === null || typeof v === "string";

// 단계 메시지 → 쉬운 말. 알려진 틀(성공 요약 JSON · 실패 문장)에 맞을 때만 known=true.
function stepSummary(key: StepKey, message: string | undefined): { text: string; known: boolean } {
  const m = message ?? "";
  if (m === "") return { text: DASH, known: true };
  if (m === SKIPPED_RAW) return { text: "이전 단계가 실패해 실행하지 않음", known: true };
  const o = parseObject(m);
  if (o && key === "feature_generation") {
    if (isStrOrNull(o.last_asof) && isInt(o.etf_upserted) && isInt(o.market_upserted)) {
      return {
        text: `마지막 자료일 ${o.last_asof ?? DASH} · ETF ${fmtCount(o.etf_upserted)}줄 · 시장 ${fmtCount(o.market_upserted)}줄 저장`,
        known: true,
      };
    }
  }
  if (o && key === "sanity_check") {
    if (
      typeof o.sanity_status === "string" &&
      isInt(o.etf_feature_rows) &&
      isInt(o.warnings) &&
      isInt(o.errors)
    ) {
      return {
        text: `점검 결과 '${sanityWord(o.sanity_status)}' · ETF 학습용 값 ${fmtCount(o.etf_feature_rows)}줄 · 경고 ${fmtCount(o.warnings)}건 · 오류 ${fmtCount(o.errors)}건`,
        known: true,
      };
    }
  }
  if (o && key === "baseline_lookback") {
    if (
      isStrOrNull(o.feature_asof_end) &&
      (o.evaluated_days === null || isInt(o.evaluated_days)) &&
      typeof o.baseline_report_status === "string"
    ) {
      return {
        text: `자료 끝 ${o.feature_asof_end ?? DASH} · 평가 ${fmtCount(o.evaluated_days)}거래일 · 보고 ${baselineWord(o.baseline_report_status)}`,
        known: true,
      };
    }
  }
  const fz = key === "feature_generation" ? FEATURE_ZERO_RE.exec(m) : null;
  if (fz) {
    return {
      // 서버 조건 = etf ≤ 0 또는 market ≤ 0(app/ml_job_runner.py) — 한쪽만 0 이어도 실패하므로 '둘 다 0' 으로 쓰지 않는다.
      text: `ETF · 시장 값 중 저장된 줄이 0건인 쪽이 있음(ETF ${fmtCount(Number(fz[1]))}줄 · 시장 ${fmtCount(Number(fz[2]))}줄) — 두 가지가 모두 있어야 합니다. 서버 설명: 자료 저장소가 비어 있거나 대상 종목 범위가 0`,
      known: true,
    };
  }
  const se = key === "sanity_check" ? SANITY_ERROR_RE.exec(m) : null;
  if (se) {
    return {
      text: `점검 결과 '오류' · 오류 ${fmtCount(Number(se[1]))}건 · 경고 ${fmtCount(Number(se[2]))}건 — 자세한 내용은 「이전 자료 점검」`,
      known: true,
    };
  }
  const be = key === "baseline_lookback" ? BASELINE_ERROR_RE.exec(m) : null;
  if (be) {
    return {
      text: `계산 결과 '오류' · 오류 ${fmtCount(Number(be[1]))}건 · 경고 ${fmtCount(Number(be[2]))}건 — 자세한 내용은 「Baseline 실험」`,
      known: true,
    };
  }
  return { text: m, known: false };
}

// 원문 시각 → 한국 시각. 시간대 없는 값 · 깨진 값은 원문 그대로, 없으면 "-".
function fullTime(iso: string | null | undefined, seconds = true): string {
  if (iso == null) return DASH;
  return kstText(iso, seconds) ?? iso;
}

// 표 칸 — 작업 시작일과 같은 날이면 'HH:MM:SS' 만, 다르면 날짜까지.
function cellTime(iso: string | null | undefined, baseDate: string | null): string {
  if (iso == null) return DASH;
  const k = kstText(iso);
  if (k == null) return iso;
  const [d, t] = k.split(" ");
  return baseDate === d ? t : k;
}

function durationText(start: string | null, end: string | null): string | null {
  if (kstText(start) == null || kstText(end) == null) return null;
  const ms = new Date(end as string).getTime() - new Date(start as string).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const s = Math.round(ms / 1000);
  if (s < 60) return `약 ${s}초`;
  return `약 ${Math.floor(s / 60)}분 ${s % 60}초`;
}

function stepOf(job: MlJobState, key: StepKey): MlJobStepState | undefined {
  return job.steps?.[key];
}

// 실패 내용 — 알려진 실패 문장이면 쉬운 말, 아니면 원문(+ 원인 확인 필요).
function failureDetail(job: MlJobState): { key: StepKey | null; text: string | null; known: boolean } {
  const key = STEP_KEYS.find((k) => stepOf(job, k)?.status === "failed") ?? null;
  if (key) {
    const msg = stepOf(job, key)?.message ?? "";
    const sum = stepSummary(key, msg);
    if (msg !== "" && sum.known) return { key, text: sum.text, known: true };
  }
  const raw = job.error || (key ? stepOf(job, key)?.message : "") || null;
  return { key, text: raw, known: false };
}

function emptyText(message: string | null): string {
  if (message == null || message.startsWith(EMPTY_RAW_PREFIX)) {
    return "「이전 자료와 실험 다시 만들기」 버튼을 누르면 뒤에서 시작합니다.";
  }
  return message;
}

function corruptText(message: string | null): string {
  if (message == null || message.startsWith(CORRUPT_RAW_PREFIX)) {
    return "실행 상태 기록 파일이 손상되어 읽을 수 없습니다. 파일을 직접 확인하거나 삭제한 뒤 다시 시도하세요. 원인 확인 필요(원문은 아래 자세한 정보).";
  }
  return message;
}

function alreadyRunningText(message: string | null): string {
  const base = "이미 실행 중인 작업이 있어 새로 시작하지 않았습니다.";
  if (message == null || message === ALREADY_RUNNING_RAW) return base;
  return `${base} ${message}`;
}

function startFailText(status: string, message: string | null): string {
  if (status === "error") {
    if (message != null && message.startsWith(START_CORRUPT_RAW_PREFIX)) {
      return "시작하지 못했습니다: 실행 상태 기록 파일이 손상되어 새로 시작하지 않았습니다 · 원인 확인 필요(원문은 아래 자세한 정보)";
    }
    return `시작하지 못했습니다: ${message ??"서버가 사유를 보내지 않았습니다 · 원인 확인 필요"}`;
  }
  return `시작 요청 결과를 알 수 없습니다(응답 상태 '${status}') · 원인 확인 필요${message ? `: ${message}` : ""}`;
}

function conclusionOf(state: LoadState): { tone: ConclusionTone; label: string; text: ReactNode } {
  if (state.phase === "loading") {
    return { tone: "muted", label: "불러오는 중", text: "실행 기록을 읽는 중입니다." };
  }
  if (state.phase === "error") {
    return {
      tone: "bad",
      label: "불러오지 못함",
      text: "실행 기록을 서버에서 받지 못했습니다 · 원인 확인 필요",
    };
  }
  const { data } = state;
  if (data.status === "empty") {
    return { tone: "muted", label: "실행 기록 없음", text: "아직 한 번도 실행하지 않았습니다." };
  }
  if (data.status === "error") {
    return {
      tone: "bad",
      label: "상태 기록 손상",
      text: "실행 상태 기록을 읽을 수 없습니다 · 원인 확인 필요",
    };
  }
  if (data.status !== "ok") {
    return {
      tone: "warn",
      label: "알 수 없는 응답",
      text: `응답 상태 '${String(data.status)}' · 원인 확인 필요`,
    };
  }
  const job = data.job;
  if (!job) {
    return {
      tone: "bad",
      label: "기록 내용 없음",
      text: "응답에 실행 기록 내용이 없습니다 · 원인 확인 필요",
    };
  }
  const start = fullTime(job.started_at, false);
  if (job.status === "success") {
    const done = STEP_KEYS.filter((k) => stepOf(job, k)?.status === "success").length;
    const dur = durationText(job.started_at, job.finished_at);
    return {
      tone: "ok",
      label: "완료",
      text: (
        <>
          <b>{start}</b> 실행 ·{" "}
          {done === STEP_KEYS.length
            ? `${STEP_KEYS.length}단계 모두 완료`
            : `${STEP_KEYS.length}단계 중 ${done}단계만 완료로 기록됨 · 확인 필요`}
          {dur ? ` · ${dur}` : ""} · 완료는 실험 채택을 뜻하지 않음
        </>
      ),
    };
  }
  if (job.status === "running") {
    const now = STEP_KEYS.find((k) => stepOf(job, k)?.status === "running");
    return {
      tone: "warn",
      label: "실행 중",
      text: (
        <>
          <b>{start}</b> 시작{now ? ` · 지금 「${STEP_NAMES[now]}」 단계` : ""}
        </>
      ),
    };
  }
  if (job.status === "queued") {
    return {
      tone: "warn",
      label: "시작 대기",
      text: (
        <>
          <b>{start}</b> 요청 · 첫 단계 시작을 기다리는 중
        </>
      ),
    };
  }
  if (job.status === "failed") {
    const f = failureDetail(job);
    return {
      tone: "bad",
      label: "실패",
      text: (
        <>
          <b>{start}</b> 실행{f.key ? ` · 「${STEP_NAMES[f.key]}」 단계에서 실패` : ""} ·{" "}
          {f.known ? f.text : "원인 확인 필요"}
        </>
      ),
    };
  }
  return {
    tone: "warn",
    label: "알 수 없는 상태",
    text: (
      <>
        <b>{start}</b> · 상태 값 &apos;{String(job.status)}&apos; · 원인 확인 필요
      </>
    ),
  };
}

// 접힌 개발 정보 — 기존 응답이 준 값만(작업 번호 · 요청 위치 · 신호 시각 · 원문 · 파일 경로).
function devLines(state: LoadState, action: ActionNote | null): string[] {
  const lines: string[] = [];
  if (state.phase === "ready") {
    const { data } = state;
    lines.push(`응답 상태 원문: ${data.status}`);
    if (data.message) lines.push(`응답 메시지 원문: ${data.message}`);
    const job = data.job;
    if (data.status === "ok" && job) {
      lines.push(`작업 번호 ${job.job_id} · 요청 위치 ${job.requested_by}`);
      lines.push(`작업 상태 원문: ${job.status}`);
      lines.push(`시작 원문 ${job.started_at ?? DASH} · 끝 원문 ${job.finished_at ?? DASH}`);
      const hb = job.last_heartbeat_at;
      const hbKst = kstText(hb);
      lines.push(`마지막 신호(heartbeat) ${hbKst ? `${hbKst} (원문 ${hb})` : (hb ?? DASH)}`);
      if (job.message) lines.push(`작업 메시지 원문: ${job.message}`);
      if (job.error) lines.push(`실패 원문: ${job.error}`);
      for (const key of STEP_KEYS) {
        const s = stepOf(job, key);
        lines.push(
          `${key} · 상태 ${s?.status ?? DASH} · 시작 원문 ${s?.started_at ?? DASH} · 끝 원문 ${s?.finished_at ?? DASH} · 파일 ${s?.artifact_path || DASH} · 원문 ${s?.message || DASH}`,
        );
      }
      if (job.last_success_summary) {
        lines.push(`마지막 성공 요약 원문:\n${JSON.stringify(job.last_success_summary, null, 2)}`);
      }
    }
  }
  if (action?.raw) lines.push(`시작 요청 응답 원문: ${action.raw}`);
  return lines;
}

export default function MLEvidenceRefreshCard() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [starting, setStarting] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<ActionNote | null>(null);
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
      const raw = `status=${res.status} · message=${res.message ?? DASH}`;
      if (res.status === "already_running") {
        setActionMessage({ text: alreadyRunningText(res.message), raw });
      } else if (res.status === "accepted") {
        setActionMessage({
          text: "이전 자료와 실험 다시 만들기를 시작했습니다. 뒤에서 이어서 실행됩니다.",
          raw,
        });
      } else {
        setActionMessage({ text: startFailText(res.status, res.message), raw });
      }
      await load();
    } catch (e) {
      setActionMessage({ text: `시작 요청을 보내지 못했습니다 — ${describeError(e)}`, raw: null });
    } finally {
      setStarting(false);
    }
  }, [load]);

  const job = state.phase === "ready" ? state.data.job : null;
  const running = isRunning(job);
  const buttonDisabled = starting || running;
  const concl = conclusionOf(state);
  const dev = devLines(state, actionMessage);

  return (
    <div className="card">
      <h2>이전 자료와 실험 다시 만들기</h2>

      <CardConclusion tone={concl.tone} label={concl.label}>
        {concl.text}
      </CardConclusion>

      <div className="ml-card-controls">
        <button type="button" onClick={handleStart} disabled={buttonDisabled}>
          이전 자료와 실험 다시 만들기
        </button>
        <button type="button" onClick={load} disabled={starting}>
          상태 다시 읽기
        </button>
        {running && (
          <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
            실행 중 · 5초마다 상태를 자동으로 다시 읽습니다.
          </span>
        )}
      </div>

      {actionMessage && (
        <div className="message info" style={{ marginBottom: 8 }}>
          {actionMessage.text}
        </div>
      )}

      <p className="helper" style={{ marginBottom: 8 }}>
        위의 「이전 학습용 값」 → 「이전 자료 점검」 → 아래 「Baseline 실험」을 한 번에 다시
        만듭니다. <b>현재 예측 비교의 입력이나 모델은 바뀌지 않습니다.</b> 실행은 뒤에서
        이어지고 화면은 멈추지 않습니다.
      </p>

      {state.phase === "error" && (
        <div className="message error">상태를 읽지 못했습니다 — {state.message}</div>
      )}

      {state.phase === "ready" && state.data.status === "empty" && (
        <div className="message info">{emptyText(state.data.message)}</div>
      )}

      {/* FIX r2 (B-1) — status 파일 손상을 미실행과 구분해 명시 노출. 사용자가
          파일을 직접 확인 또는 삭제 후 재시도해야 한다. */}
      {state.phase === "ready" && state.data.status === "error" && (
        <div className="message error">{corruptText(state.data.message)}</div>
      )}

      {state.phase === "ready" && state.data.status === "ok" && job && (
        <JobStatusPanel job={job} />
      )}

      {dev.length > 0 && <DevDetails>{dev.join("\n")}</DevDetails>}
    </div>
  );
}

function JobStatusPanel({ job }: { job: MlJobState }) {
  const baseDate = kstText(job.started_at)?.split(" ")[0] ?? null;
  const showFailure = job.status === "failed" || Boolean(job.error);
  const f = showFailure ? failureDetail(job) : null;
  return (
    <div>
      {f && (
        <div className="message error" style={{ marginBottom: 8 }}>
          실패 내용:{" "}
          {f.known
            ? f.text
            : f.text
              ? `원인 확인 필요 · 원문 ${f.text}`
              : "서버가 사유를 남기지 않았습니다 · 원인 확인 필요"}
        </div>
      )}

      <p className="helper" style={{ marginBottom: 6 }}>
        시작 {fullTime(job.started_at)} · 끝 {fullTime(job.finished_at)} (한국 시각)
      </p>

      <table className="market-topn-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th style={{ width: 220 }}>단계</th>
            <th style={{ width: 100 }}>결과</th>
            <th style={{ width: 110 }}>시작</th>
            <th style={{ width: 110 }}>끝</th>
            <th>요약</th>
          </tr>
        </thead>
        <tbody>
          {STEP_KEYS.map((key) => {
            const s = stepOf(job, key);
            const v = stepStatusView(s?.status);
            const sum = stepSummary(key, s?.message);
            const unknownFail = s?.status === "failed" && !sum.known;
            return (
              <tr key={key}>
                <td>{STEP_LABELS[key]}</td>
                <td>
                  <span className={toneBadgeClass(v.tone)}>{v.text}</span>
                </td>
                <td style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                  {cellTime(s?.started_at, baseDate)}
                </td>
                <td style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                  {cellTime(s?.finished_at, baseDate)}
                </td>
                <td style={{ fontSize: "0.8rem" }}>
                  {unknownFail ? `원인 확인 필요 · 원문 ${sum.text}` : sum.text}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
