"use client";
// POC5-13 · POC5-15 — 「확인 근거」 목록 위 요약(PLAN 판정 §3 · §4).
// 현재 상태 + ? / 하락 구간 종목 수 · 비중 / 구간별 / 작은 보조 묶음(시장 국면 · 판정 범위 ·
// PC 저장 종가 기준). 정의 · 산식 · PC 와 OCI 차이는 ? 도움말로 옮겼다.
// POC6-33(판정 Q4 · Q31 · Q32 · Q48 · PLAN E1 · I-15) — 머리 '현재 보유 점검 상태' · 세 칸(하락 구간 · 자료 확인 필요 ·
// 가격 기준일) · 보조 한 줄(보유 저장 시각 · 기존 후보 목록 기준일(가격 기준일과 다를 때만) · 계산 가능 · 시장 국면 · 판정 범위).
// 가격 기준일(price_basis.reference_date)은 이 칸 한 곳에서만 이름을 붙여 보인다(예전 'PC 저장 가격 기준일' ·
// 'PC 가격 흐름 기준일' 두 이름). 보유 저장 시각 = 보유 파일 수정 시각(holdings_asof) · 분 단위 한국 시각 · 값은 그대로.
import { fmtKstDate } from "../today/todayHelpers";
import { DECLINE_SHORT, PARTIAL_EVAL_TEXT, fmtShare } from "./declineSummary";
import HelpPopover from "./HelpPopover";
import { PARTIAL_JUDGE_TEXT, riskHelpParagraphs, type RiskStateView } from "./riskCombination";

export const RISK_HEAD_LABEL = "현재 보유 점검 상태";
export const PRICE_DATE_NOTE = "KODEX 200 마지막 저장일 · 5 · 20저장일 흐름과 하락 구간의 기준";
// POC6-33 RESULT 판정 §2-6 — 응답 market_asof(구성종목 중복 비교에 쓰는 기존 후보 목록 · compute_topn 의 asof)의 이름.
// 가격 기준일 · 상세 주간 순위의 기간과 구별되게 이름을 붙이고, 보일 때만 ? 도움말에 뜻을 더한다.
export const MARKET_ASOF_LABEL = "기존 후보 목록 기준일";
export const HELP_MARKET_ASOF =
  "기존 후보 목록 기준일은 종목 상세 ‘구성종목 중복’이 비교에 쓰는 기존 후보 목록의 날짜입니다. 종목 가격 흐름 · 하락 구간의 ‘가격 기준일’, 종목 상세 주간 순위(「주간 ETF 점검」과 같은 수익률 순위)의 기간과 따로 정해지며, 가격 기준일과 같은 날이면 적지 않습니다.";

// 기존 후보 목록 기준일이 가격 기준일과 같은 날이면 다시 적지 않는다(날짜 부분 비교). 그 날짜가 없으면 적지 않고,
// 가격 기준일을 모르면 같은 날인지 알 수 없어 이름을 붙여 적는다.
function marketDateShown(market: string | null, priceDate: string | null): boolean {
  if (!market) return false;
  if (!priceDate) return true;
  return market.slice(0, 10) !== priceDate.slice(0, 10);
}

export default function DeclineSummaryBlock({
  v,
  needCheck,
  calcOk,
  calcTotal,
  holdingsAsof,
  marketAsof,
}: {
  v: RiskStateView;
  needCheck: number;
  calcOk: number;
  calcTotal: number;
  holdingsAsof: string | null;
  marketAsof: string | null;
}) {
  const s = v.summary;
  if (!s) return null;
  const combo = v.combo;
  const showMarket = marketDateShown(marketAsof, s.flowDate);
  const help = showMarket ? [...riskHelpParagraphs(v), HELP_MARKET_ASOF] : riskHelpParagraphs(v);
  return (
    <div className="hre-risk" data-testid="hre-risk-summary">
      <div className="hre-risk-head" data-testid="hre-risk-state">
        <span className="k">{RISK_HEAD_LABEL}</span>
        <strong className="hre-risk-headline">{combo.text}</strong>
        <HelpPopover label={RISK_HEAD_LABEL} paragraphs={help} />
      </div>
      <div className="hre-risk-stats">
        <div className="hre-risk-stat">
          <span className="k">PC 최근 20저장일 하락 구간</span>
          <span className="v" data-testid="hre-risk-total">
            <strong>{s.inBand}종목</strong> · 보유 평가 비중 <strong>{fmtShare(s.inBandShare)}</strong>
            {s.evalPartial && s.inBandShare !== null ? (
              <span className="muted"> ({PARTIAL_EVAL_TEXT})</span>
            ) : null}
          </span>
        </div>
        <div className="hre-risk-stat">
          <span className="k">자료 확인 필요</span>
          <span className="v" data-testid="hre-risk-need">
            <strong>{needCheck}종목</strong>
          </span>
        </div>
        <div className="hre-risk-stat">
          <span className="k">가격 기준일</span>
          <span className="v" data-testid="hre-risk-date">
            <strong>{s.flowDate ?? "확인 불가"}</strong>
          </span>
          <span className="s">{PRICE_DATE_NOTE}</span>
        </div>
      </div>
      <div className="hre-risk-bands">
        {s.bands.map((b) => (
          <span key={b.state} className="hre-risk-band" data-testid={`hre-risk-band-${b.state}`}>
            <span className="nm">{DECLINE_SHORT[b.state]}</span> {b.count}종목 · {fmtShare(b.share)}
          </span>
        ))}
      </div>
      <div className="hre-risk-aux" data-testid="hre-risk-scope">
        <span>보유 저장 시각 {fmtKstDate(holdingsAsof)}</span>
        {showMarket ? (
          <span>
            {MARKET_ASOF_LABEL} {fmtKstDate(marketAsof)}
          </span>
        ) : null}
        <span>
          계산 가능 {calcOk}/{calcTotal}종목
        </span>
        <span>시장 국면 {v.regime ?? "확인 불가"}</span>
        <span>
          구간 판정 가능 {s.judgeable}/{s.total}종목
          {combo.partial ? ` · ${PARTIAL_JUDGE_TEXT}` : ""}
        </span>
        <span>PC 저장 종가 기준</span>
      </div>
    </div>
  );
}
