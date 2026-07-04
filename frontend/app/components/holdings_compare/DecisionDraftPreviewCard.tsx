"use client";

// Decision Draft Preview v1 카드 (2026-07-03).
//
// 책임 (지시문 §8):
// - 선택 ETF 하나에 대한 임시 판단 근거 미리보기 생성 버튼.
// - 생성 결과는 현재 프론트엔드 메모리에만 유지 (부모 컴포넌트의 state).
// - 대상이 바뀌면 이전 요청 결과 폐기.
// - 실패/시간 초과 시 짧은 재시도 안내.
// - 기존 PENDING draft / 승인 상태 / OCI 미노출.

import { useCallback, useEffect, useRef, useState } from "react";

import {
  postDecisionDraftPreview,
  type DecisionDraftPreviewResponse,
  type DecisionDraftTargetKind,
} from "@/lib/api";

interface Props {
  targetKind: DecisionDraftTargetKind;
  ticker: string;
  displayName?: string;
}

const FAILURE_TEXT = "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요.";
const DASH = "-";

export default function DecisionDraftPreviewCard({
  targetKind,
  ticker,
  displayName,
}: Props) {
  const [result, setResult] = useState<DecisionDraftPreviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  // 요청 시작 시점의 target 식별자 — 늦게 도착한 응답이 새 대상에 표시되지 않도록.
  const currentReqIdRef = useRef<number>(0);

  // 대상(ticker, targetKind)이 바뀌면 이전 preview 폐기 (지시문 §8.4).
  useEffect(() => {
    setResult(null);
    setError(null);
    setLoading(false);
    currentReqIdRef.current += 1;
  }, [targetKind, ticker]);

  const handleGenerate = useCallback(async () => {
    if (loading) return;
    if (!ticker) return;
    const reqId = ++currentReqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await postDecisionDraftPreview(targetKind, ticker);
      // 대상이 바뀐 뒤 늦게 도착한 응답이면 폐기.
      if (reqId !== currentReqIdRef.current) return;
      if (res.status !== "ok" || !res.preview_text) {
        setError(FAILURE_TEXT);
        setResult(null);
      } else {
        setResult(res);
      }
    } catch {
      if (reqId !== currentReqIdRef.current) return;
      setError(FAILURE_TEXT);
      setResult(null);
    } finally {
      if (reqId === currentReqIdRef.current) {
        setLoading(false);
      }
    }
  }, [loading, targetKind, ticker]);

  const label = targetKind === "holding" ? "보유 ETF" : "후보 ETF";

  return (
    <div className="decision-draft-preview">
      <div className="decision-draft-preview-actions">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={loading || !ticker}
          className="button-primary"
        >
          {loading ? "판단 근거 미리보기 생성 중..." : "판단 근거 미리보기 생성"}
        </button>
        <span className="helper" style={{ marginLeft: 8, fontSize: "0.75rem" }}>
          대상: {displayName ?? ticker} ({label})
        </span>
      </div>
      {error ? (
        <div className="message error" style={{ marginTop: 8 }}>
          {error}
        </div>
      ) : null}
      {result && result.status === "ok" ? (
        <div className="decision-draft-preview-body" style={{ marginTop: 8 }}>
          <div className="helper" style={{ fontSize: "0.75rem" }}>
            선택 ETF 기준일: {result.evidence_as_of?.target_as_of_date ?? DASH}
            {" · "}
            KODEX200 기준일: {result.evidence_as_of?.kodex200_as_of_date ?? DASH}
            {" · "}
            VIX 기준일: {result.evidence_as_of?.vix_as_of_date ?? DASH}
          </div>
          <pre className="decision-draft-preview-text">
            {result.preview_text}
          </pre>
          <div className="helper" style={{ fontSize: "0.7rem" }}>
            이 미리보기는 저장되지 않으며, 새로고침·화면 이탈·선택 변경 시 폐기됩니다.
          </div>
        </div>
      ) : null}
    </div>
  );
}
