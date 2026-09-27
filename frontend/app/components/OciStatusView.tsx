"use client";

// OCI 운영 상태 패널 — 「OCI 운영·적용」(`approval`) 화면의 ① 지금 OCI 상태 (읽기만).
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

import { useEffect, useState } from "react";
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

function stateOf(j: OciJobStatus): { label: string; tone: Tone } {
  if (j.status === "SUCCESS") return { label: "정상", tone: "ok" };
  if (j.status === "STALE")
    return { label: j.job === "crontab" ? "일부 누락" : "오래됨", tone: "warn" };
  if (j.status === "UNKNOWN") return { label: "확인 불가", tone: "unknown" };
  return { label: j.status, tone: "unknown" };
}

function contentOf(j: OciJobStatus): string {
  if (j.job === "crontab") {
    if (j.status === "SUCCESS") return "시장 브리핑 · 보유 브리핑 · 장중 급등락";
    if (j.status === "STALE") return `빠짐: ${missingKinds(j.detail)}`;
    if (j.status === "UNKNOWN") return "등록된 예약을 읽지 못함";
  }
  if (j.job === "holdings_source" || j.job === "runtime_state_db") {
    const iso = j.detail.match(ISO_RE)?.[0] ?? null;
    const when = fmtKst(iso, false);
    if (when) return `마지막 수정 ${when}`;
    if (j.status === "UNKNOWN") return "파일 없음 또는 확인 불가";
  }
  if (j.job === "push_job_results") {
    return "이 화면에서는 볼 수 없음 (발송 여부는 Telegram 에서 확인)";
  }
  return j.detail;
}

function summaryOf(s: OciStartupStatus): { icon: string; title: string; sub: string; tone: Tone } {
  if (s.overall === "OPERATING") {
    return {
      icon: "✅",
      title: "정상 운영 중",
      sub: "자동 발송 예약이 모두 등록되어 있습니다",
      tone: "ok",
    };
  }
  if (s.overall === "DEGRADED") {
    const cron = s.jobs.find((j) => j.job === "crontab");
    return {
      icon: "⚠️",
      title: "일부 예약 누락",
      sub: cron ? `빠진 예약: ${missingKinds(cron.detail)}` : s.summary_line,
      tone: "warn",
    };
  }
  return {
    icon: "❔",
    title: "확인 불가",
    sub: s.reachable ? "OCI 에서 자동 발송 예약을 읽지 못했습니다" : s.summary_line,
    tone: "unknown",
  };
}

export default function OciStatusPanel() {
  const [status, setStatus] = useState<OciStartupStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await fetchOciStartupStatus();
        if (!cancelled) setStatus(s);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiConfigError) setErrorMsg(`구성 오류: ${e.message}`);
        else if (e instanceof ApiRequestError)
          setErrorMsg(`요청 실패(HTTP ${e.httpStatus}): ${e.message}`);
        else setErrorMsg(`알 수 없는 오류: ${(e as Error).message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const checked = status ? fmtKst(status.checked_at, true) : null;
  const summary = status ? summaryOf(status) : null;

  return (
    <div>
      <p className="subtitle">
        PC 백엔드 시작 때 1번 확인{checked ? ` · ${checked}` : ""}
      </p>

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
              PC 백엔드를 시작할 때 한 번 읽은 값입니다. 새로고침해도 OCI 를 다시 읽지
              않습니다.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
