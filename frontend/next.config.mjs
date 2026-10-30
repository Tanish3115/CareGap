import path from "node:path";
import { fileURLToPath } from "node:url";
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: path.dirname(fileURLToPath(import.meta.url)),
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

