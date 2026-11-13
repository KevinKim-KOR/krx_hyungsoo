"use client";

// POC6-29 보완 R1(RESULT 판정 §1 · 보완 PLAN 판정 Q-R1 · Q-R3 · Q-R6) — 국내 시세 3칸(네이버 빠른 시세 저장값 ·
//   [최신 자료 갱신]을 누를 때만 받음 · 화면을 열 때 · [요약 다시 읽기]는 저장값만).
// POC6-29 보완 2차(판정서 V2 §2 · S 판정 §3 · PLAN §10-2) — 「오늘 시장 변화」: 공통 시점(거래일 · 장 상태 · 마지막 조회)은
//   머리에 한 번 · 다른 칸만 그 칸에 시각을 적는다. 당일 판정(오늘 저장값으로 계산한 기존 시장 판정)은 날짜 · 저장 시점을
//   붙여 여기 둔다(아침 요약의 기준일 판정과 섞지 않음).
// 형수님 결정(2026-11-13) — 당일 판정은 강조 상자 · 바로 아래 시장 판정 근거 표 → 코스피 공식 종가 덩어리(children).
import type { ReactNode } from "react";
import type { QueryState } from "@/lib/api/queryCache";
import type { QuickQuotesResponse } from "@/lib/api/quickQuotes";
import { quoteView, type NowSentence } from "@/lib/marketNowText";
import { quoteHeader } from "@/lib/morningText";

const PLACEHOLDER = ["코스피", "코스닥", "KODEX 200"];

export default function MarketNowBlock({
  quick,
  today,
  children,
}: {
  quick: QueryState<QuickQuotesResponse>;
  // 당일 판정 문장(시장 판정 응답 · KODEX 200 저장 시점 기준) · 없으면 null
  today: NowSentence | null;
  // 당일 판정 바로 아래에 둘 것(시장 판정 근거 표 · 코스피 공식 종가 덩어리)
  children?: ReactNode;
}) {
  const data = quick.phase === "success" ? quick.data : null;
  const head = quoteHeader(data?.items ?? null);
  const readFail =
    quick.phase === "error"
      ? "빠른 시세 저장값을 읽지 못했습니다(PC 서버 확인)"
      : data?.status === "invalid"
        ? (data.message ?? "빠른 시세 저장 파일을 읽지 못했습니다.")
        : null;
  return (
    <div className="tc-now" data-testid="tc-market-now">
      <div className="tc-morning-head">
        <strong>오늘 시장 변화</strong>{" "}
        <span className="tc-muted tc-small" data-testid="tc-now-head">
          {head.head ?? "네이버 시세 · [최신 자료 갱신]을 누를 때 받습니다"}
        </span>
      </div>
      {readFail ? (
        <div className="tc-warn tc-small" data-testid="tc-now-read-fail">
          {readFail}
        </div>
      ) : null}
      <div className="tc-now-quotes">
        {data
          ? data.items.map((it) => {
              const v = quoteView(it);
              const own = head.differs.has(it.code);
              return (
                <div className="tc-now-quote" key={v.label} data-testid="tc-now-quote">
                  <div className="tc-muted tc-small">
                    {v.label} {own && v.badge ? <span className="tc-sum-badge tc-sum-muted">{v.badge}</span> : null}
                  </div>
                  <div className="tc-now-val">{v.value ?? "시세 미확인"}</div>
                  {v.change ? <div className={v.dir === "up" ? "tc-up" : v.dir === "down" ? "tc-down" : ""}>{v.change}</div> : null}
                  {own && v.time ? (
                    <div className="tc-muted tc-small" data-testid="tc-now-own-time">
                      {v.time} · {v.fetched}
                    </div>
                  ) : null}
                  {v.note ? <div className={v.warn ? "tc-warn tc-small" : "tc-muted tc-small"}>{v.note}</div> : null}
                </div>
              );
            })
          : PLACEHOLDER.map((label) => (
              <div className="tc-now-quote" key={label} data-testid="tc-now-quote">
                <div className="tc-muted tc-small">{label}</div>
                <div className="tc-now-val">{quick.phase === "error" ? "확인 불가" : "불러오는 중"}</div>
              </div>
            ))}
      </div>
      {today ? (
        <div className="tc-now-verdict" data-testid="tc-now-regime">
          <div className="tc-now-verdict-text">{today.text}</div>
          {today.basis ? <div className="tc-now-verdict-basis"> {today.basis}</div> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
