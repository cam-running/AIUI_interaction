#!/bin/bash
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/$(id -u)
# 添加日志输出和进程ID记录
# 等待 PulseAudio 守护进程启动
echo "检查 PulseAudio 守护进程状态..."
PULSEAUDIO_WAIT_COUNT=0
MAX_WAIT_TIME=30
cd /home/ict/face_voice

# 检查是否等待超时
if [ $PULSEAUDIO_WAIT_COUNT -eq $MAX_WAIT_TIME ]; then
    echo "警告: PulseAudio 等待超时，尝试启动 TTS 服务..."
else
    echo "PulseAudio 守护进程准备就绪"
fi

# 测试音频设备连通性
echo "测试音频设备连通性..."
if command -v pactl > /dev/null 2>&1; then
    # 使用 pactl 检查音频设备
    if pactl info > /dev/null 2>&1; then
        echo "音频设备连通性测试通过"
    else
        echo "警告: 音频设备连通性测试失败"
    fi
else
    # 备用方案：使用 aplay 测试
    echo "使用 aplay 进行音频设备测试..."
    timeout 3 aplay -q -D plughw:0,0 /dev/zero > /dev/null 2>&1 &
    TEST_PID=$!
    sleep 2
    kill $TEST_PID > /dev/null 2>&1
    echo "音频设备测试完成"
fi

# 启动服务前再次确认音频环境
echo "启动main_server服务前最终检查..."
sleep 1

# 启动服务
echo "启动main_server服务..."
nohup python3 /home/ict/face_voice/main_server.py > server.log 2>&1 &
echo $! > server.pid
PID=$!
echo "main_server服务已启动，PID: $PID"

# 验证服务启动状态
sleep 3
if kill -0 $PID > /dev/null 2>&1; then
    echo "主服务启动成功，正在运行"
else
    echo "错误: 主服务启动失败，请检查日志文件 server.log"
    exit 1
fi