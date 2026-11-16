"use client";

// 「ETF 구성종목」 / 구성종목 탭 (POC2 — 2026-05-27 · POC6-31 STEP 3).
//
// 책임:
// - draft 의 후보 ETF 목록 + [구성종목 수집].
// - POC6-31(판정 Q6 (b) · §1) — 수집은 서버 작업(POST /market/constituents/collect)이 필요한 ETF만 10개씩 받는다.
//   진행 따라가기는 탭이 바뀌어도 이어지도록 화면(ETFExposureView)이 useCandidateCollect 로 들고, 이 탭은 보여 주기만 한다.
//   상태는 이 목록으로 읽는다(GET .../collect/status?tickers=) — 같은 목록의 작업이 없으면 저장 기록으로 ETF별 상태
//   (서버를 다시 켜도 같은 상태 · 판정 §1 넷째). 다른 목록의 작업이 돌면 그 작업을 이 목록 결과로 쓰지 않는다.
//   읽기만으로 수집이 시작되지 않는다. 보유 구성종목 단계와 겹친 ETF는 서버가 한 번만 부른다.
// - GET /market/constituents/analysis → ETF별 실제 구성일 · 상위 구성종목 + 집중도.
//
// AI Sessions 로 넘기는 흐름은 별도 카드가 담당.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  CONSTITUENTS_TOP_K,
  type ConstituentItem,
  type ConstituentsAnalysisResponse,
} from "@/lib/api";
import {
  fetchConstituentsCollectStatus,
  postConstituentsCollect,
  type ConstituentsCollectJob,
} from "@/lib/api/constituentsStatus";
import { TARGET_RULE_TEXT, countsText, itemReason, unloggedText } from "@/lib/constituentsText";
import { md } from "@/lib/etfCompare";
import type { ETFExposureDraft } from "@/lib/etfExposureDraft";

const DASH = "-";
const POLL_MS = 1500;
const POLL_MAX = 240; // 6분 — 3묶음 · 묶음마다 30초 예산 + 요청 대기를 넉넉히 넘김

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(2)}%`;
}

// 구성일 표시(판정 §1 첫째) — 순위 끝날과 같으면 'M/D 기준 구성', 끝날보다 새면 '현재 편입 참고'.
export function asofLabel(c: ConstituentItem, listEnd: string | null | undefined): string {
  const base =
    listEnd && c.asof > listEnd ? `${md(c.asof)} 구성 · 현재 편입 참고` : `${md(c.asof)} 기준 구성`;
  return c.asof_confirmed === false ? `${base} · 원천 기준일 미확인` : base;
}

// 이 목록의 수집 상태 한 줄 — 진행 중 · 끝(이번 작업 결과) · 저장 기록 기준 상태(작업 없음).
export function collectLine(job: ConstituentsCollectJob): string {
  const target = job.target_date ? `목표일 ${md(job.target_date)}` : null;
  if (job.state === "running") {
    const head = job.batch_total
      ? `${job.batch_index ?? 0}/${job.batch_total} 묶음 받는 중 — 받을 ETF ${job.total ?? 0}개 중 ${job.done ?? 0}개 끝`
      : "구성종목 받는 중...";
    return target ? `${head} · ${target}` : head;
  }
  if (job.stored) {
    if (job.stored_status === "read_failed") return `구성 상태 — ${job.reason ?? "읽지 못했습니다"}`;
    const need = job.needs_check ?? 0;
    return `저장 기록 기준 상태${target ? `(${target})` : ""} — ${countsText(job.counts, job.total ?? job.items.length, {
      subject: "후보",
      statusMode: true,
    })}${need > 0 ? ` · 다시 확인 필요 ${need} — [구성종목 수집]으로 받습니다` : ""}`;
  }
  const tail = job.reason ? ` · ${job.reason}` : "";
  const unlogged = unloggedText(job.unlogged_logs);
  return `수집 끝 — ${target ? `${target} · ` : ""}${countsText(job.counts, job.total ?? job.items.length, {
    subject: "후보",
    calls: job.calls,
    shared: job.shared,
  })}${tail}${unlogged ? ` · ${unlogged}` : ""}`;
}

export interface CandidateCollect {
  job: ConstituentsCollectJob | null; // 이 목록의 상태(작업 또는 저장 기록)
  other: { total: number; done: number } | null; // 다른 목록의 작업이 도는 중
  error: string | null;
  running: boolean;
  start: () => void;
}

// 후보 수집 상태 따라가기(화면이 들고 탭은 보여 주기만) — 탭을 바꿔도 이어지고, 이 목록의 작업이 끝나면 onDone(분석 다시 읽기).
export function useCandidateCollect(tickers: string[], onDone: () => void): CandidateCollect {
  const [job, setJob] = useState<ConstituentsCollectJob | null>(null);
  const [other, setOther] = useState<{ total: number; done: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const ticks = useRef(0);
  const busy = useRef(false);
  const mine = useRef(false); // 이 목록의 작업을 따라가는 중(끝나면 onDone)
  const alive = useRef(true);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  const key = tickers.join(",");
  const tickersRef = useRef(tickers);
  tickersRef.current = tickers;
  // 검증자 r1 F4(같은 뿌리) — 상태 읽기 · 수집 시작 응답에 순번 · 가장 최근 요청의 응답만 반영(늦은 이전 응답이
  // 진행 중 작업을 '끝남'처럼 덮어 따라가기를 멈추지 않게).
  const reqSeq = useRef(0);
  const issue = () => {
    const my = ++reqSeq.current;
    return () => my === reqSeq.current;
  };

  const stop = useCallback(() => {
    if (timer.current !== null) clearInterval(timer.current);
    timer.current = null;
    ticks.current = 0;
  }, []);

  // 받은 상태 반영 — 더 따라갈지(true) 돌려준다.
  const apply = useCallback((j: ConstituentsCollectJob): boolean => {
    if (j.other_list) {
      // POST 가 다른 목록의 작업을 돌려줌 — 그 작업을 이 목록 결과로 쓰지 않는다.
      setOther({ total: j.total ?? 0, done: j.done ?? 0 });
      return true;
    }
    setJob(j);
    setOther(j.stored && j.other_job ? { total: j.other_job.total, done: j.other_job.done } : null);
    if (!j.stored && j.state === "running") {
      mine.current = true;
      return true;
    }
    if (mine.current) {
      mine.current = false;
      doneRef.current();
    }
    return !!(j.stored && j.other_job);
  }, []);

  const follow = useCallback(() => {
    stop();
    timer.current = setInterval(async () => {
      if (busy.current) return;
      ticks.current += 1;
      if (ticks.current > POLL_MAX) {
        stop();
        setError("상태 확인 시간이 너무 길어졌습니다. 잠시 뒤 이 화면을 다시 열면 이 목록의 상태를 다시 읽습니다.");
        return;
      }
      busy.current = true;
      const latest = issue();
      try {
        const j = await fetchConstituentsCollectStatus(tickersRef.current);
        if (!alive.current || !latest()) return;
        if (!apply(j)) stop();
      } catch (e) {
        if (!alive.current || !latest()) return;
        stop();
        setError(describeError(e));
      } finally {
        busy.current = false;
      }
    }, POLL_MS);
  }, [apply, stop]);

  // 목록이 정해지면(화면을 열 때) 이 목록의 상태를 한 번 읽는다 — 작업이 돌면 이어서 따라간다(읽기만).
  useEffect(() => {
    alive.current = true;
    if (!key) return;
    const latest = issue();
    fetchConstituentsCollectStatus(tickersRef.current)
      .then((j) => {
        if (alive.current && latest() && apply(j)) follow();
      })
      .catch((e) => {
        if (alive.current && latest()) setError(describeError(e));
      });
    return () => {
      alive.current = false;
      stop();
    };
  }, [key, apply, follow, stop]);

  const start = useCallback(async () => {
    setError(null);
    const latest = issue();
    try {
      const j = await postConstituentsCollect(tickersRef.current);
      if (!alive.current || !latest()) return;
      // 이 목록의 작업(돌고 있거나 바로 끝남)이면 끝날 때 분석을 다시 읽는다 · 다른 목록 작업이면 그 작업이 끝날 때까지 안내만.
      if (!j.other_list) mine.current = true;
      if (apply(j)) follow();
    } catch (e) {
      if (latest()) setError(describeError(e));
    }
  }, [apply, follow]);

  const running = !!job && !job.stored && job.state === "running";
  return { job, other, error, running, start: () => void start() };
}

// POC6-31 사용자 직접 지시(2026-11-16) — [구성종목 수집] 버튼은 화면 제목 줄(ETFExposureView 머리 · 형제 화면과 같은 중간 버튼),
// 수집 상태 줄은 탭과 상관없이 그 아래에 둔다. 탭 안의 예전 '후보 ETF 구성종목 수집' 카드는 없앴다.
export function CollectButton({ collect, count }: { collect: CandidateCollect; count: number }) {
  return (
    <button
      type="button"
      className="wb-btn btn-md"
      onClick={collect.start}
      disabled={collect.running || !!collect.other || count === 0}
      data-testid="cst-collect-btn"
    >
      {collect.running ? "수집 중..." : "구성종목 수집"}
    </button>
  );
}

export function CollectStatus({ collect }: { collect: CandidateCollect }) {
  const { job, other, error } = collect;
  return (
    <>
      {other ? (
        <div className="message info" data-testid="cst-other-list">
          다른 목록({other.total}개)을 받는 중({other.done}개 끝) — 끝난 뒤 이 목록의 [구성종목 수집]을 누르세요
        </div>
      ) : null}
      {job && (job.state !== "idle" || job.stored) ? (
        <div className="message info" data-testid="cst-collect-line">
          {collectLine(job)}
          {job.reason_detail ? (
            <details className="tc-small">
              <summary>자세히</summary>
              {job.reason_detail}
            </details>
          ) : null}
        </div>
      ) : null}
      {error ? <div className="message error">{error}</div> : null}
    </>
  );
}

// 수집 설명(상태 · 고른 후보 줄 아래 — 결론 → 버튼 → 설명 순서)
export function CollectHelp() {
  return (
    <p className="helper" style={{ margin: 0 }} data-testid="cst-collect-help">
      구성종목은 ETF마다 비중 상위 {CONSTITUENTS_TOP_K}개까지 받습니다(서버가 필요한 ETF만 10개씩 · 원천 기준일이 확인된
      목표일 이상 구성은 다시 부르지 않음) · {TARGET_RULE_TEXT}.
    </p>
  );
}

interface Props {
  // 2026-08-19 — 티커 → ETF 이름. 응답의 etf_name 은 네이버 구성종목 API 가 ETF
  // 자기 이름을 주지 않아 **저장 시점부터 전부 null** 이다(DB 실측). 그래서 화면이
  // 이미 들고 있는 draft 후보 스냅샷의 이름을 쓴다. 없으면 티커만 — 지어내지 않는다.
  nameByTicker?: Record<string, string>;
  draft: ETFExposureDraft;
  analysis: ConstituentsAnalysisResponse | null;
  collect: CandidateCollect;
  onPick?: (ticker: string, name: string | null) => void;
}

export default function ConstituentsTab({ draft, analysis, nameByTicker, collect, onPick }: Props) {
  const listEnd = draft.list_condition?.end ?? draft.asof;
  const itemByTicker = new Map((collect.job?.items ?? []).map((i) => [i.ticker, i]));

  return (
    <>
      {analysis ? (
        <div className="card">
          <h2>상위 구성종목</h2>
          <p className="helper" style={{ marginBottom: 8 }}>
            구성 자료 {analysis.coverage.available_count}/{analysis.coverage.requested_count} · ETF마다 실제
            구성일을 머리에 적습니다. 중복률은 이 표시 깊이와 무관하게 상위 {analysis.overlap_top_k}건 기준입니다.
          </p>
          {/* 2026-06-06 ETF Exposure Data Unfolding 1차 (지시문 §5.2 / AC-2) —
              구성종목 details 를 자동 펼침(open) 으로 표시. ETF별 종목이 한눈에
              비교 가능하도록 한다.
              2026-08-19 설계 확정 — **등락률 열 제거.** 값을 못 가져온 게 아니라
              연결한 적 없는 자리였고, 채우려면 개별주 시세 수집이라는 새 데이터
              계약이 필요하다. 항상 `unavailable` 인 열은 고장으로 읽히므로 열과
              안내문을 함께 뺀다(0%·ETF 등락률·추정값으로 대체하지 않는다).
              개별주 등락률 수집은 BACKLOG. */}
          {analysis.constituents.map((c: ConstituentItem) => (
            <details
              key={c.etf_ticker}
              className="card"
              style={{ marginBottom: 8 }}
              open
            >
              {/* 2026-08-19 사용자 지시 — 다른 화면 카드와 같은 줄 규칙으로 맞춘다.
                  이름 먼저(굵게) · 티커는 뒤에 작게 · 배지는 공용 `.wb-hb` 사용.
                  source(`naver_stock_etf_component`)는 화면에서 뺐다 — 내부 코드
                  문자열이고 현재 값이 한 종류뿐이다(펼친 안쪽 상단에 남긴다). */}
              <summary className="cst-summary">
                <b className="cst-name">
                  {c.etf_name ?? nameByTicker?.[c.etf_ticker] ?? c.etf_ticker}
                </b>
                <span className={`wb-hb ${c.status === "ok" ? "ok" : "mute"}`}>
                  {c.status === "ok" ? asofLabel(c, listEnd) : "구성 자료 없음"}
                </span>
                <code className="cst-tk">{c.etf_ticker}</code>
                {itemByTicker.get(c.etf_ticker) ? (
                  <span className="cst-cache">{itemByTicker.get(c.etf_ticker)?.label}</span>
                ) : null}
                {onPick && c.status === "ok" ? (
                  <button
                    type="button"
                    className="wb-btn btn-md"
                    onClick={(e) => {
                      e.preventDefault();
                      onPick(c.etf_ticker, nameByTicker?.[c.etf_ticker] ?? null);
                    }}
                  >
                    후보로 고르기
                  </button>
                ) : null}
              </summary>
              {c.status === "ok" ? (
                <>
                  {/* summary 줄에서 뺀 source 를 여기 남긴다 — 어디서 온 값인지는
                      필요할 때 확인할 수 있어야 한다. */}
                  <div className="cst-src">출처: 네이버 구성종목 · 구성일 {md(c.asof)}</div>
                  <ul className="dashboard-status-list" style={{ marginTop: 6 }}>
                    <li>Top 1 집중도: <strong>{fmtPct(c.concentration.top1_weight_pct)}</strong></li>
                    <li>Top 3 집중도: <strong>{fmtPct(c.concentration.top3_weight_pct)}</strong></li>
                    <li>Top 5 집중도: <strong>{fmtPct(c.concentration.top5_weight_pct)}</strong></li>
                    <li>Top 10 집중도: <strong>{fmtPct(c.concentration.top10_weight_pct)}</strong></li>
                  </ul>
                  <table className="market-topn-table">
                    <thead>
                      <tr>
                        <th style={{ width: 50 }}>순위</th>
                        <th style={{ width: 90 }}>티커</th>
                        <th>종목명</th>
                        <th style={{ width: 90, textAlign: "right" }}>비중</th>
                      </tr>
                    </thead>
                    <tbody>
                      {c.top_holdings.map((h) => {
                        // 2026-05-31 — Naver 통합. 해외형 종목 (ticker=null) 은
                        // reuters code 또는 ISIN 으로 식별 노출.
                        const displayId =
                          h.ticker ||
                          h.constituent_reuters_code ||
                          h.constituent_isin ||
                          null;
                        return (
                          <tr key={`${c.etf_ticker}-${h.rank}`}>
                            <td>{h.rank}</td>
                            <td>{displayId ? <code>{displayId}</code> : DASH}</td>
                            <td>{h.name ?? DASH}</td>
                            <td style={{ textAlign: "right" }}>
                              {fmtPct(h.weight_pct)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {/* 2026-08-19 설계 확정 표시 계약 — 확보된 건수만 적는다.
                      "전체 구성종목" 이라고 쓰지 않는다(ETF 전체는 더 많다).
                      비중이 없는 종목을 **0 으로 합산하지 않는다** — 그렇게 하면
                      표에는 `-` 인 값이 합계에서는 완성된 수치처럼 보인다
                      (검증자 P2). 값이 있는 것만 더하고, 빠진 개수를 밝힌다. */}
                  {(() => {
                    const known = c.top_holdings.filter(
                      (h) => h.weight_pct !== null && h.weight_pct !== undefined,
                    );
                    const missing = c.top_holdings.length - known.length;
                    const sum = known.reduce(
                      (acc, h) => acc + (h.weight_pct as number),
                      0,
                    );
                    return (
                      <p
                        className="helper"
                        style={{ marginTop: 4, fontSize: "0.78rem" }}
                      >
                        상위 {c.top_holdings.length}개 표시 · 표시 비중 합계{" "}
                        {known.length === 0 ? "확인 불가" : fmtPct(sum)}
                        {missing > 0 ? (
                          <span style={{ color: "var(--warn)" }}>
                            {" "}
                            (비중 미확인 {missing}개 제외)
                          </span>
                        ) : null}
                      </p>
                    );
                  })()}
                </>
              ) : (
                <div className="helper" style={{ marginTop: 6 }}>
                  구성 자료가 없습니다 — 위 [구성종목 수집]으로 받습니다.
                  {itemByTicker.get(c.etf_ticker) ? ` (${itemReason(itemByTicker.get(c.etf_ticker)!)})` : ""}
                </div>
              )}
            </details>
          ))}
        </div>
      ) : null}
    </>
  );
}
