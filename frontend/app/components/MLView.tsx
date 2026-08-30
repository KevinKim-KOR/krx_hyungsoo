"use client";

// ML 실험 (ml) — 2026-08-16 사용자 직접 지시로 신설.
//
// 배경: ML 관련 카드가 세 화면에 흩어져 있었다.
//   - DataStatusView(진단·상태)   : MLEvidenceRefreshCard · MLFeatureSanityCard · MLBaselineV0Card
//   - ETFExposureView(비교·판단)  : MLTimeseriesReadinessCard
//   - MarketDiscoveryView(비교·판단): RelativeUpsideRunCard
// 판단하러 들어간 화면(비교·판단)에 ML 실험 카드가 붙어 있어 화면이 무거웠다.
// 성격이 같은 것끼리 한 메뉴로 모은다. 카드 내용·동작·API 는 건드리지 않는다.
//
// 2026-08-29 POC3-ML-02 REJECT Closeout:
//   `relative_upside_v0` 이 REJECT 판정을 받아 판단 화면에서 소비하지 않는다.
//   실행 성공 후 "요즘 잘 오르는 ETF 로 이동" 안내를 **제거**했다 — 연구용 실행에서
//   판단 화면으로 유도하면 "연구용" 표기가 무력해진다. 이 화면은 연구용 baseline
//   재현 경로로만 남는다. 자동 실행·스케줄러·후보 화면 연결은 두지 않는다.
//   (결과·오류 상태는 이 화면이 보유 — 카드 remount 와 무관하게 유지. 2026-06-21 회귀 수정 유지.)

import { useState } from "react";
import MLEvidenceRefreshCard from "./MLEvidenceRefreshCard";
import MLFeatureSanityCard from "./MLFeatureSanityCard";
import MLBaselineV0Card from "./MLBaselineV0Card";
import MLTimeseriesReadinessCard from "./MLTimeseriesReadinessCard";
import RelativeUpsideRunCard from "./RelativeUpsideRunCard";
import type { RelativeUpsideRunResult } from "@/lib/api/mlRelativeUpside";

export default function MLView() {
  const [relativeUpsideResult, setRelativeUpsideResult] =
    useState<RelativeUpsideRunResult | null>(null);
  const [relativeUpsideErrorMessage, setRelativeUpsideErrorMessage] = useState<
    string | null
  >(null);

  return (
    <section aria-labelledby="ml-h">
      <h1 id="ml-h">ML 실험</h1>
      <p className="subtitle">
        학습 자료 상태와 baseline·참고점수를 모아 둔 화면입니다. 투자 판단 자체는
        비교·판단 화면에서 하고, 여기서는 ML 자료가 쓸 만한 상태인지만 확인합니다.
      </p>

      <MLTimeseriesReadinessCard />
      <MLFeatureSanityCard />
      <MLEvidenceRefreshCard />
      <MLBaselineV0Card />

      <RelativeUpsideRunCard
        result={relativeUpsideResult}
        errorMessage={relativeUpsideErrorMessage}
        onResult={(res) => {
          setRelativeUpsideResult(res);
          setRelativeUpsideErrorMessage(null);
        }}
        onError={(msg) => setRelativeUpsideErrorMessage(msg)}
      />
    </section>
  );
}
