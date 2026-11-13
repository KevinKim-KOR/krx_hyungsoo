"use client";

// POC6-29 보완 2차(판정서 V2 §2 · S 판정 §1 · PLAN §10-3 ③ · 형수님 결정 2026-11-12) — 근거 표.
// 열 = 자료 · 최근 값 · 변화 · 단기 흐름 · 기준일 · 상태 [?]. 출처 · 받은 시각 · 비교 시작 · 끝일은 [?] 안에만.
// - 수급(외국인 · 기관계 · 개인) = 끝일 하루 · 기존 20 · 60거래일 창(기간 표시) · 5거래일 합(GET /market/short-flows).
// - VIX = 값 · 전일 · 5거래일 전 대비(기존 시장 위험 참고 값) / 원/달러 · WTI = 값 · 직전 · 5회 전 대비(기존 단기 관측 칸).
// 기준일 · 늦음 = 아침 기준 응답(같은 판단 · Q-S4). 새 계산 없음.
import type { MarketRiskVix } from "@/lib/api";
import type { FlowPriceObs, MarketFlowContext } from "@/lib/api/marketFlow";
import type { MorningBasisResponse, MorningItem } from "@/lib/api/morningBasis";
import type { ShortFlowInvestor, ShortFlowsResponse } from "@/lib/api/shortFlows";
import { kstMdHm } from "@/lib/marketNowText";
import { investorOf, itemOf, shortFlowText } from "@/lib/morningText";
import { foreignView, md, netWord, num2, priceObs, signedPct, withUnit, wonAbs } from "@/lib/todayMarketLines";
import { vixFreshnessNotice } from "@/lib/vixFreshness";
import SourceHint from "./SourceHint";

interface Row {
  key: string;
  name: string;
  latest: string;
  change: string;
  short: string;
  date: string;
  state: { text: string; warn: boolean };
  src: string | null;
}

function stateOf(it: MorningItem | null): { text: string; warn: boolean } {
  if (!it) return { text: "확인 중", warn: false };
  if (it.state === "fresh") return { text: "최신", warn: false };
  if (it.state === "late") return { text: `${it.behind ?? "?"}거래일 늦음`, warn: true };
  if (it.state === "observed") return { text: "관측일", warn: false };
  if (it.state === "one_weekday_behind" || it.state === "update_check") {
    return { text: `${it.behind ?? "?"}평일 늦음`, warn: true };
  }
  return { text: "기준 확인 필요", warn: true };
}

function signed(diff: number, unit: string): string {
  return `${diff > 0 ? "+" : diff < 0 ? "-" : ""}${withUnit(Math.abs(diff), unit)}`;
}

function windowText(i: ShortFlowInvestor | null): string {
  if (!i?.recent5) return "";
  return ` · 5거래일 ${md(i.recent5.from)} ~ ${md(i.recent5.to)}${i.previous5 ? ` · 직전 ${md(i.previous5.from)} ~ ${md(i.previous5.to)}` : ""}`;
}

function flowRows(fd: MarketFlowContext | null, sf: ShortFlowsResponse | null, it: MorningItem | null): Row[] {
  const fv = foreignView(fd);
  const r60 = fd?.windows?.r60 ?? null;
  const base = `OCI 수집 → PC 반영 ${kstMdHm(it?.received_at ?? null)}`;
  return (["foreign", "institution", "individual"] as const).map((key) => {
    const inv = investorOf(sf, key);
    const name = key === "foreign" ? "외국인" : key === "institution" ? "기관계" : "개인";
    let change = "확인 불가";
    if (key === "foreign" && fv.recent && fv.recent.avg != null) {
      const r = fv.recent;
      const p = fv.previous && fv.previous.avg != null ? fv.previous : null;
      // 두 구간 방향이 다르면 구간마다 방향과 함께(검토 정정 F2 · 기존 규칙)
      const pair = p
        ? netWord(p.avg!) === netWord(r.avg!)
          ? `일평균 ${netWord(r.avg!)} ${wonAbs(p.avg!)} → ${wonAbs(r.avg!)}`
          : `일평균 ${netWord(p.avg!)} ${wonAbs(p.avg!)} → ${netWord(r.avg!)} ${wonAbs(r.avg!)}`
        : `일평균 ${wonAbs(r.avg!)} ${netWord(r.avg!)}`;
      change =
        `${pair}(${p ? `직전 20거래일 ${md(p.from)} ~ ${md(p.to)} → ` : ""}최근 20거래일 ${md(r.from)} ~ ${md(r.to)})` +
        (fv.trend ? ` · ${fv.trend}` : "");
    } else if (key !== "foreign" && r60?.[key]) {
      const w = r60[key]!;
      change = `최근 60거래일(${md(w.from)} ~ ${md(w.to)}) ${wonAbs(w.sum)} ${netWord(w.sum)}`;
    }
    return {
      key,
      name,
      latest: inv?.last ? `${md(inv.last.date)} 하루 ${wonAbs(inv.last.value)} ${netWord(inv.last.value)}` : "확인 불가",
      change,
      short: shortFlowText(inv),
      date: sf?.end_date ? md(sf.end_date) : "확인 불가",
      state: stateOf(it),
      src: `${base}${windowText(inv)}`,
    };
  });
}

function vixRow(vix: MarketRiskVix | null, it: MorningItem | null): Row {
  if (!vix || vix.availability !== "available" || vix.close == null) {
    return { key: "vix", name: "VIX", latest: "확인 불가", change: "", short: "", date: "", state: stateOf(it), src: null };
  }
  const s = vix.recent_20d_series ?? [];
  const from = s.length >= 6 ? s[s.length - 6].date : null; // 서버 5거래일 변화와 같은 행(최근에서 다섯 번째 앞)
  const prev = s.length >= 2 ? s[s.length - 2].date : null; // 서버 전일 변화와 같은 행
  const notice = vixFreshnessNotice(vix);
  return {
    key: "vix",
    name: "VIX",
    latest: num2(vix.close),
    change: vix.change_1d_pct != null ? `직전${prev ? `(${md(prev)})` : ""} 대비 ${signedPct(vix.change_1d_pct)}` : "",
    short: vix.change_5d_pct != null ? `5거래일 전 대비 ${signedPct(vix.change_5d_pct)}` : "",
    date: `${md(vix.as_of_date)} 미국`,
    state: it?.state === "fresh" ? { text: "최신", warn: false } : notice ? { text: notice.text, warn: true } : stateOf(it),
    src: `FDR(미국 VIX) · ${kstMdHm(it?.received_at ?? null)} 받음${from ? ` · 5거래일 전 ${md(from)} → ${md(vix.as_of_date)}` : ""}`,
  };
}

function priceRow(key: "usdkrw" | "wti", o: FlowPriceObs | null, it: MorningItem | null): Row {
  const name = key === "usdkrw" ? "원/달러" : "WTI";
  const unit = key === "usdkrw" ? "원" : "달러";
  if (!o) return { key, name, latest: "확인 불가", change: "", short: "", date: "", state: stateOf(it), src: null };
  return {
    key,
    name,
    latest: withUnit(o.value, unit),
    change: o.d1 ? `직전(${md(o.d1.from_date)}) 대비 ${signed(o.d1.diff, unit)}(${signedPct(o.d1.pct)})` : "",
    short: o.d5 ? `5회 전 대비 ${signed(o.d5.diff, unit)}(${signedPct(o.d5.pct)})` : "",
    date: md(o.date),
    state: stateOf(it),
    src: `Yahoo · ${kstMdHm(it?.received_at ?? null)} 받음${o.d5 ? ` · 5회 전 ${md(o.d5.from_date)} → ${md(o.date)}` : ""}`,
  };
}

export default function MarketEvidenceTable({
  flow,
  short,
  morning,
  vix,
  vixAction,
}: {
  flow: MarketFlowContext | null;
  short: ShortFlowsResponse | null;
  morning: MorningBasisResponse | null;
  vix: MarketRiskVix | null;
  // [VIX 다시 받기](있을 때만 · VIX 줄 상태 칸에)
  vixAction: React.ReactNode;
}) {
  const rows: Row[] = [
    ...flowRows(flow, short, itemOf(morning, "flows")),
    vixRow(vix, itemOf(morning, "vix")),
    priceRow("usdkrw", priceObs(flow, "usdkrw"), itemOf(morning, "usdkrw")),
    priceRow("wti", priceObs(flow, "wti"), itemOf(morning, "wti")),
  ];
  return (
    <div className="ec-table-wrap">
      <table className="ec-table tc-ev-table" data-testid="tc-ev-table">
        <thead>
          <tr>
            <th scope="col">자료</th>
            <th scope="col">최근 값</th>
            <th scope="col">변화</th>
            <th scope="col">단기 흐름</th>
            <th scope="col">기준일 · 상태</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`tc-ev-${r.key}`} aria-label={r.name}>
              <th scope="row">{r.name}</th>
              <td>{r.latest}</td>
              <td>{r.change}</td>
              <td data-testid={`tc-ev-short-${r.key}`}>{r.short}</td>
              <td>
                {r.date}{" "}
                <span className={r.state.warn ? "tc-sum-badge tc-sum-warn" : "tc-muted tc-small"}>{r.state.text}</span>
                <SourceHint text={r.src} testId={`tc-src-${r.key}`} />
                {r.key === "vix" ? vixAction : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
