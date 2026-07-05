import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@saas/ui-tokens", "@saas/design-system"],
  experimental: {
    optimizePackageImports: ["@saas/ui-tokens", "@saas/design-system"],
  },
};

export default nextConfig;
