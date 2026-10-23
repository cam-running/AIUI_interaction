#!/bin/bash

for i in {1..3}; do
    echo "第 $i 次尝试查找并杀死进程..."
    PID=$(ps -ef | grep main_server.py | grep -v grep | awk '{print $2}')

    if [ -n "$PID" ]; then
        echo "找到进程，PID 为 $PID，正在杀死该进程..."
        kill -9 $PID
        echo "进程已杀死。"
    else
        echo "未找到运行中的 main_server.py 进程。"
    fi

    # 每次循环间隔1秒
    sleep 1
done