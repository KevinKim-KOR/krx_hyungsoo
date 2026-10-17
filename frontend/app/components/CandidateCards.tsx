"use client";

// 요즘 잘 오르는 ETF — 후보 카드 목록 (2026-08-16 사용자 실화면 직접 지시).
//
// 기존 17열 가로 표(CandidateTable)를 대체하는 **기본 보기**. 표 보기는 별도 탭으로 남는다.
// ETF 비교하기·확인 근거와 같은 카드 규칙: 좌측 2단 카드 + 우측 지표 열 + 정상이면 배지 숨김.
//
// 17열을 버리지 않고 나눈다 — 자주 보는 것은 카드에, 나머지는 행을 펼쳤을 때.
//   카드 : 순위 · ETF명 · 티커 · 1개월 수익률 · 시장가 · NAV · 괴리율
//   지표 : 일간 · 1개월 · 3개월 + KODEX200 대비 1M
//          (아랫줄이 KODEX 대비 지표인 것은 ETF 비교하기·확인 근거와 같은 배치)
//   배지 : 보유 여부 3-state · 데이터 상태(정상이면 숨김)
//   펼침 : 6개월 · 12개월 · 3년 · KODEX200 대비 3M · 고점 대비
//
// 2026-08-29 POC3-ML-02 REJECT Closeout — `relative_upside_v0` 이 REJECT 판정을
// 받아 참고점수 배지와 점수 근거를 뺐다. 큰 숫자 자리는 1개월 수익률이 대신한다.
//
// "1년" 열은 없앴다 — backend `twelve_month` 를 두 번 표시하던 중복이었다
// (기존 코드 주석에 "동일 값 또 표시" 로 명시돼 있었다). 17열 → 16열.
//
// 데이터 접근·판정은 전부 CandidateTable 과 동일하다. 표시 형태만 다르다.
//
// POC5-21 (2026-10-17) — 후보 목록 위 기간 두 줄(ReturnPeriodLine) · 이름 옆 '수익률 끝일' /
// '계산 기간 확인 불가' · 값 아래 실제 시작일 · KODEX200 대비 값 단위 %p(두 수익률의 차이).
// 판정은 lib/returnPeriod 하나(표 · 복사문과 같다).

import { useState } from "react";
import type { MarketBasis, MarketCandidate, MarketContextKodex200 } from "@/lib/api";
import {
  PERIOD_KEYS,
  allPeriodsUnknown,
  candidateBadges,
  cmpGroup,
  cmpNote,
  cmpState,
  periodGroup,
  valueNote,
  valuePeriod,
  type PeriodGroup,
  type PeriodKey,
} from "@/lib/returnPeriod";
import ReturnPeriodLine, { PeriodNote } from "./ReturnPeriodLine";

const DASH = "-";

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return DASH;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function dirColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "var(--muted)";
  // 국내 관례 — 상승 빨강 / 하락 파랑 (전용 토큰).
  return v >= 0 ? "var(--pnl-up)" : "var(--pnl-down)";
}

// 두 수익률의 차이(KODEX200 대비) — 단위 %p.
function fmtPctp(v: number | null | undefined): string {
  if (v === null || v === undefined) return DASH;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%p`;
}

function fmtWon(v: number | null | undefined): string {
  if (v === null || v === undefined) return DASH;
  return Math.round(v).toLocaleString("ko-KR");
}

// 보유 여부 3-state — 보유 목록 미로드면 "확인 불가"(미보유로 축약하지 않는다).
function HeldBadge({ held }: { held: boolean | null }) {
  if (held === null) return <span className="wb-hb danger">보유 확인 불가</span>;
  if (held) return <span className="wb-hb hold">보유</span>;
  return <span className="wb-hb mute">미보유</span>;
}

export default function CandidateCards({
  candidates,
  heldTickers,
  selected,
  onSelect,
  basis = "one_month",
  marketAsof,
  kodex,
}: {
  candidates: MarketCandidate[];
  // POC5-21 — 선택 기간 · 시장 저장 최신일 · KODEX200 1M · 3M 날짜.
  basis?: MarketBasis;
  marketAsof?: string | null;
  kodex?: MarketContextKodex200 | null;
  // 보유 ticker 집합. undefined 면 조회 미완/실패 → 3-state 의 "확인 불가".
  heldTickers?: Set<string>;
  selected?: string | null;
  onSelect?: (ticker: string) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  // POC5-21 — 기간별 날짜 묶음 · KODEX200 대비 비교 묶음(표시 후보 전체에서 한 번).
  const groups = Object.fromEntries(
    PERIOD_KEYS.map((k) => [k, periodGroup(candidates, k)]),
  ) as Record<PeriodKey, PeriodGroup>;
  const cmp1 = cmpGroup(candidates, "1m", kodex);
  const cmp3 = cmpGroup(candidates, "3m", kodex);

  if (candidates.length === 0) {
    return <p className="wb-muted">표시할 후보가 없습니다.</p>;
  }

  return (
    <>
      <ReturnPeriodLine
        candidates={candidates}
        selected={basis}
        marketAsof={marketAsof}
        kodex={kodex}
      />
      <div className="wb-hlist" data-testid="candidate-card-list">
        {candidates.map((c, idx) => {
          const key = `${c.rank ?? "x"}-${c.ticker ?? "x"}-${idx}`;
          const dailyRet = c.returns?.daily?.return_pct ?? null;
          const oneRet = c.returns?.one_month?.return_pct ?? null;
          const threeRet = c.returns?.three_month?.return_pct ?? null;
          const sixRet = c.returns?.six_month?.return_pct ?? null;
          const twelveRet = c.returns?.twelve_month?.return_pct ?? null;
          const threeYearRet = c.returns?.three_year?.return_pct ?? null;
          const exKodex1m = c.excess_return?.vs_kodex200_1m_pctp ?? null;
          const exKodex3m = c.excess_return?.vs_kodex200_3m_pctp ?? null;
          const nav = c.data_quality?.nav_discount ?? null;
          const navVal = nav?.nav ?? null;
          const priceVal = nav?.market_price ?? null;
          const discountVal = nav?.discount_rate_pct ?? null;
          const flagVal = nav?.flag ?? null;
          const dq = c.data_quality?.status ?? null;
          const drawdown = c.drawdown_20d != null ? c.drawdown_20d * 100 : null;
          const held = heldTickers ? (c.ticker ? heldTickers.has(c.ticker) : false) : null;
          const isOpen = expanded === key;
          const isSel = !!c.ticker && selected === c.ticker;
          const badges = candidateBadges(c, basis, groups[basis], marketAsof);
          const allUnk = allPeriodsUnknown(c);
          const note = (k: PeriodKey) => valueNote(valuePeriod(c.returns?.[k]), groups[k], allUnk);

          return (
            <div key={key}>
              <div
                className={`wb-hrow${isSel ? " sel" : ""}`}
                role="button"
                tabIndex={0}
                aria-pressed={isSel}
                aria-expanded={isOpen}
                aria-label={`${c.name ?? c.ticker ?? "종목"} 상세 보기`}
                onClick={() => {
                  setExpanded(isOpen ? null : key);
                  if (c.ticker && onSelect) onSelect(c.ticker);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setExpanded(isOpen ? null : key);
                    if (c.ticker && onSelect) onSelect(c.ticker);
                  }
                }}
              >
                <div className="wb-hcard">
                  <div className="wb-hrow-top">
                    <div className="wb-hrow-name">
                      <span className="cand-rank">{c.rank ?? DASH}</span>
                      {c.name ?? c.ticker ?? DASH}
                      <span className="wb-hbadges">
                        <HeldBadge held={held} />
                        {/* 데이터 상태는 정상(ok)이면 띄우지 않는다 — 이상만 눈에 띄게. */}
                        {badges.map((b) => (
                          <span key={b} className="wb-hb mute">
                            {b}
                          </span>
                        ))}
                        {dq && dq !== "ok" && (
                          <span className="wb-hb warn">⚠ 데이터 {dq}</span>
                        )}
                      </span>
                    </div>
                    {/* 2026-08-29 POC3-ML-02 REJECT Closeout — 참고점수를 뺀 자리에
                        1개월 수익률을 둔다. compute_topn 기본 정렬 기준(one_month desc)
                        과 같은 값이라 "왜 이 순서인지"를 그대로 설명한다.
                        값이 없으면 0 으로 채우지 않고 기존 결측 표기(DASH)를 따른다. */}
                    <div className="wb-hrow-pnl">
                      <span
                        className={oneRet == null ? "amt wb-hmuted" : "amt"}
                        style={{ color: dirColor(oneRet) }}
                      >
                        {fmtPct(oneRet)}
                      </span>
                      <span className="rate wb-hmuted">1개월</span>
                    </div>
                  </div>
                  <div className="wb-hrow-bot">
                    <div className="wb-hrow-facts">
                      <span className="tk">{c.ticker ?? DASH}</span>
                      <span className="sep">/</span>
                      <span>
                        시장가 <span className="wv">{fmtWon(priceVal)}</span>
                      </span>
                      <span className="sep">/</span>
                      <span>
                        NAV <span className="wv">{fmtWon(navVal)}</span>
                      </span>
                      <span className="sep">/</span>
                      {discountVal != null ? (
                        <span>
                          괴리율{" "}
                          <span className="wv" style={{ color: dirColor(discountVal) }}>
                            {fmtPct(discountVal)}
                          </span>
                          {flagVal ? (
                            <span className="cand-flag"> {flagVal}</span>
                          ) : null}
                        </span>
                      ) : (
                        <span className="wb-hmuted">괴리율 —</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="wb-hmetrics">
                  <div className="wb-hm3">
                    <div className="wb-hm-cell">
                      <span className="k">일간</span>
                      <span className="v" style={{ color: dirColor(dailyRet) }}>
                        {fmtPct(dailyRet)}
                      </span>
                      <PeriodNote text={note("daily")} />
                    </div>
                    <div className="wb-hm-cell">
                      <span className="k">1개월</span>
                      <span className="v" style={{ color: dirColor(oneRet) }}>
                        {fmtPct(oneRet)}
                      </span>
                      <PeriodNote text={note("one_month")} />
                    </div>
                    <div className="wb-hm-cell">
                      <span className="k">3개월</span>
                      <span className="v" style={{ color: dirColor(threeRet) }}>
                        {fmtPct(threeRet)}
                      </span>
                      <PeriodNote text={note("three_month")} />
                    </div>
                  </div>
                  <div className="wb-hm-ex">
                    <span className="k">KODEX200 대비 1M</span>
                    <span className="v" style={{ color: dirColor(exKodex1m) }}>
                      {fmtPctp(exKodex1m)}
                      <PeriodNote text={cmpNote(cmpState(c, "1m", kodex), cmp1)} />
                    </span>
                  </div>
                </div>
              </div>
              {isOpen ? (
                <div className="cand-detail">
                  <div className="cand-detail-grid">
                    <DetailCell
                      label="6개월"
                      value={fmtPct(sixRet)}
                      color={dirColor(sixRet)}
                      note={note("six_month")}
                    />
                    <DetailCell
                      label="12개월"
                      value={fmtPct(twelveRet)}
                      color={dirColor(twelveRet)}
                      note={note("twelve_month")}
                    />
                    <DetailCell
                      label="3년"
                      value={fmtPct(threeYearRet)}
                      color={dirColor(threeYearRet)}
                      note={note("three_year")}
                    />
                    <DetailCell
                      label="KODEX200 대비 3M"
                      value={fmtPctp(exKodex3m)}
                      color={dirColor(exKodex3m)}
                      note={cmpNote(cmpState(c, "3m", kodex), cmp3)}
                    />
                    <DetailCell label="고점 대비" value={fmtPct(drawdown)} color={dirColor(drawdown)} />
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </>
  );
}

function DetailCell({
  label,
  value,
  color,
  note,
}: {
  label: string;
  value: string;
  color: string;
  note?: string | null;
}) {
  return (
    <div className="cand-dcell">
      <span className="k">{label}</span>
      <span className="v" style={{ color }}>
        {value}
        <PeriodNote text={note ?? null} />
      </span>
    </div>
  );
}
