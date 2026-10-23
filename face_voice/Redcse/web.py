# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   web.py
# @Time       2025-09-16
# 完整的视频流，稍微有点延迟但CPU占用低
import av
import os
import cv2
import glob
import base64
import uvicorn
import asyncio
import logging
import numpy as np
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("camera_server")

SAVE_DIR = "/home/ict/web_images"
os.makedirs(SAVE_DIR, exist_ok=True)

def find_camera():
    devices = sorted(glob.glob("/dev/video*"))
    for dev in devices:
        try:
            test = av.open(dev, format="v4l2", options={"input_format": "mjpeg"})
            test.close()
            logger.info(f"找到可用摄像头: {dev}")
            return dev
        except Exception as e:
            logger.warning(f"跳过 {dev}, 打开失败: {e}")
    raise RuntimeError("没有找到可用的摄像头设备")

CAM_PATH = find_camera()
container = av.open(CAM_PATH, format="v4l2", options={"input_format": "mjpeg"})

clients = set()
frame_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
latest_frame = None

async def frame_producer():
    """不断读取摄像头帧，覆盖旧帧"""
    global latest_frame
    try:
        for packet in container.demux(video=0):
            frame_bytes = bytes(packet)
            latest_frame = frame_bytes
            # 队列只保留最新一帧
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await frame_queue.put(frame_bytes)
            await asyncio.sleep(0)
    except Exception as e:
        logger.error(f"摄像头读取异常: {e}")

async def frame_broadcaster():
    """低延迟广播帧"""
    while True:
        try:
            frame = await asyncio.wait_for(frame_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue  # 没有新帧则继续循环
        disconnected = set()
        for ws in list(clients):
            try:
                await ws.send_bytes(frame)
            except (WebSocketDisconnect, Exception):
                disconnected.add(ws)
        for ws in disconnected:
            clients.discard(ws)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(frame_producer())
    asyncio.create_task(frame_broadcaster())
    logger.info("摄像头生产者和广播器启动")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/lives")
def index():
    return HTMLResponse("""
    <html>
      <head><title>Camera Live</title></head>
      <body>
        <h1>实时画面（WebSocket MJPEG 低延迟）</h1>
        <button onclick="screenshot()">截图</button>
        <img id="img" width="1280"/>
        <script>
          const ws = new WebSocket("ws://" + location.host + "/ws");
          const img = document.getElementById("img");
          let oldUrl = null;
          ws.binaryType = "arraybuffer";
          ws.onmessage = (evt) => {
              if (oldUrl) URL.revokeObjectURL(oldUrl);
              oldUrl = URL.createObjectURL(new Blob([evt.data], {type: "image/jpeg"}));
              img.src = oldUrl;
          };
          function screenshot() {
              fetch("/capture", {method:"POST"}).then(r => r.text()).then(alert);
          }
        </script>
      </body>
    </html>
    """)

@app.post("/capture")
async def screenshot():
    global latest_frame
    if latest_frame is None:
        return "没有可用帧"
    nparr = np.frombuffer(latest_frame, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return "帧解码失败"
    filename = datetime.now().strftime("%Y%m%d_%H%M%S.jpg")
    path = os.path.join(SAVE_DIR, filename)
    cv2.imwrite(path, img)
    logger.info(f"截图保存: {path}")
    return f"截图已保存: {path}"

@app.get("/camera_base64")
# @app.post("/capture")
async def camera_base64():
    global latest_frame
    if latest_frame is None:
        return JSONResponse({"code": 500, "message": "没有可用帧", "data": {}})
    base64_image = base64.b64encode(latest_frame).decode('utf-8')
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {"base64_content": base64_image, "content_type": "image/jpeg"}
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    logger.info(f"WebSocket 客户端已连接，总数: {len(clients)}")
    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        logger.warning("WebSocket 客户端断开")
    finally:
        clients.discard(websocket)
        await websocket.close()
        logger.info(f"WebSocket 连接关闭，总数: {len(clients)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=34550)
