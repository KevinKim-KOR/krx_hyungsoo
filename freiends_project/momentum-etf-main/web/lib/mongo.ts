import fs from "node:fs";
import path from "node:path";
import { MongoClient } from "mongodb";

declare global {
  // eslint-disable-next-line no-var
  var __momentumMongoClientPromise: Promise<MongoClient> | undefined;
}

function readRootEnvValue(key: string): string | null {
  const envPath = path.join(process.cwd(), "..", ".env");
  if (!fs.existsSync(envPath)) {
    return null;
  }

  const raw = fs.readFileSync(envPath, "utf-8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const separatorIndex = trimmed.indexOf("=");
    if (separatorIndex <= 0) {
      continue;
    }
    const envKey = trimmed.slice(0, separatorIndex).trim();
    if (envKey !== key) {
      continue;
    }
    const envValue = trimmed.slice(separatorIndex + 1).trim();
    return envValue.replace(/^['"]|['"]$/g, "");
  }

  return null;
}

function resolveEnv(key: string): string {
  const fromProcess = process.env[key]?.trim();
  if (fromProcess) {
    return fromProcess;
  }
  const fromFile = readRootEnvValue(key)?.trim() ?? "";
  return fromFile;
}

function buildMongoUriFromParts(): string | null {
  const user = resolveEnv("MONGO_DB_USER");
  const password = resolveEnv("MONGO_DB_PASSWORD");
  const host = resolveEnv("MONGO_DB_HOST");
  if (!user || !password || !host) {
    return null;
  }

  const dbName = resolveEnv("MONGO_DB_NAME") || "momentum_etf_db";
  const isSrv = host.endsWith(".mongodb.net");
  const scheme = isSrv ? "mongodb+srv" : "mongodb";
  const defaultOpts = isSrv
    ? "retryWrites=true&w=majority"
    : "authSource=admin&retryWrites=true&w=majority";
  const options = resolveEnv("MONGO_DB_OPTIONS") || defaultOpts;

  const userEnc = encodeURIComponent(user);
  const passEnc = encodeURIComponent(password);
  const base = `${scheme}://${userEnc}:${passEnc}@${host}/${dbName}`;
  return options ? `${base}?${options}` : base;
}

function getMongoUri(): string {
  // 1순위: 명시적 연결 문자열 (하위호환 / 롤백 용이)
  const explicit = resolveEnv("MONGO_DB_CONNECTION_STRING");
  if (explicit) {
    return explicit;
  }
  // 2순위: USER/PASSWORD/HOST 부품으로 조립
  const fromParts = buildMongoUriFromParts();
  if (fromParts) {
    return fromParts;
  }
  throw new Error(
    "MongoDB 연결 정보가 없습니다. MONGO_DB_CONNECTION_STRING 또는 MONGO_DB_USER/PASSWORD/HOST 환경변수를 설정하세요.",
  );
}

function getMongoDbName(): string {
  return resolveEnv("MONGO_DB_NAME") || "momentum_etf_db";
}

export async function getMongoClient(): Promise<MongoClient> {
  if (!global.__momentumMongoClientPromise) {
    const client = new MongoClient(getMongoUri());
    global.__momentumMongoClientPromise = client.connect();
  }
  return global.__momentumMongoClientPromise;
}

export async function getMongoDb() {
  const client = await getMongoClient();
  return client.db(getMongoDbName());
}
