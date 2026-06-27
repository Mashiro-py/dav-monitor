# 多阶段构建：Node 用国内镜像 build → nginx 托管静态文件 + 反代后端
# 构建上下文 = 仓库根目录（见 frontend-compose.yml 的 context: ..）

# ---------- 构建阶段 ----------
FROM node:20-alpine AS build
WORKDIR /app
# 国内 npm 镜像，避免国外源超时
RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
# VITE_API_BASE 留空 → 前端用相对路径 /api，由 nginx 反代到后端
RUN npm run build

# ---------- 托管阶段 ----------
FROM nginx:1.27-alpine
COPY deploy/frontend-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
