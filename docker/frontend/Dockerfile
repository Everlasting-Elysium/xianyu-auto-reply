# 前端 Dockerfile
# 使用预构建的 dist 目录（本地构建: cd frontend && npx vite build）

FROM nginx:alpine

RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.aliyun.com|g' /etc/apk/repositories

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/dist /usr/share/nginx/html

EXPOSE 80

ENV TZ=Asia/Shanghai

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
