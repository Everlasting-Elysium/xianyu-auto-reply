#!/bin/bash
# ==========================================
# 闲鱼自动回复系统 - All-in-One 启动脚本
# 数据持久化到宿主机 ./data/ 目录
# 用法:
#   bash run-allinone.sh start      # 首次启动 / 升级镜像后启动
#   bash run-allinone.sh stop       # 停止并删除容器（数据保留）
#   bash run-allinone.sh restart    # 重启容器
#   bash run-allinone.sh logs       # 查看日志
#   bash run-allinone.sh status     # 查看状态
#   bash run-allinone.sh build      # 本地重新构建镜像
#   bash run-allinone.sh shell      # 进入容器 shell
# ==========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

WORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$WORK_DIR/data"

CONTAINER_NAME="${CONTAINER_NAME:-xianyu-allinone}"
IMAGE_NAME="${IMAGE_NAME:-xianyu-allinone:latest}"
HOST_PORT="${HOST_PORT:-9000}"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-xianyu2026}"
BACKEND_WEB_PUBLIC_URL="${BACKEND_WEB_PUBLIC_URL:-http://localhost:${HOST_PORT}}"
FRONTEND_PUBLIC_URL="${FRONTEND_PUBLIC_URL:-http://localhost:${HOST_PORT}}"

require_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装，请先安装 Docker${NC}"
        echo "安装教程: https://docs.docker.com/get-docker/"
        exit 1
    fi
}

ensure_data_dirs() {
    mkdir -p \
        "$DATA_DIR/mysql" \
        "$DATA_DIR/redis" \
        "$DATA_DIR/static" \
        "$DATA_DIR/backups" \
        "$DATA_DIR/browser_data" \
        "$DATA_DIR/logs/backend-web" \
        "$DATA_DIR/logs/websocket" \
        "$DATA_DIR/logs/scheduler" \
        "$DATA_DIR/logs/supervisor"
}

container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

image_exists() {
    docker image inspect "$IMAGE_NAME" >/dev/null 2>&1
}

cmd_build() {
    require_docker
    echo -e "${CYAN}=== 本地构建镜像 $IMAGE_NAME ===${NC}"
    if [ ! -d "$WORK_DIR/frontend/dist" ]; then
        echo -e "${YELLOW}警告: frontend/dist 不存在，需先在宿主机构建前端：${NC}"
        echo "  cd frontend && pnpm install && pnpm build  (或 npm)"
        echo ""
        read -p "是否仍然继续？(y/N) " -n 1 -r
        echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
    fi
    docker build -f "$WORK_DIR/Dockerfile.allinone" -t "$IMAGE_NAME" "$WORK_DIR"
    echo -e "${GREEN}✓ 镜像构建完成${NC}"
}

cmd_start() {
    require_docker
    ensure_data_dirs

    if ! image_exists; then
        echo -e "${YELLOW}镜像 $IMAGE_NAME 不存在，先执行 build${NC}"
        cmd_build
    fi

    if container_running; then
        echo -e "${YELLOW}容器已在运行：${CONTAINER_NAME}${NC}"
        cmd_status
        exit 0
    fi

    if container_exists; then
        echo -e "${CYAN}删除旧容器（保留数据卷绑定不动）...${NC}"
        docker rm -f "$CONTAINER_NAME" >/dev/null
    fi

    echo -e "${CYAN}=== 启动 All-in-One 容器 ===${NC}"
    echo "  容器名: $CONTAINER_NAME"
    echo "  端口  : $HOST_PORT -> 80"
    echo "  数据目录: $DATA_DIR"
    echo ""

    docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        -p "${HOST_PORT}:80" \
        -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD" \
        -e MYSQL_PASSWORD="$MYSQL_ROOT_PASSWORD" \
        -e BACKEND_WEB_PUBLIC_URL="$BACKEND_WEB_PUBLIC_URL" \
        -e FRONTEND_PUBLIC_URL="$FRONTEND_PUBLIC_URL" \
        -v "$DATA_DIR/mysql:/var/lib/mysql" \
        -v "$DATA_DIR/redis:/data/redis" \
        -v "$DATA_DIR/static:/app/static" \
        -v "$DATA_DIR/backups:/app/backups" \
        -v "$DATA_DIR/browser_data:/app/websocket/browser_data" \
        -v "$DATA_DIR/logs/backend-web:/app/backend-web/logs" \
        -v "$DATA_DIR/logs/websocket:/app/websocket/logs" \
        -v "$DATA_DIR/logs/scheduler:/app/scheduler/logs" \
        -v "$DATA_DIR/logs/supervisor:/var/log/supervisor" \
        "$IMAGE_NAME" >/dev/null

    echo -e "${GREEN}✓ 容器已启动${NC}"
    echo ""
    echo -e "${CYAN}等待服务就绪（最多 90 秒）...${NC}"
    for i in $(seq 1 90); do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}/health" 2>/dev/null | grep -q 200; then
            echo -e "${GREEN}✓ 服务已就绪${NC}"
            echo ""
            echo "  访问地址: ${BACKEND_WEB_PUBLIC_URL}"
            echo "  默认账号: admin / admin123"
            return 0
        fi
        sleep 1
    done
    echo -e "${YELLOW}⚠ 90 秒内未能确认服务就绪，请用 'bash run-allinone.sh logs' 查看日志${NC}"
}

cmd_stop() {
    require_docker
    if ! container_exists; then
        echo -e "${YELLOW}容器不存在：${CONTAINER_NAME}${NC}"
        return 0
    fi
    echo -e "${CYAN}停止并删除容器（数据保留在 $DATA_DIR）...${NC}"
    docker rm -f "$CONTAINER_NAME" >/dev/null
    echo -e "${GREEN}✓ 已停止${NC}"
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_logs() {
    require_docker
    docker logs -f --tail 200 "$CONTAINER_NAME"
}

cmd_status() {
    require_docker
    if ! container_exists; then
        echo -e "${YELLOW}容器不存在${NC}"
        exit 0
    fi
    docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "数据目录用量:"
    du -sh "$DATA_DIR"/* 2>/dev/null | sort -h
}

cmd_shell() {
    require_docker
    docker exec -it "$CONTAINER_NAME" bash
}

cmd_backup() {
    require_docker
    if [ ! -d "$DATA_DIR" ]; then
        echo -e "${RED}数据目录不存在: $DATA_DIR${NC}"
        exit 1
    fi
    BACKUP_FILE="$WORK_DIR/xianyu-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
    echo -e "${CYAN}打包数据到 $BACKUP_FILE ...${NC}"
    tar -czf "$BACKUP_FILE" -C "$WORK_DIR" data
    echo -e "${GREEN}✓ 备份完成: $(du -h "$BACKUP_FILE" | cut -f1)${NC}"
}

case "${1:-start}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    logs)    cmd_logs ;;
    status)  cmd_status ;;
    build)   cmd_build ;;
    shell)   cmd_shell ;;
    backup)  cmd_backup ;;
    *)
        echo "用法: $0 {start|stop|restart|logs|status|build|shell|backup}"
        echo ""
        echo "  start    启动容器（首次或镜像更新后）"
        echo "  stop     停止并删除容器（数据保留）"
        echo "  restart  重启容器"
        echo "  logs     查看实时日志"
        echo "  status   查看运行状态和数据目录用量"
        echo "  build    本地重新构建镜像"
        echo "  shell    进入容器交互 shell"
        echo "  backup   打包 data/ 为 tar.gz 备份"
        echo ""
        echo "环境变量（可选，覆盖默认值）:"
        echo "  HOST_PORT              对外端口（默认 9000）"
        echo "  CONTAINER_NAME         容器名（默认 xianyu-allinone）"
        echo "  IMAGE_NAME             镜像名（默认 xianyu-allinone:latest）"
        echo "  MYSQL_ROOT_PASSWORD    MySQL root 密码（默认 xianyu2026）"
        echo "  BACKEND_WEB_PUBLIC_URL 后端对外URL（默认 http://localhost:9000）"
        echo "  FRONTEND_PUBLIC_URL    前端对外URL（默认 http://localhost:9000）"
        exit 1
        ;;
esac
