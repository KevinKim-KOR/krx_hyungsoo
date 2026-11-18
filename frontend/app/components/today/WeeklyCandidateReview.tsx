"use client";

// POC6-32 V2 ③ 「선택한 후보 검토」(판정 V2 Q11 (d) · Q12 (c) · §3 · PLAN §3-1 R1 ~ R5 · §9 I-7 ~ I-11 · I-17).
// 후보 하나를 고르면 보유 한 종목을 고르는 단계 없이 그 후보 자체의 근거와 내 보유 전체의 겹침을 줄마다 보인다.
// - R1 어떤 상품인가: 공식 기준정보(CSV 글자 · 파일 날짜 · 총보수는 '0.45%' 모양) · 구성 요약(주식 상위 3개 · 상위 n개 합 ·
//   서버 구성 줄 = 기준일 · 저장 행 수 · 상태).
// - R2 실제로 올랐나: 1 · 3개월 '가격 관측'(시장 판정과 다른 이름) · 실제 기간 · 방향 · 같은 기간 국내시장(KODEX 200) 대비
//   (비교할 수 있을 때만 국내시장 값 · 문구는 서버).
// - R3 더 확인할 것: 서버 확인 줄 그대로(보유 겹침 확인 범위 줄 = 경고 색) + [판단 근거 보기] = 기존 판단 근거 미리보기를 이
//   자리에서 펼침(미리보기 카드의 자체 [AI 세션에서 검토]는 숨김 · 미리보기 글은 주간 복사 · 넘기기에 넣지 않음 · I-17).
// - R4 내 보유에 무엇이 겹치나: V1 겹침 — 확인 범위 줄은 바로 위 R3 에 먼저 있고 여기는 주식별 노출 · 분모 · 기준일 +
//   '후보끼리 중복률과 다른 값' 한 줄. 노출을 계산하지 못한 상태(보유 없음 · 구성 자료 없음 · 읽기 실패)는 그 사유 줄.
// - R5 [비교 상세 →](「보유와 후보 비교」 후보 칸만) · [구성종목 보기 →](「ETF 구성종목」 이 ETF 하나) — 부르는 쪽이 넘김.
// 글 · 문구는 서버가 만든다(`app/weekly_candidate_review.py`) — 화면은 그대로 보인다. 금액 · 보유 이름 없음.
// 다시 읽는 동안(busy)은 버튼을 막고 펼친 미리보기를 내린다(앞 응답과 섞이지 않게).

import { useMemo, useState } from "react";
import type {
  WeeklyConstituents,
  WeeklyProduct,
  WeeklyReviewOk,
  WeeklySelectedReview,
} from "@/lib/api/weeklyReview";
import {
  directionText,
  feeText,
  md,
  signedPct,
  WEEKLY_FLOW_PERIOD,
  weeklyPreviewQuery,
} from "@/lib/weeklyReview";
import DecisionDraftPreviewCard from "../holdings_compare/DecisionDraftPreviewCard";

const val = (s: string | null | undefined) => (s && s.trim() ? s : "확인 불가");
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "확인 불가" : `${v.toFixed(2)}%`);

function Product({ p }: { p: WeeklyProduct }) {
  const file = p.csv?.ok && p.csv.asof ? <span className="tc-muted tc-small"> (KRX 공식 기준정보 {p.csv.asof} 파일)</span> : null;
  if (!p.found) {
    return (
      <div className="wr-warn">
        {p.missing_reason ?? "공식 기준정보에 없음"} — 공식 기초지수 · 투자 대상 · 상품 구조 확인 불가{file}
      </div>
    );
  }
  return (
    <div>
      공식 기초지수 <b>{val(p.index_name)}</b> · 지수산출기관 {val(p.index_provider)} · 투자 대상{" "}
      <b>
        {val(p.market)} · {val(p.asset)}
      </b>{" "}
      · 상품 구조 추적배수 {val(p.multiple)} · {val(p.replication)} · 총보수 {feeText(p.fee_pct)}
      {file}
    </div>
  );
}

function Constituents({ c }: { c: WeeklyConstituents }) {
  const n = c.top_stocks.length;
  return (
    <>
      {n ? (
        <div>
          주요 편입(주식) {c.top_stocks.map((s) => `${s.name ?? "이름 없음"} ${pct(s.weight_pct)}`).join(" · ")} →{" "}
          <b>
            상위 {n}개 합 {pct(c.top3_sum_pct)}
          </b>
        </div>
      ) : null}
      <div className={c.state === "full" || c.state === "top_rows" ? "tc-small" : "wr-warn"}>{c.line}</div>
    </>
  );
}

function Returns({ rv }: { rv: WeeklySelectedReview }) {
  return (
    <>
      <div className="wr-table-wrap">
        <table className="wr-table">
          <thead>
            <tr>
              <th>기간</th>
              <th className="wr-num">가격 관측</th>
              <th>실제 기간</th>
              <th>방향</th>
              <th>같은 기간 국내시장(KODEX 200) 대비</th>
            </tr>
          </thead>
          <tbody>
            {rv.returns.map((x) => {
              const differs = x.status === "period_differs";
              const common = differs && x.common?.start && x.common.end ? ` (공통 ${md(x.common.start)} → ${md(x.common.end)})` : "";
              return (
                <tr key={x.period} data-period={x.period}>
                  <td className="wr-nowrap">{x.label}</td>
                  <td className="wr-num">
                    {signedPct(x.value_pct)}
                    {differs ? " · 기간 다름" : ""}
                  </td>
                  <td>{x.start && x.end ? `${md(x.start)} → ${md(x.end)}${common}` : "확인 불가"}</td>
                  <td className="wr-nowrap">{directionText(x)}</td>
                  <td>
                    {x.market.comparable ? (
                      <>
                        국내시장 {signedPct(x.market.value_pct)} · <b>{x.phrase}</b>
                      </>
                    ) : (
                      x.phrase
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="tc-muted tc-small">
        {rv.price_note} · 시작 · 끝 · 가격 상태가 KODEX 200 과 같을 때만 국내시장 대비를 씀(둘 다 장중이면 &apos;잠정&apos;) ·
        기간 다름이면 값 + 실제 기간 + &apos;기간 다름 · 국내시장 대비 안 함&apos;
      </div>
    </>
  );
}

function Body({ r, rv, busy, onClear, onCompare, onExposure }: Props & { rv: WeeklySelectedReview }) {
  const [open, setOpen] = useState(false);
  const query = useMemo(() => weeklyPreviewQuery(r, rv.ticker), [r, rv.ticker]);
  const ov = rv.overlap;
  const warn = new Set(ov?.warn_lines ?? []);
  // 노출을 계산한 경우(lines 있음)는 확인 범위 줄이 R3 에 있고, 못 한 경우는 사유 줄만 있으므로 여기서 그 줄을 보인다.
  const owned = ov ? (ov.lines.length ? ov.lines : ov.warn_lines) : ["보유 겹침 확인 불가"];
  return (
    <>
      <div data-testid="wr-review-head">
        <b>
          {rv.name}({rv.ticker})
        </b>{" "}
        · 1개월 상위 {rv.rank}위
      </div>
      <div className="wk-q" data-testid="wr-r1">
        <b className="wk-q-t">어떤 상품인가</b>
        <div className="wk-q-b">
          <Product p={rv.product} />
          <Constituents c={rv.constituents} />
        </div>
      </div>
      <div className="wk-q" data-testid="wr-r2">
        <b className="wk-q-t">실제로 올랐나</b>
        <div className="wk-q-b">
          <Returns rv={rv} />
        </div>
      </div>
      <div className="wk-q" data-testid="wr-r3">
        <b className="wk-q-t">더 확인할 것</b>
        <div className="wk-q-b">
          {rv.checks.map((l, i) => (
            <div key={i} className={warn.has(l) ? "wr-warn" : "tc-small"}>
              {l}
            </div>
          ))}
          {query ? (
            <div className="wr-actions">
              <button
                type="button"
                className="btn-md tc-fold-btn"
                aria-expanded={open}
                onClick={() => setOpen((o) => !o)}
                disabled={busy}
              >
                {open ? "판단 근거 접기 ▴" : "판단 근거 보기 ▾"}
              </button>
              <span className="tc-muted tc-small">
                기존 판단 근거 미리보기를 여기서 펼침 · 화면에서만(주간 복사 · 넘기기에 넣지 않음)
              </span>
            </div>
          ) : null}
          {open && query && !busy ? (
            <div data-testid="wr-preview">
              <DecisionDraftPreviewCard
                targetKind="candidate"
                ticker={rv.ticker}
                displayName={rv.name}
                listQuery={query}
                flowPeriod={WEEKLY_FLOW_PERIOD}
                hideReviewTransfer
              />
            </div>
          ) : null}
        </div>
      </div>
      <div className="wk-q" data-testid="wr-r4">
        <b className="wk-q-t">내 보유에 무엇이 겹치나</b>
        <div className="wk-q-b">
          {owned.map((l, i) => (
            <div key={i} className={ov && ov.lines.length ? undefined : "wr-warn"}>
              {l}
            </div>
          ))}
          {ov?.date_line ? <div className="tc-muted tc-small">{ov.date_line}</div> : null}
          {ov && ov.lines.length ? <div className="tc-muted tc-small">{rv.overlap_note}</div> : null}
        </div>
      </div>
      <div className="wr-actions" data-testid="wr-review-go">
        <button type="button" className="btn-md tc-fold-btn" onClick={onCompare} disabled={busy}>
          비교 상세 →
        </button>
        <button type="button" className="btn-md tc-fold-btn" onClick={onExposure} disabled={busy}>
          구성종목 보기 →
        </button>
        <button type="button" className="btn-md tc-fold-btn" onClick={onClear} disabled={busy}>
          고른 후보 지우기
        </button>
        <span className="tc-muted tc-small">
          [비교 상세] = 보유를 바꿀 상품을 볼 때(이 후보 한쪽만 채움) · [구성종목 보기] = 이 ETF 하나
        </span>
      </div>
    </>
  );
}

interface Props {
  // 지금 보이는 응답(한 응답 = 한 검토 건)
  r: WeeklyReviewOk;
  busy: boolean;
  onClear: () => void;
  onCompare: () => void;
  onExposure: () => void;
}

export default function WeeklyCandidateReview(props: Props) {
  const { r } = props;
  const rv = r.selected_review;
  return (
    <div className="wr-sec" data-testid="wr-review">
      <div>
        <span className="wr-sec-title">③ 선택한 후보 검토</span>{" "}
        <span className="tc-muted tc-small">
          후보를 고르면 그 후보의 근거와 내 보유 전체의 겹침을 봅니다 · 시스템이 정하는 것 = 가격 방향과 비교 가능 범위 ·
          쓸 만한지는 직접 기록
        </span>
      </div>
      {r.selected_missing ? (
        <div className="wr-warn">고른 후보가 지금 목록에 없습니다(자료가 바뀜) — 위 표에서 다시 고르세요.</div>
      ) : null}
      {rv ? (
        // 고른 후보가 바뀌면 펼친 미리보기를 접고 처음부터(다른 후보 이름에 앞 미리보기를 붙이지 않음)
        <Body key={rv.ticker} {...props} rv={rv} />
      ) : (
        <div>
          <span className="wr-pill">고르기 전</span>{" "}
          <span className="tc-muted tc-small">
            위 표의 [고르기]로 후보를 고르면 어떤 상품인지 · 실제로 올랐는지 · 내 보유에 무엇이 겹치는지 봅니다.
          </span>
        </div>
      )}
    </div>
  );
}
