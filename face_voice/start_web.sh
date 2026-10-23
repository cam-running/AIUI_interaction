#!/bin/bash
cd /home/ict/face_voice
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/$(id -u)

LOG_FILE="/home/ict/face_voice/web5.log"
echo "Starting service at $(date)" >> "$LOG_FILE"
#nohup /home/ict/face_voice/Redcse/face_web > "$LOG_FILE" 2>&1 &
nohup python3 /home/ict/face_voice/Redcse/web.py > "$LOG_FILE" 2>&1 &
echo $! > /home/ict/face_voice/web.pid
