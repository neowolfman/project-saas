/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@saas/ui-tokens", "@saas/design-system"],
  experimental: {
    optimizePackageImports: ["@saas/ui-tokens", "@saas/design-system"],
  },
};

export default nextConfig;
