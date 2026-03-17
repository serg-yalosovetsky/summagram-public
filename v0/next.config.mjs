/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  experimental: {
    proxyTimeout: 120_000, // 120s — LLM inference can take 30-90s
  },
  transpilePackages: ["react-force-graph-2d", "force-graph", "d3-force", "d3-selection"],
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const etlUrl = process.env.NEXT_PUBLIC_ETL_URL || 'http://localhost:8002'
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
      {
        source: '/api/chat/:path*',
        destination: `${backendUrl}/chat/:path*`,
      },
      {
        source: '/media/:path*',
        destination: `${backendUrl}/media/:path*`,
      },
      {
        source: '/etl/:path*',
        destination: `${etlUrl}/:path*`,
      },
    ]
  },
  turbopack: {
    root: process.cwd(),
  },
}

export default nextConfig
