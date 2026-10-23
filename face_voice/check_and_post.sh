#!/bin/bash

# 脚本所在目录（自动获取，确保日志文件保存在同级目录）
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
# 日志文件路径（与脚本同目录，文件名含日期）
LOG_FILE="${SCRIPT_DIR}/check_log.log"

# 要检查的端口列表
PORTS=(34555 5001 34550 34505)

# 最大等待时间（秒）
MAX_WAIT=100
WAIT_INTERVAL=2
WAITED=0

# 目标地址
URL="http://192.168.123.1:9000/confirm"

# 日志函数：同时输出到控制台和日志文件
log() {
    local timestamp=$(date '+%F %T')
    local message="[$timestamp] $1"
    echo "$message"  # 输出到控制台
    echo "$message" >> "$LOG_FILE"  # 写入日志文件
}

# 检查单个端口是否在监听
is_port_open() {
    local port=$1
    ss -ltn | grep -q ":$port "
    return $?
}

# 检查所有端口是否都监听
all_ports_open() {
    for port in "${PORTS[@]}"; do
        if ! is_port_open "$port"; then
            return 1
        fi
    done
    return 0
}

log "===== 脚本启动 ====="
log "开始检测端口：${PORTS[*]}"
log "最大等待时间：${MAX_WAIT}秒，检查间隔：${WAIT_INTERVAL}秒"

# 等待所有端口监听就绪
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    if all_ports_open; then
        TIMESTAMP=$(date +%s)
        SEND_TIME=$(date '+%F %T')  # 记录请求发送的格式化时间
        log "所有端口均已启动，准备发送GET请求..."
        log "GET请求发送时间：${SEND_TIME}（时间戳：${TIMESTAMP}）"
        
        # 执行curl并记录结果
        #curl_result=$(curl -s -w "\nHTTP状态码: %{http_code}" -X GET "$URL" -d "id=11&timestamp=$TIMESTAMP")
        curl_result=$(curl -s -w "\nHTTP状态码: %{http_code}" -X GET "${URL}?id=11&timestamp=$TIMESTAMP")
	log "GET请求响应：${curl_result}"
        log "GET请求已发送。"
        log "===== 脚本正常结束 ====="
        exit 0
    else
        log "尚有端口未就绪（已等待${WAITED}秒），继续等待..."
        sleep "$WAIT_INTERVAL"
        WAITED=$((WAITED + WAIT_INTERVAL))
    fi
done

log "超时：端口未全部启动（总等待${MAX_WAIT}秒），终止发送请求。"
log "===== 脚本超时结束 ====="
exit 1
    

