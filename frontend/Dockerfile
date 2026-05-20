# syntax=docker/dockerfile:1.6

# ---------- deps ----------
FROM node:22-alpine AS deps
WORKDIR /app
RUN npm install -g npm@11
COPY package.json package-lock.json ./
# npm ci 대신 install 사용 — Mac(darwin-arm64) 로컬 lock 파일과
# Linux(linux-x64) 컨테이너의 플랫폼별 optional native binary 차이로
# ci 가 sync 검증을 거절하는 문제 회피
RUN npm install --no-audit --no-fund

# ---------- builder ----------
FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm install -g npm@11
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------- runner ----------
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
