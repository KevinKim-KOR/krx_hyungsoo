"use client";

// 진단·상태 (diagnostics) — POC3-07 신규.
//
// 설계(§5.3): 정상 업무 메뉴와 시각적으로 분리된 마지막 관리 그룹.
// 목적 3가지:
//   1) PC 백엔드 기동 시 읽은 OCI 상태 상세
//   2) 개발·검증용 기능(샘플·미리보기·개발 호환 점검) 격리
//   3) MOCK·PREVIEW·TEST·LEGACY·미연결 기능 관리
//
// 여기 있는 기능은 정상 업무가 아니다. 미리보기·샘플 결과에는 PREVIEW/TEST 성격을
// 명시한다. 이 화면 지시로 OCI job·Telegram·SCP 를 자동 실행하지 않는다(진단 도구는
// side effect 없는 조회만).
//
// 이동 내역:
//   - DataStatusView            : 기존 데이터 상태 진단 (data_status 메뉴 흡수)
//   - OciStartupStatusDetail    : 기동 시 OCI 상태 상세 (신규)
//   - ManualPreviewSection      : 미리보기·수동 전달 점검 (approval 에서 이동)
//   - DevCompatSection          : 개발·호환 점검 (approval 에서 이동)
//   - DashboardView(LEGACY)     : 기존 대시보드 (dashboard 메뉴 → LEGACY 로 이동)

import { useEffect, useState } from "react";
import DataStatusView from "./DataStatusView";
import DashboardView from "./DashboardView";
import ManualPreviewSection from "./approval/ManualPreviewSection";
import DevCompatSection from "./approval/DevCompatSection";
import type { MenuKey } from "./LeftSidebar";
import {
  ApiConfigError,
  ApiRequestError,
  fetchOciStartupStatus,
  type OciStartupStatus,
  type Run,
} from "@/lib/api";

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
  onNavigate: (key: MenuKey) => void;
}

// 기동 시 읽은 OCI 상태 상세. 이 GET 은 백엔드 캐시를 반환하며 OCI 를 재조회하지
// 않는다(설계자 Q2). 자동 polling·수동 새로고침 버튼을 두지 않는다.
function OciStartupStatusDetail() {
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

  return (
    <section aria-labelledby="oci-startup-h" className="card">
      <h2 id="oci-startup-h">OCI 운영 상태 (기동 시 확인)</h2>
      <p className="helper" style={{ marginBottom: 12 }}>
        아래는 PC 백엔드가 <strong>기동될 때 1회</strong> 읽은 OCI 상태입니다.
        화면을 새로고침해도 OCI 를 다시 조회하지 않습니다(기동 시 확인값 표시).
      </p>
      {errorMsg ? (
        <div className="message error">{errorMsg}</div>
      ) : status === null ? (
        <div className="helper">확인 중…</div>
      ) : (
        <div>
          <div className="helper" style={{ marginBottom: 8 }}>
            확인 시각:{" "}
            {status.checked_at
              ? new Date(status.checked_at).toLocaleString()
              : "미확인"}{" "}
            · 상태: {status.overall} · 접속: {status.reachable ? "성공" : "실패"}
          </div>
          <ul style={{ margin: "8px 0", paddingLeft: 18 }}>
            {status.jobs.map((j) => (
              <li key={j.job} style={{ marginBottom: 4 }}>
                <strong>{j.job}</strong>: {j.status}
                {j.detail ? ` — ${j.detail}` : ""}
              </li>
            ))}
          </ul>
          {status.note ? (
            <p className="helper" style={{ marginTop: 8 }}>
              {status.note}
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}

export default function DiagnosticsView({ run, setRun, onNavigate }: Props) {
  return (
    <section aria-labelledby="diagnostics-h">
      <h1 id="diagnostics-h">진단·상태</h1>
      <p className="helper" style={{ marginBottom: 16 }}>
        정상 업무 화면이 아닙니다. 기동 시 OCI 상태 상세, 데이터 진단, 미리보기·샘플
        (PREVIEW/TEST), 참고용 이전 화면(LEGACY)을 이곳에서 관리합니다.
      </p>

      {/* A. 기동 시 OCI 상태 상세 */}
      <OciStartupStatusDetail />

      {/* B. 데이터 진단 (data_status 흡수) */}
      <div style={{ marginTop: 24 }}>
        <DataStatusView />
      </div>

      {/* C. 미리보기·샘플 (approval 에서 이동, PREVIEW/TEST 성격) */}
      <div style={{ marginTop: 24 }} className="diagnostics-preview">
        <h2>미리보기·샘플 (PREVIEW/TEST)</h2>
        <p className="helper" style={{ marginBottom: 12 }}>
          아래는 실제 자동 발송이 아니라 미리보기·샘플용입니다. 결과는 발송된 것이
          아닙니다.
        </p>
        <ManualPreviewSection run={run} setRun={setRun} />
        <DevCompatSection run={run} setRun={setRun} />
      </div>

      {/* D. LEGACY — 기존 대시보드 (참고용) */}
      <details className="card" style={{ marginTop: 24 }}>
        <summary
          style={{ cursor: "pointer", color: "var(--muted)", fontWeight: 600 }}
        >
          기존 대시보드 (LEGACY · 참고용) — 정상 운영 화면 아님
        </summary>
        <div style={{ marginTop: 12 }}>
          <DashboardView onNavigate={onNavigate} />
        </div>
      </details>
    </section>
  );
}
