"use client";

// POC6-29 보완 2차 — 코스피 공식 종가(KRX · 직전 대비 + 비교 날짜 · 5회 전 대비 · 기준일 · 배지 · [?]) · 저점 문장 + 비교 기준 ·
//   20 · 60 · 6개월 칸 · 바로 아래 KOSPI 차트(사용자 결정 ① '숫자 바로 아래') · 코스피 지표(펼친 채).
// 형수님 결정(2026-11-13): 근거 접기 안이 아니라 「오늘 시장 변화」 당일 판정 · 시장 판정 근거 표 바로 아래에 한 덩어리로 둔다.
// 숫자는 응답 칸 그대로(새 계산 없음) · 출처 · 받은 시각은 [?] 안에만(형수님 결정 2026-11-12).
import type { MarketTopNResponse } from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import type { QueryState } from "@/lib/api/queryCache";
import { kospiStatusView, kospiValuesUsable } from "@/lib/kospiStatus";
import { kstMdHm } from "@/lib/marketNowText";
import { itemOf } from "@/lib/morningText";
import { kospiObs, lowSentence, md, num2, signedPct } from "@/lib/todayMarketLines";
import KospiChart from "./KospiChart";
import KospiHeadline from "./KospiHeadline";
import SourceHint from "./SourceHint";

function tone(p: number | null | undefined): string {
  if (p == null) return "";
  return p > 0 ? "tc-up" : p < 0 ? "tc-down" : "";
}

export default function KospiCloseBlock({
  market,
  flow,
  morning,
}: {
  market: QueryState<MarketTopNResponse>;
  flow: QueryState<MarketFlowContext>;
  morning: QueryState<MorningBasisResponse>;
}) {
  const ctx = market.phase === "success" ? (market.data.market_context ?? null) : null;
  const fd = flow.phase === "success" ? flow.data : null;
  const mb = morning.phase === "success" ? morning.data : null;
  const kospi = ctx?.kospi ?? null;
  const kv = kospiStatusView(kospi, market.phase);
  const usable = kospiValuesUsable(kospi);
  const obs = kospiObs(fd);
  const low = lowSentence(obs);
  const kItem = itemOf(mb, "kospi");
  const k6 = fd?.periods?.["6M"]?.kospi ?? null;
  return (
    <section className="tc-kospi-block" aria-label="코스피 공식 종가" data-testid="tc-kospi-close">
      <div className="tc-label">코스피 공식 종가(KRX)</div>
      {obs ? (
        <div className="tc-flow-close">
          <span className="tc-flow-big">{num2(obs.value)}</span>{" "}
          {obs.d1 ? (
            <>
              <span className={tone(obs.d1.diff)}>
                {obs.d1.diff >= 0 ? "+" : "-"}
                {num2(Math.abs(obs.d1.diff))}pt ({signedPct(obs.d1.pct)})
              </span>{" "}
              {/* 비교 날짜를 직접 적는다(직전 '저장' 종가일 · '전일'로 부르지 않음 · RESULT 판정 §3-1) */}
              <span className="tc-muted tc-small">{md(obs.d1.from_date)} 대비</span>
            </>
          ) : null}{" "}
          {obs.d5 ? (
            <span className="tc-small" data-testid="tc-kospi-d5">
              · 5회 전 대비 {obs.d5.diff >= 0 ? "+" : "-"}
              {num2(Math.abs(obs.d5.diff))}pt ({signedPct(obs.d5.pct)})
            </span>
          ) : null}{" "}
          <span className="tc-muted tc-small">· 기준일 {md(obs.date)}</span>
          {!kv.loading
            ? kv.badges.map((b) => (
                <span key={b.text}>
                  {" "}
                  <span className={b.tone === "warn" ? "tc-sum-badge tc-sum-warn" : "tc-sum-badge tc-sum-muted"}>{b.text}</span>
                </span>
              ))
            : null}
          <SourceHint
            text={`KRX 공식 종가 · ${kstMdHm(kItem?.received_at ?? null)} 받음${obs.d5 ? ` · 5회 전 ${md(obs.d5.from_date)} → ${md(obs.date)}` : ""}`}
            testId="tc-src-kospi"
          />
        </div>
      ) : (
        <div className="tc-muted">{flow.phase === "loading" || flow.phase === "idle" ? "불러오는 중" : "확인 불가"}</div>
      )}
      {obs && low ? (
        <div className="tc-flow-low tc-small" data-testid="tc-kospi-low">
          {low}
          {obs.range
            ? ` (비교 기준: 직전 20개 저장 종가의 ${obs.range.dir === "아래" ? "최저" : "최고"} ${num2(obs.range.bound)} · ${md(obs.range.bound_date)})`
            : ""}
        </div>
      ) : null}
      {/* 사용자 결정 ① — 차트는 코스피 숫자 바로 아래(형수님 결정 2026-11-13 · 접기 밖 · 당일 판정 · 판정 표 아래). */}
      <div className="tc-flow-tiles">
        {(
          [
            ["tc-tile-20", "코스피 20거래일", kospi?.return_20d_pct],
            ["tc-tile-60", "코스피 60거래일", kospi?.return_60d_pct],
          ] as const
        ).map(([id, label, v]) => (
          <div className="tc-flow-tile" data-testid={id} key={id}>
            <div className="tc-muted tc-small">{label}</div>
            <div className={`tc-flow-num ${usable ? tone(v) : ""}`}>{usable ? signedPct(v ?? null) : "확인 불가"}</div>
            <div className="tc-muted tc-small">
              {usable ? `${md(kospi?.as_of_date)} 기준` : kv.loading ? "확인 중" : (kv.reason ?? "자료 없음")}
            </div>
          </div>
        ))}
        <div className="tc-flow-tile" data-testid="tc-tile-6m">
          <div className="tc-muted tc-small">코스피 6개월</div>
          <div className={`tc-flow-num ${k6 ? tone(k6.pct) : ""}`}>{k6 ? signedPct(k6.pct) : "확인 불가"}</div>
          <div className="tc-muted tc-small">{k6 ? `${md(k6.from_date)}~${md(k6.to_date)} · 수급과 같은 기간` : "자료 없음"}</div>
        </div>
      </div>
      <div className="tc-flow-chart" data-testid="tc-flow-chart">
        <div className="tc-label">KOSPI 가격 흐름</div>
        <KospiChart kospi={kospi} phase={market.phase} />
      </div>
      <KospiHeadline market={market} embedded startOpen />
    </section>
  );
}
