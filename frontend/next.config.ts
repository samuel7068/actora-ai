import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://backend:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["10.10.100.19"],
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
