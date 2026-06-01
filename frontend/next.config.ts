import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://backend:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["10.10.100.19"],
  experimental: {
    // 영상 분석 업로드용 — 기본 10MB 초과 시 잘림. 500MB 까지 허용.
    // (Next 16: middlewareClientMaxBodySize 는 deprecated, proxyClientMaxBodySize 가 신규 키)
    // proxyTimeout: dev 프록시가 장시간 처리(GPT-4V) 도중 socket hang up 하지 않도록 10분.
    ...({
      proxyClientMaxBodySize: "500mb",
      proxyTimeout: 10 * 60 * 1000,
    } as object),
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
