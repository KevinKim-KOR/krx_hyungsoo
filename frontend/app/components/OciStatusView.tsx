"use client";

// OCI 운영 상태 (oci_status) — 2026-08-16 사용자 직접 지시로 독립 메뉴화.
//
// 배경: POC3-07 이 이 카드를 `diagnostics`(진단·상태) 화면 안에 두었으나, 내용은
// "PC 백엔드 기동 시 읽은 OCI 운영 상태" 로 **정상 업무 조회**다. 미리보기·샘플·LEGACY
// 와 한 서랍에 있으면 성격이 섞인다. 카드 내용·API 는 그대로 두고 위치만 분리한다.
//
// 이 GET 은 백엔드 캐시를 반환하며 OCI 를 재조회하지 않는다(설계자 Q2).
// 자동 polling·수동 새로고침 버튼을 두지 않는다.

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchOciStartupStatus,
  type OciStartupStatus,
} from "@/lib/api";

export default function OciStatusView() {
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
    <section aria-labelledby="oci-startup-h">
      <h1 id="oci-startup-h">OCI 운영 상태</h1>
      <p className="subtitle">
        PC 백엔드가 <strong>기동될 때 1회</strong> 읽은 OCI 상태입니다. 화면을
        새로고침해도 OCI 를 다시 조회하지 않습니다(기동 시 확인값 표시).
      </p>

      <div className="card">
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
              · 상태: {status.overall} · 접속:{" "}
              {status.reachable ? "성공" : "실패"}
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
      </div>
    </section>
  );
}
