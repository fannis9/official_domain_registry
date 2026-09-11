# 前端多阶段构建(构建上下文为仓库根目录): node 打包 -> nginx 静态服务 + 反代
FROM node:22-alpine AS build
WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmmirror.com
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund --registry=${NPM_REGISTRY}
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
