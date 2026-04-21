import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

export function getWorkspaceRoot(): string {
  const candidates = [process.cwd(), path.join(process.cwd(), "..")];
  for (const candidate of candidates) {
    if (candidate.endsWith(`${path.sep}momentum-etf`) || candidate === "momentum-etf") {
      return candidate;
    }
  }
  return path.join(process.cwd(), "..");
}

export async function resolvePythonBinary(): Promise<string> {
  const root = getWorkspaceRoot();
  const candidates = [path.join(root, ".venv", "bin", "python"), path.join(process.cwd(), ".venv", "bin", "python")];

  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      continue;
    }
  }

  throw new Error("프로젝트 가상환경 Python을 찾을 수 없습니다.");
}

export async function spawnPythonScript(args: string[]): Promise<void> {
  const root = getWorkspaceRoot();
  const pythonBinary = await resolvePythonBinary();
  const child = spawn(pythonBinary, args, {
    cwd: root,
    env: process.env,
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}
