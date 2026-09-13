"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

import { useEffect, useState } from "react";
import { fetchOciStartupStatus, type OciStartupStatus } from "@/lib/api";
import type { MenuKey } from "../LeftSidebar";

// ── 컨테이너 ─────────────────────────────────────────────────────────────────
// POC3-07: 기동 시 읽은 OCI 상태 한 줄. 이 GET 은 백엔드 캐시를 반환하며 OCI 를
// 재조회하지 않는다. 실패·미확인이면 UNKNOWN 으로 조용히 한 줄만 표시(첫 화면을
// 막지 않음). 상세는 진단·상태로 이동.
export default function OciStatusOneLine({
  onNavigate,
}: {
  onNavigate?: (key: MenuKey) => void;
}) {
  const [status, setStatus] = useState<OciStartupStatus | null>(null);
  const [failed, setFailed] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await fetchOciStartupStatus();
        if (!cancelled) setStatus(s);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  let text: string;
  if (failed) text = "OCI 상태 미확인";
  else if (status === null) text = "OCI 상태 확인 중…";
  else {
    const when = status.checked_at
      ? new Date(status.checked_at).toLocaleString()
      : "미확인";
    text = `OCI: ${status.summary_line} · 확인 ${when}`;
  }

  return (
    <p className="tc-muted tc-subnote" style={{ marginTop: 4 }}>
      {text}
      {onNavigate ? (
        <>
          {" · "}
          <button
            type="button"
            className="tc-linklike"
            onClick={() => onNavigate("diagnostics")}
          >
            진단·상태에서 상세 보기 →
          </button>
        </>
      ) : null}
    </p>
  );
}
