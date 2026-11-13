"use client";

// POC6-29 보완 2차(판정서 V2 §2 · S 판정 §3 · PLAN §10-1) — 「시장 흐름」 맨 위 아침 요약.
// - 머리 = 직전 국내 거래일 마감 기준(아침 기준 응답 · 한 번만).
// - 준비 상태 한 줄 = 필수 3(코스피 공식 종가 · KODEX 200 판정 근거 · 투자자 수급) · 사유는 서버가 확인한 결과 그대로.
// - 아침 판정 = 기준일까지의 저장 이력으로 계산한 기존 판정(서버) · 근거가 확인되지 않으면 '아침 판정 미확인'.
// - 문장은 기준을 채운 자료만(코스피 공식 종가 · 외국인 5거래일 · VIX · 원/달러 · WTI). 못 채운 자료의 이전 문장은
//   [시장 근거와 다른 변화 보기] ③ 으로 보낸다. 최근 변화는 기준을 채운 계열의 사건 1 ~ 2줄.
// 설계자 정리(2026-11-13 · 마감 뒤 · 형수님 선택): 제목 한 줄 → 시장 판단(굵게) + KODEX 200 핵심 근거 → 기준을 채운 자료 문장
//   (원/달러 · WTI 는 원/달러가 기준일을 채웠을 때 값만 · 과거 사건은 최근 변화 줄 · 날짜별 상세) → 최근 변화(그대로) → 끝 한 줄
//   (빠진 자료 'M/D까지 있습니다' · 원인 · 확인 시각은 [자료 상태 보기] · 모두 준비되면 짧게 한 줄).
import type { MarketTopNResponse } from "@/lib/api";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import type { QueryState } from "@/lib/api/queryCache";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import type { ShortFlowsResponse } from "@/lib/api/shortFlows";
import { fxwtiSentence, vixSentence, type NowSentence } from "@/lib/marketNowText";
import { flowsMorning, itemOf, morningStatus, morningVerdict } from "@/lib/morningText";
import { kospiObs, md, num2, recentChanges, signedPct } from "@/lib/todayMarketLines";
import { regimeLabelKo } from "./todayHelpers";

function Sentence({ s }: { s: NowSentence }) {
  return (
    <p data-testid={`tc-morning-${s.key}`}>
      {s.text}
      {s.basis ? <span className="tc-muted tc-small"> {s.basis}</span> : null}
      {s.stale ? (
        <>
          {" "}
          <span className="tc-sum-badge tc-sum-warn">{s.stale}</span>
        </>
      ) : null}
    </p>
  );
}

export default function MorningSummary({
  morning,
  market,
  flow,
  short,
}: {
  morning: QueryState<MorningBasisResponse>;
  market: QueryState<MarketTopNResponse>;
  flow: QueryState<MarketFlowContext>;
  short: QueryState<ShortFlowsResponse>;
}) {
  const mb = morning.phase === "success" ? morning.data : null;
  const fd = flow.phase === "success" ? flow.data : null;
  const sf = short.phase === "success" ? short.data : null;
  const st = morningStatus(mb, morning.phase);
  const verdict = mb ? morningVerdict(mb, (c) => regimeLabelKo(c.regime_code, c.regime_label)) : null;
  const kospiItem = itemOf(mb, "kospi");
  const flowsItem = itemOf(mb, "flows");
  const obs = kospiObs(fd);
  const sentences: NowSentence[] = [];
  if (kospiItem?.met) {
    sentences.push(
      obs && obs.date === kospiItem.stored_date
        ? {
            key: "kospi",
            text:
              `코스피 ${md(obs.date)} 공식 종가 ${num2(obs.value)}` +
              (obs.d1 ? `(${md(obs.d1.from_date)} 대비 ${signedPct(obs.d1.pct)}).` : "."),
            basis: "KRX",
            stale: null,
          }
        : { key: "kospi", text: `코스피 공식 종가 ${md(kospiItem.stored_date)}까지 준비됨.`, basis: "KRX", stale: null },
    );
  }
  if (flowsItem?.met) {
    const s = flowsMorning(sf);
    if (s) sentences.push(s);
  }
  const vix = market.phase === "success" ? (market.data.market_risk_reference?.vix ?? null) : null;
  const vs = vixSentence(vix);
  if (vs) sentences.push(vs);
  // 원/달러가 기준일을 채웠을 때만 값 문장(과거 사건 없이 · 사건은 아래 최근 변화 줄)
  const fx = fxwtiSentence(fd, false);
  if (fx.sentence && itemOf(mb, "usdkrw")?.met) sentences.push(fx.sentence);
  // 기준을 채운 계열의 사건만 위로(원/달러 · WTI 는 각 원천 기준 · 코스피 · 수급은 아침 기준 충족 때만)
  const allowKospi = !!kospiItem?.met;
  const allowFlows = !!flowsItem?.met;
  const changes = fd
    ? recentChanges(fd, false, fx.merged, (e) =>
        e.key === "kospi" ? allowKospi : e.key === "foreign" || e.key === "institution" ? allowFlows : true,
      )
    : null;
  return (
    <div className="tc-morning" data-testid="tc-morning">
      <div className="tc-morning-head">
        <strong>아침 요약 · {mb?.expected_date ? `${md(mb.expected_date)} 마감 기준` : "기준일 확인 중"}</strong>
      </div>
      {verdict ? (
        <p className="tc-morning-verdict" data-testid="tc-morning-regime">
          <strong>{verdict.head}</strong>
          {verdict.detail ? ` ${verdict.detail}` : null}
        </p>
      ) : null}
      <div className="tc-now-text" data-testid="tc-morning-text">
        {sentences.map((s, i) => (
          <Sentence s={s} key={`${s.key}-${i}`} />
        ))}
      </div>
      {changes && changes.shown.length > 0 ? (
        <div className="tc-small" data-testid="tc-morning-changes">
          <strong>최근 변화</strong> · {changes.shown.join(" · ")}
          <span className="tc-muted"> · 전체 {(fd?.events ?? []).length}건은 아래 [시장 근거와 다른 변화 보기] ②에서</span>
        </div>
      ) : null}
      <div className={`tc-morning-status tc-morning-status-${st.tone}`} data-testid="tc-morning-ready">
        {st.text}
        {st.reasons.length > 0 ? (
          <details className="tc-morning-why">
            <summary>자료 상태 보기</summary>
            {st.reasons.map((t) => (
              <div className="tc-muted tc-small" key={t} data-testid="tc-morning-reason">
                {t}
              </div>
            ))}
          </details>
        ) : null}
      </div>
    </div>
  );
}
