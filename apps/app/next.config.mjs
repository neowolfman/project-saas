/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@saas/ui-tokens", "@saas/design-system", "@saas/api-contracts"],
};

export default nextConfig;
