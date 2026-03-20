import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backend = process.env.INKSIGHT_BACKEND_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8080";
    return [
      // Proxy all /api requests to backend to avoid missing new routes.
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
