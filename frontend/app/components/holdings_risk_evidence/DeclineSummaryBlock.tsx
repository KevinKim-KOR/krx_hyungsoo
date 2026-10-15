"use client";
// POC5-13 · POC5-15 — 「확인 근거」 목록 위 요약(PLAN 판정 §3 · §4).
// 현재 상태 + ? / 하락 구간 종목 수 · 비중 / 구간별 / 작은 보조 묶음(시장 국면 · 판정 범위 ·
// PC 가격 흐름 기준일 · PC 저장 종가 기준). 정의 · 산식 · PC 와 OCI 차이는 ? 도움말로 옮겼다.
import { DECLINE_SHORT, PARTIAL_EVAL_TEXT, fmtShare } from "./declineSummary";
import HelpPopover from "./HelpPopover";
import { PARTIAL_JUDGE_TEXT, riskHelpParagraphs, type RiskStateView } from "./riskCombination";

export default function DeclineSummaryBlock({ v }: { v: RiskStateView }) {
  const s = v.summary;
  if (!s) return null;
  const combo = v.combo;
  return (
    <div className="hre-risk" data-testid="hre-risk-summary">
      <div className="hre-risk-head" data-testid="hre-risk-state">
        <span className="k">현재 상태</span>
        <strong className="hre-risk-headline">{combo.text}</strong>
        <HelpPopover label="현재 상태" paragraphs={riskHelpParagraphs(v)} />
      </div>
      <div className="hre-risk-row">
        <span className="k">PC 최근 20저장일 하락 구간</span>
        <span className="v" data-testid="hre-risk-total">
          <strong>{s.inBand}종목</strong> · 보유 평가 비중 <strong>{fmtShare(s.inBandShare)}</strong>
          {s.evalPartial && s.inBandShare !== null ? (
            <span className="muted"> ({PARTIAL_EVAL_TEXT})</span>
          ) : null}
        </span>
      </div>
      <div className="hre-risk-bands">
        {s.bands.map((b) => (
          <span key={b.state} className="hre-risk-band" data-testid={`hre-risk-band-${b.state}`}>
            <span className="nm">{DECLINE_SHORT[b.state]}</span> {b.count}종목 · {fmtShare(b.share)}
          </span>
        ))}
      </div>
      <div className="hre-risk-aux" data-testid="hre-risk-scope">
        <span>시장 국면 {v.regime ?? "확인 불가"}</span>
        <span>
          구간 판정 가능 {s.judgeable}/{s.total}종목
          {combo.partial ? ` · ${PARTIAL_JUDGE_TEXT}` : ""}
        </span>
        {s.flowDate ? <span>PC 가격 흐름 기준일 {s.flowDate}</span> : null}
        <span>PC 저장 종가 기준</span>
      </div>
    </div>
  );
}
