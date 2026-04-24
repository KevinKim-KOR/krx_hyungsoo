import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js 는 프론트 전용. API 는 FastAPI(8000) 로 CORS 직접 호출.
  // Route Handlers / rewrites 사용하지 않는다 (설계 결정).
  reactStrictMode: true,
};

export default nextConfig;
