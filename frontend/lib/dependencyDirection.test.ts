// POC3-02D-OPS-03 설계자 RESULT STEP 5 — 프론트 의존 방향 검사.
// `frontend/lib` 는 화면(React 컴포넌트 · `app/components`)을 가져오지 않는다.
// 방향은 컴포넌트 → lib 하나다. lib 의 모든 .ts/.tsx 원문에서 import · export from ·
// 동적 import · require 대상을 읽어, `app/components` 로 풀리면 실패한다.
// 외부 호출 0 — 저장소 파일만 읽는다.
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const THIS_FILE = fileURLToPath(import.meta.url);
const LIB_DIR = path.dirname(THIS_FILE);
const FRONTEND_DIR = path.dirname(LIB_DIR);
const COMPONENTS_DIR = path.join(FRONTEND_DIR, "app", "components");

// `from "x"` · `import "x"` · `import("x")` · `require("x")` 의 대상 문자열.
const SPECIFIER_RE =
  /(?:\bfrom\s*|^\s*import\s*|\bimport\s*\(\s*|\brequire\s*\(\s*)["'`]([^"'`]+)["'`]/gm;

function importSpecifiers(source: string): string[] {
  return [...source.matchAll(SPECIFIER_RE)].map((m) => m[1]);
}

// `@/` 별칭(tsconfig paths · vitest alias)과 상대 경로를 실제 경로로 풀어 본다.
function resolvesIntoComponents(spec: string, fromFile: string): boolean {
  let target: string;
  if (spec.startsWith("@/")) {
    target = path.join(FRONTEND_DIR, spec.slice(2));
  } else if (spec.startsWith(".")) {
    target = path.resolve(path.dirname(fromFile), spec);
  } else {
    return false;
  }
  const rel = path.relative(COMPONENTS_DIR, target);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function violations(source: string, fromFile: string): string[] {
  return importSpecifiers(source).filter((s) => resolvesIntoComponents(s, fromFile));
}

function listSources(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...listSources(full));
    } else if (/\.tsx?$/.test(name)) {
      out.push(full);
    }
  }
  return out;
}

describe("frontend/lib 의존 방향 — app/components 를 가져오지 않는다", () => {
  it("lib 의 모든 .ts/.tsx 파일", () => {
    // 이 검사 파일은 아래 자기 점검용 예시 문자열을 담고 있어 제외한다.
    const files = listSources(LIB_DIR).filter((f) => f !== THIS_FILE);
    expect(files.length).toBeGreaterThan(0);
    // KOSPI 판정 · 문구 생성기가 lib 에 있다(설계자 RESULT STEP 5).
    expect(files).toContain(path.join(LIB_DIR, "kospiStatus.ts"));
    const found = files.flatMap((f) =>
      violations(readFileSync(f, "utf-8"), f).map(
        (s) => `${path.relative(FRONTEND_DIR, f)} → ${s}`,
      ),
    );
    expect(found).toEqual([]);
  });

  it("검사기 자기 점검 — 별칭 · 상대 경로 · 동적 import · re-export 를 잡는다", () => {
    const from = path.join(LIB_DIR, "sub", "x.ts");
    const bad = [
      'import { a } from "@/app/components/KospiStatusNote";',
      "import type { B } from '../../app/components/today/KospiChart';",
      'export { c } from "@/app/components";',
      'const d = await import("@/app/components/MarketContextCard");',
      'const e = require("../../app/components/X");',
    ].join("\n");
    expect(violations(bad, from)).toHaveLength(5);
    const ok = [
      'import type { MarketContextKospi } from "../api";',
      'import { kospiStatusText } from "@/lib/kospiStatus";',
      'import { useState } from "react";',
      'import { x } from "@/app/components_other/y";',
    ].join("\n");
    expect(violations(ok, from)).toEqual([]);
  });
});
