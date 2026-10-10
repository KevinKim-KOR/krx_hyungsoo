"use client";

// POC5-06 설계 개정 2 §5 · §10-3 — 재진입 검토 창 '3. ML 검토'(이후 20거래일 최저 종가 변화 · 연구 추정).
// [ML 검토 실행]을 누를 때만 POST 1회(창을 연 것만으로는 학습하지 않는다). 결과 = 추정값 · 단순 기준 ·
// 과거 검증 오차를 나란히 + 비교 문구 · 구간 표 · 한계. 자료 부족 · 가격 기준 불명 · 축 불확실이면
// 추정값을 보이지 않는다. 저장일이 기대 완료일보다 이르면 추정값 옆에 '이 날짜 기준 검토'(설계 §2).
// 신뢰구간 · 확률 · 성공률은 표시하지 않는다. 매수/매도 지시가 아니다.

import { useRef, useState } from "react";
import { runReentryMl, type ReentryMlResponse } from "@/lib/api";
import { apiErrorText } from "./format";

const REASON_LABEL: Record<string, string> = {
  MISSING_PRICE: "연구 축 날짜의 저장 종가 없음",
  SOURCE_NOT_ALLOWED: "허용 밖 가격 출처",
  BAD_CLOSE: "유한한 양수가 아닌 종가",
  CHANGE_MISSING: "change 누락(연속성 확인 불가)",
  SOURCE_RESWITCH: "FinanceDataReader → NAVER_FDR 재전환",
  BASIS_BREAK: "가격 기준 변화(계단)",
};

function signedPct(v: number): string {
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}%`;
}

function pp(v: number | undefined): string {
  return v === undefined ? "—" : v.toFixed(2);
}

function Result({ r }: { r: ReentryMlResponse }) {
  const res = r.result;
  const ok = r.status === "OK" && res.final && res.overall;
  const excluded = Object.entries(res.samples?.excluded_by_reason ?? {});
  return (
    <div aria-live="polite">
      {ok ? (
        <>
          <div className="hmx-rv-estimate">
            <div className="hmx-rv-metric">
              <div className="hmx-rv-lbl">
                추정값(기준일 {r.t})
                {r.stale ? (
                  <>
                    {" "}
                    <span
                      className="hmx-tag hmx-tag-warn"
                      title={`기대 완료일 ${r.expected_completed_date ?? "—"}`}
                    >
                      {r.stale_note ?? "이 날짜 기준 검토"}
                    </span>
                  </>
                ) : null}
              </div>
              <div className="hmx-rv-val hmx-rv-big">{signedPct(res.final!.estimate_pct)}</div>
            </div>
            <div className="hmx-rv-metric">
              <div className="hmx-rv-lbl">단순 기준(학습 중앙값)</div>
              <div className="hmx-rv-val hmx-rv-big">{signedPct(res.final!.baseline_median_pct)}</div>
            </div>
            <div className="hmx-rv-metric">
              <div className="hmx-rv-lbl">과거 검증 오차 MAE(모델 / 기준)</div>
              <div className="hmx-rv-val hmx-rv-big">
                {pp(res.overall!.mae_model_pp)} / {pp(res.overall!.mae_baseline_pp)}%p
              </div>
            </div>
          </div>
          <div className={res.overall!.verdict === "WORSE" ? "hmx-info hmx-rv-warn" : "hmx-info"}>
            {res.overall!.verdict_text} · 연구 추정 · 투자 유효성 미확정 · 이 값은 매수/매도 지시가 아닙니다.
          </div>
        </>
      ) : (
        <div className="hmx-info hmx-rv-warn" style={{ marginTop: 0 }}>
          {r.status_text}
          {r.reason ? ` — ${r.reason}` : ""}
        </div>
      )}
      {res.blocks && res.blocks.length > 0 ? (
        <>
          <div className="hmx-rv-sub">과거 검증(63일 × 3구간 · 같은 날짜로 모델과 기준 비교)</div>
          <div className="hmx-tbl-wrap">
            <table className="hmx-tbl">
              <thead>
                <tr>
                  <th>구간</th>
                  <th>기간</th>
                  <th className="hmx-r">학습 표본</th>
                  <th className="hmx-r">유효 검증 / 63</th>
                  <th className="hmx-r">MAE 모델</th>
                  <th className="hmx-r">MAE 기준</th>
                </tr>
              </thead>
              <tbody>
                {res.blocks.map((b) => (
                  <tr key={b.block}>
                    <td>{b.block}</td>
                    <td>
                      {b.first_date} ~ {b.last_date}
                    </td>
                    <td className="hmx-r">{b.train_n.toLocaleString("ko-KR")}</td>
                    <td className="hmx-r">{b.valid_n}</td>
                    <td className="hmx-r">{b.status === "OK" ? pp(b.mae_model_pp) : "자료 부족"}</td>
                    <td className="hmx-r">{b.status === "OK" ? pp(b.mae_baseline_pp) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      <ul className="hmx-rv-limits">
        {res.samples ? (
          <li>
            학습 표본 {res.samples.valid_n.toLocaleString("ko-KR")}
            {excluded.length > 0
              ? ` · 제외 ${excluded.map(([k, n]) => `${REASON_LABEL[k] ?? k} ${n}`).join(" · ")}`
              : " · 제외 0"}
          </li>
        ) : null}
        {r.axis ? (
          <li>
            {r.axis.label}(연도 파일 없는 해의 건너뛴 평일 {r.axis.skipped_weekday_count}일) — {r.axis.limit_note}
          </li>
        ) : null}
        <li>{r.partial_check_note}</li>
        <li>가격: {r.price_basis_label}</li>
        {r.notes.slice(1, 4).map((n) => (
          <li key={n}>{n}</li>
        ))}
        <li className="hmx-rv-path">연구 산출물: {r.artifact.folder}</li>
      </ul>
    </div>
  );
}

interface Props {
  positionId: string;
  cycleId: string;
  available: boolean;
  targetName: string;
}

export default function ReentryMlPanel({ positionId, cycleId, available, targetName }: Props) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ReentryMlResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reqNo = useRef(0);

  const run = async () => {
    const no = ++reqNo.current;
    setRunning(true);
    setError(null);
    try {
      const r = await runReentryMl(positionId, cycleId);
      if (no === reqNo.current) setResult(r);
    } catch (e) {
      if (no === reqNo.current) {
        setResult(null); // 실패를 직전 결과로 바꾸지 않는다
        setError(apiErrorText(e));
      }
    } finally {
      if (no === reqNo.current) setRunning(false);
    }
  };

  return (
    <section className="hmx-rv-part" aria-labelledby="rv-p3">
      <h4 id="rv-p3">
        <span className="hmx-rv-n">3</span>ML 검토 — {targetName}
      </h4>
      {!available ? (
        <p className="muted hmx-small" style={{ margin: 0 }}>
          ML 대상이 아닙니다(ETF 만 · 저장 가격이 있어야 합니다). 내 거래 · 저장된 근거는 그대로 볼 수
          있습니다.
        </p>
      ) : (
        <>
          <p className="muted hmx-small" style={{ margin: "0 0 8px" }}>
            선택 ETF 하나로 고정 모델(Ridge)을 한 번 학습해, 기준일 종가 대비 이후 20거래일 중 가장 낮은
            종가 변화를 추정하고 단순 기준(학습 기간 중앙값)과 과거 검증 오차를 비교합니다.
          </p>
          <button type="button" className="hmx-btn-sm" onClick={() => void run()} disabled={running}>
            {running ? "계산 중…" : result ? "ML 검토 다시 실행" : "ML 검토 실행"}
          </button>
          {error ? (
            <div className="hmx-error" role="alert">
              {error}
            </div>
          ) : null}
          {result ? (
            <div style={{ marginTop: 10 }}>
              <Result r={result} />
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
