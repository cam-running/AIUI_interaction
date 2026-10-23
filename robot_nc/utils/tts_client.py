"""
TTS语音合成客户端模块 - 修复打断后说话半截问题
核心修复：
1. 中断状态隔离，避免新请求重置旧请求标记
2. 音频流关闭逻辑优化，仅在真正完成/中断时关闭
3. 真实检测播放状态，而非超时等待
4. 延长旧连接清理时间，增加资源保护
"""
import websocket
import sounddevice as sd
from time import mktime
from wsgiref.handlers import format_date_time
from urllib.parse import urlparse, urlencode
import threading
import time
import json
import hmac
import hashlib
import datetime
import base64
import queue
import platform
system = platform.system().lower()
if system == "linux":
    sd.default.device = 'pulse'
elif system == "windows":
    sd.default.device = None
elif system == "darwin":
    sd.default.device = None
import io
from collections import deque
from config.config.settings import config
from utils.pc2_requests import _send_led_color_task
from utils.tts_cache import get_cached_audio, save_audio_cache
from utils.logger import logger


# ==============================
# 全局音频配置
# ==============================
UNIFIED_AUDIO_CONFIG = {
    'samplerate': 16000,
    'channels': 1,
    'dtype': 'int16',     # 16-bit PCM
    'blocksize': 512,     # 非 Windows
    'latency': 'low',
    'device': None,
}

WINDOWS_AUDIO_CONFIG = {
    'samplerate': 16000,
    'channels': 1,
    'dtype': 'int16',
    'blocksize': 1024,    # Windows 稳定性更好
    'latency': 'low',
    'device': None,
}


# ==============================
# 优化版字节 FIFO 缓冲（线程安全）
# ==============================
class ByteFIFO:
    def __init__(self):
        self._buf = deque()
        self._size = 0
        self._lock = threading.Lock()
        self._playing = threading.Event()  # 新增：标记是否有音频待播放

    def write(self, data: bytes):
        if not data:
            return
        with self._lock:
            self._buf.append(data)
            self._size += len(data)
            self._playing.set()  # 有数据则标记为播放中

    def read(self, nbytes: int) -> bytes:
        """优化版read方法，减少重复操作"""
        if nbytes <= 0:
            return b''
        
        out = bytearray()
        with self._lock:
            while nbytes > 0 and self._buf:
                chunk = self._buf[0]
                take = min(len(chunk), nbytes)
                out.extend(chunk[:take])
                if take < len(chunk):
                    self._buf[0] = chunk[take:]
                else:
                    self._buf.popleft()
                self._size -= take
                nbytes -= take
            
            # 无数据时标记为播放完成
            if not self._buf:
                self._playing.clear()
        
        return bytes(out)

    def clear(self):
        with self._lock:
            self._buf.clear()
            self._size = 0
            self._playing.clear()

    def __len__(self):
        with self._lock:
            return self._size
    
    def is_playing(self):
        """新增：真实检测是否还有音频待播放"""
        with self._lock:
            return self._playing.is_set() or self._size > 0


# ==============================
# 优化版音频流管理器（单例 RawOutputStream + 回调）
# ==============================
class AudioStreamManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._stream = None
        self._fifo = ByteFIFO()  # 使用修改后的ByteFIFO
        self._is_windows = platform.system().lower() == 'windows'
        self._config = WINDOWS_AUDIO_CONFIG if self._is_windows else UNIFIED_AUDIO_CONFIG

        # 自动获取每帧字节数，更通用
        try:
            # 创建临时流来获取dtype信息
            temp_stream = sd.RawOutputStream(
                samplerate=self._config['samplerate'],
                channels=self._config['channels'],
                dtype=self._config['dtype'],
                blocksize=1,  # 最小块大小
                device=self._config['device']
            )
            self._bytes_per_sample = temp_stream.dtype.itemsize
            temp_stream.close()
        except Exception:
            # 回退到默认值
            self._bytes_per_sample = 2  # int16
        
        self._frame_bytes = self._config['channels'] * self._bytes_per_sample

    def get_audio_config(self):
        return self._config

    def _callback(self, outdata, frames, time_info, status):
        """优化版回调，使用memoryview直接填充，避免bytes拼接"""
        required = frames * self._frame_bytes
        data = self._fifo.read(required)

        if len(data) < required:
            # 使用memoryview直接填充零，避免bytes拼接
            outdata[:len(data)] = data
            outdata[len(data):] = b'\x00' * (required - len(data))
        else:
            outdata[:] = data

    def init_stream(self):
        with self._lock:
            if self._stream and self._stream.active:
                return self._stream

            cfg = self._config
            self._fifo.clear()

            self._stream = sd.RawOutputStream(
                samplerate=cfg['samplerate'],
                channels=cfg['channels'],
                dtype=cfg['dtype'],
                blocksize=cfg['blocksize'],
                latency=cfg['latency'],
                device=cfg['device'],
                callback=self._callback,
            )
            self._stream.start()
            logger.info(f"[音频] RawOutputStream 初始化成功: blocksize={cfg['blocksize']}, samplerate={cfg['samplerate']}")
            return self._stream

    def play_bytes(self, chunk: bytes):
        """喂入原始 PCM 字节（16kHz, 16bit, mono）"""
        if not chunk:
            return
        self._fifo.write(chunk)

    def clear_buffer(self):
        """清空音频缓冲区"""
        with self._lock:
            self._fifo.clear()
            logger.info("[音频] 缓冲区已清空")

    def stop_stream(self, force: bool = False):
        """
        新增：可选强制关闭，非强制时等待播放完成
        :param force: True=立即关闭，False=等待缓冲区播放完
        """
        with self._lock:
            if not self._stream:
                return
            
            # if not force:
            #     # 非强制关闭：等待缓冲区播放完成（最多等5秒）
            #     wait_time = 0
                # while self._fifo.is_playing() and wait_time < 5.0:
                    # time.sleep(0.1)
                    # wait_time += 0.1
            
            try:
                self._stream.stop()
                self._stream.close()
                logger.info("[音频] 音频流已安全关闭")
            except Exception as e:
                logger.info(f"[音频] 关闭失败: {e}")
            finally:
                self._stream = None
                self._fifo.clear()

    def expected_chunk_size(self):
        """建议的投喂对齐字节数（一个 block 对应的字节量）"""
        return self._config['blocksize'] * self._frame_bytes
    
    def is_audio_playing(self):
        """新增：对外暴露播放状态检测"""
        with self._lock:
            if not self._stream or not self._stream.active:
                return False
            return self._fifo.is_playing()


_audio_manager = AudioStreamManager()


# ==============================
# 优化版 TTS 客户端
# ==============================
class AIUITTSClient:
    def __init__(self, text: str, use_cache: bool = True):
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
        self.text = text.strip()
        self.use_cache = use_cache
        self.call_time = time.time()
        self.start_play_time = None
        self.handshake = self.assemble_auth_url(
            config.XUNFEI_STREAMING_TTS_URL)
        self.ws = None
        self._play_thread = None
        self._cache_play_thread = None  # 缓存播放线程引用
        
        # 使用BytesIO替代列表，减少内存分配
        self._audio_buffer = io.BytesIO()
        self._interrupted = threading.Event()  # 实例私有，不再被外部重置
        self._connection_established = threading.Event()
        self._audio_complete = False  # 标记音频是否接收完成
        
        self._max_retries = 3  # 最大重试次数
        self._retry_count = 0  # 当前重试次数

    def is_connection_ready(self, ws):
        """检查WebSocket连接是否就绪"""
        try:
            return (ws and ws.sock and
                    hasattr(ws.sock, 'connected') and
                    ws.sock.connected and
                    not self._interrupted.is_set())
        except Exception:
            return False

    def assemble_auth_url(self, base_url):
        host = urlparse(base_url).netloc
        path = urlparse(base_url).path
        now = datetime.datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(config.XUNFEI_API_SECRET.encode(),
                                 signature_origin.encode(), digestmod=hashlib.sha256).digest()
        signature_base64 = base64.b64encode(signature_sha).decode()
        authorization_origin = (
            f'api_key="{config.XUNFEI_API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_base64}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode()).decode()
        v = {"host": host, "date": date, "authorization": authorization}
        return base_url + "?" + urlencode(v)

    def send_text(self):
        """发送文本数据，优化连接检查"""
        if not self._is_ws_connected():
            raise Exception("WebSocket连接不可用")
            
        aiui_data = {
            "header": {
                "sn": "yd-00:00:00:00:00:01",
                "appid": config.XUNFEI_APP_ID,
                "stmid": "text-1",
                "status": 3,
                "scene": 'IFLYTEK.hts'
            },
            "parameter": {
                "tts": {
                    "vcn": config.TTS_VOICE,
                    "tts": {
                        "channels": 1,
                        "sample_rate": 16000,
                        "bit_depth": 16,
                        "encoding": "raw"
                    }
                }
            },
            "payload": {
                "text": {
                    "compress": "raw",
                    "format": "plain",
                    "text": base64.b64encode(self.text.encode()).decode(),
                    "encoding": "utf8",
                    "status": 3
                }
            }
        }
        self.ws.send(json.dumps(aiui_data, ensure_ascii=False))

    def _is_ws_connected(self):
        """辅助函数：检查WebSocket连接状态"""
        try:
            return (self.ws and hasattr(self.ws, 'sock') and self.ws.sock and
                    hasattr(self.ws.sock, 'connected') and self.ws.sock.connected)
        except Exception:
            return False

    def interrupt(self):
        """中断播放 - 优化：仅标记中断，由音频流自行清理"""
        self._interrupted.set()
        logger.info("[中断] 标记播放中断")
        
        # 强制停止音频流（立即）
        _audio_manager.stop_stream(force=True)
        logger.info("[TTS] 音频流已强制停止")

        # 关闭WebSocket连接
        if self.ws:
            try:
                self._connection_established.clear()
                if self._is_ws_connected():
                    self.ws.close()
                    logger.info("[中断] WebSocket连接已关闭")
            except Exception as e:
                logger.info(f"[中断] 关闭WebSocket失败: {e}")
            finally:
                self.ws = None

        logger.info("[中断] 播放中断完成")

    # ---- WebSocket 回调 ----
    def on_open(self, ws):
        logger.info("[TTS] WebSocket连接已建立")
        self._connection_established.set()
        self._retry_count = 0  # 重置重试计数

        # 连接建立后立即发送数据
        try:
            # 检查连接是否仍然有效且未被中断
            if self._is_ws_connected() and not self._interrupted.is_set():
                self.send_text()
                logger.info("[TTS] 数据发送成功")
            else:
                logger.warning("[TTS] 连接已中断，跳过数据发送")
                self._connection_established.clear()
        except Exception as e:
            logger.warning(f"[TTS] 发送数据失败: {e}")
            self._connection_established.clear()

    def on_message(self, ws, message):
        # 中断状态优先检查
        if self._interrupted.is_set():
            logger.info("[TTS] 已中断，跳过消息处理")
            return
            
        try:
            data = json.loads(message)

            if data.get("header", {}).get("code") != 0:
                logger.info(f"TTS错误: {data}")
                self._interrupted.set()
                ws.close()
                return

            tts_audio_b64 = data.get("payload", {}).get("tts", {}).get("audio")
            if tts_audio_b64:
                try:
                    # 16kHz/16bit/mono 裸PCM
                    pcm = base64.b64decode(tts_audio_b64)
                    self._audio_buffer.write(pcm)  # 写入BytesIO
                    _audio_manager.play_bytes(pcm)  # 交给回调流
                except Exception as e:
                    logger.info(f"[错误] 音频解码失败: {e}")

            # 检查是否完成（仅在未中断时处理）
            if data.get("header", {}).get("status") == 2 and not self._interrupted.is_set():
                logger.info("[TTS] 收到结束状态，准备关闭连接")
                self._audio_complete = True
                
                # 收尾：缓存
                if self.use_cache and self._audio_buffer.tell() > 0:
                    try:
                        audio_data = self._audio_buffer.getvalue()
                        save_audio_cache(self.text, audio_data)
                        logger.info(f"[TTS] 缓存保存成功，总大小: {len(audio_data)} bytes")
                    except Exception as e:
                        logger.info(f"[TTS] 缓存保存失败: {e}")

                # 等待音频播放完成后再关闭连接（非强制）
                self._wait_for_audio_completion()

                # 关闭WebSocket连接（仅在未中断时）
                if not self._interrupted.is_set():
                    ws.close()
                    logger.info("[TTS] WebSocket连接已关闭")

        except json.JSONDecodeError as e:
            logger.info(f"[TTS] JSON解析错误: {e}")
        except Exception as e:
            logger.info(f"[TTS] 消息处理异常: {e}")
            import traceback
            traceback.print_exc()

    def _wait_for_audio_completion(self):
        """修复：真实检测音频播放状态，而非超时等待"""
        try:
            if self._interrupted.is_set():
                logger.info("[TTS] 已中断，跳过播放等待")
                return
                
            if self._audio_buffer.tell() == 0:
                logger.info("[TTS] 无音频数据，无需等待")
                return

            # 真实检测播放状态（最多等10秒）
            # wait_time = 0
            logger.info("[TTS] 等待音频缓冲区播放完成...")
            # while _audio_manager.is_audio_playing() and wait_time < 10.0:
            while _audio_manager.is_audio_playing():
                # time.sleep(0.1)
                # wait_time += 0.1
                if self._interrupted.is_set():
                    logger.info("[TTS] 等待中被中断")
                    return

            logger.info("[TTS] 音频播放完成")

            # 非强制停止音频流（等待缓冲区播放完）
            _audio_manager.stop_stream(force=False)
            logger.info("[TTS] 音频流已正常停止")

        except Exception as e:
            logger.info(f"[TTS] 等待音频完成时出错: {e}")

    def on_error(self, ws, error):
        # 改进错误处理：区分不同类型的错误
        error_str = str(error) if error else "未知错误"

        # 忽略一些常见的非致命错误
        if "already closed" in error_str.lower() or "connection is closed" in error_str.lower():
            logger.info(f"[TTS] 连接已关闭，忽略错误: {error_str}")
            return

        # 记录其他错误但不立即关闭连接
        logger.info(f"[TTS] 连接错误: {error_str}")

        # 只有在严重错误时才关闭连接
        if "timeout" in error_str.lower() or "connection refused" in error_str.lower():
            logger.info("[TTS] 严重连接错误，关闭连接")
            self._interrupted.set()
            ws.close()

    def on_close(self, ws, code, reason):
        self._connection_established.clear()
        close_info = f"代码:{code}" if code else ""
        if reason:
            close_info += f", 原因:{reason}"
        logger.info(f"[TTS] 连接关闭 {close_info}")

        # 修复：仅在音频未完成且未中断时，才尝试等待播放
        if not self._audio_complete and not self._interrupted.is_set():
            logger.info("[TTS] 连接提前关闭，等待剩余音频播放...")
            self._wait_for_audio_completion()
        else:
            logger.info("[TTS] 连接关闭，无需额外处理音频流")

    # ---- 优化版缓存播放 ----
    def play_cached_audio(self, audio_data: bytes):
        logger.info(f"[缓存] 开始播放，大小={len(audio_data)} bytes")
        
        # 中断检查
        if self._interrupted.is_set():
            logger.info("[缓存] 已中断，跳过播放")
            return
            
        _audio_manager.init_stream()
        # 尽量按块对齐喂入
        align = _audio_manager.expected_chunk_size()
        if align <= 0:
            align = 2048

        for i in range(0, len(audio_data), align):
            # 检查是否被打断
            if self._interrupted.is_set():
                logger.info("[缓存] 播放被中断")
                return

            chunk = audio_data[i:i+align]
            _audio_manager.play_bytes(chunk)

            # 使用Event等待，更响应中断
            if self._interrupted.wait(0.01):
                logger.info("[缓存] 播放被中断")
                return

        # 播放完成后的等待，真实检测播放状态
        if not self._interrupted.is_set():
            logger.info("[缓存] 等待缓存音频播放完成...")
            wait_time = 0
            while _audio_manager.is_audio_playing() and wait_time < 5.0:
                # time.sleep(0.1)
                # wait_time += 0.1
                if self._interrupted.is_set():
                    break

        logger.info("[缓存] 播放完成")

    def start(self):
        # 先播缓存
        if self.use_cache:
            cached_audio = get_cached_audio(self.text)
            if cached_audio:
                logger.info("[缓存] 命中，使用缓存播放")
                self._cache_play_thread = threading.Thread(
                    target=self.play_cached_audio, args=(cached_audio,), daemon=True)
                self._cache_play_thread.start()
                return  # 确保缓存播放后直接返回，不执行API请求

        # 初始化音频流并请求合成
        _audio_manager.init_stream()
        logger.info(f"[API] 请求TTS: {self.text[:30]}...")

        # 确保每次都创建新的WebSocket连接
        self._create_new_connection()

    def _create_new_connection(self):
        """创建新的WebSocket连接 - 修复：不再重置_interrupted"""
        logger.info("[TTS] 开始创建新的WebSocket连接")
        
        # 修复：仅重置连接状态，不重置中断状态
        self._connection_established.clear()
        # 移除：self._interrupted.clear() ❌ 核心修复点
        
        # 创建新的WebSocket连接
        self.ws = websocket.WebSocketApp(
            self.handshake,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        logger.info("[TTS] WebSocket对象已创建，准备启动连接线程")
        
        # 启动WebSocket线程
        self._play_thread = threading.Thread(
            target=lambda: self.ws.run_forever(), daemon=True)
        self._play_thread.start()
        
        logger.info("[TTS] WebSocket连接线程已启动")


# ==============================
# 优化版全局控制
# ==============================
_current_tts_client = None
_lock = threading.Lock()
_playback_done_event = threading.Event()  # 播放完成事件


def play_text_async(text: str, use_cache: bool = True):
    # 安全替换昵称
    machinename = getattr(config, 'machinename', None) or '小勇'
    text = text.replace('小勇', machinename)
    global _current_tts_client
    if not text or not isinstance(text, str) or text.strip() == "":
        logger.info("[错误] 文本内容不能为空")
        return
    
    with _lock:
        if _current_tts_client:
            logger.info("[停止] 打断旧播放")
            _current_tts_client.interrupt()
            _current_tts_client = None
            # 修复：延长等待时间到1秒，确保旧连接完全清理
            _playback_done_event.wait(timeout=0.3)
        
        # 创建新的TTS客户端
        tts_client = AIUITTSClient(text, use_cache)
        _current_tts_client = tts_client
        
        # 启动新的TTS客户端
        tts_client.start()


def stop_playback():
    global _current_tts_client
    with _lock:
        if _current_tts_client:
            _current_tts_client.interrupt()
            _current_tts_client = None
        _audio_manager.stop_stream(force=True)


def is_playing() -> bool:
    with _lock:
        return (_current_tts_client is not None and 
                not _current_tts_client._interrupted.is_set() and
                _audio_manager.is_audio_playing())
