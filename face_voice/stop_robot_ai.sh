#!/bin/bash
PID=$(ps -ef | grep main_robot.py | grep -v grep | awk '{print $2}')

for i in {1..3}; do
    if [ -n "$PID" ]; then
        echo 
        echo 
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo 
            break
        else
            echo 
        fi
    else
        echo 
        break
    fi
    sleep 1
done  
