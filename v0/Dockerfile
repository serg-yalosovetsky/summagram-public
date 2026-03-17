# v0 Next.js Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install

# Copy application code
COPY . .

# Expose Next.js port
EXPOSE 3000

# Run in dev mode (hot-reload with volume mounts)
CMD ["pnpm", "dev", "-H", "0.0.0.0"]
