#!/bin/bash

# 机器人系统 Docker 构建脚本（智能适配 Linux 环境 - aarch64 优化版）
echo "开始构建机器人系统 Docker 镜像..."

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检测系统架构
ARCH=$(uname -m)
echo -e "${BLUE}检测到系统架构: $ARCH${NC}"

# 设置平台参数
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    PLATFORM="linux/arm64"
    echo -e "${GREEN}使用 ARM64 平台配置${NC}"
elif [ "$ARCH" = "x86_64" ]; then
    PLATFORM="linux/amd64"
    echo -e "${GREEN}使用 AMD64 平台配置${NC}"
else
    echo -e "${YELLOW}未知架构 $ARCH，使用默认配置${NC}"
    PLATFORM="linux/$ARCH"
fi

# Docker 服务状态检查
echo -e "${BLUE}检查 Docker 服务状态...${NC}"
if sudo systemctl is-active --quiet docker; then
    echo -e "${GREEN}Docker 服务正在运行${NC}"
else
    echo -e "${YELLOW}启动 Docker 服务...${NC}"
    sudo systemctl start docker
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Docker 服务启动成功${NC}"
    else
        echo -e "${RED}Docker 服务启动失败，请检查 Docker 安装${NC}"
        exit 1
    fi
fi

# 设置 Docker 构建参数
export DOCKER_BUILDKIT=1
export DOCKER_DEFAULT_PLATFORM=$PLATFORM

# aarch64 架构特殊设置
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    echo -e "${YELLOW}为 ARM64 架构设置特殊配置...${NC}"
    # 增加构建超时时间
    export COMPOSE_HTTP_TIMEOUT=300
    export DOCKER_CLIENT_TIMEOUT=300
fi

# 检查 docker-compose.yml 文件是否存在
COMPOSE_FILE="docker/docker-compose.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}错误：找不到 $COMPOSE_FILE 文件${NC}"
    exit 1
fi

echo -e "${GREEN}找到 Docker Compose 配置文件${NC}"

# 停止并删除现有容器
echo -e "${YELLOW}停止现有容器...${NC}"
sudo docker-compose -f "$COMPOSE_FILE" down

# 网络连接测试
echo -e "${BLUE}测试网络连接...${NC}"
if curl -s --connect-timeout 10 https://registry-1.docker.io/v2/ > /dev/null; then
    echo -e "${GREEN}Docker Hub 连接正常${NC}"
elif curl -s --connect-timeout 10 https://mirrors.aliyun.com > /dev/null; then
    echo -e "${YELLOW}阿里云镜像源连接正常${NC}"
elif curl -s --connect-timeout 10 https://www.baidu.com > /dev/null; then
    echo -e "${YELLOW}网络连接正常，但 Docker Hub 可能较慢${NC}"
else
    echo -e "${RED}网络连接异常，请检查网络设置${NC}"
    echo -n "是否继续构建？可能会失败 [y/N]: "
    read -r REPLY
    if [ "$REPLY" != "y" ] && [ "$REPLY" != "Y" ]; then
        exit 1
    fi
fi

# 清理旧镜像（可选）
echo -n "是否清理旧的 Docker 镜像和缓存？[y/N]: "
read -r REPLY
if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    echo -e "${YELLOW}清理旧镜像和缓存...${NC}"
    sudo docker system prune -f
    sudo docker image prune -a -f
fi

# 构建镜像
echo -e "${YELLOW}构建 Docker 镜像 (平台: $PLATFORM)...${NC}"
if [ -n "$http_proxy" ]; then
    echo "使用代理构建..."
    sudo docker-compose -f "$COMPOSE_FILE" build --no-cache \
        --build-arg http_proxy="$http_proxy" \
        --build-arg https_proxy="$https_proxy" \
        --build-arg HTTP_PROXY="$HTTP_PROXY" \
        --build-arg HTTPS_PROXY="$HTTPS_PROXY" \
        --build-arg no_proxy="$no_proxy" \
        --build-arg NO_PROXY="$NO_PROXY" \
        --build-arg TARGETPLATFORM=$PLATFORM
else
    echo "直接网络构建..."
    sudo docker-compose -f "$COMPOSE_FILE" build --no-cache \
        --build-arg TARGETPLATFORM=$PLATFORM
fi

# 检查构建是否成功
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Docker 镜像构建成功！${NC}"
else
    echo -e "${RED}Docker 镜像构建失败！${NC}"
    echo -e "${YELLOW}故障排查建议：${NC}"
    echo "1. 检查网络连接"
    echo "2. 如果使用代理，配置 Docker 守护进程代理："
    echo "   ./configure_docker_daemon_proxy.sh"
    echo "3. 检查 Docker 服务状态：sudo systemctl status docker"
    echo "4. 查看 Docker 日志：sudo journalctl -u docker.service"
    echo "5. 检查磁盘空间：df -h"
    echo "6. 检查 Docker 权限：sudo usermod -aG docker \$USER"
    echo "7. 重启 Docker 服务：sudo systemctl restart docker"
    echo ""
    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
        echo -e "${BLUE}ARM64 架构特别注意事项：${NC}"
        echo "- 某些 Python 包可能需要从源码编译，构建时间较长"
        echo "- 确保有足够的内存（建议 4GB 以上）"
        echo "- 如果遇到包不兼容，请检查 requirements.txt"
        echo "- 可以尝试使用 piwheels 源：pip config set global.extra-index-url https://www.piwheels.org/simple"
    fi
    echo -e "${BLUE}如果网络问题持续，可以尝试：${NC}"
    echo "- 使用 Docker 镜像加速器（如阿里云、腾讯云）"
    echo "- 手动拉取基础镜像：sudo docker pull --platform $PLATFORM ubuntu:22.04"
    echo ""
    echo -e "${BLUE}代理使用示例：${NC}"
    echo "- 使用代理构建：./build_and_run.sh --proxy http://127.0.0.1:2080"
    echo "- 设置环境变量：export http_proxy=http://127.0.0.1:2080"
    exit 1
fi

# 启动容器
echo -e "${YELLOW}启动机器人系统容器...${NC}"
sudo docker-compose -f "$COMPOSE_FILE" up -d

# 检查容器是否启动成功
if [ $? -eq 0 ]; then
    echo -e "${GREEN}机器人系统容器启动成功！${NC}"
    echo -e "${GREEN}访问地址:${NC}"
    echo "  - 主应用: http://localhost:8000"
    echo "  - Server TTS: http://localhost:8001"
    echo "  - Face Voice 主服务: http://localhost:8002"
    echo "  - Face Voice 视频服务: http://localhost:8003"
    echo "  - Redcse Web: http://localhost:8004"
    echo ""
    echo -e "${YELLOW}常用命令:${NC}"
    echo "  查看日志: sudo docker-compose -f $COMPOSE_FILE logs -f"
    echo "  停止服务: sudo docker-compose -f $COMPOSE_FILE stop"
    echo "  重启服务: sudo docker-compose -f $COMPOSE_FILE restart"
    echo "  进入容器: sudo docker exec -it robot-system bash"
    echo "  查看状态: sudo docker-compose -f $COMPOSE_FILE ps"
    echo ""
    echo -e "${GREEN}构建完成！系统架构: $ARCH, 平台: $PLATFORM${NC}"
else
    echo -e "${RED}容器启动失败！${NC}"
    echo "查看错误日志：sudo docker-compose -f $COMPOSE_FILE logs"
    exit 1
fi 