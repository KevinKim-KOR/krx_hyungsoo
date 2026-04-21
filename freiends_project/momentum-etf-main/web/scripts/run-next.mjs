import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

function parseEnvLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) {
    return null;
  }

  const separatorIndex = trimmed.indexOf("=");
  if (separatorIndex <= 0) {
    return null;
  }

  const key = trimmed.slice(0, separatorIndex).trim();
  let value = trimmed.slice(separatorIndex + 1).trim();

  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    value = value.slice(1, -1);
  }

  return [key, value];
}

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return;
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  for (const line of raw.split(/\r?\n/)) {
    const parsed = parseEnvLine(line);
    if (!parsed) {
      continue;
    }
    const [key, value] = parsed;
    if (!process.env[key]) {
      process.env[key] = value;
    }
  }
}

function loadAppEnv() {
  const candidates = [
    path.join(process.cwd(), ".env"),
    path.join(process.cwd(), ".env.local"),
    path.join(process.cwd(), "..", ".env"),
    path.join(process.cwd(), "..", ".env.local"),
  ];

  for (const candidate of candidates) {
    loadEnvFile(candidate);
  }
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value || !String(value).trim()) {
    throw new Error(`${name} 환경변수가 필요합니다.`);
  }
}

function validateStartEnv() {
  requireEnv("AUTH_SESSION_SECRET");
  requireEnv("GOOGLE_CLIENT_ID");
  requireEnv("GOOGLE_CLIENT_SECRET");
  requireEnv("AUTH_ALLOWED_EMAILS");
  requireEnv("APP_BASE_URL");
}

function main() {
  const nextCommand = process.argv[2];
  const nextArgs = process.argv.slice(3);

  if (!nextCommand) {
    throw new Error("next 실행 명령이 필요합니다.");
  }

  loadAppEnv();

  if (nextCommand === "start") {
    validateStartEnv();
  }

  const child = spawn("next", [nextCommand, ...nextArgs], {
    stdio: "inherit",
    shell: true,
    env: process.env,
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });
}

main();
