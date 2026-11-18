"use client";

// AI Sessions / 기록 조회 탭 (POC2 — 2026-05-21).
//
// 최근 N건 목록 + 상세 보기. 목록에는 GPT / Gemini / Claude 답변 입력 여부가
// has_* 플래그로 표시되어, 어떤 채널에서 응답을 받았는지 한눈에 본다.
//
// POC6-32 V2(PLAN §4-4) — 판정 칸은 출처별 표시 글자(verdictText · 저장값은 그대로) · 주간 기록(「주간 ETF 점검」)
// 상세는 '당시 검토'(저장 값만 · 다시 계산 · 시장 조회 없음 · ai_sessions/WeeklyReviewSnapshot)를 먼저 보이고
// 질문 원문 · 저장 칸(JSON)은 접힌 칸에 둔다 · 주간이 아닌 기록 상세는 지금 그대로.
// openId = 「주간 ETF 점검」 ⑤ [기록 열기]가 넘긴 기록 → 처음 그릴 때 그 상세를 바로 열고 그 카드로 스크롤.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchDecisionSession,
  fetchDecisionSessions,
  type DecisionSessionDetail,
  type DecisionSessionSummary,
} from "@/lib/api";
import {
  isSelectedPreviewRecord,
  isWeeklyRecord,
  kstDateTimeLabel,
  verdictText,
} from "@/lib/aiSessionsDraft";
import { constituentDatesText } from "@/lib/pairExposureText";
import WeeklyReviewSnapshot from "./ai_sessions/WeeklyReviewSnapshot";

interface Props {
  // 부모 (AISessionsView) 가 저장 직후 reload 트리거할 수 있도록 buster 사용.
  reloadTrigger: number;
  // 처음 그릴 때 바로 열 기록 id(없으면 null · 「주간 ETF 점검」 [기록 열기]).
  openId?: string | null;
}

const NOT_FOUND = "기록을 찾을 수 없습니다.";

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
  // POC6-32 V2 — 주간 기록은 '당시 검토' + 접힌 원문(질문 · 저장 칸 · AI 답은 '당시 검토' 안에서 AI 별로 접힘).
  if (isWeeklyRecord(detail.source_screen)) {
    return (
      <div className="card decision-card decision-detail-card">
        <h2>기록 상세 — {detail.id}</h2>
        <WeeklyReviewSnapshot detail={detail} />
        <details className="wrs-fold" data-testid="wrs-raw">
          <summary>원문 펼치기 — 질문 원문 · 저장 칸(시장 근거 · 구성 · 겹침 · 데이터 품질)</summary>
          <RawSections detail={detail} answers={false} />
        </details>
        <div className="btn-row" style={{ marginTop: 12 }}>
          <button type="button" onClick={onClose}>
            상세 닫기
          </button>
        </div>
      </div>
    );
  }
  // POC5-24 — 선택 근거 모드 기록(「보유와 비교」 판단 근거 미리보기에서 넘김)만 따로 표시.
  const sel = isSelectedPreviewRecord(detail.source_screen, detail.candidate_snapshot);
  const sp = sel ? detail.candidate_snapshot[0].selected_preview : null;
  const priceDate = sp?.evidence_as_of?.target_as_of_date || null;
  return (
    <div className="card decision-card decision-detail-card">
      <h2>기록 상세 — {detail.id}</h2>
      <ul className="dashboard-status-list">
        <li>생성일시: <strong>{detail.created_at}</strong></li>
        <li>
          {sel ? "기록 기준일" : "기준일"}: <strong>{detail.asof}</strong>
          {sel && !priceDate ? " — 미리보기 생성일 사용 · 가격 기준일 미확인" : ""}
        </li>
        <li>화면: <strong>{detail.source_screen}</strong></li>
        <li>
          판정:{" "}
          <strong>{verdictText(detail.source_screen, detail.user_verdict)}</strong>
        </li>
        <li>후보 수: <strong>{detail.candidate_snapshot.length}</strong></li>
        {detail.linked_market_refresh_id ? (
          <li>
            연결된 refresh: <code>{detail.linked_market_refresh_id}</code>
          </li>
        ) : null}
      </ul>

      <h3>{sel ? "당시 화면의 후보 목록 필터" : "필터 조건"}</h3>
      <ul>
        <li>인버스 제외: {detail.filters.exclude_inverse ? "예" : "아니오"}</li>
        <li>레버리지 제외: {detail.filters.exclude_leveraged ? "예" : "아니오"}</li>
        <li>합성 제외: {detail.filters.exclude_synthetic ? "예" : "아니오"}</li>
        <li>선물형 제외: {detail.filters.exclude_futures ? "예" : "아니오"}</li>
      </ul>

      {sel ? (
        // POC5-24 — 선택 종목 1건 · 보유에 목록 번호를 붙이지 않는다 · 후보 순위는 전달 당시 화면 목록 순위
        // (미리보기 원문의 'n위'는 생성 시각 서버 목록 · 그 사이 시장 자료가 바뀌면 다를 수 있다).
        <>
          <h3>선택 종목 (저장 시점)</h3>
          <ul>
            {detail.candidate_snapshot.slice(0, 1).map((c) => (
              <li key={c.ticker ?? "x"}>
                {c.selected_preview?.target_kind === "holding"
                  ? "보유"
                  : `후보${c.rank != null ? ` · 당시 화면 목록 ${c.rank}위` : ""}`}{" "}
                · {c.name ?? "-"} ({c.ticker ?? "-"})
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <h3>후보 스냅샷 (저장 시점)</h3>
          <ul>
            {detail.candidate_snapshot.map((c, idx) => (
              <li key={`${c.ticker ?? "x"}-${idx}`}>
                {c.rank ?? idx + 1}. {c.name ?? "-"} ({c.ticker ?? "-"})
              </li>
            ))}
          </ul>
        </>
      )}

      {(() => {
        // POC5-24 — 넘겨받은 판단 근거 원문(저장 JSON 안) · 질문(편집본)과 구분해 보인다.
        if (!sp) return null;
        const edited = sp.preview_text !== detail.question_text;
        return (
          <>
            <h3>넘겨받은 판단 근거 (원문)</h3>
            <div className="helper">
              {sp.target_kind === "holding" ? "보유" : "후보"} · 미리보기 생성{" "}
              {kstDateTimeLabel(sp.generated_at)} · 가격 기준일 {priceDate ?? "미확인"} ·{" "}
              {constituentDatesText(sp.evidence_as_of) ? `${constituentDatesText(sp.evidence_as_of)} · ` : ""}
              {edited ? "아래 AI 질문은 저장 때 편집됨" : "아래 AI 질문과 같은 글"}
            </div>
            {edited ? <pre className="decision-pre">{sp.preview_text}</pre> : null}
          </>
        );
      })()}
      <RawSections detail={detail} answers />

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

// 질문 원문 · (answers 이면) AI 답 원문 · 저장 칸(JSON) — 주간이 아닌 기록은 펼쳐 둔 그대로 · 주간 기록은 접힌 칸 안에서
// (주간 기록의 AI 답은 '당시 검토' 안에서 AI 별로 접혀 있으므로 여기서는 빼고 그린다).
function RawSections({
  detail,
  answers,
}: {
  detail: DecisionSessionDetail;
  answers: boolean;
}) {
  return (
    <>
      <h3>AI 질문</h3>
      <pre className="decision-pre">{detail.question_text}</pre>

      {answers ? (
        <>
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

      {detail.short_term_momentum_snapshot &&
      Object.keys(detail.short_term_momentum_snapshot).length > 0 ? (
        <>
          <h3>단기 흐름 (저장 시점)</h3>
          <pre className="decision-pre">
            {JSON.stringify(detail.short_term_momentum_snapshot, null, 2)}
          </pre>
        </>
      ) : null}

      {detail.data_quality_snapshot &&
      Object.keys(detail.data_quality_snapshot).length > 0 ? (
        <>
          <h3>데이터 품질 (저장 시점)</h3>
          <pre className="decision-pre">
            {JSON.stringify(detail.data_quality_snapshot, null, 2)}
          </pre>
        </>
      ) : null}
    </>
  );
}

export default function AISessionsListTab({ reloadTrigger, openId = null }: Props) {
  const [recent, setRecent] = useState<DecisionSessionSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [detail, setDetail] = useState<DecisionSessionDetail | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  // 마지막에 연 상세 요청만 반영(넘겨받은 기록을 여는 중에 다른 행 [보기]를 누르면 늦게 온 앞 응답을 버림).
  const detailSeq = useRef(0);
  // 넘겨받은 기록은 한 번만 연다(Strict Mode 효과 두 번 실행에도) · 그 상세가 그려지면 그 카드로 스크롤.
  const openedId = useRef<string | null>(null);
  const scrollToDetail = useRef(false);
  const detailBox = useRef<HTMLDivElement | null>(null);

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
    const seq = ++detailSeq.current;
    setDetailLoadingId(id);
    setDetail(null);
    setDetailError(null);
    fetchDecisionSession(id)
      .then((res) => {
        if (seq !== detailSeq.current) return;
        if (res.status === "ok" && res.record) {
          setDetail(res.record);
        } else {
          // 서버의 '찾지 못함' 안내는 영어라 화면에는 쉬운 한국어 한 줄만.
          setDetailError(NOT_FOUND);
        }
      })
      .catch((e) => {
        if (seq === detailSeq.current) setDetailError(describeError(e));
      })
      .finally(() => {
        if (seq === detailSeq.current) setDetailLoadingId(null);
      });
  }, []);

  // 「주간 ETF 점검」 [기록 열기] — 처음 그릴 때 그 기록 상세를 바로 연다(목록 10건 안에 없어도 id 로 읽음).
  useEffect(() => {
    if (!openId || openedId.current === openId) return;
    openedId.current = openId;
    scrollToDetail.current = true;
    handleOpenDetail(openId);
  }, [openId, handleOpenDetail]);

  // 넘겨받은 기록 상세가 그려지면 그 카드로(목록 아래에 그려져 첫 화면에 안 보일 수 있음 · 화면 이동의 맨 위 규칙은 그대로).
  useEffect(() => {
    if (!detail || !scrollToDetail.current) return;
    scrollToDetail.current = false;
    const el = detailBox.current;
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "start" });
  }, [detail]);

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
                  <td>{verdictText(r.source_screen, r.user_verdict)}</td>
                  <td style={{ textAlign: "right" }}>{r.candidate_count}</td>
                  <td>
                    <AnswerBadges
                      hasGpt={r.has_gpt_answer}
                      hasGemini={r.has_gemini_answer}
                      hasClaude={r.has_claude_answer}
                    />
                  </td>
                  <td>
                    {/* POC5-24 — 선택 근거 기록만 '[이름(티커)]'(Q1 (a)). */}
                    {r.target_label ? <strong>[{r.target_label}] </strong> : null}
                    {r.summary || "-"}
                  </td>
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

      <div ref={detailBox}>
        {detail ? <DetailCard detail={detail} onClose={handleCloseDetail} /> : null}
      </div>
    </>
  );
}
