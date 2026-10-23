#!/usr/bin/env python3
# coding=utf-8
import asyncio
import json
import base64
import threading
import queue
from dataclasses import dataclass
from utils.logger import logger

try:
    import websockets
except ImportError:
    raise RuntimeError("pip install websockets")

@dataclass
class PcmChunk:
    pcm: bytes          # 16k/16bit/mono raw bytes
    vad_status: int     # 1=start 2=continue 3=end
    ts_ms: int = 0      # optional

class WsPcmRecorder:
    """
    连接 WS 服务，接收音频帧（16k int16 mono），以 generator 形式产出 PcmChunk。
    - 支持 text(json + base64) 和 binary(frame header + pcm 或纯 pcm) 两种。
    - 你可以按你的上游协议微调 parse 部分。
    """
    def __init__(self, uri="ws://127.0.0.1:7000/", chunk=2048, reconnect=True):
        self.uri = uri
        self.chunk = chunk
        self.reconnect = reconnect

        self._q = queue.Queue(maxsize=2000)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()

    def read(self):
        """yield PcmChunk"""
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=1.0)
            except queue.Empty:
                continue
            if item is None:
                break
            yield item

    # ---------------- internal ----------------
    def _thread_main(self):
        while not self._stop.is_set():
            try:
                asyncio.run(self._ws_loop())
            except Exception as e:
                logger.error(f"[WsPcmRecorder] ws loop exception: {e}")
            if not self.reconnect or self._stop.is_set():
                break
            logger.warning("[WsPcmRecorder] reconnect in 1s ...")
            self._stop.wait(1.0)

    async def _ws_loop(self):
        logger.info(f"[WsPcmRecorder] connect {self.uri}")
        async with websockets.connect(self.uri, ping_interval=20, ping_timeout=20) as ws:
            logger.info("[WsPcmRecorder] connected")
            while not self._stop.is_set():
                msg = await ws.recv()

                # 1) binary: 直接认为是 pcm（或你可扩展成带 header）
                if isinstance(msg, (bytes, bytearray)):
                    # 如果你 binary 是“纯 pcm”，这里就需要外部事件提供 vad_status
                    # 建议：binary 只用于 audio_frame，并在另一个 text JSON 中给 vad_status。
                    # 这里先按“纯 pcm + vad_status=2”兜底。
                    chunk = PcmChunk(pcm=bytes(msg), vad_status=2)
                    self._safe_put(chunk)
                    continue

                # 2) text json
                if isinstance(msg, str):
                    try:
                        j = json.loads(msg)
                    except Exception:
                        logger.warning(f"[WsPcmRecorder] non-json text: {msg[:200]}")
                        continue

                    msg_type = j.get("msg_type") or j.get("type")
                    if msg_type == "wakeup_detail":
                        # 唤醒事件不走 pcm 队列，这里只打日志或转发给上层
                        logger.info(f"[WsPcmRecorder] wakeup: {j.get('params',{})}")
                        continue

                    if msg_type in ("audio_frame", "pcm_frame", "vad_audio"):
                        vad_status = int(j.get("vad_status", 2))
                        ts_ms = int(j.get("ts_ms", 0))
                        # pcm 数据可能放在 base64 字段
                        b64 = j.get("pcm_b64") or j.get("audio_b64") or j.get("data_b64")
                        if not b64:
                            # 也可能你用的是字段 "pcm" 直接字符串（不推荐）
                            logger.warning("[WsPcmRecorder] audio_frame without b64 payload")
                            continue
                        try:
                            pcm = base64.b64decode(b64)
                        except Exception as e:
                            logger.error(f"[WsPcmRecorder] base64 decode failed: {e}")
                            continue

                        self._safe_put(PcmChunk(pcm=pcm, vad_status=vad_status, ts_ms=ts_ms))
                        continue

                    # 其他事件
                    # logger.debug(f"[WsPcmRecorder] ignore msg_type={msg_type}")
                    continue

    def _safe_put(self, item: PcmChunk):
        try:
            self._q.put_nowait(item)
        except queue.Full:
            # 队列满丢弃，保证不阻塞音频链路
            logger.warning("[WsPcmRecorder] queue full, drop frame")
