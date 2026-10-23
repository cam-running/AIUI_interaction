#!/usr/bin/env python3
# pip install websockets
import asyncio
import websockets
import json
import base64
import os
import math
import struct
import subprocess
import threading
from datetime import datetime

OUT_DIR = "./vad_pcm_out"
URI = "ws://127.0.0.1:7000/"

# ===== Beep settings =====
BEEP_SR = 16000           # Hz
BEEP_SEC = 0.5            # seconds
BEEP_FREQ = 1000          # Hz
BEEP_AMP = 0.20           # 0.0~1.0
APLAY_BIN = "/usr/bin/aplay"

# 可选：指定输出设备（例如 "default" / "hw:2,0" / "plughw:2,0"）
APLAY_DEVICE = ""


def new_pcm_path(prefix="vad"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return os.path.join(OUT_DIR, f"{prefix}_{ts}.pcm")


def gen_sine_pcm(sr: int, sec: float, freq: float, amp: float) -> bytes:
    n = int(sr * sec)
    a = max(0.0, min(amp, 1.0)) * 32767.0
    out = bytearray()
    two_pi_f = 2.0 * math.pi * freq
    for i in range(n):
        t = i / sr
        v = int(a * math.sin(two_pi_f * t))
        out += struct.pack("<h", v)
    return bytes(out)


def play_beep_async():
    def _worker():
        try:
            pcm = gen_sine_pcm(BEEP_SR, BEEP_SEC, BEEP_FREQ, BEEP_AMP)
            cmd = [APLAY_BIN, "-q", "-f", "S16_LE", "-r", str(BEEP_SR), "-c", "1"]
            if APLAY_DEVICE:
                cmd += ["-D", APLAY_DEVICE]

            p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                p.stdin.write(pcm)
                p.stdin.flush()
            finally:
                try:
                    p.stdin.close()
                except Exception:
                    pass
            p.wait(timeout=3)
        except Exception as e:
            print(f"[PY][BEEP] WARN: failed to play beep: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _is_skippable_delim(ch: str) -> bool:
    """
    Skip:
      - ASCII control chars (0x00~0x20): includes \0, \r, \n, \t, space, etc.
      - Common record separators sometimes used in streaming logs:
        0x1e (RS), 0x1f (US)
    """
    if not ch:
        return True
    o = ord(ch)
    if o <= 0x20:
        return True
    if o in (0x1e, 0x1f):
        return True
    return False


def iter_json_objects(payload: str):
    """
    Robustly parse 1..N JSON objects from a single string.
    Handles:
      - '{"a":1}\n{"b":2}\n'
      - '{"a":1}{"b":2}'
      - plus trailing control delimiters like '\\x00' or '\\x1e'
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
            # 如果剩余全是可跳过分隔符，则不算错误，直接结束
            j = i
            while j < n and _is_skippable_delim(s[j]):
                j += 1
            if j >= n:
                return

            # 真正的坏数据：打印剩余片段（可见化控制字符）
            tail_raw = s[i:i+200]
            tail_vis = (
                tail_raw
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
                .replace("\x00", "\\x00")
                .replace("\x1e", "\\x1e")
                .replace("\x1f", "\\x1f")
            )
            print(f"[PY] WARN: json chunk decode failed at pos={i}: {e}; tail='{tail_vis}'")
            return

        yield obj
        i = end


class VadCollector:
    def __init__(self):
        self.collecting = False
        self.buf = bytearray()
        self.current_path = None
        self.seg_index = 0

    def _force_finalize_if_needed(self):
        if self.collecting and self.buf:
            fallback_path = self.current_path or new_pcm_path(prefix=f"vad_{self.seg_index:04d}_forced")
            with open(fallback_path, "wb") as f:
                f.write(self.buf)
            print(f"[PY] WARN: forced finalize previous segment -> {fallback_path} ({len(self.buf)} bytes)")

    def handle_vad_audio(self, obj: dict):
        vad_status = int(obj.get("vad_status", -1))
        sr = int(obj.get("sample_rate", 0))
        fmt = obj.get("format", "")

        if sr != 16000 or fmt != "s16le":
            print(f"[PY] WARN: unexpected audio format: sr={sr}, fmt={fmt}, skip")
            return

        pcm_b64 = obj.get("pcm_b64", "")
        if not pcm_b64:
            return

        try:
            chunk = base64.b64decode(pcm_b64, validate=False)
        except Exception as e:
            print("[PY] WARN: base64 decode failed:", e)
            return

        if vad_status == 1:
            self._force_finalize_if_needed()

            self.seg_index += 1
            self.collecting = True
            self.buf = bytearray()
            self.current_path = new_pcm_path(prefix=f"vad_{self.seg_index:04d}")

            self.buf.extend(chunk)
            print(f"[PY] vad_status=1 start segment #{self.seg_index} -> {self.current_path}, +{len(chunk)} bytes")

        elif vad_status == 2:
            if not self.collecting:
                self.seg_index += 1
                self.collecting = True
                self.buf = bytearray()
                self.current_path = new_pcm_path(prefix=f"vad_{self.seg_index:04d}_auto")
                print(f"[PY] WARN: vad_status=2 without start; auto start segment #{self.seg_index} -> {self.current_path}")

            self.buf.extend(chunk)

        elif vad_status == 3:
            if not self.collecting:
                self.seg_index += 1
                self.current_path = new_pcm_path(prefix=f"vad_{self.seg_index:04d}_tailonly")
                self.buf = bytearray()

            self.buf.extend(chunk)

            path = self.current_path or new_pcm_path(prefix=f"vad_{self.seg_index:04d}")
            with open(path, "wb") as f:
                f.write(self.buf)

            print(f"[PY] vad_status=3 end segment #{self.seg_index} -> {path} ({len(self.buf)} bytes)")

            self.collecting = False
            self.buf = bytearray()
            self.current_path = None


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"[PY] connecting {URI}")
    async with websockets.connect(URI, ping_interval=20, ping_timeout=20) as ws:
        print("[PY] connected")

        vad = VadCollector()

        while True:
            raw = await ws.recv()

            if isinstance(raw, (bytes, bytearray)):
                payload = raw.decode("utf-8", errors="replace")
            else:
                payload = raw

            for obj in iter_json_objects(payload):
                msg_type = obj.get("msg_type")

                if msg_type == "wakeup":
                    params = obj.get("params", {})
                    print(
                        f"[PY][WAKEUP] keyword={params.get('keyword','')}, "
                        f"score={params.get('score',None)}, beam={params.get('beam',None)}, physical={params.get('physical',None)}"
                    )
                    play_beep_async()
                    continue

                if msg_type == "wakeup_detail":
                    params = obj.get("params", {})
                    print(
                        f"[PY][WAKEUP_DETAIL] angle={params.get('angle',None)}°, "
                        f"beam={params.get('beam',None)}, physical={params.get('physical',None)}"
                    )
                    continue

                if msg_type == "vad_audio":
                    vad.handle_vad_audio(obj)
                    continue
                # other types ignored


if __name__ == "__main__":
    asyncio.run(main())
