"use client";

// POC6-31 STEP 4(PLAN C22 · C24 · 판정 Q12 · Q19 · 목업 M3) — 「종목별 근거」의 구성종목 비교(예전 '구성종목 겹침' 자리).
// 확인 범위를 수치보다 먼저 · 후보 주요 주식(원본 1 ~ 10행)마다 후보 비중 · 고른 보유 비중 · 내 보유 전체의 확인된 노출.
// 계산 입력은 같은 자리에서 펼쳐 읽는다(계산에 쓴 자릿수 그대로 · 금액 없음). 「보유」 화면의 '노출 확인'은 그대로.
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchPairExposure, pairExposureUrl, type PairExposure, type PairQuery } from "@/lib/api/pairExposure";
import {
  AFTER_ADD_TEXT,
  STATUS_TEXT,
  formulaText,
  heldText,
  pairCellText,
  pct2,
  rangeText,
  scopeLines,
  wtext,
} from "@/lib/pairExposureText";

const USE_TEXT: Record<string, string> = {
  sum: "합산",
  other_date: "다른 구성일(참고)",
  unconfirmed: "원천 기준일 미확인(빠짐)",
  no_data: "구성 자료 없음(빠짐)",
  no_weight: "시세 미확인(분모 밖)",
};
const RANGE_TEXT: Record<string, string> = {
  full: "원천 전체",
  depth: "30행까지(그 밖 미확인)",
  legacy: "예전 10행(그 밖 미확인)",
  unverified: "원천 전체 확인 기록 없음(그 밖 미확인)",
};

export type PairPhase =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error" }
  | { phase: "success"; data: PairExposure };

export default function PairExposureBlock({ q, hasPick }: { q: PairPhase; hasPick: boolean }) {
  if (!hasPick) {
    return (
      <div className="pe-block" data-testid="pe-block">
        <div className="ec-small">후보를 고르면 구성종목 비교를 봅니다.</div>
      </div>
    );
  }
  if (q.phase === "error") {
    return (
      <div className="pe-block" data-testid="pe-block">
        <div className="wb-warn" data-testid="pe-error">
          구성종목 비교를 읽지 못했습니다 — [다시 불러오기]를 누르세요.
        </div>
      </div>
    );
  }
  if (q.phase !== "success") {
    return (
      <div className="pe-block" data-testid="pe-block">
        <div className="ec-small">구성종목 비교 읽는 중...</div>
      </div>
    );
  }
  const p = q.data;
  if (p.status === "no_etf_list" || p.status === "no_holdings") {
    return (
      <div className="pe-block" data-testid="pe-block">
        <div className="wb-warn" data-testid="pe-status">
          {STATUS_TEXT[p.status]}
        </div>
      </div>
    );
  }
  const sc = scopeLines(p);
  // 보유를 못 읽거나 분모가 없어도 짝 칸(편입 비중)은 보인다 — 노출만 '비중 확인 불가'(검토 지적 frontend#2)
  const limited = p.status === "holdings_unreadable" || p.status === "no_weight_basis";
  return (
    <div className="pe-block" data-testid="pe-block">
      {limited ? (
        <div className="wb-warn" data-testid="pe-status">
          {STATUS_TEXT[p.status as "holdings_unreadable" | "no_weight_basis"]}
        </div>
      ) : null}
      <div className="pe-scope" data-testid="pe-scope">
        <div className="pe-scope-t">확인 범위(먼저 읽기)</div>
        {/* 기준일 줄 = 서버 글(미리보기 원문과 같음 · 검증자 STEP 4~5 r1 B-6) */}
        <div data-testid="pe-dates">{p.date_line}</div>
        {sc && !limited ? (
          <>
            <div data-testid="pe-included">{sc.included}</div>
            <div data-testid="pe-missing">{sc.missing}</div>
            <div className="ec-small" data-testid="pe-sum">
              {sc.sum}
            </div>
          </>
        ) : null}
        {p.scope ? (
          <details data-testid="pe-etfs">
            <summary>{rangeText(p)} — 보유 ETF별 펼쳐 보기</summary>
            <div className="wb-table-wrap">
              <table className="wb-table">
                <thead>
                  <tr>
                    <th>보유 ETF</th>
                    <th>평가 비중</th>
                    <th>구성일</th>
                    <th>저장 행</th>
                    <th>계산</th>
                  </tr>
                </thead>
                <tbody>
                  {(p.scope?.etfs ?? []).map((e) => (
                    <tr key={e.ticker}>
                      <td>{e.name ?? e.ticker}</td>
                      <td>{e.weight === null ? "미확인" : `${e.weight}%`}</td>
                      <td>{e.asof ?? "—"}</td>
                      <td>
                        {e.state === "no_data" ? "—" : `${e.stored_rows}행`}
                        {e.range ? ` · ${RANGE_TEXT[e.range]}` : ""}
                      </td>
                      <td>{USE_TEXT[e.use]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        ) : null}
      </div>
      {p.candidate.state !== "confirmed" ? (
        <div className="wb-warn" data-testid="pe-no-candidate">
          후보 구성:{" "}
          {p.candidate.state === "unconfirmed" ? `원천 기준일 미확인(${p.candidate.asof} 보존 자료)` : "구성 자료 없음"} —
          비교하지 않음(겹침 없음이라는 뜻 아님). 「ETF 구성종목」에서 [구성종목 수집] 뒤 다시 불러오세요.
        </div>
      ) : (
        <>
          <div className="wb-table-wrap">
            <table className="wb-table" data-testid="pe-table">
              <thead>
                <tr>
                  <th>후보 주요 주식(원본 1 ~ 10행)</th>
                  <th>후보 비중</th>
                  <th>고른 보유 비중</th>
                  <th>내 보유 전체의 확인된 노출</th>
                </tr>
              </thead>
              <tbody>
                {p.stocks.map((s) => (
                  <tr key={s.key}>
                    <td>{s.name}</td>
                    <td>{s.candidate_weight === null ? "—" : wtext(s.candidate_weight)}</td>
                    <td>{s.pair ? pairCellText(p, s.pair) : "고른 보유 없음"}</td>
                    <td>
                      {s.exposure && s.exposure.value === null ? (
                        // 확인한 부분이 하나도 없으면 0.00% 가 아니라 확인 불가(검증자 STEP 4~5 r1 F10)
                        <>
                          <b>확인 불가</b>
                          <span className="tc-muted"> · 확인한 구성 없음</span>
                        </>
                      ) : s.exposure ? (
                        <b>{pct2(s.exposure.value)}</b>
                      ) : (
                        "비중 확인 불가"
                      )}
                      {/* 합계에서 빠진 ETF 사유 = 서버 글(미리보기 원문과 같음 · 사유별 · 검증자 STEP 4~5 r2 F14) */}
                      {s.exposure && p.stock_notes?.[s.key] ? (
                        <span className="tc-muted" data-testid="pe-note">
                          {" "}
                          · {p.stock_notes[s.key]}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {p.stocks.length === 0 ? (
            <div className="ec-small">후보 상위 10행에 식별 가능한 주식이 없습니다(현금 · 채권 · 파생 · ETF · 종류 미확인 가림).</div>
          ) : p.candidate_non_stock_rows > 0 ? (
            <div className="ec-small">후보 상위 10행 중 주식이 아니거나 종류 미확인인 {p.candidate_non_stock_rows}행은 뺐습니다.</div>
          ) : null}
          <div className="ec-small">
            &apos;편입 비중 확인 불가&apos; = 편입은 저장돼 있으나 비중을 읽을 수 없어 합계에 넣지 않음 ·
            &apos;0(확인)&apos; = 원천이 준 전체 구성(30행 미만으로 다 받음)에 없음 · &apos;저장 범위에서 미확인&apos; = 30행(또는 예전
            10행)까지만 받아 그 밖은 모름.
          </div>
          <RefLine p={p} />
          <div className="ec-small" data-testid="pe-held">
            {heldText(p)}
          </div>
          <details data-testid="pe-formula">
            <summary>계산 입력 펼쳐 보기</summary>
            <ul className="dashboard-status-list">
              {p.stocks.map((s) => (
                <li key={s.key}>{formulaText(s)}</li>
              ))}
            </ul>
            <div className="ec-small">
              계산에 쓴 자릿수 그대로 보입니다. 금액은 보이지 않습니다. 평가액이 일부만 확인되면 &apos;부분 평가액 기준&apos;,
              분모가 없으면 &apos;비중 확인 불가&apos;. 고른 보유가 개별 주식이면 &apos;이 주식 자체&apos;와 그 주식의 평가 비중을
              나눠 봅니다.
            </div>
          </details>
        </>
      )}
      {p.holding?.kind === "stock" ? (
        <div className="ec-small" data-testid="pe-holding-stock">
          고른 보유는 개별 주식입니다 — 전체 보유에서 차지하는 평가 비중 {p.holding.weight === null ? "미확인" : pct2(p.holding.weight)}
        </div>
      ) : null}
      <div className="ec-small">{AFTER_ADD_TEXT}</div>
    </div>
  );
}

function RefLine({ p }: { p: PairExposure }) {
  const refs = p.stocks.flatMap((s) => s.reference.map((r) => ({ s, r })));
  if (refs.length === 0) return null;
  return (
    <div className="ec-small" data-testid="pe-reference">
      다른 구성일 참고(합계에 넣지 않음):{" "}
      {refs
        .map(
          ({ s, r }) =>
            `${r.name ?? r.ticker} ${r.asof} — ${s.name} ${r.constituent_weight === null ? "비중 확인 불가" : wtext(r.constituent_weight)}`,
        )
        .join(" · ")}
    </div>
  );
}

// 비교 화면이 고른 후보 · 보유 · 조건으로 읽는다. 조건(주소)이 바뀌면 다시 읽고 늦은 응답은 버린다(요청 번호).
export function usePairExposure(q: PairQuery | null): PairPhase & { key: string; reload: () => void } {
  const key = q ? pairExposureUrl(q) : "";
  const [state, setState] = useState<{ key: string; s: PairPhase }>({ key: "", s: { phase: "idle" } });
  const seq = useRef(0);
  const qRef = useRef(q);
  qRef.current = q;
  const load = useCallback(() => {
    const cur = qRef.current;
    const id = ++seq.current;
    if (!cur) {
      setState({ key: "", s: { phase: "idle" } });
      return;
    }
    const k = pairExposureUrl(cur);
    setState({ key: k, s: { phase: "loading" } });
    fetchPairExposure(cur).then(
      (data) => {
        if (id === seq.current) setState({ key: k, s: { phase: "success", data } });
      },
      () => {
        if (id === seq.current) setState({ key: k, s: { phase: "error" } });
      },
    );
  }, []);
  useEffect(() => {
    load();
  }, [key, load]);
  // 지금 조건과 다른 주소의 결과는 '읽는 중'으로 본다(고른 종목을 바꾼 직후 예전 비교를 보이지 않음).
  const s: PairPhase = state.key === key ? state.s : key ? { phase: "loading" } : { phase: "idle" };
  return { ...s, key, reload: load };
}
