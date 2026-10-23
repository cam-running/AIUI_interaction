# core/aiui/ws_recorder.py
# pip install websockets
import asyncio
import json
import base64
import threading
import queue
from typing import Callable, Dict, Generator, Iterable, Optional, Tuple, Any

import websockets

from utils.logger import logger


VadItem = Tuple[int, bytes, Dict[str, Any]]  # (vad_status, pcm_bytes, meta)


def _is_skippable_delim(ch: str) -> bool:
    """
    Some upstream implementations may append control delimiters after JSON,
    or pack multiple JSON objects in one TEXT frame separated by delimiters.

    Skip:
      - ASCII control chars (<= 0x20): includes \x00 \r \n \t and space
      - common record separators: 0x1e (RS), 0x1f (US)
    """
    if not ch:
        return True
    o = ord(ch)
    if o <= 0x20:
        return True
    if o in (0x1e, 0x1f):
        return True
    return False


def iter_json_objects(payload: str) -> Iterable[dict]:
    """
    Parse 1..N JSON objects from a single string payload.

    Handles:
      - '{"a":1}\n{"b":2}\n'
      - '{"a":1}{"b":2}'
      - '{"a":1}\x00{"b":2}\x1e'
    """
    decoder = json.JSONDecoder()
    s = payload
    i = 0
    n = len(s)

    while True:
        # skip whitespace/control delimiters
        while i < n and _is_skippable_delim(s[i]):
            i += 1
        if i >= n:
            return

        try:
            obj, end = decoder.raw_decode(s, i)
        except json.JSONDecodeError as e:
            # If the rest is only delimiters, end quietly
            j = i
            while j < n and _is_skippable_delim(s[j]):
                j += 1
            if j >= n:
                return

            # Otherwise, log a compact warning and stop parsing this frame
            tail_raw = s[i:i + 160]
            tail_vis = (
                tail_raw
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
                .replace("\x00", "\\x00")
                .replace("\x1e", "\\x1e")
                .replace("\x1f", "\\x1f")
            )
            logger.warning(f"[WsVadAudioRecorder] json chunk decode failed at pos={i}: {e}; tail='{tail_vis}'")
            return

        if isinstance(obj, dict):
            yield obj
        i = end


class WsVadAudioRecorder:
    """
    连接 WS 服务，读取 msg_type=vad_audio 的音频帧。
    每次 yield: (vad_status:int, pcm:bytes, meta:dict)

    pcm 是 16k/16bit/mono s16le 的裸 PCM bytes（可直接送 ASR 或写 wav）。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7000,
        path: str = "/",
        reconnect: bool = True,
        max_queue: int = 2000,
        ping_interval: int = 20,
        ping_timeout: int = 20,
        on_wakeup: Optional[Callable[[str], None]] = None,
    ):
        self.uri = f"ws://{host}:{port}{path}"
        self.reconnect = reconnect
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._on_wakeup = on_wakeup

        self._q: "queue.Queue[Optional[VadItem]]" = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._runner, daemon=True)
        self._thread.start()

    def close(self):
        """Stop background thread. Note: this will stop read() generator eventually."""
        self._stop.set()
        # Best-effort to unblock consumers
        self._safe_put(None)

    def read(self) -> Generator[VadItem, None, None]:
        """generator"""
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=1.0)
            except queue.Empty:
                continue
            if item is None:
                break
            yield item

    # ---------------- internal ----------------
    def _runner(self):
        while not self._stop.is_set():
            try:
                asyncio.run(self._loop())
            except Exception as e:
                logger.error(f"[WsVadAudioRecorder] loop exception: {e}")
            if not self.reconnect or self._stop.is_set():
                break
            logger.warning("[WsVadAudioRecorder] reconnect after 1s ...")
            self._stop.wait(1.0)

        # notify consumers
        self._safe_put(None)

    async def _loop(self):
        logger.info(f"[WsVadAudioRecorder] connect: {self.uri}")
        async with websockets.connect(
            self.uri,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
        ) as ws:
            logger.info("[WsVadAudioRecorder] connected")

            while not self._stop.is_set():
                msg = await ws.recv()                

                # Upstream is TEXT JSON. If binary appears, ignore.
                if isinstance(msg, (bytes, bytearray)):
                    continue
                if not isinstance(msg, str) or not msg:
                    continue
                for j in iter_json_objects(msg):
                    msg_type = j.get("msg_type")
                    params = j.get("params") or {}

                    if msg_type != "vad_audio":
                        logger.info("🎤 接收WS发送的文本，播放TTS ,msg:{}".format(msg))

                    # ---------------- wakeup ----------------
                    if msg_type == "wakeup":
                        keyword = params.get("keyword", "")
                        kw_type = params.get("keyword_type", "")
                        start_ms = params.get("start_ms", 0)
                        end_ms = params.get("end_ms", 0)
                        score = params.get("score", 0)
                        threshold = params.get("threshold", 0)
                        boundary = params.get("boundary", "")
                        beam = params.get("beam", -1)
                        physical = params.get("physical", -1)
                        angle = params.get("angle", 0)  # wakeup 里通常为 0，你给的原始数据是 0

                        logger.info(
                            f"[PY][WAKEUP] keyword={keyword} type={kw_type} "
                            f"score={score}/{threshold} beam={beam} physical={physical} "
                            f"start={start_ms} end={end_ms} angle={angle} boundary={boundary}"
                        )
                        if self._on_wakeup:
                            try:
                                self._on_wakeup(None)
                            except Exception as e:
                                logger.error(f"[WsVadAudioRecorder] wakeup callback failed: {e}")
                        continue

                    # ---------------- wakeup_detail ----------------
                    if msg_type == "wakeup_detail":
                        keyword = params.get("keyword", "")
                        kw_type = params.get("keyword_type", "")
                        start_ms = params.get("start_ms", 0)
                        end_ms = params.get("end_ms", 0)
                        score = params.get("score", 0)
                        threshold = params.get("threshold", 0)
                        boundary = params.get("boundary", "")
                        beam = params.get("beam", -1)
                        physical = params.get("physical", -1)
                        angle = params.get("angle", 0)   # 重点字段：277
                        power = params.get("power", 0.0)
                        snr = params.get("snr", 0.0)
                        power_td = params.get("power_td", 0.0)

                        logger.info(
                            f"[PY][WAKEUP_DETAIL] angle={angle}° "
                            f"keyword={keyword} type={kw_type} "
                            f"score={score}/{threshold} beam={beam} physical={physical} "
                            f"start={start_ms} end={end_ms} power={power:.2f} snr={snr:.2f} power_td={power_td:.2f} "
                            f"boundary={boundary}"
                        )
                        continue

                    # ---------------- vad_audio (原有逻辑) ----------------
                    if msg_type != "vad_audio":
                        continue

                    # 下面保持你现有的 vad_audio 解码逻辑不变
                    try:
                        vad_status = int(j.get("vad_status", -1))
                        sr = int(j.get("sample_rate", 16000))
                        fmt = (j.get("format", "s16le") or "").lower()
                        b64 = j.get("pcm_b64", "")

                        if not b64:
                            continue

                        if sr != 16000:
                            logger.warning(f"[WsVadAudioRecorder] sample_rate={sr} (expect 16000)")
                        if fmt != "s16le":
                            logger.warning(f"[WsVadAudioRecorder] format={fmt} (expect s16le)")

                        pcm = base64.b64decode(b64, validate=False)
                        if not pcm:
                            continue
                    except Exception as e:
                        logger.error(f"[WsVadAudioRecorder] parse vad_audio failed: {e}")
                        continue

                    meta = {
                        "channel": j.get("channel", -1),
                        "ts_ms": j.get("ts_ms", 0),
                        "sample_rate": sr,
                        "format": fmt,
                    }
                    self._safe_put((vad_status, pcm, meta))


    def _safe_put(self, item: Optional[VadItem]):
        try:
            self._q.put_nowait(item)
        except queue.Full:
            # For realtime audio, dropping frames is better than blocking indefinitely.
            logger.warning("[WsVadAudioRecorder] queue full, drop frame")
            # Optional improvement (if you prefer): drop oldest then put newest
            # try:
            #     _ = self._q.get_nowait()
            #     self._q.put_nowait(item)
            # except Exception:
            #     pass
