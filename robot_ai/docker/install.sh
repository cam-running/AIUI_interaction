#!/bin/bash
###
 # @Author: zhaoyong 77912776@qq.com
 # @Date: 2025-07-04 15:09:21
 # @LastEditTime: 2025-07-09 10:45:10
 # @LastEditors: zhaoyong 77912776@qq.com
 # @FilePath: \robot_ai\docker\install.sh
 # @Description: Robot AI Docker 离线安装脚本
### 
# Robot AI Docker 离线安装脚本
# 支持 ARM64 架构的完全离线 Docker 安装和容器部署
#
# 使用方法：
#   sudo ./install.sh          # 常规安装（检测已有Docker）
#   sudo ./install.sh --force  # 强制重新安装（完全卸载后重装）
#   sudo ./install.sh -f       # 强制重新安装（简写）

set -e  # 出错时立即退出

# 设置UTF-8编码环境
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    printf "${BLUE}[INFO]${NC} %s %s\n" "$(date '+%H:%M:%S')" "$1"
}

log_success() {
    printf "${GREEN}[SUCCESS]${NC} %s %s\n" "$(date '+%H:%M:%S')" "$1"
}

log_warning() {
    printf "${YELLOW}[WARNING]${NC} %s %s\n" "$(date '+%H:%M:%S')" "$1"
}

log_error() {
    printf "${RED}[ERROR]${NC} %s %s\n" "$(date '+%H:%M:%S')" "$1"
}

# 错误处理函数
handle_error() {
    log_error "脚本执行失败，退出代码：$1"
    exit "$1"
}

# 设置错误处理
trap 'handle_error $?' ERR

# 保证当前目录为 install.sh 所在路径
cd "$(dirname "$0")"

log_info "========== Robot AI Docker 离线部署开始 =========="
log_info "当前工作目录：$(pwd)"
log_info "系统架构：$(uname -m)"

# 显示使用说明
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo ""
    echo "Robot AI Docker 离线安装脚本"
    echo ""
    echo "使用方法："
    echo "  sudo ./install.sh          # 默认强制重新安装（推荐）"
    echo "  sudo ./install.sh --keep   # 保留现有Docker安装"
    echo "  sudo ./install.sh --force  # 强制重新安装（明确指定）"
    echo "  sudo ./install.sh -f       # 强制重新安装（简写）"
    echo "  sudo ./install.sh --help   # 显示帮助信息"
    echo ""
    echo "必需文件："
    echo "  - docker_file/containerd.io_1.7.27-1_arm64.deb"
    echo "  - docker_file/docker-ce-cli_24.0.7-1~ubuntu.22.04~jammy_arm64.deb"
    echo "  - docker_file/docker-ce_24.0.7-1~ubuntu.22.04~jammy_arm64.deb"
    echo "  - docker_file/docker-compose-linux-aarch64"
    echo "  - Dockerfile"
    echo "  - docker-compose.yml"
    echo ""
    exit 0
fi

# 检查系统架构
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
    log_warning "当前系统架构为 $ARCH，此脚本针对 ARM64 优化"
fi

# 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    log_error "此脚本需要 root 权限，请使用 sudo 运行"
    exit 1
fi

log_info "========== 检查 Docker 安装状态 =========="

# 检查是否强制重新安装（默认强制重新安装）
FORCE_REINSTALL=${1:-"--force"}
if [ "$FORCE_REINSTALL" = "--keep" ]; then
    log_info "保留现有Docker安装模式"
    FORCE_INSTALL=false
else
    log_warning "强制重新安装模式，将完全卸载并重新安装 Docker"
    
    # 停止 Docker 服务
    log_info "停止 Docker 服务..."
    systemctl stop docker &> /dev/null || true
    systemctl stop containerd &> /dev/null || true
    
    # 完全卸载 Docker
    log_info "卸载现有 Docker 安装..."
    apt-get remove -y docker-ce docker-ce-cli containerd.io docker-compose-plugin &> /dev/null || true
    apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin &> /dev/null || true
    rm -rf /var/lib/docker /etc/docker
    rm -f /usr/local/bin/docker-compose
    rm -rf /usr/local/lib/docker/cli-plugins
    
    log_success "Docker 卸载完成"
    FORCE_INSTALL=true
fi

# 检查 Docker 是否已安装并运行
if command -v docker &> /dev/null && [ "$FORCE_INSTALL" = false ]; then
    DOCKER_VERSION=$(docker --version 2>/dev/null || echo "未知版本")
    log_success "已安装 Docker：$DOCKER_VERSION"
    
    # 检查 Docker 服务状态
    if systemctl is-active --quiet docker; then
        log_success "Docker 服务正在运行"
    else
        log_warning "Docker 服务未运行，正在启动..."
        systemctl start docker
        systemctl enable docker
    fi
    
    # 检查 Docker Compose
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo "未知版本")
        log_success "已安装 Docker Compose：$COMPOSE_VERSION"
    else
        log_warning "未找到 Docker Compose，将进行离线安装"
        # 离线安装 Docker Compose
        if [ -f "docker_file/docker-compose-linux-aarch64" ]; then
            log_info "使用离线安装包安装 Docker Compose..."
            cp docker_file/docker-compose-linux-aarch64 /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
            # 创建符号链接以支持 docker compose 子命令
            mkdir -p /usr/local/lib/docker/cli-plugins
            ln -sf /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
            log_success "Docker Compose 离线安装完成"
        else
            log_error "未找到 Docker Compose 离线安装包：docker_file/docker-compose-linux-aarch64"
            exit 1
        fi
    fi
else
    log_warning "未检测到 Docker，开始离线安装..."
    
    # 检查所需的 .deb 文件
    log_info "检查 Docker 离线安装包..."
    DEB_FILES=(
        "docker_file/containerd.io_1.7.27-1_arm64.deb"
        "docker_file/docker-ce-cli_24.0.7-1~ubuntu.22.04~jammy_arm64.deb"
        "docker_file/docker-ce_24.0.7-1~ubuntu.22.04~jammy_arm64.deb"
    )
    
    for file in "${DEB_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "缺少必要文件：$file"
            exit 1
        fi
        log_info "找到安装包：$(basename "$file")"
    done
    
    log_info "开始离线安装 Docker..."
    
    # 安装必要的系统依赖（这些通常已经预装在Ubuntu系统中）
    log_info "检查系统依赖..."
    REQUIRED_PACKAGES=(
        "ca-certificates"
        "curl"
        "gnupg"
        "lsb-release"
        "systemd"
        "iptables"
    )
    
    # 只检查关键依赖是否存在，不进行在线更新
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if ! dpkg -l | grep -q "^ii  $pkg "; then
            log_warning "缺少系统依赖：$pkg，请确保系统已预装必要依赖"
        fi
    done
    
    # 卸载旧版本（如果存在）
    log_info "清理旧版本 Docker..."
    apt-get remove -y docker docker-engine docker.io containerd runc &> /dev/null || true
    
    # 离线安装 .deb 包
    log_info "离线安装 Docker 软件包..."
    # 按正确顺序安装依赖包
    dpkg -i docker_file/containerd.io_1.7.27-1_arm64.deb || true
    dpkg -i docker_file/docker-ce-cli_24.0.7-1~ubuntu.22.04~jammy_arm64.deb || true
    dpkg -i docker_file/docker-ce_24.0.7-1~ubuntu.22.04~jammy_arm64.deb || true
    
    # 修复依赖关系（如果需要）
    log_info "修复依赖关系..."
    apt-get install -f -y &> /dev/null || true
    
    # 启动并设置开机自启
    log_info "配置 Docker 服务..."
    systemctl daemon-reload
    systemctl enable docker
    systemctl start docker
    
    # 等待 Docker 服务完全启动
    log_info "等待 Docker 服务启动..."
    sleep 5
    
    # 验证安装
    if docker --version &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        log_success "Docker 离线安装成功：$DOCKER_VERSION"
    else
        log_error "Docker 安装失败"
        exit 1
    fi
    
    # 离线安装 Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_info "离线安装 Docker Compose..."
        if [ -f "docker_file/docker-compose-linux-aarch64" ]; then
            cp docker_file/docker-compose-linux-aarch64 /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
            # 创建符号链接以支持 docker compose 子命令
            mkdir -p /usr/local/lib/docker/cli-plugins
            ln -sf /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
            log_success "Docker Compose 离线安装完成"
        else
            log_error "未找到 Docker Compose 离线安装包：docker_file/docker-compose-linux-aarch64"
            exit 1
        fi
    fi
fi

# 配置用户权限
log_info "配置 Docker 用户权限..."
CURRENT_USER=${SUDO_USER:-$USER}
if [ "$CURRENT_USER" != "root" ] && [ -n "$CURRENT_USER" ]; then
    usermod -aG docker "$CURRENT_USER"
    log_success "已将用户 $CURRENT_USER 添加到 docker 组"
    log_warning "请重新登录以使权限生效"
fi

# 验证 Docker 安装
log_info "========== 验证 Docker 安装 =========="
docker --version
docker info > /dev/null 2>&1 && log_success "Docker 运行正常" || log_error "Docker 运行异常"

if docker compose version &> /dev/null; then
    docker compose version
    log_success "Docker Compose 可用"
elif command -v docker-compose &> /dev/null; then
    docker-compose --version
    log_success "Docker Compose 可用"
else
    log_error "Docker Compose 不可用"
    exit 1
fi