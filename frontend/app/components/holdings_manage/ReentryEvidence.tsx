"use client";

// POC5-06 설계 개정 2 §2 · §3 · §10-4 — 재진입 검토 창 '2. 저장된 근거'(읽기 표시 · 계산 0).
// 최근 가격 상태(기준일 feature 다섯 값) · 매도 뒤 가격 변화(05 시장 흐름 그대로) · 같은 종목 알림
// (원장 사본 · SUBJECT 기본 — 관측만 된 행은 건수 + 펼치기 · 사업군 대표 / 기초지수 묶음 구성은 '연관 근거'로
// 따로) · 이동 링크.
// 평가 칸 = 최신 평가 + 메모(화면에만 · 산출물에는 식별자 · helpfulness 만) + 건수.
// 가격 결과 · 사용자 평가는 나란히 보이고 '적중 / 실패'로 합치지 않는다. 평가 = 알림 전체 평가 ·
// 사용자 판단 근거로 먼저(설계 §3) · 계약 버전은 알림 칸에 보존.

import type {
  LedgerEvidence,
  LedgerEvidenceItem,
  MarketFlowResponse,
  ReentryFeatureName,
  ReentryPriceState,
} from "@/lib/api";
import {
  HORIZONS,
  NOT_TARGET,
  PUSH_KIND_LABEL,
  helpfulnessLabel,
  outcomeCell,
} from "../alert_records/format";
import { MarketFlowView } from "./MarketFlowPanel";
import { savedAt } from "./historyText";

export const FEATURE_LABELS: [ReentryFeatureName, string][] = [
  ["chg5", "5거래일 종가 변화"],
  ["chg20", "20거래일 종가 변화"],
  ["chg60", "60거래일 종가 변화"],
  ["vol20", "20일 변동성(일별)"],
  ["from_high60", "60일 최고 종가 대비"],
];

// 비율(0.0123) → "+1.23%" · 변동성은 부호 없이.
export function ratioPct(v: number, signed = true): string {
  const p = v * 100;
  const s = signed ? (p > 0 ? "+" : p < 0 ? "−" : "") : "";
  return `${s}${Math.abs(p).toFixed(2)}%`;
}

function PriceState({ ps }: { ps: ReentryPriceState }) {
  return (
    <>
      <div className="hmx-rv-sub" style={{ marginTop: 0 }}>
        최근 가격 상태 <span className="muted hmx-small">— {ps.price_basis_label ?? "저장 종가"}</span>
      </div>
      {ps.features ? (
        <div className="hmx-rv-metrics">
          {FEATURE_LABELS.map(([k, label]) => (
            <div className="hmx-rv-metric" key={k}>
              <div className="hmx-rv-lbl">{label}</div>
              <div className="hmx-rv-val">{ratioPct(ps.features![k], k !== "vol20")}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="hmx-info" style={{ marginTop: 0 }}>
          {ps.reason ?? "최근 가격 상태를 계산할 수 없습니다."}
        </div>
      )}
    </>
  );
}

function outcomeText(item: LedgerEvidenceItem): string {
  if (!item.outcome_target) return NOT_TARGET;
  return HORIZONS.map((h) => outcomeCell(item.outcomes.find((o) => o.horizon === h))).join(" / ");
}

function feedbackText(item: LedgerEvidenceItem): string {
  const fb = item.feedback.latest;
  if (!fb) return "—";
  const more = item.feedback.count > 1 ? ` 외 ${item.feedback.count - 1}건` : "";
  return `${helpfulnessLabel(fb.helpfulness)}${fb.memo ? ` · ${fb.memo}` : ""}${more}`;
}

// 한 알림(event)에 item 이 여럿이어도 알림 한 건으로 센다(설계 §10-4 — 중복 발송처럼 세지 않음).
function alertCount(items: LedgerEvidenceItem[]): string {
  const events = new Set(items.map((i) => i.event_id)).size;
  return events === items.length ? `${events}건` : `${events}건(항목 ${items.length}개)`;
}

function AlertTable({ items, related }: { items: LedgerEvidenceItem[]; related?: boolean }) {
  return (
    <div className="hmx-tbl-wrap">
      <table className="hmx-tbl">
        <thead>
          <tr>
            <th>시각</th>
            <th>알림</th>
            <th>내 평가(알림 전체)</th>
            {related ? <th>기록된 자격</th> : <th>상태</th>}
            <th>전달</th>
            <th>노출</th>
            <th>가격 결과 +1 / +5 / +20</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={`${it.event_id}:${it.item_seq}`}>
              <td>{savedAt(it.runtime_kst)}</td>
              <td>
                {PUSH_KIND_LABEL[it.push_kind] ?? it.push_kind}
                {it.contract_version ? (
                  <span className="muted hmx-small"> · {it.contract_version}</span>
                ) : null}
              </td>
              <td>{feedbackText(it)}</td>
              <td>{related ? it.link_text.replace("연관 근거 — ", "") : (it.state_label ?? "—")}</td>
              <td>{it.view_text}</td>
              <td>
                <span className={it.exposure === "NONE" ? "hmx-tag" : "hmx-tag hmx-tag-acc"}>
                  {it.exposure === "NONE" ? "노출 분류 없음" : it.exposure}
                </span>
              </td>
              <td>{outcomeText(it)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Ledger({ ev }: { ev: LedgerEvidence }) {
  const own = ev.items.filter((i) => i.link_kind === "SUBJECT");
  const ownShown = own.filter((i) => i.view !== "OBSERVED");
  const ownObserved = own.filter((i) => i.view === "OBSERVED"); // 관측만 = 건수 + 펼치기(PLAN §2-3)
  const related = ev.items.filter((i) => i.link_kind !== "SUBJECT");
  const synced = ev.synced_at ? ` · 마지막 동기화 ${savedAt(ev.synced_at)}` : "";
  return (
    <>
      <div className="hmx-rv-sub">
        같은 종목의 알림 <span className="muted hmx-small">(원장 사본{synced})</span>
      </div>
      {ev.status !== "OK" ? (
        <div className="hmx-info" style={{ marginTop: 0 }}>
          {ev.status_text ?? "원장 사본을 읽을 수 없습니다."} — 내 거래 · 가격 근거는 그대로 볼 수 있습니다.
        </div>
      ) : own.length === 0 ? (
        <p className="muted hmx-small" style={{ margin: 0 }}>
          원장 사본에 이 종목 알림이 없습니다.
        </p>
      ) : (
        <>
          {ownShown.length > 0 ? (
            <AlertTable items={ownShown} />
          ) : (
            <p className="muted hmx-small" style={{ margin: 0 }}>
              본문에 실린 이 종목 알림은 없습니다.
            </p>
          )}
          {ownObserved.length > 0 ? (
            <details style={{ marginTop: 8 }}>
              <summary className="hmx-small" style={{ cursor: "pointer" }}>
                관측만 된 알림(본문에 안 실림) {alertCount(ownObserved)}
              </summary>
              <AlertTable items={ownObserved} />
            </details>
          ) : null}
        </>
      )}
      {related.length > 0 ? (
        <details style={{ marginTop: 8 }}>
          <summary className="hmx-small" style={{ cursor: "pointer" }}>
            연관 근거 — 사업군 신호의 대표 ETF · 기초지수 묶음 구성 ETF 로 기록된 알림 {alertCount(related)}
          </summary>
          <AlertTable items={related} related />
        </details>
      ) : null}
      {ev.items.some((i) => i.feedback.latest) ? (
        <p className="muted hmx-small" style={{ margin: "6px 0 0" }}>
          평가는 알림 전체에 대한 평가입니다(종목별 평가 아님). 가격 결과와 평가를 합쳐 적중 · 실패로
          판정하지 않습니다.
        </p>
      ) : null}
    </>
  );
}

interface Props {
  priceState: ReentryPriceState;
  marketFlow: MarketFlowResponse;
  ledger: LedgerEvidence;
  navigation: { menu: string; label: string; note: string }[];
  onNavigate?: (menu: string) => void;
}

export default function ReentryEvidence({ priceState, marketFlow, ledger, navigation, onNavigate }: Props) {
  const hasFlow = marketFlow.events.length > 0 || marketFlow.holding_period !== null;
  return (
    <section className="hmx-rv-part" aria-labelledby="rv-p2">
      <h4 id="rv-p2">
        <span className="hmx-rv-n">2</span>저장된 근거
      </h4>
      <PriceState ps={priceState} />
      <div className="hmx-rv-sub">매도 뒤 · 보유 기간 가격 변화</div>
      {hasFlow ? (
        <div className="hmx-flow" style={{ marginTop: 0 }}>
          <MarketFlowView data={marketFlow} />
        </div>
      ) : (
        <p className="muted hmx-small" style={{ margin: 0 }}>
          이 기간에는 매매 기록이 없어 매도 뒤 변화가 없습니다.
        </p>
      )}
      <Ledger ev={ledger} />
      <div className="hmx-row-actions" style={{ marginTop: 10, flexWrap: "wrap" }}>
        {navigation.map((n) => (
          <button
            key={n.menu}
            type="button"
            className="hmx-btn-sm hmx-ghost"
            title={n.note}
            onClick={() => onNavigate?.(n.menu)}
            disabled={!onNavigate}
          >
            {n.label} ↗
          </button>
        ))}
      </div>
      <p className="muted hmx-small" style={{ margin: "6px 0 0" }}>
        {navigation.map((n) => n.note).join(" / ")}. 검토 창은 이 동작을 자동으로 실행하지 않습니다.
      </p>
    </section>
  );
}
