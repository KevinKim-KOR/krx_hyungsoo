"use client";

// POC6-29 보완 2차 — 코스피 공식 종가(KRX · 직전 대비 + 비교 날짜 · 5회 전 대비 · 기준일 · 배지 · [?]) · 저점 문장 + 비교 기준 ·
//   1 · 3 · 6개월 칸(2026-11-14 전엔 20 · 60거래일 · 6개월) · 바로 아래 KOSPI 차트(사용자 결정 ① '숫자 바로 아래') · 코스피 지표(펼친 채).
// 형수님 결정(2026-11-13): 근거 접기 안이 아니라 「오늘 시장 변화」 당일 판정 · 시장 판정 근거 표 바로 아래에 한 덩어리로 둔다.
// 숫자는 응답 칸 그대로(새 계산 없음) · 출처 · 받은 시각은 [?] 안에만(형수님 결정 2026-11-12).
import type { MarketTopNResponse } from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import type { QueryState } from "@/lib/api/queryCache";
import { kospiStatusView } from "@/lib/kospiStatus";
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
  const obs = kospiObs(fd);
  const low = lowSentence(obs);
  const kItem = itemOf(mb, "kospi");
  const k6 = fd?.periods?.["6M"]?.kospi ?? null;
  // 기간 칸 값이 없을 때 — 불러오는 중 · 불러오지 못함 · 응답에 그 기간이 없음을 나눈다(독립 검토 2026-11-14 · '자료 없음'으로
  // 뭉뚱그리지 않음 · 다시 읽기 실패로 남은 이전 응답은 값 그대로 · 카드 아래 안내가 알림).
  const tileEmpty =
    flow.phase === "loading" || flow.phase === "idle"
      ? { num: "확인 중", sub: "불러오는 중" }
      : flow.phase === "error"
        ? { num: "확인 불가", sub: "시장 흐름을 불러오지 못했습니다" }
        : { num: "확인 불가", sub: "자료 없음" };
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
      {/* 형수님 결정(2026-11-14 · POC6-29-1 결과서 §4-2): 20 · 60거래일 칸(시장 판정 응답 · KOSPI 기준일이 기대 직전 거래일이 아니면
          값을 주지 않아 주말 · KRX 공개 전 새벽엔 '확인 불가')을 6개월 칸과 같은 시장 흐름 응답의 1 · 3개월(저장 종가 ·
          시작 ~ 끝 날짜 · 가격과 수급의 공통 비교 종료일까지)로 바꿨다. 응답 칸 그대로(새 계산 없음). */}
      <div className="tc-flow-tiles">
        {(
          [
            ["tc-tile-1m", "코스피 1개월", fd?.periods?.["1M"]?.kospi ?? null],
            ["tc-tile-3m", "코스피 3개월", fd?.periods?.["3M"]?.kospi ?? null],
          ] as const
        ).map(([id, label, k]) => (
          <div className="tc-flow-tile" data-testid={id} key={id}>
            <div className="tc-muted tc-small">{label}</div>
            <div className={`tc-flow-num ${k ? tone(k.pct) : ""}`}>{k ? signedPct(k.pct) : tileEmpty.num}</div>
            <div className="tc-muted tc-small">{k ? `${md(k.from_date)}~${md(k.to_date)}` : tileEmpty.sub}</div>
          </div>
        ))}
        <div className="tc-flow-tile" data-testid="tc-tile-6m">
          <div className="tc-muted tc-small">코스피 6개월</div>
          <div className={`tc-flow-num ${k6 ? tone(k6.pct) : ""}`}>{k6 ? signedPct(k6.pct) : tileEmpty.num}</div>
          <div className="tc-muted tc-small">{k6 ? `${md(k6.from_date)}~${md(k6.to_date)} · 수급과 같은 기간` : tileEmpty.sub}</div>
        </div>
      </div>
      <div className="tc-flow-chart" data-testid="tc-flow-chart">
        <div className="tc-label">KOSPI 가격 흐름</div>
        <KospiChart kospi={kospi} phase={market.phase} />
      </div>
      <KospiHeadline market={market} morning={morning} embedded startOpen />
    </section>
  );
}
