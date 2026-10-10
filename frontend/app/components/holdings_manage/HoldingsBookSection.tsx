"use client";

// POC5-05 개정 2 §2 — 「종목 관리」 보유 표(읽기 표시) · 매매 입력 · History · 과거 보유 연결.
// 보유 줄(또는 [매매])을 누르면 그 종목 · 계좌가 고정된 매매 입력 창이 열리고, 저장하면 수량 ·
// 평단과 History 가 함께 바뀐다. 수량 · 평단을 직접 고치는 일은 부모의 '입력 정정' 모드에서 한다.
// 수익률 열 = 「보유 현황」과 같은 /holdings/enriched 값(줄별 연결 · 새 시세 조회 없음 · Q-C).
// History · 시장 흐름은 누를 때만 조회한다(열기만으로 외부 조회 · ML 없음). POC5-06: History 기간의
// [재진입 검토] → 검토 창이 History 자리를 대신하고 '← History' 로 돌아온다(창 위에 창 없음).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchEnrichedHoldings,
  fetchTradeHistory,
  type EnrichedHolding,
  type HoldingCycleView,
  type HoldingItem,
  type HoldingsFileStatus,
  type PositionHistory,
  type TradeEventView,
} from "@/lib/api";
import { invalidateQueries } from "@/lib/api/queryCache";
import { HOLDINGS_INVALIDATION_KEYS } from "@/lib/api/dashboardKeys";
import { fmtNum, fmtSignedPct, pnlClass } from "./format";
import TradeDialog from "./TradeDialog";
import NewHoldingDialog from "./NewHoldingDialog";
import HistoryDialog from "./HistoryDialog";
import ReentryReviewDialog from "./ReentryReviewDialog";
import type { MenuKey } from "../LeftSidebar";
import ClosedHoldings from "./ClosedHoldings";

const ACCOUNT_ORDER = ["일반", "ISA", "연금", "오픈뱅킹", "기타"];

function sortForView(items: HoldingItem[]): HoldingItem[] {
  const rank = (a: string) => {
    const i = ACCOUNT_ORDER.indexOf(a);
    return i === -1 ? ACCOUNT_ORDER.length : i;
  };
  return [...items].sort((x, y) => {
    const ax = x.account_group ?? "일반";
    const ay = y.account_group ?? "일반";
    if (rank(ax) !== rank(ay)) return rank(ax) - rank(ay);
    if (ax !== ay) return ax.localeCompare(ay, "ko");
    return (x.name || x.ticker).localeCompare(y.name || y.ticker, "ko");
  });
}

type CorrectTarget = {
  recordId: string;
  kind: "BUY" | "SELL";
  tradeDate: string;
  tradeTime: string | null;
  price: string;
  quantity: string;
  memo: string | null;
};

type Open =
  | {
      kind: "trade";
      holding: HoldingItem;
      initialKind?: "buy" | "sell" | "sell_all";
      correct?: CorrectTarget | null;
      eventDates?: string[]; // 정정이면 그 기록이 속한 기간의 날짜들
    }
  | { kind: "new"; rebuy?: PositionHistory | null }
  | { kind: "history"; positionId: string }
  | { kind: "review"; positionId: string; cycleId: string }
  | null;

interface Props {
  holdings: HoldingItem[]; // GET /holdings 순서(= /holdings/enriched 의 source_index 순서)
  revision: number;
  status: HoldingsFileStatus;
  busy: boolean;
  reloadKey: number;
  onEdit: () => void;
  onChanged: () => void; // 저장 · 창 닫기 뒤 부모가 보유 · 적용 상태를 다시 읽는다
  onNavigate?: (key: MenuKey) => void; // 재진입 검토 창의 이동 링크(가격 갱신 · 원장 새로고침 화면)
}

export default function HoldingsBookSection({
  holdings,
  revision,
  status,
  busy,
  reloadKey,
  onEdit,
  onChanged,
  onNavigate,
}: Props) {
  const [open, setOpen] = useState<Open>(null);
  const [positions, setPositions] = useState<PositionHistory[]>([]);
  const [priceByPos, setPriceByPos] = useState<Record<string, EnrichedHolding>>({});

  useEffect(() => {
    let alive = true;
    fetchTradeHistory()
      .then((h) => alive && setPositions(h.positions))
      .catch(() => alive && setPositions([]));
    fetchEnrichedHoldings()
      .then((r) => {
        if (!alive) return;
        const map: Record<string, EnrichedHolding> = {};
        r.items.forEach((it, i) => {
          const pid = holdings[it.source_index ?? i]?.position_id;
          if (pid) map[pid] = it;
        });
        setPriceByPos(map);
      })
      .catch(() => alive && setPriceByPos({}));
    return () => {
      alive = false;
    };
  }, [reloadKey, holdings]);

  const rows = useMemo(() => sortForView(holdings), [holdings]);
  // 과거 보유 = 끝난 보유 기간이 있는 줄(매매가 모두 취소돼 기간이 없는 줄은 목록에 넣지 않는다).
  const closed = positions.filter((p) => !p.is_open && p.cycles.length > 0);
  const accountOptions = useMemo(() => {
    // 계좌는 목록에서만 고른다(POC3-08 (D)) — 추천값 + 현재 · 과거 보유의 계좌.
    const s = new Set<string>(ACCOUNT_ORDER);
    holdings.forEach((h) => h.account_group && s.add(h.account_group));
    positions.forEach((p) => p.account_group && s.add(p.account_group));
    return Array.from(s);
  }, [holdings, positions]);

  const close = useCallback(() => {
    setOpen(null);
    onChanged();
  }, [onChanged]);

  // 매매 · 정정 · 취소 저장 성공 = 보유가 바뀌었다 → 다른 화면의 보유 · 근거 읽기 캐시도 비운다
  //   (입력 정정 저장과 같은 HOLDINGS_INVALIDATION_KEYS · 실패 때는 비우지 않는다).
  const changed = useCallback(() => {
    for (const k of HOLDINGS_INVALIDATION_KEYS) invalidateQueries(k);
    onChanged();
  }, [onChanged]);
  const saved = useCallback(() => {
    setOpen(null);
    changed();
  }, [changed]);

  // 현재 기간의 정확한 잔량(서버 십진 문자열) — 전량매도는 이 값을 보낸다.
  const exactQuantityOf = (h: HoldingItem): string | null => {
    const pos = positions.find((p) => p.position_id === h.position_id);
    return pos?.cycles.find((c) => c.cycle_id === h.cycle_id)?.quantity ?? null;
  };

  const eventDatesOf = (h: HoldingItem): string[] => {
    const pos = positions.find((p) => p.position_id === h.position_id);
    const cy = pos?.cycles.find((c) => c.cycle_id === h.cycle_id);
    return (cy?.events ?? []).map((e) => e.date).filter((d): d is string => !!d);
  };

  const onCorrect = (pos: PositionHistory, cy: HoldingCycleView, ev: TradeEventView) => {
    const h: HoldingItem = holdings.find((x) => x.position_id === pos.position_id) ?? {
      ticker: pos.ticker,
      name: pos.name,
      account_group: pos.account_group,
      position_id: pos.position_id,
      cycle_id: cy.cycle_id,
      quantity: Number(cy.quantity),
      avg_buy_price: Number(cy.avg_buy_price ?? 0),
    };
    const p = ev.payload as Record<string, string | null>;
    setOpen({
      kind: "trade",
      holding: h,
      eventDates: cy.events.map((e) => e.date).filter((d): d is string => !!d),
      correct: {
        recordId: ev.record_id,
        kind: ev.kind === "SELL" ? "SELL" : "BUY",
        tradeDate: String(p.trade_date),
        tradeTime: p.trade_time ?? null,
        price: String(p.price),
        quantity: String(p.quantity),
        memo: p.memo ?? null,
      },
    });
  };

  const price = (pid?: string | null) => (pid ? priceByPos[pid] : undefined);

  return (
    <div className="card">
      <div className="hmx-cycle-head">
        <h2 style={{ margin: 0 }}>1. 보유 종목</h2>
        <div className="hmx-row-actions">
          <button type="button" className="hmx-btn-sm" onClick={() => setOpen({ kind: "new" })} disabled={busy}>
            새 보유 추가
          </button>
          <button type="button" className="hmx-btn-sm hmx-ghost" onClick={onEdit} disabled={busy}>
            입력 정정
          </button>
        </div>
      </div>
      <p className="helper">
        보유 줄을 누르면 그 종목의 매매(추가매수 · 분할매도 · 전량매도)를 입력합니다. 저장하면 수량 ·
        평단과 History 가 함께 바뀝니다. 수량 · 평단을 직접 고치는 일은 &lsquo;입력 정정&rsquo;에서
        합니다(매매가 아닌 정정으로 기록).
      </p>
      {rows.length === 0 ? (
        <div className="helper" style={{ padding: "12px 0" }}>
          {status === "NO_FILE"
            ? "아직 저장된 보유가 없습니다 — [새 보유 추가]로 시작하세요."
            : "현재 보유 없음(전량매도) — 지난 보유는 아래 '과거 보유'에서 볼 수 있습니다."}
        </div>
      ) : (
        <div className="hmx-tbl-wrap">
          <table className="hmx-tbl">
            <thead>
              <tr>
                <th>종목</th>
                <th>계좌</th>
                <th className="hmx-r">수량</th>
                <th className="hmx-r">평단</th>
                <th className="hmx-r">매입금액</th>
                <th className="hmx-r">수익률</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => {
                const pr = price(h.position_id);
                const rate = pr?.pnl_rate_pct ?? null;
                return (
                  <tr
                    key={h.position_id ?? `${h.ticker}-${h.account_group}`}
                    className="hmx-click"
                    tabIndex={0}
                    onClick={() => setOpen({ kind: "trade", holding: h })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setOpen({ kind: "trade", holding: h });
                      }
                    }}
                  >
                    <td>
                      {h.name || h.ticker} <span className="muted hmx-small">{h.ticker}</span>
                    </td>
                    <td>{h.account_group ?? "일반"}</td>
                    <td className="hmx-r">{fmtNum(h.quantity, 6)}</td>
                    <td className="hmx-r">{fmtNum(h.avg_buy_price)}</td>
                    <td className="hmx-r">{fmtNum(h.quantity * h.avg_buy_price, 0)}</td>
                    <td className={`hmx-r ${pnlClass(rate)}`}>{rate === null ? "—" : fmtSignedPct(rate)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="hmx-row-actions">
                        <button
                          type="button"
                          className="hmx-btn-sm hmx-ghost"
                          onClick={() => setOpen({ kind: "trade", holding: h })}
                        >
                          매매
                        </button>
                        <button
                          type="button"
                          className="hmx-btn-sm hmx-ghost"
                          onClick={() => h.position_id && setOpen({ kind: "history", positionId: h.position_id })}
                        >
                          History
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="muted hmx-small" style={{ margin: "8px 0 0" }}>
            {rows.length}종목 · 수익률은 「보유 현황」과 같은 현재가 기준 값(현재가 없으면 —)
          </p>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <ClosedHoldings
          positions={closed}
          onHistory={(pid) => setOpen({ kind: "history", positionId: pid })}
          onRebuy={(p) => setOpen({ kind: "new", rebuy: p })}
        />
      </div>

      {open?.kind === "trade" ? (
        <TradeDialog
          holding={open.holding}
          revision={revision}
          initialKind={open.initialKind}
          eventDates={open.eventDates ?? eventDatesOf(open.holding)}
          exactQuantity={exactQuantityOf(open.holding)}
          correct={open.correct ?? null}
          onClose={close}
          onSaved={saved}
        />
      ) : null}
      {open?.kind === "new" ? (
        <NewHoldingDialog
          revision={revision}
          rebuy={
            open.rebuy
              ? {
                  position_id: open.rebuy.position_id,
                  ticker: open.rebuy.ticker,
                  name: open.rebuy.name,
                  account_group: open.rebuy.account_group,
                }
              : null
          }
          pastPositions={closed}
          accountOptions={accountOptions}
          onClose={close}
          onSaved={saved}
          onOpenHistory={(pid) => setOpen({ kind: "history", positionId: pid })}
        />
      ) : null}
      {open?.kind === "history" ? (
        <HistoryDialog
          positionId={open.positionId}
          priceInfo={(() => {
            const pr = price(open.positionId);
            return pr
              ? { current_price: pr.current_price, pnl_amount: pr.pnl_amount, pnl_rate_pct: pr.pnl_rate_pct }
              : null;
          })()}
          onClose={close}
          onRebuy={(p) => setOpen({ kind: "new", rebuy: p })}
          onCorrect={onCorrect}
          onChanged={changed}
          onReview={(cid) => setOpen({ kind: "review", positionId: open.positionId, cycleId: cid })}
        />
      ) : null}
      {open?.kind === "review" ? (
        <ReentryReviewDialog
          positionId={open.positionId}
          cycleId={open.cycleId}
          onBack={() => setOpen({ kind: "history", positionId: open.positionId })}
          onClose={close}
          onNavigate={onNavigate ? (menu) => onNavigate(menu as MenuKey) : undefined}
          onTrade={(p) => {
            const h = holdings.find((x) => x.position_id === p.position_id);
            setOpen(h ? { kind: "trade", holding: h } : { kind: "new", rebuy: p });
          }}
        />
      ) : null}
    </div>
  );
}
