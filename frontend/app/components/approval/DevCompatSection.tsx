"use client";

// OCI 적용·알림 — 개발·호환 점검 영역 (B구간 이동 대상 + C구간 기본 접힘).
//
// 설계 정정(Q2-b): push_kind=null(종류 확인 불가 — 기존 기록) run 은 정보 PUSH 로도
// 판단 초안으로도 분류하지 않고 여기(개발·호환 점검)에서만 표시한다. 임의 기본 분류 금지.
// 샘플 초안 생성 등 개발/테스트용 기능도 여기 둔다. (기본 접힘은 C구간에서 확정)

import { useState } from "react";
import RunPanel from "../RunPanel";
import SampleDraftQuickButton from "../SampleDraftQuickButton";
import { isKnownPushKind } from "./pushKindLabel";
import type { Run } from "@/lib/api";

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
}

export default function DevCompatSection({ run, setRun }: Props) {
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 종류 확인 불가(push_kind=null) run 만 여기서 다룬다.
  const showUnknownRun = run !== null && !isKnownPushKind(run.push_kind);

  return (
    <details className="card dev-compat-section" style={{ marginTop: 24 }}>
      <summary
        style={{ cursor: "pointer", color: "var(--muted)", fontWeight: 600 }}
      >
        개발·호환 점검 — 일반 운영 기능 아님
      </summary>
      <div style={{ marginTop: 12 }}>
        <p className="helper" style={{ marginBottom: 12 }}>
          아래는 개발·호환 점검용입니다. 정상 운영 동선에서는 사용하지 않습니다.
        </p>
        <SampleDraftQuickButton onDraftCreated={setRun} />

        {showUnknownRun ? (
          <div style={{ marginTop: 16 }}>
            <div className="helper" style={{ marginBottom: 8 }}>
              종류 확인 불가 — 기존 기록 (정보 PUSH 종류를 신뢰할 수 없어 여기에
              표시합니다).
            </div>
            <RunPanel
              run={run!}
              setRun={setRun}
              loading={loading}
              setLoading={setLoading}
              errorMsg={errorMsg}
              setErrorMsg={setErrorMsg}
            />
          </div>
        ) : null}
      </div>
    </details>
  );
}
