"use client";
// POC5-19 — 「확인 근거」 종목 상세 기본 표시: 가격 흐름 / 거래량 / 가격 흔들림 세 묶음(개정 판정 §2 · 사용자 확정 목업).
// 받은 근거 응답 값 · 기존 문구만 쓴다(새 계산 · 조회 없음). 계산할 수 없는 항목은 그 묶음에 기존 사유를 보인다.
// 묶음마다 실제 기준일과 ? 하나. 기준일이 다른 자료는 기존 안내를 그대로 붙이고 한 시점 결론으로 묶지 않는다.
import type { HoldingsMarketEvidenceItem, PriceBasis } from "@/lib/api";
import { NO_VOLUME_TEXT, VOLUME_HELP, pastVolumeNote, volumeCells } from "@/lib/storedVolume";
import { directionColor } from "../workbench/helpers";
import HelpPopover from "./HelpPopover";
import { declineDetailText } from "./declineSummary";
import { bandShortText, pct, pctp } from "./evidenceStrip";
import type { RiskEvidenceRow } from "./helpers";
import { COMPARISON_TEXT, cellValue, hidesValues, volatilityHelp, volatilityNote } from "./priceVolatility";
import { HELP_BAND_BASIS } from "./riskCombination";
import { TREND_HELP_BASIS, trendLimits } from "./volumeTrend";

export const PRICE_HELP_MEANING =
  "5일 · 20일은 PC 저장 종가로 그만큼 앞선 저장일과 비교한 변화입니다. KODEX200 대비는 같은 기간 KODEX200 변화와의 차이(%p)입니다. 오르내림 예측이나 매매 의견이 아닙니다.";

export default function EvidenceGroups({
  row,
  item,
  basis,
}: {
  row: RiskEvidenceRow;
  item: HoldingsMarketEvidenceItem | null;
  basis: PriceBasis | null;
}) {
  const stale = row.price_dates?.comparison === "date_mismatch";
  const bandText = bandShortText(row, basis);
  const sv = item?.stored_volume;
  const vcells = sv && sv.status !== "no_price_data" ? volumeCells(sv) : null;
  const past = sv ? pastVolumeNote(sv, basis?.reference_date) : null;
  const pv = item?.price_volatility;
  const flowDate = basis?.reference_date ?? null;
  return (
    <div className="evg" data-testid="evidence-groups">
      <div className="evg-cell" data-testid="evg-price">
        <div className="evg-head">
          <span className="evg-title">가격 흐름</span>
          <HelpPopover label="가격 흐름" paragraphs={[PRICE_HELP_MEANING, HELP_BAND_BASIS]} />
        </div>
        {stale ? (
          <div className="evg-reason">{declineDetailText(row, basis)}</div>
        ) : (
          <div className="evg-grid">
            <span className="k">5일</span>
            <span className="v" style={{ color: directionColor(row.return_5d_pct) }}>
              {pct(row.return_5d_pct)}
            </span>
            <span className="k">20일</span>
            <span className="v" style={{ color: directionColor(row.return_20d_pct) }}>
              {pct(row.return_20d_pct)}
            </span>
            <span className="k">KODEX200 대비 20일</span>
            <span className="v" style={{ color: directionColor(row.excess_vs_kodex200_20d_pctp) }}>
              {pctp(row.excess_vs_kodex200_20d_pctp)}
            </span>
            <span className="k">하락 구간</span>
            <span className="v">{bandText}</span>
          </div>
        )}
        <div className="evg-foot">기준일 {row.price_dates?.end_date ?? "확인 불가"} · PC 저장 종가</div>
      </div>

      <div className="evg-cell" data-testid="evg-volume">
        <div className="evg-head">
          <span className="evg-title">거래량</span>
          <HelpPopover
            label="거래량"
            paragraphs={[VOLUME_HELP, TREND_HELP_BASIS, ...trendLimits(item?.volume_trend)]}
          />
        </div>
        {vcells ? (
          <div className="evg-grid">
            <span className="k">{vcells[1].label}</span>
            <span className="v">{vcells[1].value}</span>
            <span className="k">{vcells[3].label}</span>
            <span className="v">{vcells[3].value}</span>
            <span className="k">{vcells[2].label}</span>
            <span className="v">{vcells[2].value}</span>
            {past ? <span className="evg-wide evg-reason hre-status-check">{past}</span> : null}
          </div>
        ) : (
          <div className="evg-reason">{NO_VOLUME_TEXT}</div>
        )}
        <div className="evg-foot">기준일 {sv?.asof_date ?? "확인 불가"}</div>
      </div>

      <div className="evg-cell" data-testid="evg-volatility">
        <div className="evg-head">
          <span className="evg-title">가격 흔들림</span>
          {pv ? <HelpPopover label="가격 흔들림" paragraphs={volatilityHelp(pv)} /> : null}
        </div>
        {!pv ? (
          <div className="evg-reason">확인 불가</div>
        ) : hidesValues(pv) ? (
          <div className="evg-reason">{volatilityNote(pv, flowDate)}</div>
        ) : (
          <div className="evg-grid">
            <span className="k">최근 20구간</span>
            <span className="v">{cellValue(pv.recent, pv.recent_reason)}</span>
            <span className="k">직전 20구간</span>
            <span className="v">{cellValue(pv.previous, pv.previous_reason)}</span>
            <span
              className={pv.comparison ? "evg-wide v" : "evg-wide evg-reason"}
              data-testid="evg-volatility-cmp"
            >
              {pv.comparison ? COMPARISON_TEXT[pv.comparison] : volatilityNote(pv, flowDate)}
            </span>
          </div>
        )}
        <div className="evg-foot">기준일 {pv?.end_date ?? "확인 불가"}</div>
      </div>
    </div>
  );
}
