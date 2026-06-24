#!/bin/bash
set -e

# ================================================
# 闲鱼自动回复系统 All-in-One 启动脚本
# MySQL + Redis + Backend-Web + WebSocket + Scheduler + Nginx
# ================================================

echo "=========================================="
echo "  Xianyu Auto Reply - All-in-One"
echo "=========================================="

# ---------- 环境变量默认值 ----------
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=${MYSQL_USER:-root}
export MYSQL_PASSWORD=${MYSQL_PASSWORD:-xianyu2026}
export MYSQL_DATABASE=${MYSQL_DATABASE:-xianyu_data}
export MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-$MYSQL_PASSWORD}
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
export REDIS_PASSWORD=
export REDIS_DB=0
export ENVIRONMENT=${ENVIRONMENT:-production}
export BACKEND_WEB_PORT=8089
export WEBSOCKET_PORT=8090
export SCHEDULER_PORT=8091
export CORS_ORIGINS="*"
export WEBSOCKET_SERVICE_URL=http://127.0.0.1:8090
export SCHEDULER_SERVICE_URL=http://127.0.0.1:8091
export BACKEND_WEB_SERVICE_URL=http://127.0.0.1:8089
export BACKEND_WEB_PUBLIC_URL=${BACKEND_WEB_PUBLIC_URL:-http://localhost:8089}
export FRONTEND_PUBLIC_URL=${FRONTEND_PUBLIC_URL:-http://localhost:9000}
export STATIC_DIR=/app/static
export BACKUP_DIR=/app/backups
export BROWSER_HEADLESS=true
export AUTO_START_WEBSOCKET=true
export AUTO_START_CRAWL_JOBS=false
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export SQL_ECHO=${SQL_ECHO:-false}
export TZ=Asia/Shanghai
export JWT_ALGORITHM=HS256
export ACCESS_TOKEN_EXPIRE_MINUTES=1440
export REFRESH_TOKEN_EXPIRE_MINUTES=10080

# ---------- 创建必要目录 ----------
mkdir -p /var/log/supervisor
mkdir -p /var/run/mysqld && chown mysql:mysql /var/run/mysqld
mkdir -p /data/redis
mkdir -p /app/static/uploads
mkdir -p /app/backups
mkdir -p /app/backend-web/logs
mkdir -p /app/websocket/logs
mkdir -p /app/scheduler/logs
mkdir -p /app/websocket/browser_data

# ---------- 初始化 MySQL ----------
MYSQL_DATA_DIR=/var/lib/mysql

if [ ! -d "$MYSQL_DATA_DIR/mysql" ]; then
    echo "[INIT] Initializing MySQL data directory..."
    mysqld --initialize-insecure --user=mysql --datadir="$MYSQL_DATA_DIR"

    echo "[INIT] Starting MySQL for initialization..."
    mysqld_safe --skip-networking &
    MYSQL_PID=$!

    # 等待 MySQL 启动
    for i in $(seq 1 30); do
        if mysqladmin ping --silent 2>/dev/null; then
            break
        fi
        echo "[INIT] Waiting for MySQL... ($i/30)"
        sleep 1
    done

    echo "[INIT] Creating database and user..."
    mysql -u root <<-EOSQL
        ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
        CREATE DATABASE IF NOT EXISTS \`${MYSQL_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
        GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
        FLUSH PRIVILEGES;
EOSQL

    echo "[INIT] Stopping bootstrap MySQL..."
    mysqladmin -u root -p"${MYSQL_ROOT_PASSWORD}" shutdown 2>/dev/null || kill $MYSQL_PID 2>/dev/null
    wait $MYSQL_PID 2>/dev/null || true
    sleep 2
    echo "[INIT] MySQL initialization complete."
else
    echo "[INFO] MySQL data directory exists, skipping initialization."
fi

# ---------- 写入服务 .env 文件 ----------
for SVC_DIR in /app/backend-web /app/websocket /app/scheduler; do
    cat > "$SVC_DIR/.env" <<EOF
ENVIRONMENT=${ENVIRONMENT}
LOG_LEVEL=${LOG_LEVEL}
SQL_ECHO=${SQL_ECHO}
MYSQL_HOST=${MYSQL_HOST}
MYSQL_PORT=${MYSQL_PORT}
MYSQL_USER=${MYSQL_USER}
MYSQL_PASSWORD=${MYSQL_PASSWORD}
MYSQL_DATABASE=${MYSQL_DATABASE}
REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_DB=${REDIS_DB}
CORS_ORIGINS=${CORS_ORIGINS}
WEBSOCKET_SERVICE_URL=${WEBSOCKET_SERVICE_URL}
SCHEDULER_SERVICE_URL=${SCHEDULER_SERVICE_URL}
BACKEND_WEB_SERVICE_URL=${BACKEND_WEB_SERVICE_URL}
BACKEND_WEB_PUBLIC_URL=${BACKEND_WEB_PUBLIC_URL}
FRONTEND_PUBLIC_URL=${FRONTEND_PUBLIC_URL}
STATIC_DIR=${STATIC_DIR}
BACKUP_DIR=${BACKUP_DIR}
BROWSER_HEADLESS=${BROWSER_HEADLESS}
AUTO_START_WEBSOCKET=${AUTO_START_WEBSOCKET}
AUTO_START_CRAWL_JOBS=${AUTO_START_CRAWL_JOBS}
BACKEND_WEB_PORT=${BACKEND_WEB_PORT}
WEBSOCKET_PORT=${WEBSOCKET_PORT}
SCHEDULER_PORT=${SCHEDULER_PORT}
JWT_ALGORITHM=${JWT_ALGORITHM}
ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES}
REFRESH_TOKEN_EXPIRE_MINUTES=${REFRESH_TOKEN_EXPIRE_MINUTES}
TZ=${TZ}
EOF
done

echo "[INFO] Starting all services via Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
