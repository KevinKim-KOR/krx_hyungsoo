"use client";

// POC6-27 — 「지금 확인할 내용」 › 시장 흐름(설계 §3 · 사용자 결정 ① ③ · PLAN 판정 §2 · Q1 · Q9).
//
// 순서(판정 §2): 판정 배지 · KODEX 200 기준일 · [AI용 시장 정보 복사] → 코스피 종가 · 저점 문장 →
//   20 · 60거래일 · 6개월 → KOSPI 차트(기존 KospiChart · 최근 최대 120개 저장일) → 외국인 수급 →
//   최근 큰 변화(늘 보임) → [시장 근거와 다른 변화 보기](없어진 KOSPI 카드의 나머지 지표 · 원/달러 · WTI ·
//   사건 전체 · 자료별 기준일).
// 숫자는 시장 판정 응답(20 · 60거래일 · 판정) · 시장 흐름 응답의 구조 칸(종가 · 기준값 · 6개월 · 수급)에서만
// 읽는다(새 계산 · 문장 파싱 없음). 값이 없으면 '확인 불가'.
import { useState } from "react";
import type { MarketTopNResponse, PriceSeriesResponse } from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";
import { FLOW_LINK_WARN, type MarketFlowContext } from "@/lib/api/marketFlow";
import { kospiStatusView, kospiValuesUsable } from "@/lib/kospiStatus";
import {
  eventSentence,
  foreignView,
  hasStructuredEvents,
  kospiObs,
  lowSentence,
  md,
  netWord,
  num2,
  priceObs,
  recentChanges,
  signedPct,
  withUnit,
  wonAbs,
} from "@/lib/todayMarketLines";
import KospiChart from "./KospiChart";
import KospiHeadline from "./KospiHeadline";
import { failOf, joinStale, staleOf } from "./summaryLines";
import { regimeLabelKo } from "./todayHelpers";
import type { MenuKey } from "../LeftSidebar";

function dirWord(p: number | null | undefined): string | null {
  if (p == null || !Number.isFinite(p)) return null;
  return p > 0 ? "상승" : p < 0 ? "하락" : "보합";
}

function tone(p: number | null | undefined): string {
  if (p == null) return "";
  return p > 0 ? "tc-up" : p < 0 ? "tc-down" : "";
}

export default function MarketFlowBlock({
  market,
  flow,
  series,
  onCopy,
  copyDisabled,
  copyMessage,
  copyFallback,
  onNavigate,
}: {
  market: QueryState<MarketTopNResponse>;
  flow: QueryState<MarketFlowContext>;
  series: QueryState<PriceSeriesResponse>;
  onCopy: () => void;
  copyDisabled: boolean;
  copyMessage: string | null;
  // 복사 실패 때 직접 선택해 복사할 글(성공처럼 보이지 않게 · 판정 §4)
  copyFallback: string | null;
  onNavigate: (key: MenuKey) => void;
}) {
  const [openWhy, setOpenWhy] = useState(false);
  const ctx = market.phase === "success" ? (market.data.market_context ?? null) : null;
  const fd = flow.phase === "success" ? flow.data : null;
  const obs = kospiObs(fd);
  const low = lowSentence(obs);
  const kospi = ctx?.kospi ?? null;
  const kv = kospiStatusView(kospi, market.phase);
  const usable = kospiValuesUsable(kospi);
  const k6 = fd?.periods?.["6M"]?.kospi ?? null;
  const fv = foreignView(fd);
  const changes = fd ? recentChanges(fd, low !== null) : null;
  const streak = ctx?.regime_streak;
  const badge = ctx
    ? `${regimeLabelKo(ctx.regime_code, ctx.regime_label)}` +
      (streak && streak.streak_days != null ? ` · ${streak.streak_days}거래일째${streak.at_least ? " 이상" : ""}` : " · 지속일 자료 없음")
    : market.phase === "loading" || market.phase === "idle"
      ? "불러오는 중"
      : "시장 판정 확인 불가";
  const stale = joinStale(
    staleOf("수급 · 환율 · 유가", flow),
    failOf("수급 · 환율 · 유가", flow),
    staleOf("KOSPI 가격 흐름", series),
    failOf("KOSPI 가격 흐름", series),
  );
  // 기간 비교 기준일 문장(end_basis)은 외국인 수급 아래에 이미 있다 — 여기에는 수급 연결 경고만(같은 문장 두 번 없음 · 설계 §7).
  const note = fd?.flow_link && FLOW_LINK_WARN.includes(fd.flow_link.state) ? `수급 연결: ${fd.flow_link.text}` : null;
  const fx = priceObs(fd, "usdkrw");
  const oil = priceObs(fd, "wti");

  return (
    <section className="tc-card tc-flow" aria-label="시장 흐름" data-testid="tc-market-flow">
      <div className="tc-flow-head">
        <div>
          <h3 className="tc-h3">시장 흐름</h3>
          <div className="tc-flow-sub">
            <span className="tc-sum-badge tc-sum-info" data-testid="tc-flow-regime">
              {badge}
            </span>{" "}
            <span className="tc-muted tc-small">
              KODEX 200 · {ctx?.asof ? `${md(ctx.asof)} 기준` : "기준일 확인 불가"} · 시장 판정은 화면을 열 때 · 시장 갱신 뒤 읽은 값([요약 다시 읽기] 대상 아님)
            </span>
          </div>
        </div>
        <button type="button" className="btn-md tc-fold-btn" onClick={onCopy} disabled={copyDisabled}>
          AI용 시장 정보 복사
        </button>
      </div>
      {copyMessage ? (
        <p className={copyFallback ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-copy-message">
          {copyMessage}
        </p>
      ) : null}
      {copyFallback ? (
        <textarea className="tc-copy-fallback" readOnly value={copyFallback} rows={10} aria-label="복사할 시장 정보" />
      ) : null}

      {/* 코스피 종가 · 저점 문장 — 종가(그날)와 비교 기준값(직전 20개 저장 종가 최저 · 날짜)을 나눠 쓴다. */}
      <div className="tc-flow-close" data-testid="tc-kospi-close">
        {obs ? (
          <>
            <span className="tc-muted">{md(obs.date)} 코스피 종가</span>{" "}
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
            ) : null}
          </>
        ) : (
          <span className="tc-muted">
            코스피 종가 {flow.phase === "loading" || flow.phase === "idle" ? "불러오는 중" : "확인 불가"}
          </span>
        )}
      </div>
      {obs && low ? (
        <div className="tc-flow-low" data-testid="tc-kospi-low">
          {low}{" "}
          <button type="button" className="tc-linklike tc-small" aria-expanded={openWhy} onClick={() => setOpenWhy((v) => !v)}>
            {openWhy ? "근거 닫기" : "근거 보기"}
          </button>
          {openWhy && obs.range ? (
            <div className="tc-muted tc-small" data-testid="tc-kospi-low-why">
              비교 기준: 직전 20개 저장 종가의 {obs.range.dir === "아래" ? "최저" : "최고"} {num2(obs.range.bound)}(
              {obs.range.bound_date}) · 그날 종가 {num2(obs.value)}({obs.date}) · 장중 움직임은 보지 않습니다
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="tc-flow-tiles">
        <div className="tc-flow-tile" data-testid="tc-tile-20">
          <div className="tc-muted tc-small">20거래일</div>
          <div className={`tc-flow-num ${usable ? tone(kospi?.return_20d_pct) : ""}`}>
            {usable ? signedPct(kospi?.return_20d_pct ?? null) : "확인 불가"}
          </div>
          <div className="tc-muted tc-small">
            {usable ? `${md(kospi?.as_of_date)} 기준` : kv.loading ? "확인 중" : (kv.reason ?? "자료 없음")}
          </div>
        </div>
        <div className="tc-flow-tile" data-testid="tc-tile-60">
          <div className="tc-muted tc-small">60거래일</div>
          <div className={`tc-flow-num ${usable ? tone(kospi?.return_60d_pct) : ""}`}>
            {usable ? signedPct(kospi?.return_60d_pct ?? null) : "확인 불가"}
          </div>
          <div className="tc-muted tc-small">
            {usable ? `${md(kospi?.as_of_date)} 기준` : kv.loading ? "확인 중" : (kv.reason ?? "자료 없음")}
          </div>
        </div>
        <div className="tc-flow-tile" data-testid="tc-tile-6m">
          <div className="tc-muted tc-small">
            6개월 {k6 && dirWord(k6.pct) ? <span className="tc-sum-badge tc-sum-info">{dirWord(k6.pct)}</span> : null}
          </div>
          <div className={`tc-flow-num ${k6 ? tone(k6.pct) : ""}`}>{k6 ? signedPct(k6.pct) : "확인 불가"}</div>
          <div className="tc-muted tc-small">
            {k6 ? `${md(k6.from_date)}~${md(k6.to_date)} · 수급과 같은 기간` : "자료 없음"}
          </div>
        </div>
      </div>

      {/* 사용자 결정 ① — 차트는 코스피 수치 바로 아래 · 외국인 수급 위(판정 Q9 · 기존 최근 최대 120개 저장일). */}
      <div className="tc-flow-chart" data-testid="tc-flow-chart">
        <div className="tc-label">KOSPI 가격 흐름</div>
        <KospiChart kospi={kospi} phase={market.phase} />
      </div>

      <div className="tc-flow-section" data-testid="tc-flow-foreign">
        <div className="tc-flow-row">
          <strong>외국인 수급</strong>
          <span className="tc-muted tc-small">{fv.six ? `${md(fv.six.end)}까지` : ""}</span>
        </div>
        {fd && !fd.has_flows ? (
          <div className="tc-muted tc-small">{fd.windows?.lines?.[0] ?? "투자자별 수급 자료 없음"}</div>
        ) : (
          <>
            <div>
              6개월 누적{" "}
              {fv.six ? (
                <>
                  <strong>
                    {wonAbs(fv.six.sum)} {netWord(fv.six.sum)}
                  </strong>{" "}
                  <span className="tc-muted tc-small">
                    ({fv.six.days}/{fv.six.expected}일{fv.six.partial ? " · 부분 집계" : ""})
                  </span>
                </>
              ) : (
                "확인 불가"
              )}
            </div>
            <div>
              {fv.recent && fv.previous && fv.previous.avg != null && fv.recent.avg != null ? (
                <>
                  {netWord(fv.previous.avg) === netWord(fv.recent.avg) ? (
                    <>
                      하루 평균 {netWord(fv.recent.avg)}액{" "}
                      <strong>
                        {wonAbs(fv.previous.avg)} → {wonAbs(fv.recent.avg)}
                      </strong>
                    </>
                  ) : (
                    <>
                      하루 평균{" "}
                      <strong>
                        {netWord(fv.previous.avg)} {wonAbs(fv.previous.avg)} → {netWord(fv.recent.avg)} {wonAbs(fv.recent.avg)}
                      </strong>
                    </>
                  )}
                  {fv.trend ? ` · ${fv.trend}` : ""}
                </>
              ) : fd ? (
                <span className="tc-muted">최근 · 직전 20거래일 비교 확인 불가</span>
              ) : null}
            </div>
            {fv.recent && fv.previous ? (
              <div className="tc-muted tc-small">
                직전 20거래일({md(fv.previous.from)}~{md(fv.previous.to)}) → 최근 20거래일({md(fv.recent.from)}~
                {md(fv.recent.to)})
              </div>
            ) : null}
          </>
        )}
        {fd?.end_basis?.text ? <div className="tc-muted tc-small">{fd.end_basis.text}</div> : null}
      </div>

      {/* 사용자 결정 ③ — 최근 큰 변화는 늘 보인다(최근 2건 · 외 N건 · 위 저점 문장과 같은 1건만 뺌). */}
      <div className="tc-flow-section" data-testid="tc-flow-changes">
        <strong>최근 큰 변화</strong>
        {!fd ? (
          <div className="tc-muted tc-small">
            {flow.phase === "loading" || flow.phase === "idle" ? "불러오는 중" : "수급 · 환율 · 유가 자료를 불러오지 못했습니다"}
          </div>
        ) : changes?.legacy ? (
          <div className="tc-small">{changes.legacy}</div>
        ) : (
          <>
            {changes && changes.shown.length > 0 ? (
              <ul className="tc-list-plain">
                {changes.shown.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            ) : changes?.empty ? (
              <div className="tc-muted tc-small">{changes.empty}</div>
            ) : (
              <div className="tc-muted tc-small">
                {changes?.unchecked ? "위 문장 외 확인한 자료에서는 최근 큰 변화 없음" : "위 문장 외 최근 큰 변화 없음"}
              </div>
            )}
            {changes && changes.rest > 0 ? <div className="tc-muted tc-small">외 {changes.rest}건</div> : null}
            {changes?.unchecked ? <div className="tc-muted tc-small">{changes.unchecked}</div> : null}
          </>
        )}
      </div>
      {note ? <div className="tc-sum-note">{note}</div> : null}
      {stale ? <div className="tc-sum-stale">{stale}</div> : null}

      <details className="tc-flow-more">
        <summary>시장 근거와 다른 변화 보기</summary>
        <div className="tc-flow-more-body">
          <KospiHeadline market={market} embedded />
          <div className="tc-stat-block">
            <div className="tc-label">원/달러 · WTI</div>
            <ul className="tc-list-plain">
              <li>원/달러 {fx ? `${withUnit(fx.value, fx.unit)} · ${fx.date}(런던 날짜)` : "확인 불가"}</li>
              <li>
                WTI{" "}
                {oil
                  ? `${withUnit(oil.value, oil.unit)}${oil.d1 ? `(${signedPct(oil.d1.pct)})` : ""} · ${oil.date}(뉴욕 날짜 · 관측일만 표시)`
                  : "확인 불가"}
              </li>
            </ul>
          </div>
          {fd ? (
            <div className="tc-stat-block" data-testid="tc-flow-events-all">
              <div className="tc-label">
                최근 큰 변화 전체 {(fd.events ?? []).length}건
                {changes && changes.excluded > 0 ? ` · 위 저점 문장과 같은 ${changes.excluded}건은 요약에서 뺌` : ""}
              </div>
              {(fd.events ?? []).length > 0 ? (
                <ul className="tc-list-plain">
                  {(fd.events ?? []).map((e, i) => (
                    <li key={`${e.date}-${e.kind}-${i}`}>
                      {hasStructuredEvents(fd) ? eventSentence(e) : `${e.text} (괄호 안 = 비교 기준값)`}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="tc-muted tc-small">{fd.event_check?.empty_text ?? "없음"}</div>
              )}
              <div className="tc-muted tc-small">
                자료별 기준일:{" "}
                {(fd.status ?? []).map((s) => `${s.label} ${s.E ?? "확인 불가"}`).join(" · ") || "확인 불가"}
              </div>
            </div>
          ) : null}
          <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("market_discovery")}>
            시장 흐름 자세히(요즘 잘 오르는 ETF)
          </button>
        </div>
      </details>
    </section>
  );
}
