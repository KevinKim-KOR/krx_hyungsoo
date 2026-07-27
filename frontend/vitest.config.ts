// POC3-01 REMEDIATION — 최소 UI 테스트 체계 (Vitest + RTL + jsdom).
// Next.js 구성은 유지하고 테스트 러너만 추가. Playwright/Cypress/snapshot 미도입.
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    // node_modules / .next 는 제외.
    exclude: ["node_modules", ".next"],
  },
  resolve: {
    alias: {
      // `@/` → 프로젝트 루트 (tsconfig paths 와 정합).
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
});
