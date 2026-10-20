"use client";

// 판단 근거 미리보기 카드 (Decision Draft Preview v1 2026-07-03 · POC5-23 2026-10-18 묶음 개편).
//
// - 선택 종목 하나의 근거를 버튼 한 번으로 모은다(서버가 화면 API 응답에서 꺼내 글로 조립).
// - 화면은 응답 글을 묶음([제목]) 단위 상자로만 나눠 보인다 — 상자 글을 이으면 응답 글 그대로이고,
//   [복사]는 응답 글(`preview_text`)을 그대로 복사한다(설계 §4 '같은 문자열').
// - 대상 종목 · 종류 · 후보 목록 조건이 바뀌면 이전 결과를 비우고 늦은 응답은 버린다(판정 §4).
// - 저장 · 발송 · 승인 · LLM 호출 없음.

import { getMarketFlowPeriod } from "@/lib/marketFlowPeriod";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  postDecisionDraftPreview,
  type DecisionDraftListQuery,
  type DecisionDraftPreviewResponse,
  type DecisionDraftTargetKind,
  type DecisionFilters,
} from "@/lib/api";
import {
  SELECTED_PREVIEW_SOURCE,
  describeDraftOrigin,
  kstDateOf,
  loadAISessionsDraft,
  saveAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";
import type { MenuKey } from "../LeftSidebar";
import { SAME_PERIOD_LIMIT } from "@/lib/samePeriodKodex";
import { VOLUME_HELP } from "@/lib/storedVolume";
import HelpPopover from "../holdings_risk_evidence/HelpPopover";
import { VOL_HELP_BASIS, VOL_HELP_MEANING } from "../holdings_risk_evidence/priceVolatility";

interface Props {
  targetKind: DecisionDraftTargetKind;
  ticker: string;
  displayName?: string;
  // 후보만 — 화면 목록 조건(같은 목록에서 찾기).
  listQuery?: DecisionDraftListQuery;
  // POC5-24 — [AI 세션에서 검토]: 화면 목록 필터(세션 필수 항목) · 후보 순위 · 메뉴 이동.
  screenFilters?: DecisionFilters;
  rank?: number | null;
  onNavigate?: (key: MenuKey) => void;
}

// POC5-24 — 지금 보이는 응답 그대로 AI 세션 초안(재생성 · 재계산 없음 · 질문 = 원문).
// 기록 기준일(asof) = 가격 기준일 · 없으면 생성 시각의 KST 날짜(가격 기준일 칸은 비운 채 그대로).
// 원문 · 생성 시각이 없거나 날짜를 정할 수 없으면 null(넘기지 않음).
export function buildSelectedPreviewDraft(
  res: DecisionDraftPreviewResponse,
  target: { kind: DecisionDraftTargetKind; ticker: string; name: string; rank: number | null },
  filters: DecisionFilters,
): AISessionsDraft | null {
  if (res.status !== "ok" || !res.preview_text || !res.generated_at) return null;
  const asof = res.evidence_as_of?.target_as_of_date || kstDateOf(res.generated_at);
  if (!asof) return null;
  return {
    asof,
    filters,
    candidate_snapshot: [
      {
        rank: target.kind === "candidate" ? target.rank : null,
        ticker: target.ticker,
        name: target.name,
        tags: [],
        selected_preview: {
          target_kind: target.kind,
          generated_at: res.generated_at,
          evidence_as_of: res.evidence_as_of ?? null,
          preview_text: res.preview_text,
        },
      },
    ],
    question_text: res.preview_text,
    linked_market_refresh_id: null,
    draft_created_at: new Date().toISOString(),
    source_screen: SELECTED_PREVIEW_SOURCE,
  };
}

const FAILURE_TEXT = "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요.";
const COPY_FAILED_TEXT = "복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.";
const DASH = "-";

export const PREVIEW_HELP = [
  "선택한 종목 하나의 관측값을 묶음별로 모았습니다. 매매 판단이나 위험 등급이 아닙니다. 아래 글과 [복사] 결과는 같은 글이며, 누른 시각에 다시 계산한 값이라 위 목록 · 상세와 날짜가 다를 수 있습니다.",
  "가격 흐름 — 5 · 10 · 20저장일은 PC 저장 종가 6 · 11 · 21개로 낸 변화율입니다. '단기 KODEX200 차이(저장일 수 기준)'는 이 종목과 KODEX200 을 각각 저장일 수로 센 구간의 변화율 차이(%p)라 같은 날짜를 맞춘 비교가 아닙니다. 보유 종목은 시작 · 끝 날짜가 KODEX200 과 다르면 값을 비우고, 후보는 날짜 일치를 따로 검사하지 않습니다.",
  "KODEX200 동일 기간 비교 — 1 · 3개월 수익률과 같은 시작 · 끝 날짜의 KODEX200 수익률을 뺀 차이(%p)입니다. 보유 종목은 지금 1개월 상위 10 후보에 든 경우만 값이 있습니다. " +
    SAME_PERIOD_LIMIT,
  "거래량 — " + VOLUME_HELP,
  "가격 흔들림 — " + VOL_HELP_MEANING + " " + VOL_HELP_BASIS,
  "중복 — 보유 ETF 는 이 ETF 저장 구성종목 상위 10건과, 구성종목이 저장된 지금 1개월 상위 10 후보에 2번 이상 나오는 종목의 겹침입니다(내 보유 ETF 사이 중복 아님 · 일치 0건은 비교 범위 한정)."
    + " 후보는 각 보유 ETF 와 저장 구성종목 상위 10건끼리 비교한 「ETF 구성종목」 중복률(Top 10 기준)이며, 구성종목 자료가 없는 쌍은 계산하지 않습니다(중복 없음이라는 뜻 아님). 직접 보유 여부는 따로 적습니다.",
];

// 응답 글을 묶음 단위로 나눈다(제목 줄 '[…]' + 본문). 글 자체는 바꾸지 않는다.
export function splitPreviewSections(text: string): { title: string; body: string }[] {
  return text.split("\n\n").map((sec) => {
    const [first, ...rest] = sec.split("\n");
    return { title: first.replace(/^\[|\]$/g, ""), body: rest.join("\n") };
  });
}

export default function DecisionDraftPreviewCard({
  targetKind,
  ticker,
  displayName,
  listQuery,
  screenFilters,
  rank,
  onNavigate,
}: Props) {
  // POC5-24 — 저장 안 한 기존 초안이 있으면 바꾸기 전에 묻는다(Q2 (a)).
  const [pendingReplace, setPendingReplace] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionDraftPreviewResponse | null>(null);
  // 결과가 어느 대상(종류 · 종목 · 목록 조건)의 것인지 — 다른 대상 이름에 예전 원문을 붙이지 않도록.
  const [resultFor, setResultFor] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  // 요청 시작 시점의 대상 식별자 — 늦게 도착한 응답이 새 대상에 표시되지 않도록.
  const currentReqIdRef = useRef<number>(0);
  const queryKey = useMemo(
    () => (targetKind === "candidate" ? JSON.stringify(listQuery ?? null) : ""),
    [targetKind, listQuery],
  );

  const targetKey = `${targetKind}|${ticker}|${queryKey}`;

  // 대상(종류 · 종목 · 후보 목록 조건)이 바뀌면 이전 미리보기 폐기 · 초안 교체 확인도 닫는다.
  useEffect(() => {
    setResult(null);
    setError(null);
    setLoading(false);
    setCopyState("idle");
    setPendingReplace(null);
    currentReqIdRef.current += 1;
  }, [targetKind, ticker, queryKey]);

  const handleGenerate = useCallback(async () => {
    if (loading || !ticker) return;
    const reqId = ++currentReqIdRef.current;
    const reqFor = targetKey;
    setLoading(true);
    setError(null);
    setCopyState("idle");
    setPendingReplace(null);
    try {
      const res = await postDecisionDraftPreview(targetKind, ticker, listQuery, getMarketFlowPeriod());
      if (reqId !== currentReqIdRef.current) return;
      if (res.status !== "ok" || !res.preview_text) {
        // 서버 사유(예: 현재 목록 조건에 없음)가 있으면 그대로 · 없으면 기본 문구.
        setError(res.message || FAILURE_TEXT);
        setResult(null);
      } else {
        setResult(res);
        setResultFor(reqFor);
        setPendingReplace(null);
      }
    } catch {
      if (reqId !== currentReqIdRef.current) return;
      setError(FAILURE_TEXT);
      setResult(null);
    } finally {
      if (reqId === currentReqIdRef.current) setLoading(false);
    }
  }, [loading, targetKind, ticker, listQuery, targetKey]);

  const handleCopy = useCallback(() => {
    const text = result?.preview_text;
    if (!text) return;
    if (!navigator.clipboard?.writeText) {
      setCopyState("failed");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => setCopyState("copied"),
      () => setCopyState("failed"),
    );
  }, [result]);

  const reviewDraft = useMemo(
    () =>
      result && resultFor === targetKey && screenFilters
        ? buildSelectedPreviewDraft(
            result,
            { kind: targetKind, ticker, name: displayName ?? ticker, rank: rank ?? null },
            screenFilters,
          )
        : null,
    [result, resultFor, targetKey, screenFilters, targetKind, ticker, displayName, rank],
  );

  // [AI 세션에서 검토] · [바꾸고 이동] — 저장하지 않은 초안이 있으면 먼저 묻는다(force 면 교체).
  const goReview = useCallback(
    (force: boolean) => {
      if (!reviewDraft || loading) {
        setPendingReplace(null);
        return;
      }
      const old = loadAISessionsDraft();
      if (old && !force) {
        setPendingReplace(describeDraftOrigin(old));
        return;
      }
      saveAISessionsDraft(reviewDraft);
      setPendingReplace(null);
      onNavigate?.("ai_sessions");
    },
    [reviewDraft, loading, onNavigate],
  );

  const label = targetKind === "holding" ? "보유" : "후보";
  const ok =
    result && resultFor === targetKey && result.status === "ok" && result.preview_text
      ? result
      : null;
  const gen = ok?.generated_at ? ok.generated_at.replace("T", " ").slice(0, 16) : DASH;

  return (
    <div className="decision-draft-preview">
      <div className="ddp-head">
        <strong>판단 근거 미리보기</strong>
        <HelpPopover label="판단 근거 미리보기" paragraphs={PREVIEW_HELP} />
        <span className="helper ddp-target">
          대상: {displayName ?? ticker} ({label})
        </span>
      </div>
      <div className="decision-draft-preview-actions">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={loading || !ticker}
          className="button-primary"
        >
          {loading ? "판단 근거 미리보기 생성 중..." : ok ? "다시 생성" : "판단 근거 미리보기 생성"}
        </button>
        {ok ? (
          <button type="button" className="btn-md" onClick={handleCopy}>
            복사
          </button>
        ) : null}
        {ok && reviewDraft && onNavigate && !loading ? (
          <button type="button" className="btn-md" onClick={() => goReview(false)}>
            AI 세션에서 검토
          </button>
        ) : null}
        {copyState === "copied" ? (
          <span className="ddp-copied">복사했습니다 — AI 대화창에 붙여 넣으세요.</span>
        ) : copyState === "failed" ? (
          <span className="ddp-copied">{COPY_FAILED_TEXT}</span>
        ) : null}
      </div>
      {pendingReplace ? (
        <div className="ddp-replace" role="alert">
          <span>
            저장하지 않은 AI 세션 초안이 있습니다({pendingReplace}). 바꾸면 그 초안은 사라집니다.
          </span>
          <button type="button" className="btn-md" onClick={() => goReview(true)}>
            바꾸고 이동
          </button>
          <button type="button" className="btn-md ddp-cancel" onClick={() => setPendingReplace(null)}>
            취소
          </button>
        </div>
      ) : null}
      {error ? (
        <div className="message error" style={{ marginTop: 8 }}>
          {error}
        </div>
      ) : null}
      {ok ? (
        <div className="decision-draft-preview-body" style={{ marginTop: 8 }}>
          <div className="ddp-dates">
            생성 {gen} · 가격 기준일 {ok.evidence_as_of?.target_as_of_date ?? DASH} · KODEX200{" "}
            {ok.evidence_as_of?.kodex200_as_of_date ?? DASH} · VIX{" "}
            {ok.evidence_as_of?.vix_as_of_date ?? DASH}(미국 날짜)
          </div>
          <div className="ddp-grid" data-testid="ddp-grid">
            {splitPreviewSections(ok.preview_text as string).map((sec, i) => (
              <section className="ddp-sec" key={i}>
                <div className="ddp-sec-t">{sec.title}</div>
                <pre className="ddp-sec-b">{sec.body}</pre>
              </section>
            ))}
          </div>
          <div className="helper" style={{ fontSize: "0.75rem" }}>
            화면의 글과 [복사] 결과는 같은 글입니다. 저장되지 않으며, 새로고침·화면 이탈·선택 변경 시 사라집니다.
          </div>
        </div>
      ) : null}
    </div>
  );
}
