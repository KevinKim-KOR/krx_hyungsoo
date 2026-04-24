// ESLint flat config (ESLint 9+).
// eslint-config-next 는 legacy extends 방식이라 FlatCompat 으로 래핑.
// ESLint CLI 중심 실행: `npm run lint` → `eslint .`

import { FlatCompat } from "@eslint/eslintrc";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const config = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "out/**",
      "next-env.d.ts",
      "*.tsbuildinfo",
    ],
  },
];

export default config;
