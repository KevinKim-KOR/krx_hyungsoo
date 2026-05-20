"use client";

// AI 투자세션 기록 / Decision Evidence 1차 (POC2 — 2026-05-20).
//
// Market Discovery 안에서 사용되는 최소 기록 패널. 새 메뉴 / 새 화면을 만들지
// 않고, Market Discovery 응답을 그대로 받아 저장 시점 스냅샷을 보존한다.
//
// 본 컴포넌트는 KS-10 회피를 위해 MarketDiscoveryView.tsx 에서 분리됐다.
// 외부 AI API 직접 호출 / 자동 토론 / AI 응답 저장 자동화는 하지 않는다 —
// 사용자가 외부 AI 채널에서 받은 텍스트를 직접 paste 해서 저장한다.

import { useCallback, useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  DECISION_VERDICT_LABEL,
  DEFAULT_DECISION_VERDICT,
  createDecisionSession,
  fetchDecisionSession,
  fetchDecisionSessions,
  toDecisionCandidateSnapshot,
  type DecisionSessionDetail,
  type DecisionSessionSummary,
  type DecisionUserVerdict,
  type MarketCandidate,
  type MarketTopNFilters,
} from "@/lib/api";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";

interface PanelProps {
  asof: string;
  filters: MarketTopNFilters;
  candidates: MarketCandidate[];
  linkedMarketRefreshId: string | null;
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function splitNextChecks(raw: string): string[] {
  return raw
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

const VERDICT_OPTIONS: DecisionUserVerdict[] = [
  "useful",
  "needs_constituents",
  "needs_market_compare",
  "hold",
];


export default function AISessionRecordPanel(props: PanelProps) {
  const { asof, filters, candidates, linkedMarketRefreshId } = props;

  // 입력 state
  const [questionText, setQuestionText] = useState<string>("");
  const [answerText, setAnswerText] = useState<string>("");
  const [userMemo, setUserMemo] = useState<string>("");
  const [userVerdict, setUserVerdict] = useState<DecisionUserVerdict>(
    DEFAULT_DECISION_VERDICT,
  );
  const [nextChecksRaw, setNextChecksRaw] = useState<string>("");

  // 저장 + 목록 + 상세 state
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [recent, setRecent] = useState<DecisionSessionSummary[]>([]);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [detail, setDetail] = useState<DecisionSessionDetail | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);

  const loadRecent = useCallback(() => {
    fetchDecisionSessions(10)
      .then((res) => {
        setRecent(res.records);
        setRecentError(null);
      })
      .catch((e) => setRecentError(describeError(e)));
  }, []);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

  const handleFillQuestion = useCallback(() => {
    // 지시문 §7.1 — 현재 Market Discovery 응답 기반으로 복사용 문구를 질문에 채움.
    // CopyTextCard 와 동일 모듈 (`buildMarketDiscoveryCopyText`) 사용 — 결과 텍스트
    // 도 동일.
    const text = buildMarketDiscoveryCopyText({ asof, filters, candidates });
    setQuestionText(text);
    setStatusMessage(null);
    setErrorMessage(null);
  }, [asof, filters, candidates]);

  const handleSave = useCallback(async () => {
    if (candidates.length === 0) {
      setErrorMessage("후보가 비어 있어 저장할 수 없습니다.");
      return;
    }
    if (questionText.trim().length === 0) {
      setErrorMessage("AI 질문을 입력하세요.");
      return;
    }
    if (answerText.trim().length === 0) {
      setErrorMessage("AI 답변을 입력하세요.");
      return;
    }
    setSaving(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const res = await createDecisionSession({
        asof,
        source_screen: "market_discovery",
        filters,
        candidate_snapshot: candidates.map(toDecisionCandidateSnapshot),
        question_text: questionText,
        answer_text: answerText,
        user_memo: userMemo,
        user_verdict: userVerdict,
        next_checks: splitNextChecks(nextChecksRaw),
        linked_market_refresh_id: linkedMarketRefreshId,
      });
      setStatusMessage(`저장되었습니다 (id: ${res.id}).`);
      // 입력 초기화 — 다음 기록과 섞이지 않도록.
      setQuestionText("");
      setAnswerText("");
      setUserMemo("");
      setUserVerdict(DEFAULT_DECISION_VERDICT);
      setNextChecksRaw("");
      loadRecent();
    } catch (e) {
      setErrorMessage(describeError(e));
    } finally {
      setSaving(false);
    }
  }, [
    asof,
    filters,
    candidates,
    questionText,
    answerText,
    userMemo,
    userVerdict,
    nextChecksRaw,
    linkedMarketRefreshId,
    loadRecent,
  ]);

  const handleOpenDetail = useCallback((id: string) => {
    setDetailLoadingId(id);
    setDetail(null);
    fetchDecisionSession(id)
      .then((res) => {
        if (res.status === "ok" && res.record) {
          setDetail(res.record);
        } else {
          setErrorMessage(res.message ?? "기록을 찾을 수 없습니다.");
        }
      })
      .catch((e) => setErrorMessage(describeError(e)))
      .finally(() => setDetailLoadingId(null));
  }, []);

  const handleCloseDetail = useCallback(() => setDetail(null), []);

  return (
    <>
      <div className="card decision-card">
        <h2>AI 투자세션 기록</h2>
        <p className="helper" style={{ marginBottom: 8 }}>
          외부 AI 채널(GPT / Gemini / Claude) 에서 받은 답변과 사용자 메모 / 1차
          판정을 저장합니다. AI 를 직접 호출하지 않으며, 매수 / 매도 판단이나
          매매 결과 추적도 하지 않습니다.
        </p>

        <div className="btn-row" style={{ marginBottom: 8 }}>
          <button type="button" onClick={handleFillQuestion}>
            현재 복사용 문구를 질문에 채우기
          </button>
        </div>

        <label htmlFor="decision-question">AI 질문 (외부 AI 에게 보낸 전문)</label>
        <textarea
          id="decision-question"
          className="decision-textarea"
          value={questionText}
          onChange={(e) => setQuestionText(e.target.value)}
          rows={8}
          placeholder="AI 에게 보낸 질문을 그대로 붙여넣거나, 위 버튼으로 현재 복사용 문구를 채우세요."
        />

        <label htmlFor="decision-answer">AI 답변 (외부 AI 가 돌려준 전문)</label>
        <textarea
          id="decision-answer"
          className="decision-textarea"
          value={answerText}
          onChange={(e) => setAnswerText(e.target.value)}
          rows={10}
          placeholder="외부 AI 의 답변을 그대로 붙여넣으세요."
        />

        <label htmlFor="decision-memo">사용자 메모</label>
        <textarea
          id="decision-memo"
          className="decision-textarea"
          value={userMemo}
          onChange={(e) => setUserMemo(e.target.value)}
          rows={4}
          placeholder="해석 / 의문점 / 다음 액션 등을 자유롭게."
        />

        <label htmlFor="decision-verdict">사용자 1차 판정</label>
        <select
          id="decision-verdict"
          className="decision-select"
          value={userVerdict}
          onChange={(e) =>
            setUserVerdict(e.target.value as DecisionUserVerdict)
          }
        >
          {VERDICT_OPTIONS.map((v) => (
            <option key={v} value={v}>
              {DECISION_VERDICT_LABEL[v]}
            </option>
          ))}
        </select>

        <label htmlFor="decision-next-checks">
          다음 확인 항목 (한 줄당 1항목)
        </label>
        <textarea
          id="decision-next-checks"
          className="decision-textarea"
          value={nextChecksRaw}
          onChange={(e) => setNextChecksRaw(e.target.value)}
          rows={4}
          placeholder={"예:\nKODEX200 대비 초과수익 확인\n구성 종목 중복률 확인"}
        />

        <div className="btn-row" style={{ marginTop: 12 }}>
          <button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "저장 중..." : "기록 저장"}
          </button>
        </div>

        {statusMessage ? (
          <div className="message info" style={{ marginTop: 8 }}>
            {statusMessage}
          </div>
        ) : null}
        {errorMessage ? (
          <div className="message error" style={{ marginTop: 8 }}>
            {errorMessage}
          </div>
        ) : null}
      </div>

      <div className="card decision-card">
        <h2>최근 AI 투자세션 기록</h2>
        {recentError ? (
          <div className="message error">{recentError}</div>
        ) : null}
        {recent.length === 0 ? (
          <div className="helper">아직 저장된 기록이 없습니다.</div>
        ) : (
          <table className="market-topn-table">
            <thead>
              <tr>
                <th>생성일시</th>
                <th>기준일</th>
                <th>판정</th>
                <th style={{ textAlign: "right" }}>후보 수</th>
                <th>요약</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td>{r.created_at}</td>
                  <td>{r.asof}</td>
                  <td>{DECISION_VERDICT_LABEL[r.user_verdict] ?? r.user_verdict}</td>
                  <td style={{ textAlign: "right" }}>{r.candidate_count}</td>
                  <td>{r.summary || "-"}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => handleOpenDetail(r.id)}
                      disabled={detailLoadingId === r.id}
                    >
                      {detailLoadingId === r.id ? "..." : "보기"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {detail ? (
        <div className="card decision-card decision-detail-card">
          <h2>기록 상세 — {detail.id}</h2>
          <ul className="dashboard-status-list">
            <li>생성일시: <strong>{detail.created_at}</strong></li>
            <li>기준일: <strong>{detail.asof}</strong></li>
            <li>화면: <strong>{detail.source_screen}</strong></li>
            <li>
              판정:{" "}
              <strong>
                {DECISION_VERDICT_LABEL[detail.user_verdict] ?? detail.user_verdict}
              </strong>
            </li>
            <li>후보 수: <strong>{detail.candidate_snapshot.length}</strong></li>
            {detail.linked_market_refresh_id ? (
              <li>
                연결된 refresh: <code>{detail.linked_market_refresh_id}</code>
              </li>
            ) : null}
          </ul>

          <h3>AI 질문</h3>
          <pre className="decision-pre">{detail.question_text}</pre>

          <h3>AI 답변</h3>
          <pre className="decision-pre">{detail.answer_text}</pre>

          {detail.user_memo ? (
            <>
              <h3>사용자 메모</h3>
              <pre className="decision-pre">{detail.user_memo}</pre>
            </>
          ) : null}

          {detail.next_checks.length > 0 ? (
            <>
              <h3>다음 확인 항목</h3>
              <ul>
                {detail.next_checks.map((c, idx) => (
                  <li key={idx}>{c}</li>
                ))}
              </ul>
            </>
          ) : null}

          <div className="btn-row" style={{ marginTop: 12 }}>
            <button type="button" onClick={handleCloseDetail}>
              상세 닫기
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
