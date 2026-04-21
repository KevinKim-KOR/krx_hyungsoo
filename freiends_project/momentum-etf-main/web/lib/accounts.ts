import fs from "node:fs/promises";
import path from "node:path";

type AccountConfig = {
  account_id: string;
  order: number;
  name: string;
  icon: string;
  country_code: string;
  currency: string;
};

const ACCOUNT_DIR_PATTERN = /^(?<order>\d+)_(?<account>[a-z0-9_]+)$/;

async function getAccountsRoot(): Promise<string> {
  const candidates = [
    path.join(process.cwd(), "zaccounts"),
    path.join(process.cwd(), "..", "zaccounts"),
  ];

  for (const candidate of candidates) {
    try {
      // 개발(`web/`)과 Docker(`/app`)를 모두 지원하기 위해 실제 존재 경로를 우선 사용한다.
      await fs.access(candidate);
      return candidate;
    } catch {
      continue;
    }
  }

  throw new Error("zaccounts 디렉터리를 찾을 수 없습니다.");
}

export async function loadAccountConfigs(): Promise<AccountConfig[]> {
  const accountsRoot = await getAccountsRoot();
  const entries = await fs.readdir(accountsRoot, { withFileTypes: true });
  const configs: AccountConfig[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".") || entry.name.startsWith("_")) {
      continue;
    }

    const match = ACCOUNT_DIR_PATTERN.exec(entry.name);
    if (!match?.groups) {
      continue;
    }

    const configPath = path.join(accountsRoot, entry.name, "config.json");
    const raw = await fs.readFile(configPath, "utf-8");
    const parsed = JSON.parse(raw) as Record<string, unknown>;

    configs.push({
      account_id: match.groups.account,
      order: Number(match.groups.order),
      name: String(parsed.name ?? match.groups.account),
      icon: String(parsed.icon ?? ""),
      country_code: String(parsed.country_code ?? "").trim().toLowerCase(),
      currency: String(parsed.currency ?? "").trim().toUpperCase(),
    });
  }

  configs.sort((left, right) => left.order - right.order);
  return configs;
}

export type { AccountConfig };
