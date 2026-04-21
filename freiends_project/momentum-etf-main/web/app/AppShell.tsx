"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import {
  IconCash,
  IconFlask2,
  IconChevronDown,
  IconMoodSmile,
  IconHome,
  IconMedal2,
  IconList,
  IconListDetails,
  IconMenu2,
  IconNotebook,
  IconReceipt2,
  IconSettings,
  IconTrendingUp,
  IconActivity,
  IconX,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
} from "@tabler/icons-react";

import { parseFearGreedSummary } from "@/lib/fear-greed";
import { GlobalTickerSearch } from "./components/GlobalTickerSearch";

const homeItem = { href: "/", label: "홈", icon: IconHome };
const holdingsItem = { href: "/holdings", label: "보유종목", icon: IconActivity };

function isNavItemActive(itemHref: string, currentPathname: string | null): boolean {
  if (!currentPathname) return false;
  if (itemHref === currentPathname) return true;
  // /ticker → /ticker/XXX 같은 동적 라우트 매칭
  if (itemHref !== "/" && currentPathname.startsWith(itemHref + "/")) return true;
  return false;
}

const navGroups = [
  {
    id: "assets",
    title: "자산",
    icon: IconCash,
    items: [
      { href: "/assets", label: "자산 관리", icon: IconList },
      { href: "/weekly", label: "주별", icon: IconReceipt2 },
      { href: "/snapshots", label: "스냅샷", icon: IconReceipt2 },
    ],
  },
  {
    id: "momentum-etf",
    title: "ETF",
    icon: IconListDetails,
    items: [
      { href: "/stocks", label: "종목 관리", icon: IconMedal2 },
      { href: "/note", label: "계좌 메모", icon: IconNotebook },
      { href: "/backtest", label: "백테스트", icon: IconFlask2 },
    ],
  },
  {
    id: "info",
    title: "정보",
    icon: IconTrendingUp,
    items: [{ href: "/market", label: "ETF 마켓", icon: "🇰🇷" }],
  },
  {
    id: "system",
    title: "시스템",
    icon: IconSettings,
    items: [{ href: "/system", label: "정보", icon: IconSettings }],
  },
] as const;

type AppShellProps = {
  children: ReactNode;
};

type FxSummary = {
  USD?: { rate: number; change_pct: number };
  AUD?: { rate: number; change_pct: number };
  updated_at?: string | null;
};

type FearGreedSummary = {
  score: number | null;
  label: string | null;
  previous_close_score: number | null;
  updated_at?: string | null;
};

type VkospiSummary = {
  price: number;
  change_pct: number;
  updated_at?: string | null;
};

function formatRate(value: number | undefined): string {
  if (!value || Number.isNaN(value)) {
    return "-";
  }
  return `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value)}원`;
}

function formatChangePct(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "";
  }
  const sign = value > 0 ? "+" : "";
  return `(${sign}${value.toFixed(2)}%)`;
}

function getFxChangeClass(value: number | undefined): string | undefined {
  if (value === undefined || value === null || Number.isNaN(value) || value === 0) {
    return undefined;
  }
  return value < 0 ? "metricNegative" : "metricPositive";
}

function formatFearGreedScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(1);
}

function formatFearGreedLabel(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const normalized = value.trim();
  if (!normalized) {
    return "-";
  }

  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function formatFearGreedDelta(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "";
  }
  const sign = value > 0 ? "+" : "";
  return `(${sign}${value.toFixed(1)})`;
}

async function loadFearGreedSummary(): Promise<FearGreedSummary | null> {
  const apiResponse = await fetch("/api/fear-greed", { cache: "no-store" });
  if (apiResponse.ok) {
    return (await apiResponse.json()) as FearGreedSummary;
  }
  return null;
}

function getDefaultOpenGroups(pathname: string | null) {
  return Object.fromEntries(
    navGroups.map((group) => [group.id, true]),
  );
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [fx, setFx] = useState<FxSummary | null>(null);
  const [isFxLoading, setIsFxLoading] = useState(true);
  const [fearGreed, setFearGreed] = useState<FearGreedSummary | null>(null);
  const [isFearGreedLoading, setIsFearGreedLoading] = useState(true);
  const [vkospi, setVkospi] = useState<VkospiSummary | null>(null);
  const [isVkospiLoading, setIsVkospiLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => getDefaultOpenGroups(pathname));
  const [isDbError, setIsDbError] = useState(false);
  const isLoginPage = pathname === "/login";

  const loadTopBarData = useCallback(async () => {
    if (isLoginPage) {
      return;
    }

    try {
      setIsFxLoading(true);
      setIsFearGreedLoading(true);
      setIsVkospiLoading(true);

      const [fxResponse, fearGreedSummary, vkospiResponse] = await Promise.all([
        fetch("/api/fx", { cache: "no-store" }),
        loadFearGreedSummary().catch(() => null),
        fetch("/api/vkospi", { cache: "no-store" }).catch(() => null),
      ]);

      const payload = fxResponse.ok ? ((await fxResponse.json()) as FxSummary) : null;
      const vkospiPayload = vkospiResponse?.ok ? ((await vkospiResponse.json()) as VkospiSummary) : null;

      setFx(payload);
      setIsFxLoading(false);
      setFearGreed(fearGreedSummary);
      setIsFearGreedLoading(false);
      setVkospi(vkospiPayload);
      setIsVkospiLoading(false);
    } catch {
      setFx(null);
      setIsFxLoading(false);
      setFearGreed(null);
      setIsFearGreedLoading(false);
      setVkospi(null);
      setIsVkospiLoading(false);
    }
  }, [isLoginPage]);

  useEffect(() => {
    void loadTopBarData();

    function handlePageShow() {
      void loadTopBarData();
    }

    window.addEventListener("pageshow", handlePageShow);
    return () => {
      window.removeEventListener("pageshow", handlePageShow);
    };
  }, [loadTopBarData]);

  useEffect(() => {
    if (isLoginPage) return;

    const errorHandler = () => {
      setIsDbError(true);
    };

    window.addEventListener("db_error_occurred", errorHandler);

    return () => {
      window.removeEventListener("db_error_occurred", errorHandler);
    };
  }, [isLoginPage]);

  useEffect(() => {
    if (isLoginPage) return;

    async function checkHealth() {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        setIsDbError(!res.ok);
      } catch {
        setIsDbError(true);
      }
    }

    void checkHealth();
  }, [isLoginPage]);

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    setOpenGroups((current) => {
      const next = { ...current };
      for (const group of navGroups) {
        if (group.items.some((item) => isNavItemActive(item.href, pathname))) {
          next[group.id] = true;
        }
      }
      return next;
    });
  }, [pathname]);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  function toggleGroup(groupId: string) {
    setOpenGroups((current) => ({ ...current, [groupId]: !current[groupId] }));
  }

  if (isLoginPage) {
    return <div className="appContent loginAppContent">{children}</div>;
  }

  const HomeIcon = homeItem.icon;
  const HoldingsIcon = holdingsItem.icon;
  const fearGreedDelta =
    fearGreed?.score !== null &&
    fearGreed?.score !== undefined &&
    fearGreed.previous_close_score !== null &&
    fearGreed.previous_close_score !== undefined
      ? fearGreed.score - fearGreed.previous_close_score
      : null;

  const navList = (
    <div className="appSidebarNavGroups">
      <div className="navbar-nav appSidebarNav appSidebarNavRoot">
        <div className="nav-item appSidebarItem">
          <Link href={homeItem.href} className={pathname === homeItem.href ? "nav-link active" : "nav-link"}>
            <span className="appSidebarIcon" aria-hidden="true">
              <HomeIcon size={18} stroke={1.9} />
            </span>
            <span className="nav-link-title">{homeItem.label}</span>
          </Link>
        </div>
        <div className="nav-item appSidebarItem">
          <Link href={holdingsItem.href} className={pathname === holdingsItem.href ? "nav-link active" : "nav-link"}>
            <span className="appSidebarIcon" aria-hidden="true">
              <HoldingsIcon size={18} stroke={1.9} />
            </span>
            <span className="nav-link-title">{holdingsItem.label}</span>
          </Link>
        </div>
      </div>
      {navGroups.map((group) => {
        const isExpanded = openGroups[group.id] ?? false;
        const hasActiveChild = group.items.some((item) => isNavItemActive(item.href, pathname));
        const GroupIcon = group.icon;
        return (
          <div key={group.id} className="appSidebarGroup">
            <button
              type="button"
              className={`appSidebarGroupToggle ${hasActiveChild ? "is-active" : ""}`.trim()}
              aria-expanded={isExpanded}
              onClick={() => toggleGroup(group.id)}
            >
              <span className="appSidebarGroupLead">
                <span className="appSidebarIcon" aria-hidden="true">
                  <GroupIcon size={18} stroke={1.9} />
                </span>
                <span className="appSidebarGroupLabel">{group.title}</span>
              </span>
              <span className={`appSidebarChevron ${isExpanded ? "is-open" : ""}`.trim()} aria-hidden="true">
                <IconChevronDown size={16} stroke={1.9} />
              </span>
            </button>
            <div className={`navbar-nav appSidebarNav appSidebarSubnav ${isExpanded ? "is-open" : ""}`.trim()}>
              {group.items.map((item) => {
                const isActive = isNavItemActive(item.href, pathname);
                const Icon = item.icon;
                return (
                  <div key={item.href} className="nav-item appSidebarItem">
                    <Link href={item.href} className={isActive ? "nav-link active" : "nav-link"}>
                      <span className="appSidebarIcon" aria-hidden="true">
                        {typeof Icon === "string" ? (
                          <span className="appSidebarEmojiIcon">{Icon}</span>
                        ) : (
                          <Icon size={18} stroke={1.9} />
                        )}
                      </span>
                      <span className="nav-link-title">{item.label}</span>
                    </Link>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className={`appLayout ${isSidebarCollapsed ? "appLayoutSidebarCollapsed" : ""}`.trim()}>
      <aside className="navbar navbar-vertical navbar-expand-lg appSidebar appSidebarDesktop">
        <div className="container-fluid appSidebarInner">
          <Link href="/" className="navbar-brand navbar-brand-autodark appSidebarBrand">
            Jason 투자
          </Link>
          {navList}
          <div className="appSidebarFooter">
            <button className="btn btn-outline-light btn-sm w-100" type="button" onClick={handleLogout}>
              로그아웃
            </button>
          </div>
        </div>
      </aside>
      <div className="appMain">
        <header className="navbar d-print-none appTopHeader">
          <div className="container-fluid appTopHeaderInner">
            <div className="appHeaderLeft">
              <button
                className="btn btn-icon btn-sm appSidebarDesktopToggle"
                type="button"
                aria-label={isSidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"}
                onClick={() => setIsSidebarCollapsed((current) => !current)}
              >
                {isSidebarCollapsed ? (
                  <IconLayoutSidebarLeftExpand size={18} stroke={1.9} />
                ) : (
                  <IconLayoutSidebarLeftCollapse size={18} stroke={1.9} />
                )}
              </button>
            </div>
            <div className="appMobileHeader">
              <button
                className="btn btn-icon btn-sm appSidebarToggle"
                type="button"
                aria-label={sidebarOpen ? "메뉴 닫기" : "메뉴 열기"}
                onClick={() => setSidebarOpen((current) => !current)}
              >
                {sidebarOpen ? <IconX size={18} stroke={1.9} /> : <IconMenu2 size={18} stroke={1.9} />}
              </button>
              <Link href="/" className="appMobileBrand">
                Jason 투자
              </Link>
            </div>
            <div className="topbarFx">
              {isDbError && (
                <span className="topbarFxItem" style={{ color: "#e03131", fontWeight: 600, background: "#ffe3e3", padding: "2px 8px", borderRadius: "4px" }}>
                  ⚠️ 몽고디비 이슈
                </span>
              )}
              <span className="topbarFxItem topbarTickerSearchItem">
                <GlobalTickerSearch />
              </span>
              <span className="topbarFxItem">
                USD/KRW:{" "}
                {isFxLoading ? (
                  <span className="topbarFxLoading" aria-label="환율 로딩 중">
                    <span className="topbarSpinner" />
                  </span>
                ) : (
                  <>
                    <strong>{formatRate(fx?.USD?.rate)}</strong>
                    <span className={getFxChangeClass(fx?.USD?.change_pct)}>
                      {formatChangePct(fx?.USD?.change_pct)}
                    </span>
                  </>
                )}
              </span>
              <span className="topbarFxItem">
                AUD/KRW:{" "}
                {isFxLoading ? (
                  <span className="topbarFxLoading" aria-label="환율 로딩 중">
                    <span className="topbarSpinner" />
                  </span>
                ) : (
                  <>
                    <strong>{formatRate(fx?.AUD?.rate)}</strong>
                    <span className={getFxChangeClass(fx?.AUD?.change_pct)}>
                      {formatChangePct(fx?.AUD?.change_pct)}
                    </span>
                  </>
                )}
              </span>
              <span className="topbarFxItem topbarSentimentItem">
                {isFearGreedLoading ? (
                  <>
                    <span className="topbarSentimentLabel">
                      <IconMoodSmile size={15} stroke={1.9} />
                      CNN:
                    </span>
                    <span className="topbarFxLoading" aria-label="CNN 공포탐욕지수 로딩 중">
                      <span className="topbarSpinner" />
                    </span>
                  </>
                ) : (
                  <a
                    href="https://fear-and-greed.jason.ai.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "inherit", textDecoration: "none", display: "flex", alignItems: "center", gap: "4px" }}
                  >
                    <span className="topbarSentimentLabel">
                      <IconMoodSmile size={15} stroke={1.9} />
                      CNN:
                    </span>
                    {fearGreed?.score != null ? (
                      <span className="topbarSentimentValue">
                        <strong>{formatFearGreedScore(fearGreed?.score)}</strong>
                        <span className="topbarSentimentText">({formatFearGreedLabel(fearGreed?.label)})</span>
                        {fearGreedDelta !== null ? (
                          <span className={getFxChangeClass(fearGreedDelta)}>
                            {formatFearGreedDelta(fearGreedDelta)}
                          </span>
                        ) : null}
                      </span>
                    ) : (
                      <strong>-</strong>
                    )}
                  </a>
                )}
              </span>
              <span className="topbarFxItem topbarSentimentItem">
                {isVkospiLoading ? (
                  <>
                    <span className="topbarSentimentLabel">
                      <IconActivity size={15} stroke={1.9} />
                      VKOSPI:
                    </span>
                    <span className="topbarFxLoading" aria-label="VKOSPI 로딩 중">
                      <span className="topbarSpinner" />
                    </span>
                  </>
                ) : (
                  <a
                    href="https://kr.investing.com/indices/kospi-volatility"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "inherit", textDecoration: "none", display: "flex", alignItems: "center", gap: "4px" }}
                  >
                    <span className="topbarSentimentLabel">
                      <IconActivity size={15} stroke={1.9} />
                      VKOSPI:
                    </span>
                    {vkospi?.price != null ? (
                      <span className="topbarSentimentValue">
                        <strong>{vkospi.price.toFixed(2)}</strong>
                        <span className={getFxChangeClass(vkospi.change_pct)}>
                          {formatChangePct(vkospi.change_pct)}
                        </span>
                      </span>
                    ) : (
                      <strong>-</strong>
                    )}
                  </a>
                )}
              </span>
            </div>
          </div>
        </header>
        <div className={`appMobileMenu ${sidebarOpen ? "is-open" : ""}`.trim()}>
          <div className="container-fluid appMobileMenuInner">
            {navList}
            <div className="appSidebarFooter appMobileMenuFooter">
              <button className="btn btn-outline-light btn-sm w-100" type="button" onClick={handleLogout}>
                로그아웃
              </button>
            </div>
          </div>
        </div>
        <div className="appBody">
          <div className="container-fluid appContent">{children}</div>
        </div>
      </div>
    </div>
  );
}
