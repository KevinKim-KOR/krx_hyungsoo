"use client";

// OCI 운영 상태 패널 — 「OCI 운영·적용」(`approval`) 화면의 ① 마지막 OCI 점검 (읽기만).
//
// 2026-08-16 사용자 직접 지시로 `diagnostics`(진단·상태)에서 떼어 독립 메뉴
// (`oci_status`)로 두었다. 내용이 "PC 백엔드 기동 시 읽은 OCI 운영 상태" 로 **정상
// 업무 조회**라 미리보기·샘플·LEGACY 와 섞이면 안 되기 때문이다.
//
// 2026-09-27 사용자 직접 지시: 「승인·적용」과 한 화면 「OCI 운영·적용」으로 합쳤다.
// 그래서 이 파일은 **화면이 아니라 패널**이다 — 자기 h1 을 두지 않고, 화면 제목과
// 섹션 제목(h2)은 ApprovalTelegramView 가 단다. `oci_status` 메뉴는 없어졌다.
// 부제(확인 시각) · 요약 · 표 · 각주 · 오류/로딩 표시는 그대로다.
//
// 이 GET 은 백엔드 캐시를 반환하며 OCI 를 재조회하지 않는다(설계자 Q2).
// 자동 polling·수동 새로고침 버튼을 두지 않는다.
//
// 2026-09-27 사용자 직접 지시(가독성): 영어 job 이름 · UTC 시각 · 내부 표기(Q5)를
// 그대로 늘어놓던 목록을 **요약 + 표** 로 바꿨다(사용자가 목업 3안 중 선택).
// 표시만 바꾼다 — 응답 · 판정 · 백엔드는 그대로다. 모르는 job · 상태 · 문구는
// 원문을 그대로 보인다(조용히 숨기지 않는다).
//
// POC6-34(PLAN O1 ~ O4 · 판정 Q1 ~ Q3): 이 값은 '지금' 이 아니라 PC 백엔드가 시작될 때(재시작
// 포함) 한 번 읽은 **마지막 점검** 결과다. 부제는 점검 성공이면 '확인 시각', 실패면 '마지막 점검
// 시도'로 그 시각을 보인다. 요약은 예약표에서 확인한 범위(필수 3종 표기)만 말하고 실제 수신은
// Telegram 으로 안내한다. 파일 두 행은 stat 만 한 결과라 '파일 확인' + 수정 시각이다. 판정
// (`overall`) · 응답은 그대로다. ① 은 읽기만 · 버튼 없음(보유 적용 상태는 글로 「종목 관리」 안내).
// I-8 — 받은 응답을 `onStatus` 로 부모에 알린다(실패 = null) · ② 가 같은 응답을 쓴다.

import { useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchOciStartupStatus,
  type OciJobStatus,
  type OciStartupStatus,
} from "@/lib/api";

const JOB_LABEL: Record<string, string> = {
  crontab: "자동 발송 예약",
  holdings_source: "보유 종목 파일",
  runtime_state_db: "운영 설정 DB",
  push_job_results: "PUSH 발송 결과",
  // 한국 거래일 계약(2026-09-11 사용자 확정 · 설계자 2026-10-02) — 고정 문구 · 늘 정상.
  trading_day_basis: "거래일 기준",
  // POC3-02D-OPS-03 확정 계약 11 — 미국(NYSE) 휴장일 파일 올해 · 다음 해 준비 상태.
  trading_calendar: "미국 휴장일 달력",
  // POC3-02D-OPS-04 항목 3 · 6(사용자 목업 확정 2026-10-06).
  intraday_representatives: "장중 대표 ETF",
  param_active: "운영 기준 활성",
};

const PUSH_KIND_LABEL: Record<string, string> = {
  market_briefing: "시장 브리핑",
  holdings_briefing: "보유 브리핑",
  holdings_risk_alert: "장중 급등락",
};

const ISO_RE = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})/;

type Tone = "ok" | "warn" | "unknown";

/** ISO 시각 → 한국 시간 `M/D(요일) HH:MM` (요일은 선택). 못 읽으면 null. */
export function fmtKst(iso: string | null, withWeekday: boolean): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d);
  const p = (t: string) => parts.find((x) => x.type === t)?.value ?? "";
  const wd = withWeekday ? `(${p("weekday")})` : "";
  return `${p("month")}/${p("day")}${wd} ${p("hour")}:${p("minute")}`;
}

// POC6-34 O1 · I-1 — 언제 읽은 값인지(재시작 포함 · '지금' 아님).
const READ_BASIS = "PC 백엔드가 시작될 때 한 번 읽음(재시작 포함)";

/** ① 부제 — 점검 성공(reachable) = '확인 시각' · 실패 = '마지막 점검 시도' · 시각 없음 · 응답 전 ·
 *  조회 오류(null) = 읽는 때만. */
export function subtitleOf(s: OciStartupStatus | null): string {
  const when = s ? fmtKst(s.checked_at, true) : null;
  if (!s || !when) return READ_BASIS;
  return `${s.reachable ? "확인 시각" : "마지막 점검 시도"} ${when} · ${READ_BASIS}`;
}

/** crontab 누락 문구(`일부 스케줄 누락: a, b`)에서 빠진 예약을 한국어 이름으로. */
function missingKinds(detail: string): string {
  const raw = detail.split(":").slice(1).join(":");
  const names = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((k) => PUSH_KIND_LABEL[k] ?? k);
  return names.length ? names.join(" · ") : detail;
}

const FILE_JOBS = new Set(["holdings_source", "runtime_state_db"]);

function stateOf(j: OciJobStatus): { label: string; tone: Tone } {
  if (j.status === "SUCCESS") {
    if (j.job === "param_active") return { label: "일치", tone: "ok" };
    // POC6-34 O3 — OCI 에서 stat 만 한 결과(내용 검사 없음) → '정상' 이 아니라 '파일 확인'.
    if (FILE_JOBS.has(j.job)) return { label: "파일 확인", tone: "ok" };
    return { label: "정상", tone: "ok" };
  }
  if (j.status === "STALE") {
    if (j.job === "crontab") return { label: "일부 누락", tone: "warn" };
    if (j.job === "trading_calendar") return { label: "준비 필요", tone: "warn" };
    if (j.job === "intraday_representatives") return { label: "확인 필요", tone: "warn" };
    if (j.job === "param_active") return { label: "다름", tone: "warn" };
    return { label: "오래됨", tone: "warn" };
  }
  if (j.status === "UNKNOWN") return { label: "확인 불가", tone: "unknown" };
  return { label: j.status, tone: "unknown" };
}

function contentOf(j: OciJobStatus): string {
  if (j.job === "crontab") {
    if (j.status === "SUCCESS") return "시장 브리핑 · 보유 브리핑 · 장중 급등락";
    if (j.status === "STALE") return `빠짐: ${missingKinds(j.detail)}`;
    if (j.status === "UNKNOWN") return "등록된 예약을 읽지 못함";
  }
  if (FILE_JOBS.has(j.job)) {
    const iso = j.detail.match(ISO_RE)?.[0] ?? null;
    const when = fmtKst(iso, false);
    // POC6-34 O3 · I-4 — 보유 행은 적용 상태를 「종목 관리」로 글 안내(① 안 버튼 없음) · DB 는
    // 알림 실행 기록도 쓰는 파일이라 '설정 바꾼 날' 이 아님.
    if (when) {
      return j.job === "holdings_source"
        ? `파일 수정 시각 ${when} · 보유 적용 상태는 「종목 관리」 맨 아래 ‘OCI 적용’에서 확인`
        : `DB 파일 수정 시각 ${when} (알림 실행 기록도 이 파일에 씀)`;
    }
    if (j.status === "SUCCESS") return "수정 시각 확인 불가";
    if (j.status === "UNKNOWN") return "파일 없음 또는 확인 불가";
  }
  if (j.job === "push_job_results") {
    return "이 화면에서는 볼 수 없음 (발송 여부는 Telegram 에서 확인)";
  }
  return j.detail;
}

function summaryOf(s: OciStartupStatus): { icon: string; title: string; sub: string; tone: Tone } {
  // POC6-34 O2 · I-2 — 예약표에서 읽은 종별 표기만 말한다(실제 발송 · 수신의 근거가 아님).
  if (s.overall === "OPERATING") {
    return {
      icon: "✅",
      title: "예약표에서 필수 3종 표기 확인",
      sub: "시장 브리핑 · 보유 브리핑 · 장중 급등락 예약 표기가 OCI 예약표에 있습니다 · 실제 수신은 Telegram 에서 확인",
      tone: "ok",
    };
  }
  if (s.overall === "DEGRADED") {
    const cron = s.jobs.find((j) => j.job === "crontab");
    return {
      icon: "⚠️",
      title: "예약표에서 필수 3종 중 일부 표기 없음",
      sub: cron ? `빠진 예약: ${missingKinds(cron.detail)}` : s.summary_line,
      tone: "warn",
    };
  }
  return {
    icon: "❔",
    title: "예약표 확인 불가",
    sub: s.reachable ? "OCI 에서 자동 발송 예약을 읽지 못했습니다" : s.summary_line,
    tone: "unknown",
  };
}

export default function OciStatusPanel({
  reloadKey = 0,
  onStatus,
}: {
  // POC3-02D-OPS-04 — ② 적용이 끝나면 바뀐다. 다시 읽어도 OCI 는 재조회하지 않는다
  // (백엔드 캐시 + '운영 기준 활성' 행만 지금 PC 운영 기준과 다시 비교 · POC5-27 부터는 적용
  // 요청 안에서 읽은 값 · 시각으로).
  reloadKey?: number;
  // POC6-34 I-8 — 이 패널이 받은 응답(조회 실패 = null)을 부모에 알린다. 다시 읽기 때도 같다.
  onStatus?: (s: OciStartupStatus | null) => void;
} = {}) {
  const [status, setStatus] = useState<OciStartupStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // 부모가 새 함수를 넘겨도 다시 조회하지 않도록 최신 콜백만 기억한다.
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await fetchOciStartupStatus();
        if (!cancelled) {
          setStatus(s);
          setErrorMsg(null); // 다시 읽기(reloadKey)가 성공하면 앞선 오류를 지운다
          onStatusRef.current?.(s);
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiConfigError) setErrorMsg(`구성 오류: ${e.message}`);
        else if (e instanceof ApiRequestError)
          setErrorMsg(`요청 실패(HTTP ${e.httpStatus}): ${e.message}`);
        else setErrorMsg(`알 수 없는 오류: ${(e as Error).message}`);
        onStatusRef.current?.(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const summary = status ? summaryOf(status) : null;

  return (
    <div>
      {/* 조회 오류면 앞서 받은 시각을 남기지 않는다(O1 — 응답 전 · 조회 오류 = 읽는 때만). */}
      <p className="subtitle">{subtitleOf(errorMsg ? null : status)}</p>

      <div className="card">
        {errorMsg ? (
          <div className="message error">{errorMsg}</div>
        ) : status === null || summary === null ? (
          <div className="helper">확인 중…</div>
        ) : (
          <div>
            <div className={`oci-summary ${summary.tone}`} role="status">
              <span className="oci-summary-icon" aria-hidden="true">
                {summary.icon}
              </span>
              <div>
                <div className="oci-summary-title">{summary.title}</div>
                <div className="oci-summary-sub">{summary.sub}</div>
              </div>
            </div>

            {status.jobs.length > 0 ? (
              <table className="oci-table">
                <thead>
                  <tr>
                    <th scope="col">항목</th>
                    <th scope="col">상태</th>
                    <th scope="col">내용</th>
                  </tr>
                </thead>
                <tbody>
                  {status.jobs.map((j) => {
                    const st = stateOf(j);
                    return (
                      <tr key={j.job}>
                        <td className="oci-table-item">{JOB_LABEL[j.job] ?? j.job}</td>
                        <td>
                          <span className={`oci-state ${st.tone}`}>{st.label}</span>
                        </td>
                        <td>{contentOf(j)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : null}

            <p className="helper" style={{ marginTop: 12 }}>
              PC 백엔드가 시작될 때(재시작 포함) 한 번 읽은 마지막 점검 값입니다. 새로고침해도
              OCI 를 다시 읽지 않습니다. &lsquo;운영 기준 활성&rsquo; 행만 ② [현재 기준 OCI 적용]
              때 다시 읽은 값으로 바뀝니다.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
