#!/bin/bash

# 机器人系统多服务启动脚本
echo "启动机器人系统多服务..."

# 设置环境变量
export PYTHONPATH=/app:/home/ict:/home/admin/Redcse
export PYTHONUNBUFFERED=1

# 检查代码仓库是否存在，不存在则重新下载
check_and_clone() {
    local dir=$1
    local repo=$2
    local branch=$3
    
    if [ ! -d "$dir" ]; then
        echo "下载代码仓库: $repo 到 $dir"
        if [ -n "$branch" ]; then
            git clone -b $branch $repo $dir
        else
            git clone $repo $dir
        fi
    else
        echo "代码仓库已存在: $dir"
    fi
}

# 检查并下载所有代码仓库
check_and_clone "/home/ict/server_tts" "https://gitee.com/latux/server_tts.git" "2025-06-19-xueyang-dev"
check_and_clone "/home/ict/face_voice" "https://gitee.com/latux/face_voice_0.git" ""
check_and_clone "/home/ict/robot_ai" "https://gitee.com/latux/robot_ai.git" "dev-torjean"
#check_and_clone "/home/admin/Redcse" "https://gitee.com/latux/Redcse.git" ""

# 安装各个服务的依赖
echo "安装服务依赖..."

# 安装 server_tts 依赖
if [ -f "/home/ict/server_tts/requirements.txt" ]; then
    echo "安装 server_tts 依赖..."
    pip install -r /home/ict/server_tts/requirements.txt
fi

# 安装 face_voice 依赖
if [ -f "/home/ict/face_voice/requirements.txt" ]; then
    echo "安装 face_voice 依赖..."
    pip install -r /home/ict/face_voice/requirements.txt
fi

# 安装 robot_ai 依赖
if [ -f "/home/ict/robot_ai/requirements.txt" ]; then
    echo "安装 robot_ai 依赖..."
    pip install -r /home/ict/robot_ai/requirements.txt
fi

# 安装 Redcse 依赖
#if [ -f "/home/admin/Redcse/requirements.txt" ]; then
#    echo "安装 Redcse 依赖..."
#    pip install -r /home/admin/Redcse/requirements.txt
#fi

# 创建日志目录
mkdir -p /var/log

echo "所有服务启动完成！"
echo "使用 supervisord 管理进程..."

# 启动 supervisord
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf 