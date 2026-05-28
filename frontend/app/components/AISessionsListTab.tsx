"use client";

// AI Sessions / 기록 조회 탭 (POC2 — 2026-05-21).
//
// 최근 N건 목록 + 상세 보기. 목록에는 GPT / Gemini / Claude 답변 입력 여부가
// has_* 플래그로 표시되어, 어떤 채널에서 응답을 받았는지 한눈에 본다.

import { useCallback, useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  DECISION_VERDICT_LABEL,
  fetchDecisionSession,
  fetchDecisionSessions,
  type DecisionSessionDetail,
  type DecisionSessionSummary,
} from "@/lib/api";

interface Props {
  // 부모 (AISessionsView) 가 저장 직후 reload 트리거할 수 있도록 buster 사용.
  reloadTrigger: number;
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function AnswerBadges({
  hasGpt,
  hasGemini,
  hasClaude,
}: {
  hasGpt: boolean;
  hasGemini: boolean;
  hasClaude: boolean;
}) {
  return (
    <span className="decision-answer-badges">
      <span
        className={
          hasGpt ? "decision-answer-badge present" : "decision-answer-badge absent"
        }
        title="GPT 답변 여부"
      >
        GPT
      </span>
      <span
        className={
          hasGemini
            ? "decision-answer-badge present"
            : "decision-answer-badge absent"
        }
        title="Gemini 답변 여부"
      >
        Gemini
      </span>
      <span
        className={
          hasClaude
            ? "decision-answer-badge present"
            : "decision-answer-badge absent"
        }
        title="Claude 답변 여부"
      >
        Claude
      </span>
    </span>
  );
}

function DetailCard({
  detail,
  onClose,
}: {
  detail: DecisionSessionDetail;
  onClose: () => void;
}) {
  return (
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

      <h3>필터 조건</h3>
      <ul>
        <li>인버스 제외: {detail.filters.exclude_inverse ? "예" : "아니오"}</li>
        <li>레버리지 제외: {detail.filters.exclude_leveraged ? "예" : "아니오"}</li>
        <li>합성 제외: {detail.filters.exclude_synthetic ? "예" : "아니오"}</li>
        <li>선물형 제외: {detail.filters.exclude_futures ? "예" : "아니오"}</li>
      </ul>

      <h3>후보 스냅샷 (저장 시점)</h3>
      <ul>
        {detail.candidate_snapshot.map((c, idx) => (
          <li key={`${c.ticker ?? "x"}-${idx}`}>
            {c.rank ?? idx + 1}. {c.name ?? "-"} ({c.ticker ?? "-"})
          </li>
        ))}
      </ul>

      <h3>AI 질문</h3>
      <pre className="decision-pre">{detail.question_text}</pre>

      {detail.gpt_answer_text ? (
        <>
          <h3>GPT 답변</h3>
          <pre className="decision-pre">{detail.gpt_answer_text}</pre>
        </>
      ) : null}

      {detail.gemini_answer_text ? (
        <>
          <h3>Gemini 답변</h3>
          <pre className="decision-pre">{detail.gemini_answer_text}</pre>
        </>
      ) : null}

      {detail.claude_answer_text ? (
        <>
          <h3>Claude 답변</h3>
          <pre className="decision-pre">{detail.claude_answer_text}</pre>
        </>
      ) : null}

      {detail.market_context_snapshot &&
      Object.keys(detail.market_context_snapshot).length > 0 ? (
        <>
          <h3>시장 문맥 (저장 시점)</h3>
          <pre className="decision-pre">
            {JSON.stringify(detail.market_context_snapshot, null, 2)}
          </pre>
        </>
      ) : null}

      {detail.constituent_snapshot &&
      Object.keys(detail.constituent_snapshot).length > 0 ? (
        <>
          <h3>구성종목 (저장 시점)</h3>
          <pre className="decision-pre">
            {JSON.stringify(detail.constituent_snapshot, null, 2)}
          </pre>
        </>
      ) : null}

      {detail.overlap_snapshot &&
      Object.keys(detail.overlap_snapshot).length > 0 ? (
        <>
          <h3>중복률 (저장 시점)</h3>
          <pre className="decision-pre">
            {JSON.stringify(detail.overlap_snapshot, null, 2)}
          </pre>
        </>
      ) : null}

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
        <button type="button" onClick={onClose}>
          상세 닫기
        </button>
      </div>
    </div>
  );
}


export default function AISessionsListTab({ reloadTrigger }: Props) {
  const [recent, setRecent] = useState<DecisionSessionSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [detail, setDetail] = useState<DecisionSessionDetail | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadRecent = useCallback(() => {
    fetchDecisionSessions(10)
      .then((res) => {
        setRecent(res.records);
        setListError(null);
      })
      .catch((e) => setListError(describeError(e)));
  }, []);

  useEffect(() => {
    loadRecent();
  }, [loadRecent, reloadTrigger]);

  const handleOpenDetail = useCallback((id: string) => {
    setDetailLoadingId(id);
    setDetail(null);
    setDetailError(null);
    fetchDecisionSession(id)
      .then((res) => {
        if (res.status === "ok" && res.record) {
          setDetail(res.record);
        } else {
          setDetailError(res.message ?? "기록을 찾을 수 없습니다.");
        }
      })
      .catch((e) => setDetailError(describeError(e)))
      .finally(() => setDetailLoadingId(null));
  }, []);

  const handleCloseDetail = useCallback(() => setDetail(null), []);

  return (
    <>
      <div className="card decision-card">
        <h2>최근 AI 투자세션 기록</h2>
        {listError ? <div className="message error">{listError}</div> : null}
        {recent.length === 0 && !listError ? (
          <div className="helper">아직 저장된 기록이 없습니다.</div>
        ) : null}
        {recent.length > 0 ? (
          <table className="market-topn-table">
            <thead>
              <tr>
                <th>생성일시</th>
                <th>기준일</th>
                <th>판정</th>
                <th style={{ textAlign: "right" }}>후보 수</th>
                <th>답변 채널</th>
                <th>요약</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td>{r.created_at}</td>
                  <td>{r.asof}</td>
                  <td>
                    {DECISION_VERDICT_LABEL[r.user_verdict] ?? r.user_verdict}
                  </td>
                  <td style={{ textAlign: "right" }}>{r.candidate_count}</td>
                  <td>
                    <AnswerBadges
                      hasGpt={r.has_gpt_answer}
                      hasGemini={r.has_gemini_answer}
                      hasClaude={r.has_claude_answer}
                    />
                  </td>
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
        ) : null}
      </div>

      {detailError ? (
        <div className="card">
          <div className="message error">{detailError}</div>
        </div>
      ) : null}

      {detail ? <DetailCard detail={detail} onClose={handleCloseDetail} /> : null}
    </>
  );
}
