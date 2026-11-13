// POC6-27 — [AI용 시장 정보 복사] 글(설계 §6 고정 프롬프트 + 현재 화면의 시장 근거 · 판정 §4).
//
// 화면이 이미 받은 값(시장 판정 응답 · 시장 흐름 응답의 구조 칸 · 최신성 판정)만 쓴다 — 다시 조회 · 새 계산 없음.
// 빠진 값은 '확인 불가', 늦거나 기준 확인이 필요한 자료는 [자료 상태] 줄에 남긴다(계속을 고른 경우 포함).
// 사건은 전체를 남긴다(화면의 '최근 2건 · 외 N건'과 달리 · 판정 §2).
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import type { TodayBasis } from "@/lib/morningText";
import { storedRowText } from "@/lib/refreshCompare";
import type { FreshRow } from "@/lib/todayFreshness";
import { freshnessLine } from "@/lib/todayFreshness";
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
  signedPct,
  withUnit,
  wonAbs,
} from "@/lib/todayMarketLines";

// 설계 §6 고정 프롬프트(글자 그대로 · 2번의 기간만 설계자 지시 2026-11-14 로 '20거래일·60거래일·6개월' → '1개월·3개월·6개월' —
// 복사문의 코스피 기간 수익률이 화면 요약 칸과 같은 1 · 3 · 6개월 저장값이 됨 · POC6-29-1 결과서 §5).
export const TODAY_MARKET_PROMPT = `아래 시장 자료를 읽고, 한국 ETF를 검토하기 전에 내가 무엇을 알아야 하는지 쉬운 한국어로 설명해 주세요.

1. 시장 상태를 한 문장으로 써 주세요. KODEX 200 시장 판정과 코스피 가격 관측의 기준을 각각 밝혀 주세요.
2. 코스피의 최근 가격 움직임과 1개월·3개월·6개월 흐름을 줄을 나눠 써 주세요. 주어진 값과 실제 비교 기간을 사용해 주세요.
3. 외국인 누적 순매도와 최근 매도 속도 변화를 구분해 주세요. 가격과 수급이 다른 방향을 보이면 그 차이를 설명해 주세요.
4. 원/달러·WTI나 최근 사건 중 위 내용을 이해하는 데 도움이 되는 관측이 있으면 별도 줄에 추가해 주세요.
5. 마지막에 다음에 확인할 점을 한 줄 써 주세요.

붙인 자료의 범위에서 관측과 해석을 구분해 주세요. 각 값의 기준일을 사용하고 빠진 값은 확인 불가로 써 주세요. 추세·원인·향후 방향에 대한 해석은 근거와 한계를 밝혀 주세요. 매매 판단에 사용할 수 있는 확인 사항까지 제시해 주세요.

[아래에 복사한 시장 자료]`;

const NA = "확인 불가";

// 시장 판정 응답은 직접 읽지 않는다 — 판정 줄은 `verdict`(화면과 같은 선택) · 코스피 기간은 시장 흐름 응답(2026-11-14 ·
// 예전 '[코스피 기간 수익률] 20 · 60거래일'이 시장 판정 응답을 읽던 유일한 줄이었다) · 늦은 자료는 `fresh`.
export function buildTodayMarketCopyText({
  flow,
  fresh,
  verdict,
}: {
  flow: MarketFlowContext | null;
  fresh: FreshRow[];
  // 설계자 RESULT 재판정 V3 §3(2026-11-13) — 시장 판정 줄은 화면 당일 상자 · 표와 같은 선택 결과(todayBasis) ·
  // 그 결과의 기준일 · 저장 상태(같은 한 번 읽기의 끝 행 · 없으면 '저장 시점 확인 필요') · 미확인이면 화면과 같은 사유.
  verdict: TodayBasis;
}): string {
  const L: string[] = [];
  const tc = verdict.ctx;
  const streak = tc?.regime_streak?.streak_days;
  L.push(
    tc
      ? `[시장 판정] KODEX 200 ${tc.regime_label ?? NA}` +
          (streak != null ? ` · ${streak}거래일째${tc.regime_streak?.at_least ? " 이상" : ""}` : " · 지속일 확인 불가") +
          ` · ${verdict.date ?? NA}` +
          ` · ${verdict.row ? storedRowText(verdict.row) : "저장 시점 확인 필요"}`
      : `[시장 판정] ${verdict.missing ?? NA}`,
  );

  const obs = kospiObs(flow);
  L.push(
    obs
      ? `[코스피 최신 종가] ${num2(obs.value)} · ${obs.date}` +
          (obs.d1
            ? ` · ${obs.d1.from_date} 대비 ${obs.d1.diff >= 0 ? "+" : "-"}${num2(Math.abs(obs.d1.diff))}pt(${signedPct(obs.d1.pct)})`
            : "")
      : `[코스피 최신 종가] ${NA}`,
  );

  // 설계자 지시(2026-11-14 · POC6-29-1 결과서 §5) — 화면 요약 칸(코스피 1 · 3 · 6개월)과 같은 시장 흐름 응답의 저장값 · 같은 기간.
  // 예전 '[코스피 기간 수익률] 20 · 60거래일'(시장 판정 응답 · 기준일이 기대 직전 거래일이 아니면 '확인 불가')은 뺐다.
  for (const [key, label] of [
    ["1M", "1개월"],
    ["3M", "3개월"],
    ["6M", "6개월"],
  ] as const) {
    const k = flow?.periods?.[key]?.kospi ?? null;
    L.push(
      k
        ? `[코스피 ${label}] ${signedPct(k.pct)} · ${md(k.from_date)} ${num2(k.from)} → ${md(k.to_date)} ${num2(k.to)}` +
            (key === "6M" ? ` · 가격과 수급의 공통 비교 종료일 ${flow?.D ? md(flow.D) : NA}` : "")
        : `[코스피 ${label}] ${NA}`,
    );
  }

  const fv = foreignView(flow);
  L.push(
    fv.six
      ? `[외국인 6개월] 누적 ${netWord(fv.six.sum)} ${wonAbs(fv.six.sum)} · ${md(fv.six.end)}까지 ${fv.six.days}/${fv.six.expected}일` +
          (fv.six.partial ? "(부분 집계)" : "")
      : `[외국인 6개월] ${NA}`,
  );
  L.push(
    fv.recent && fv.previous
      ? `[외국인 매도 속도] 직전 20거래일 ${wonAbs(fv.previous.sum)} ${netWord(fv.previous.sum)}` +
          (fv.previous.avg != null ? `(일평균 ${wonAbs(fv.previous.avg)})` : "") +
          ` → 최근 20거래일 ${wonAbs(fv.recent.sum)} ${netWord(fv.recent.sum)}` +
          (fv.recent.avg != null ? `(일평균 ${wonAbs(fv.recent.avg)})` : "") +
          ` · ${md(fv.recent.to)}까지` +
          (fv.trend ? ` · ${fv.trend}` : "")
      : `[외국인 매도 속도] ${NA}`,
  );
  const r60 = flow?.windows?.r60 ?? null;
  if (r60) {
    const part = (k: "foreign" | "individual" | "institution", label: string) => {
      const w = r60[k];
      return w ? `${label} ${w.sum < 0 ? "-" : "+"}${wonAbs(w.sum)}` : `${label} ${NA}`;
    };
    const to = r60.foreign?.to ?? null;
    L.push(
      `[60거래일 수급] ${part("foreign", "외국인")} · ${part("individual", "개인")} · ${part("institution", "기관계")}` +
        (to ? ` · ${md(to)}까지` : ""),
    );
  } else {
    L.push(`[60거래일 수급] ${NA}`);
  }

  const low = lowSentence(obs);
  if (obs && low) {
    const mark = obs.range?.dir === "위" ? "[최근 고점]" : "[최근 저점]";
    L.push(`${mark} ${obs.date} 종가 ${num2(obs.value)} · ${low.replace(/\.$/, "")}(직전 20개 저장 종가 기준)`);
  }

  const fx = priceObs(flow, "usdkrw");
  L.push(fx ? `[원/달러] ${withUnit(fx.value, fx.unit)} · ${fx.date}` : `[원/달러] ${NA}`);
  const oil = priceObs(flow, "wti");
  L.push(
    oil
      ? `[WTI] ${withUnit(oil.value, oil.unit)}` + (oil.d1 ? `(${signedPct(oil.d1.pct)})` : "") + ` · ${oil.date}`
      : `[WTI] ${NA}`,
  );

  if (flow) {
    const events = flow.events ?? [];
    if (events.length === 0) {
      L.push(`[최근 큰 변화] ${flow.event_check?.empty_text ?? "없음"}`);
    } else if (hasStructuredEvents(flow)) {
      events.forEach((e, i) => L.push(`[최근 큰 변화 ${i + 1}] ${eventSentence(e)}`));
    } else {
      events.forEach((e, i) => L.push(`[최근 큰 변화 ${i + 1}] ${e.text} (괄호 안 = 비교 기준값)`));
    }
    if (flow.event_check?.unchecked_text) L.push(`[최근 큰 변화 확인 범위] ${flow.event_check.unchecked_text}`);
  } else {
    L.push(`[최근 큰 변화] ${NA}`);
  }

  const today = flow?.freshness?.today_kst ?? null;
  const bad = fresh.filter((r) => r.state !== "fresh");
  L.push(
    bad.length === 0
      ? `[자료 상태] ${today ? `${today} 확인 · ` : ""}확인한 자료 모두 기대 기준일 기준 최신`
      : `[자료 상태] ${today ? `${today} 확인 · ` : ""}` + bad.map((r) => `${r.label} ${freshnessLine(r)}`).join(" / ") + " · 지연 원인 확인 전",
  );
  if (flow?.end_basis?.text) L.push(`[공통 비교 기간] ${flow.end_basis.text}`);

  return `${TODAY_MARKET_PROMPT}\n${L.join("\n")}\n`;
}
