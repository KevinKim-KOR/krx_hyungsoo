"use client";
// POC5-13 — 「확인 근거」 목록 위 요약(시장 국면 · PC 최근 20저장일 하락 구간 · 판정 범위).
import { DECLINE_SHORT, PARTIAL_EVAL_TEXT, fmtShare, type DeclineSummary } from "./declineSummary";

export default function DeclineSummaryBlock({ s }: { s: DeclineSummary }) {
  return (
    <div className="hre-risk" data-testid="hre-risk-summary">
      <div className="hre-risk-row">
        <span className="k">시장 국면</span>
        <span className="v">
          <strong>{s.regime ?? "확인 불가"}</strong>
        </span>
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
      <div className="hre-risk-row">
        <span className="k">판정 범위</span>
        <span className="v" data-testid="hre-risk-scope">
          구간 판정 가능 {s.judgeable}/{s.total}종목
          {s.flowDate ? <span className="muted"> · PC 가격 흐름 기준일 {s.flowDate}</span> : null}
        </span>
      </div>
      <p className="helper hre-risk-note">
        PC 저장 종가 기준 · OCI 알림과 값이 다를 수 있음. 20저장일 변화(최근 저장 종가 21개)를 소수 첫째 자리로 반올림한 뒤
        −5% · −8% · −10% 경계로 나눕니다(OCI 보유 알림과 같은 경계 · 표의 5일 · 20일 값은 소수 둘째 자리 그대로).
        종목마다 실제 기간은 상세에서 확인합니다. 시장 국면이 각 종목 하락의 원인이라는 뜻은 아닙니다.
      </p>
    </div>
  );
}
