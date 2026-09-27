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
// 막지 않음). 상세는 「OCI 운영·적용」(`approval`)의 ① 지금 OCI 상태로 이동.
// POC3-02D-OPS-02 3-1 — 2026-08-16 메뉴 분리 뒤에도 이 링크만 「개발·실험용」
// (`diagnostics` · OCI 상세 없음)으로 가던 것을 실제 도착 화면으로 고쳤다. 문구도
// 도착 화면의 메뉴 이름(LeftSidebar `approval` label)을 그대로 쓴다.
// 2026-09-27 사용자 직접 지시: 「OCI 운영 상태」(`oci_status`)가 「승인·적용」과
// 합쳐져 「OCI 운영·적용」(`approval`)이 됐다 → 도착 key · 문구를 함께 바꿨다.
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
            onClick={() => onNavigate("approval")}
          >
            OCI 운영·적용에서 상세 보기 →
          </button>
        </>
      ) : null}
    </p>
  );
}
