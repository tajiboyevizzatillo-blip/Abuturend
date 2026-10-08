# Dependency stage
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Build stage
FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined into the client bundle at build time.
# /api (same-origin) is what production uses: nginx proxies /api/ to the
# backend, so the browser never needs an absolute API URL.
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# Rewrites are baked into .next/routes-manifest.json at build time, so the
# backend origin must be known here too. Without this the rewrite targets
# 127.0.0.1:8000 *inside this container* and every server-side /api request
# fails with ECONNREFUSED. nginx masks this in production by intercepting /api/
# before the request reaches Next, which is exactly why it goes unnoticed.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL
# Cap Next.js build heap so low-RAM VPS stays responsive (SSH/web) during builds
ENV NODE_OPTIONS=--max-old-space-size=1024
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Runner stage (standalone)
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Do not phone home from the production runtime.
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
COPY --from=build /app/messages ./messages
COPY --from=build /app/i18n ./i18n
# Run unprivileged: the Next server needs no root capability.
RUN addgroup -g 10001 -S nodejs && adduser -u 10001 -S nextjs -G nodejs
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/uz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]