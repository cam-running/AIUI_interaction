#!/usr/bin/python
# coding=utf-8

import platform
import struct
import threading
import numpy as np
import platform
import socket
import sounddevice as sd

system = platform.system().lower()
if system == "linux":
    sd.default.device = 'pulse'
elif system == "windows":
    sd.default.device = None
elif system == "darwin":
    sd.default.device = None
from contextlib import contextmanager
from utils.echo_cancellation import get_self_voice_detector
from utils.logger import logger


def calc_rms(audio_bytes: bytes) -> float:
    """计算音频数据的 RMS 值"""
    if not audio_bytes:
        return 0
    samples = struct.unpack(f'{len(audio_bytes) // 2}h', audio_bytes)
    arr = np.array(samples, dtype=np.int16)

    # 避免数值溢出和无效值
    if len(arr) == 0:
        return 0

    # 使用更安全的计算方式，避免大数值溢出
    arr_float = arr.astype(np.float64)
    squared = arr_float ** 2
    mean_squared = np.mean(squared)

    # 检查数值有效性
    if np.isnan(mean_squared) or np.isinf(mean_squared) or mean_squared < 0:
        return 0

    try:
        rms = np.sqrt(mean_squared)
        # 确保结果有效
        if np.isnan(rms) or np.isinf(rms):
            return 0
        return float(rms)
    except (ValueError, RuntimeWarning):
        return 0


class Recorder:
    def __init__(self, chunk: int, channels: int = 1, rate: int = 16000, fmt: str = None):
        self.chunk = chunk
        self.channels = channels
        self.target_rate = rate  # 目标采样率
        self.actual_rate = rate  # 实际使用的采样率
        self.format = fmt or 'int16'
        self.platform = platform.system().lower()

        self.device_index = self._find_device()
        if self.device_index is None:
            raise RuntimeError("❌ 未找到可用的音频输入设备")

        # 语音活动检测
        self.is_voice_active = False
        self.voice_activity_threshold = 80.0
        self.voice_activity_count = 0
        self.voice_activity_lock = threading.RLock()

        # 回声消除
        self.self_voice_detector = get_self_voice_detector()
        self.enable_echo_cancellation = True

        # 音频流状态
        self._stream = None
        self._stream_lock = threading.RLock()
        self._is_running = False

        logger.info(
            f"🎙️ 录音器初始化: 声道={self.channels}, 目标采样率={self.target_rate}, 实际采样率={self.actual_rate}, 块大小={self.chunk}")
        logger.info(
            f"   使用设备[{self.device_index}]: {sd.query_devices(self.device_index)['name']}")

        # 如果实际采样率与目标不同，记录警告
        if self.actual_rate != self.target_rate:
            logger.warning(
                f"⚠️ 采样率不匹配: 目标={self.target_rate}Hz, 实际={self.actual_rate}Hz")

    # ----------------- 设备相关 -----------------
    def _find_device(self):
        """自动查找合适的音频输入设备"""
        devices = [
            (i, d) for i, d in enumerate(sd.query_devices())
            if d.get("max_input_channels", 0) > 0
        ]
        if not devices:
            return None

        # logger.info("使用rockchip-es8388")
        # Ubuntu环境下的设备优先级
        if platform.system().lower() == 'linux':
            # priority = ["Loostone PureMic U7-K"]
            priority = ["pulse", "default", "sysdefault",
                        "Loostone PureMic U7-K"]
            # priority = ["rockchip-es8388"，"AIUI-USB-MC","pulse", "default", "sysdefault"]
        else:
            # Windows环境下的设备优先级
            priority = ["Loostone PureMic U7-K", "rockchip-es8388",
                        "USB Audio", "sysdefault"]

        # 按优先级排序
        devices.sort(
            key=lambda x: next(
                (i for i, p in enumerate(priority)
                 if p.lower() in x[1]["name"].lower()),
                999
            )
        )
        
        # 在Ubuntu环境中，优先测试PulseAudio设备
        for idx, dev in devices:
            if self._check_sample_rate_support(idx, self.target_rate):
                logger.info(f"📍 选择输入设备: {dev['name']} ({idx})")
                self.actual_rate = self.target_rate
                return idx

        # 如果没有找到支持目标采样率的设备，尝试使用默认设备
        logger.warning(f"⚠️ 未找到支持 {self.target_rate}Hz 的设备，尝试使用默认设备")
        for idx, dev in devices:
            try:
                # 尝试使用默认采样率
                default_rate = int(dev.get('default_samplerate', 44100))
                if self._check_sample_rate_support(idx, default_rate):
                    logger.info(
                        f"📍 使用默认采样率设备: {dev['name']} ({idx}) - {default_rate}Hz")
                    self.actual_rate = default_rate
                    return idx
            except Exception as e:
                logger.debug(f"设备 {idx} 测试失败: {e}")
                continue

        # 最后选择第一个可用设备
        if devices:
            logger.warning(
                f"⚠️ 使用第一个可用设备: {devices[0][1]['name']} ({devices[0][0]})")
            # 尝试使用设备的默认采样率
            default_rate = int(devices[0][1].get('default_samplerate', 44100))
            self.actual_rate = default_rate
            return devices[0][0]

        return None

    def _check_sample_rate_support(self, device_index, target_rate):
        """检查设备是否支持目标采样率"""
        try:
            stream = sd.RawInputStream(
                samplerate=target_rate,
                channels=self.channels,
                dtype=self.format,
                blocksize=self.chunk,
                device=device_index
            )
            stream.close()
            return True
        except Exception as e:
            logger.warning(f"设备 {device_index} 不支持 {target_rate}Hz: {e}")
            return False

    # ----------------- 音频流管理 -----------------
    @contextmanager
    def audio_stream(self):
        """上下文管理器，自动开启/关闭音频流"""
        try:
            self._stream = sd.RawInputStream(
                samplerate=self.actual_rate,  # 使用实际采样率
                channels=self.channels,
                dtype=self.format,
                blocksize=self.chunk,
                device=self.device_index
            )
            self._stream.start()
            self._is_running = True
            logger.info(f"✅ 音频流已启动 (采样率: {self.actual_rate}Hz)")
            yield self._stream
        finally:
            self._close_stream()

    def _close_stream(self):
        """安全关闭音频流"""
        try:
            if self._stream:
                if hasattr(self._stream, 'stop'):
                    self._stream.stop()
                if hasattr(self._stream, 'close'):
                    self._stream.close()
                logger.debug("🔄 音频流已关闭")
        except Exception as e:
            logger.warning(f"⚠️ 关闭音频流异常: {e}")
        finally:
            self._stream = None
            self._is_running = False

    # ----------------- 核心录音逻辑 -----------------
    def _voice_activity_update(self, rms: float):
        """更新语音活动检测状态"""
        with self.voice_activity_lock:
            if rms > self.voice_activity_threshold:
                self.voice_activity_count += 1
                if self.voice_activity_count >= 2:
                    self.is_voice_active = True
            else:
                self.voice_activity_count = 0
                self.is_voice_active = False

    def read(self):
        """读取音频流，生成器返回音频块"""
        with self._stream_lock:
            with self.audio_stream() as stream:
                frame_count = 0
                buffer = b''

                while self._is_running and stream:
                    try:
                        data, _ = stream.read(self.chunk)
                        buffer += data

                        while len(buffer) >= self.chunk:
                            chunk_data, buffer = buffer[:self.chunk], buffer[self.chunk:]

                            # 回声消除
                            if self.enable_echo_cancellation and self.self_voice_detector:
                                if not self.self_voice_detector.process_recording_audio(chunk_data):
                                    continue

                            # RMS 计算 & VAD
                            if frame_count % 100 == 0:
                                rms = calc_rms(chunk_data)
                                self._voice_activity_update(rms)
                                logger.debug(
                                    f"🎚️ RMS: {rms:.2f}, 语音活动={self.is_voice_active}")

                            yield chunk_data
                            frame_count += 1
                    except Exception as e:
                        logger.error(f"❌ 音频读取异常: {e}")
                        break

    # ----------------- 控制接口 -----------------
    def close(self):
        """完全关闭录音器"""
        with self._stream_lock:
            logger.info("🔄 关闭录音器...")
            self._close_stream()
            logger.info("✅ 录音器已关闭")

    def stop_recording(self):
        """停止录音但保留设备"""
        with self._stream_lock:
            logger.info("🛑 停止录音...")
            self._close_stream()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class SpmRecorder:
    def __init__(
        self,
        chunk: int,
        rate: int = 16000,
        host: str = "127.0.0.1",
        port: int = 7000,
        fmt: str = "int16",
    ):
        self.chunk = chunk
        self.channels = 1
        self.target_rate = rate
        self.actual_rate = rate
        self.format = fmt

        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._buffer: bytes = b""
        self._is_running: bool = True
        self._lock = threading.RLock()

        logger.info(
            f"🎧 FrontendRecorder 初始化: host={host}, port={port}, "
            f"chunk={chunk}, rate={rate}, fmt={fmt}"
        )

    def _connect(self) -> None:
        """建立到 SPM 前端的 TCP 连接（如果尚未连接）"""
        if self._sock is not None:
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        self._sock = s
        logger.info(f"🔌 已连接 SPM-NC2: {self.host}:{self.port}")

    def _read_exact(self, n: int) -> bytes:
        """从 socket 精确读取 n 字节，直到读满或连接关闭"""
        assert self._sock is not None
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("🔌 前端连接已关闭")
            data += chunk
        return data

    def read(self):
        """
        生成器：每次 yield 一块长度为 self.chunk 的 PCM 数据（bytes）
        - 协议：uint32_le nsamples + nsamples*2 字节 PCM
        - 格式：int16 小端，单通道，16kHz
        """
        with self._lock:
            self._connect()
            buffer = self._buffer
            try:
                while self._is_running:
                    # 1) 按协议读取一帧：4 字节 nsamples
                    header = self._read_exact(4)
                    (nsamples,) = struct.unpack("<I", header)

                    if nsamples == 0:
                        # 防御式：不应该有 0 帧
                        continue

                    # 2) 读取 nsamples * 2 字节 PCM
                    frame_bytes = self._read_exact(nsamples * 2)

                    # 3) 累积到内部缓冲
                    buffer += frame_bytes

                    # 4) 按 chunk 大小切片输出
                    while len(buffer) >= self.chunk:
                        chunk_data, buffer = buffer[: self.chunk], buffer[self.chunk :]

                        # 这里可以按需打印 RMS 调试
                        # rms = calc_rms(chunk_data)
                        # logger.debug(f"[FRONTEND] frame rms: {rms:.2f}")

                        yield chunk_data
            except Exception as e:
                logger.error(f"❌ FrontendRecorder 读取异常: {e}")
            finally:
                # 保存剩余缓冲
                self._buffer = buffer

    def close(self) -> None:
        """关闭连接"""
        self._is_running = False
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        logger.info("🔚 FrontendRecorder 已关闭")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

# ----------------- 调试入口 -----------------
if __name__ == "__main__":
    import time

    recorder = SpmRecorder(chunk=640, host="127.0.0.1", port=7000)

    start = time.time()
    for data in recorder.read():
        # 这里可以写到文件里验证一下数据是否正确：
        with open("/tmp/frontend_chunk.raw", "ab") as f:
            f.write(data)
        if time.time() - start > 5:
            break
    recorder.close()

    # recorder = Recorder(chunk=640)
    # start = time.time()
    # for data in recorder.read():
    #     if time.time() - start > 5:
    #         break
    # recorder.close()
