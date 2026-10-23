#!/bin/bash
# Ubuntu 系统配置全面查看脚本 (兼容 x86 + ARM/Mali/RKNPU)

echo "================ 系统信息 ================"
echo "主机名: $(hostname)"
echo "操作系统: $(lsb_release -d | cut -f2)"
echo "内核版本: $(uname -r)"
echo "系统架构: $(uname -m)"
echo "运行时间: $(uptime -p)"
echo "登录用户: $(who | awk '{print $1}' | sort | uniq)"

echo
echo "================ CPU 信息 ================"
lscpu | egrep "Model name|Socket|Thread|Core|CPU MHz|CPU max MHz|CPU min MHz"

echo
echo "================ 内存信息 ================"
free -h
echo
echo "内存条详情:"
if command -v dmidecode &> /dev/null; then
    sudo dmidecode -t memory | egrep "Size:|Speed:|Manufacturer:|Part Number" | grep -v "No Module Installed"
else
    echo "dmidecode 未安装，无法读取详细内存条信息 (适用于 PC/服务器)"
fi

echo
echo "================ 硬盘信息 ================"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
echo
echo "磁盘使用情况:"
df -hT | grep -E "^/dev/"

echo
echo "================ 网络信息 ================"
ip addr show | egrep "^[0-9]|inet "
echo
echo "路由表:"
ip route show
echo
echo "DNS 配置:"
grep "nameserver" /etc/resolv.conf

echo
echo "================ GPU/NPU 信息 ================"
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "检测到 NVIDIA GPU:"
    nvidia-smi
elif ls /dev/mali* >/dev/null 2>&1; then
    echo "检测到 Mali GPU:"
    ls /dev/mali*
    dmesg | grep -i mali | head -n 10
elif [ -d /sys/class/rknpu ]; then
    echo "检测到 Rockchip NPU:"
    cat /sys/class/rknpu/*/info 2>/dev/null
elif command -v lshw >/dev/null 2>&1; then
    echo "检测到其他显卡 (lshw 显示):"
    sudo lshw -C display
else
    echo "未检测到独立 GPU/NPU，可能为集成显卡或无 GPU 设备"
fi


echo
echo "================ 主板与BIOS ================"
if command -v dmidecode >/dev/null 2>&1; then
    echo "--- 主板 ---"
    sudo dmidecode -t baseboard | egrep "Manufacturer|Product|Version|Serial"
    echo "--- BIOS ---"
    sudo dmidecode -t bios | egrep "Vendor|Version|Release"
else
    echo "dmidecode 未安装或 ARM 平台限制，尝试读取 /proc/device-tree:"
    if [ -d /proc/device-tree ]; then
        model=$(tr -d '\0' </proc/device-tree/model 2>/dev/null)
        compatible=$(tr -d '\0' </proc/device-tree/compatible 2>/dev/null)
        echo "设备型号: ${model:-未知}"
        echo "兼容信息: ${compatible:-未知}"
        if [ -f /proc/device-tree/serial-number ]; then
            echo "序列号: $(tr -d '\0' </proc/device-tree/serial-number)"
        fi
    else
        echo "未找到 /proc/device-tree，无法获取主板信息"
    fi
fi


echo
echo "================ PCI 设备 ================"
if command -v lspci &> /dev/null; then
    lspci -nn
else
    echo "lspci 工具未安装或 ARM 平台无 PCI 设备"
fi

echo
echo "================ USB 设备 ================"
lsusb

echo
echo "================ 电池与电源 (若有) ================"
upower -i $(upower -e | grep BAT 2>/dev/null) 2>/dev/null || echo "无电池信息"

echo
echo "================ 温度/传感器信息 ================"
if command -v sensors &> /dev/null; then
    sensors
else
    echo "未安装 lm-sensors，可通过 'sudo apt install lm-sensors' 获取"
fi

echo
echo "================ 内核模块 ================"
lsmod | head -20

echo
echo "================ 服务与端口 ================"
sudo ss -tuln

echo
echo "================ 进程与负载 ================"
echo "前 10 个占用 CPU 的进程:"
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 11
echo
echo "前 10 个占用内存的进程:"
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -n 11

echo
echo "================ 内核与驱动详细信息 ================"
uname -a
lsmod | wc -l | xargs echo "已加载内核模块数:"

echo
echo "================ 网络连通性测试 ================"


# 公网测试
echo "Ping 百度 (www.baidu.com) ..."
ping -c 4 www.baidu.com

echo "Ping 科大讯飞 (aiui.openspeech.cn) ..."
ping -c 4 aiui.openspeech.cn

# 中国科技大学测试
echo "Ping 中国科技大学 (www.ustc.edu.cn) ..."
ping -c 4 www.ustc.edu.cn

echo
echo "================ 网络测速 ================"
if command -v speedtest-cli >/dev/null 2>&1; then
    echo "正在测试带宽..."
    speedtest-cli
else
    echo "未安装 speedtest-cli，可通过 'sudo apt install speedtest-cli' 安装"
fi
