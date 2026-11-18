"use client";

// POC6-32 V2 — 「주간 ETF 점검」 화면 본문(PLAN V2 §2 S3 · §3-1 · §4-3 · 판정 V2 Q1 · Q5 · Q11 · Q12).
// 조건 = 1개월 상위 30 · 인버스 · 레버리지 · 합성 · 선물 제외(「후보리스트」 기본값과 같은 인자 · 다른 화면 설정과 따로).
// ① 시장 한 줄(응답의 공통 시장 근거 칸 = 일일 복사와 같은 칸 · lib/weeklyReview weeklyMarketView) → ② ETF 흐름(묶음 안
// ETF 마다 [고르기]) → ③ 선택한 후보 검토(today/WeeklyCandidateReview) → ④ AI 의견 요약(today/WeeklyRecord WeeklyAnswers) →
// ⑤ 최근 검토 기록(today/WeeklyRecord).
// 한 응답 = 한 검토 건(판정 §3-1): 화면 · [AI용 주간 검토 복사] · [AI 투자 세션으로 넘기기]가 이 응답 하나를 같이 쓴다.
//   다른 후보를 고르거나 다시 읽는 동안에는 복사 · 넘기기 · 고르기 · 상세 이동을 막는다(앞 응답과 섞이지 않게).
// 이 화면 글자에는 '후보'를 쓸 수 있다(판정 V2 Q1).
// 다시 읽는 때: 그려질 때(메뉴로 열 때마다 새로 그림) · 화면 머리 [다시 읽기](`gen` 이 오름). 그때마다 고른 ETF 별로 받아 둔
//   응답을 모두 비운다(앞 응답이 되살아나 저장 전 기록 · 갱신 전 목록을 보이지 않게 · 검토 F1). 상세에서 [← 보낸 화면으로]로
//   돌아오면 이 화면은 숨겨 둔 그대로라 다시 읽지 않는다(I-5).
//   다시 읽는 동안에는 앞 응답을 보이되 버튼을 막는다(검토 F2). 복사한 뒤 응답이 바뀌면 알리고, 넘길 때 확인한다(검토 F3).

import { useEffect, useRef, useState } from "react";
import { describeDraftOrigin, loadAISessionsDraft, saveAISessionsDraft } from "@/lib/aiSessionsDraft";
import { invalidateQueries, useSharedQuery } from "@/lib/api/queryCache";
import {
  fetchWeeklyReview,
  WEEKLY_REVIEW_KEY_PREFIX,
  weeklyReviewKey,
  type WeeklyLastRecord,
  type WeeklyReviewOk,
  type WeeklyReviewResponse,
} from "@/lib/api/weeklyReview";
import { presetExposureSingle } from "@/lib/detailNav";
import { presetOneTimeCondition } from "@/lib/etfCompareCondition";
import { md, weeklyDraft, weeklyMarketView } from "@/lib/weeklyReview";
import type { MenuKey } from "../LeftSidebar";
import { presetCompareCandidate } from "../workbench/compareSelection";
import WeeklyCandidateReview from "./WeeklyCandidateReview";
import WeeklyFlowTable from "./WeeklyFlowTable";
import { WeeklyAnswers, WeeklyLast } from "./WeeklyRecord";

type Msg = { text: string; fallback: string | null } | null;
type Pending = { kind: "draft"; origin: string } | { kind: "copy_changed" } | null;
// 보낸 화면 이름(상세 화면 안내 · 「후보리스트」 이동 한 번 조건 안내)
const ORIGIN = "「주간 ETF 점검」";

// ① 시장 한 줄 — 공통 시장 근거 칸(일일 복사 · 복사 글 시장 [근거 n] 과 같은 칸)에서 그림 · 못 읽었으면 사유.
function MarketLine({ r }: { r: WeeklyReviewOk }) {
  const v = weeklyMarketView(r.market_evidence, r.end_date);
  return (
    <div className="wr-sec" data-testid="wr-market">
      <div>
        <span className="wr-sec-title">① 시장 한 줄</span>{" "}
        <span className="tc-muted tc-small">(일일 복사와 같은 공통 시장 근거)</span>
      </div>
      {v.ok ? (
        <>
          <div>{v.line}</div>
          <div className="tc-muted tc-small">{v.basis}</div>
        </>
      ) : (
        <div className="wr-warn">{v.reason}</div>
      )}
    </div>
  );
}

// ④ AI 의견 요약 — 최근 검토 기록에 붙여넣은 답(서버 규칙 해석 · 글 뜻 비교 없음 · 자동 AI 호출 없음 · AI 의견).
function AiSummary({ last }: { last: WeeklyLastRecord }) {
  const cmp = last.status === "ok" ? last.compare : undefined;
  return (
    <div className="wr-sec" data-testid="wr-ai">
      <div>
        <span className="wr-sec-title">④ AI 의견 요약</span>{" "}
        <span className="tc-muted tc-small">
          ⑤ 최근 검토 기록에 붙여넣은 답 · AI 의견이며 결정이 아닙니다 · 상태와 인용 근거 번호만 대조(글 뜻은 비교하지 않음) ·
          원문은 「AI 투자 세션」 기록 상세
        </span>
      </div>
      {last.status !== "ok" ? (
        <div className={last.status === "error" ? "wr-warn" : "tc-muted"}>{last.message}</div>
      ) : !cmp ? (
        <div className="wr-warn">요약 확인 필요</div>
      ) : (
        <WeeklyAnswers cmp={cmp} />
      )}
    </div>
  );
}

export default function WeeklyReviewCard({ onNavigate, gen }: { onNavigate: (key: MenuKey) => void; gen: number }) {
  // 그려질 때 한 번 — 전에 받아 둔 응답(모든 ETF 키)을 비우고 새로 읽는다(조회 훅보다 먼저 · 한 번만 부름).
  useState(() => invalidateQueries(WEEKLY_REVIEW_KEY_PREFIX));
  const [selected, setSelected] = useState<string | null>(null);
  const q = useSharedQuery<WeeklyReviewResponse>(weeklyReviewKey(selected), () => fetchWeeklyReview(selected));
  const [msg, setMsg] = useState<Msg>(null);
  const [pending, setPending] = useState<Pending>(null);
  // 마지막으로 복사한 응답(넘기는 질문 원문이 복사한 글과 같은지 · 검토 F3)
  const copiedRef = useRef<WeeklyReviewOk | null>(null);
  // 다른 후보를 고르는 동안 앞 응답을 그대로 보이되(깜빡임 없음) 버튼은 막는다.
  const lastOk = useRef<WeeklyReviewOk | null>(null);
  const data = q.phase === "success" && q.data.status === "ok" ? q.data : null;
  if (data) lastOk.current = data;
  const shown = data ?? (q.phase === "loading" ? lastOk.current : null);
  const busy = data === null;

  const reloadRef = useRef(q.reloadAsync);
  reloadRef.current = q.reloadAsync;
  const firstGen = useRef(gen);
  useEffect(() => {
    if (gen === firstGen.current) return;
    // 모든 ETF 키를 비운 뒤 지금 키를 새로 읽는다 — 진행 중 조회에 합쳐지지 않고(검토 F8) 읽는 동안 버튼이 막힌다(F2).
    invalidateQueries(WEEKLY_REVIEW_KEY_PREFIX);
    reloadRef.current().catch(() => undefined);
  }, [gen]);
  // 복사한 뒤 응답이 바뀌면(다시 읽기 · 다른 후보) '그대로 복사' 안내를 내리고 다시 복사하게 한다(검토 F3).
  useEffect(() => {
    if (data && copiedRef.current && copiedRef.current !== data) {
      setMsg({ text: "복사한 뒤 화면 자료가 바뀌었습니다(다시 읽기 · 다른 후보) — 지금 화면 글을 쓰려면 다시 복사하세요.", fallback: null });
    }
  }, [data]);

  const pick = (t: string | null) => {
    setMsg(null);
    setPending(null);
    setSelected(t);
  };

  const onCopy = () => {
    if (!data) return;
    const text = data.copy_text;
    const fail = () => setMsg({ text: "복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.", fallback: text });
    try {
      const p = navigator.clipboard?.writeText(text);
      if (!p) return fail();
      p.then(() => {
        copiedRef.current = data;
        setMsg({
          text: `주간 검토 글을 복사했습니다 — 근거 ${data.evidence.length}개 · 답 받을 ETF ${data.answer_targets.length}개(지금 보이는 목록 · 기간 · 고른 후보 그대로).`,
          fallback: null,
        });
      }).catch(fail);
    } catch {
      fail();
    }
  };

  // step 0 = 처음 누름 · 1 = 복사 뒤 바뀜을 확인함 · 2 = 남은 초안 바꾸기도 확인함
  const onTransfer = (step: 0 | 1 | 2) => {
    if (!data) return;
    if (step === 0 && copiedRef.current && copiedRef.current !== data) {
      setPending({ kind: "copy_changed" });
      return;
    }
    const old = loadAISessionsDraft();
    if (old && step < 2) {
      setPending({ kind: "draft", origin: describeDraftOrigin(old, "ETF") });
      return;
    }
    saveAISessionsDraft(weeklyDraft(data));
    setPending(null);
    onNavigate("ai_sessions");
  };

  const onList = () => {
    if (shown) presetOneTimeCondition("candidates", { basis: "one_month", filters: { ...shown.condition.filters } }, ORIGIN);
    onNavigate("workbench");
  };
  // [비교 상세 →] — 「보유와 후보 비교」 후보 칸에 고른 후보 한쪽만(보유 칸은 비움 · 기본 짝 없음) + 이 화면 조건 · 기간은
  // 이번 이동에만(이동 한 번 조건 · 화면 조건 · 저장된 기본값은 바꾸지 않음).
  const onCompare = () => {
    const rv = data?.selected_review;
    if (!data || !rv) return;
    presetCompareCandidate({
      ticker: rv.ticker,
      name: rv.name,
      side: "top",
      condition: { basis: data.condition.basis, filters: { ...data.condition.filters } },
      start: data.condition.start,
      end: data.condition.end,
      origin: ORIGIN,
    });
    presetOneTimeCondition("compare", { basis: data.condition.basis, filters: { ...data.condition.filters } });
    onNavigate("holding_candidate_compare");
  };
  // [구성종목 보기 →] — 「ETF 구성종목」 한 ETF 모드(이 ETF 하나 · 보낸 화면 · 목록 조건 · 목록 초안과 따로).
  const onExposure = () => {
    const rv = data?.selected_review;
    if (!data || !rv) return;
    presetExposureSingle({
      ticker: rv.ticker,
      name: rv.name,
      from: ORIGIN,
      condition: {
        basis: data.condition.basis,
        side: data.condition.side,
        start: data.condition.start,
        end: data.condition.end,
        filters: { ...data.condition.filters },
      },
    });
    onNavigate("etf_exposure");
  };

  const three = shown?.data_quality_snapshot?.common_periods?.three_month;
  return (
    <div className="tc-card wr-card" data-testid="wr-card">
      {shown ? (
        <div className="wr-cond" data-testid="wr-cond">
          「후보리스트」 기본 조건과 같은 {shown.condition.line}
          {three?.start && three.end ? ` · 3개월 공통 기간 ${md(three.start)} → ${md(three.end)}` : ""} · 다른 화면 설정과 따로
        </div>
      ) : null}
      {q.phase === "error" ? <div className="tc-warn">목록을 불러오지 못했습니다 · [다시 읽기]로 다시 시도하세요</div> : null}
      {q.phase === "success" && q.data.status !== "ok" ? (
        <div className="tc-warn" data-testid="wr-notok">
          {q.data.message}
        </div>
      ) : null}
      {!shown && q.phase === "loading" ? <div className="tc-muted">주간 자료를 불러오는 중입니다</div> : null}
      {q.phase === "success" && q.stale ? <div className="tc-warn tc-small">⚠ 이전 조회값(다시 읽기 실패)</div> : null}
      {shown ? (
        <>
          <div className="wr-actions">
            <button type="button" className="btn-md" onClick={onCopy} disabled={busy}>
              AI용 주간 검토 복사
            </button>
            <button type="button" className="btn-md tc-fold-btn" onClick={() => onTransfer(0)} disabled={busy}>
              AI 투자 세션으로 넘기기
            </button>
            <button type="button" className="btn-md tc-fold-btn" onClick={onList}>
              후보리스트 보기 →
            </button>
            {busy ? <span className="tc-muted tc-small">다시 읽는 중 — 끝나면 복사 · 넘기기가 열립니다</span> : null}
          </div>
          {pending ? (
            <div className="wr-warn" data-testid="wr-pending">
              {pending.kind === "draft"
                ? `이미 넘긴 초안이 있습니다(${pending.origin}) — 바꾸면 그 초안은 없어집니다.`
                : "복사한 뒤 자료를 다시 읽어 지금 화면 글이 복사한 글과 다릅니다 — AI 답은 복사한 글로 받았다면 다시 복사해 물어보세요."}{" "}
              <button type="button" className="btn-md tc-fold-btn" onClick={() => onTransfer(pending.kind === "draft" ? 2 : 1)}>
                {pending.kind === "draft" ? "바꾸고 이동" : "지금 화면 글로 넘기기"}
              </button>{" "}
              <button type="button" className="btn-md tc-fold-btn" onClick={() => setPending(null)}>
                그대로 두기
              </button>
            </div>
          ) : null}
          {msg ? <p className={msg.fallback ? "tc-warn tc-small" : "tc-muted tc-small"}>{msg.text}</p> : null}
          {msg?.fallback ? (
            <textarea className="tc-copy-fallback" readOnly value={msg.fallback} rows={10} aria-label="복사할 주간 검토 글" />
          ) : null}

          <MarketLine r={shown} />
          <WeeklyFlowTable
            flows={shown.flows}
            firstRows={shown.first_rows}
            selected={shown.selected?.ticker ?? null}
            onPick={(t) => pick(t)}
            busy={busy}
          />
          <WeeklyCandidateReview
            r={shown}
            busy={busy}
            onClear={() => pick(null)}
            onCompare={onCompare}
            onExposure={onExposure}
          />
          <AiSummary last={shown.last_record} />
          <WeeklyLast last={shown.last_record} onOpen={() => onNavigate("ai_sessions")} />
        </>
      ) : null}
    </div>
  );
}
