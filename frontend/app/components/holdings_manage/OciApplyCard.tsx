"use client";

// POC3-07 §6 · POC5-05 개정 2 §7 — 「종목 관리」 OCI 적용 카드(HoldingsManageView 에서 이전).
// 저장과 별도 동작 · 명시적 클릭에서만 실행 · 실패해도 기존 OCI 적용 상태 유지(§6.4).
// POC5-05: OCI 에는 현재 보유(허용 5필드)만 보낸다. PC 보유가 마지막 성공 적용과 다르면
// '아직 OCI 미적용' · 확인할 수 없으면(성공 기록 없음 · 교체 뒤 불일치 등) '적용 여부 확인 안 됨'.

import { useCallback, useEffect, useState } from "react";
import {
  applyHoldingsToOci,
  fetchHoldingsApplyStatus,
  type HoldingsApplyResult,
  type HoldingsApplyStatusRecord,
} from "@/lib/api";
import { apiErrorText } from "./format";

interface Props {
  refreshKey: number; // 보유 저장 · 매매 뒤 부모가 올린다 → 적용 상태 다시 읽기
  busy: boolean;
}

export default function OciApplyCard({ refreshKey, busy }: Props) {
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<HoldingsApplyResult | null>(null);
  const [lastApply, setLastApply] = useState<HoldingsApplyStatusRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadApplyStatus = useCallback(async () => {
    try {
      setLastApply(await fetchHoldingsApplyStatus());
    } catch {
      // 이력 조회 실패는 조용히 무시(부가 정보). 적용 자체와 무관.
    }
  }, []);

  useEffect(() => {
    void loadApplyStatus();
  }, [loadApplyStatus, refreshKey]);

  const onApply = useCallback(async () => {
    setApplying(true);
    setApplyResult(null);
    setError(null);
    try {
      setApplyResult(await applyHoldingsToOci());
      await loadApplyStatus();
    } catch (e) {
      setError(apiErrorText(e));
    } finally {
      setApplying(false);
    }
  }, [loadApplyStatus]);

  const pending = lastApply?.pending_apply;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="hmx-cycle-head">
        <h2 style={{ margin: 0 }}>OCI 적용</h2>
        {pending === true ? (
          <span className="hmx-tag hmx-tag-warn">PC 보유 변경 있음 · 아직 OCI 미적용</span>
        ) : pending === null || pending === undefined ? (
          <span className="hmx-tag">적용 여부 확인 안 됨</span>
        ) : (
          <span className="hmx-tag">OCI 에 적용된 보유와 같음</span>
        )}
      </div>
      <p className="helper" style={{ marginBottom: 8 }}>
        저장한 현재 보유(종목 · 수량 · 평단 · 이름 · 계좌)만 OCI 운영 환경에 보냅니다. 매매
        이력 · 과거 보유는 보내지 않습니다. <strong>저장과는 별도</strong> 동작이며, 이 버튼을
        눌러야만 전송됩니다. 실패해도 기존 OCI 적용 상태는 유지됩니다.
      </p>
      {lastApply?.has_record ? (
        <div className="helper" style={{ marginBottom: 8 }}>
          마지막 성공 적용:{" "}
          {lastApply.last_applied_at
            ? new Date(lastApply.last_applied_at).toLocaleString("ko-KR")
            : "없음"}
          {lastApply.status && lastApply.status !== "OCI_APPLIED"
            ? ` · 마지막 시도 결과: ${lastApply.status}`
            : ""}
        </div>
      ) : (
        <div className="helper" style={{ marginBottom: 8 }}>
          아직 OCI 에 적용한 기록이 없습니다.
        </div>
      )}
      <button type="button" onClick={onApply} disabled={applying || busy}>
        {applying ? "적용 중..." : "저장한 보유 종목 OCI 적용"}
      </button>
      {error ? (
        <div className="message error" style={{ marginTop: 8 }}>
          {error}
        </div>
      ) : null}
      {applyResult ? (
        <div
          className={applyResult.status === "OCI_APPLIED" ? "message" : "message error"}
          style={{ marginTop: 8 }}
        >
          [{applyResult.status}] {applyResult.message}
          {applyResult.applied_at ? (
            <div className="helper" style={{ marginTop: 4 }}>
              적용 시각: {new Date(applyResult.applied_at).toLocaleString()}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
