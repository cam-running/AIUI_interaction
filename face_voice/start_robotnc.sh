#!/bin/bash
set -e

APP_DIR="/home/ict/robot_nc"
SERVICE_CMD="python3 /home/ict/robot_nc/main_robot.py"
LOG_FILE="$APP_DIR/robot_nc.log"

cd "$APP_DIR"

is_running() {
    pgrep -f "$SERVICE_CMD" > /dev/null 2>&1
}

start() {
    if is_running; then
        echo "语音交互服务已在运行，无需重复启动。"
        exit 0
    fi
    echo "启动语音交互服务..."
    sleep 1
    nohup $SERVICE_CMD >> "$LOG_FILE" 2>&1 &
    sleep 1
    if is_running; then
        PID=$(pgrep -f "$SERVICE_CMD" | head -n1)
        echo "启动成功，PID: $PID"
    else
        echo "启动失败，请检查日志：$LOG_FILE"
        exit 1
    fi
}

stop() {
    if ! is_running; then
        echo "语音交互服务未运行。"
        exit 0
    fi
    echo "停止语音交互服务..."
    pkill -f "$SERVICE_CMD" || true
    # 等待最多5秒确保退出
    for i in 1 2 3 4 5; do
        if ! is_running; then
            echo "已停止。"
            exit 0
        fi
        sleep 1
    done
    if is_running; then
        echo "常规停止失败，尝试强制终止..."
        pkill -9 -f "$SERVICE_CMD" || true
    fi
    if is_running; then
        echo "强制终止仍失败，请手动检查进程。"
        exit 1
    else
        echo "已停止。"
    fi
}

status() {
    if is_running; then
        PIDS=$(pgrep -f "$SERVICE_CMD" | xargs)
        echo "语音交互服务正在运行，PID: $PIDS"
    else
        echo "语音交互服务未运行。"
    fi
}

restart() {
    stop || true
    start
}

case "${1:-start}" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    *) echo "用法: $0 {start|stop|restart|status}"; exit 2 ;;
esac
