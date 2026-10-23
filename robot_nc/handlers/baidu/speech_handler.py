"""
百度实时语音识别处理模块
"""
from utils.logger import logger
import json
import struct
import os
import threading
import queue
import base64
import requests
import random
import sounddevice as sd
import platform
system = platform.system().lower()
if system == "linux":
    sd.default.device = 'pulse'
elif system == "windows":
    sd.default.device = None
elif system == "darwin":
    sd.default.device = None
from socket import socket, AF_INET, SOCK_STREAM
from websockets.sync.client import connect
from websockets import ConnectionClosedOK
from utils.load_config import load_config


class BaiduSpeechHandler:
    """百度实时语音识别处理类"""

    def __init__(self):
        # 根据文字长度分类的语气助词列表
        self.short_thinking_phrases = [
            "嗯",
            "这个……",
            "嗯……",
        ]

        self.medium_thinking_phrases = [
            "稍等",
            "我想想",
            "等一下",
        ]

        self.long_thinking_phrases = [
            "嗯,我想一想",
            "我琢磨一下",
            "我思考一下",
        ]

        # 加载配置
        self.config = load_config()
        self.baidu_config = self.config.get(
            'speech_recognition', {}).get('baidu_realtime', {})

        # 百度实时语音识别相关
        self.audio_socket = None
        self.baidu_ws = None
        self.play_buffer = queue.Queue()
        self.chatting = threading.Event()
        self.recording = threading.Event()
        self.is_running = False
        self.access_token = None

        # 音频播放相关
        self.output_device = None
        self.audio_stream = None

        # 初始化百度实时语音识别
        self._init_baidu_realtime()

    def _init_baidu_realtime(self):
        """初始化百度实时语音识别"""
        try:
            # 获取百度配置
            client_id = self.baidu_config.get('client_id')
            client_secret = self.baidu_config.get('client_secret')

            if not client_id or not client_secret:
                logger.error("百度配置中缺少client_id或client_secret")
                return

            # 获取access token
            token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}"
            response = requests.get(token_url)
            if response.status_code == 200:
                self.access_token = response.json().get('access_token')
                logger.info("百度实时语音识别初始化成功")
            else:
                logger.error("获取百度access token失败")
                return

        except Exception as e:
            logger.error(f"初始化百度实时语音识别失败: {e}")

    def _init_audio_socket(self):
        """初始化音频Socket连接"""
        try:
            self.audio_socket = socket(AF_INET, SOCK_STREAM)
            server_ip = self.config.get(
                'server', {}).get('ip', '192.168.123.21')
            self.audio_socket.connect((server_ip, 9080))
            logger.info("音频Socket连接建立成功")
            return True
        except Exception as e:
            from utils.tts_client import play_text_async
            play_text_async('讯飞套件连接失败，请检查讯飞套件是否正常', use_cache=True)
            logger.error(f"音频Socket连接失败: {e}")
            return False

    def _recv_all(self, num_byte):
        """接收指定字节数的数据"""
        data = b''
        while len(data) < num_byte:
            packet = self.audio_socket.recv(num_byte - len(data))
            if not packet:
                return None
            data += packet
        return data

    def _process_audio_data(self):
        """处理音频数据"""
        try:
            recv_data = self._recv_all(9)
            if not recv_data:
                return None

            sync_head, user_id, msg_type, msg_length, msg_id = struct.unpack(
                '<BBBIH', recv_data)

            if sync_head == 0xa5 and user_id == 0x01:
                recv_data = self._recv_all(msg_length + 1)
                if recv_data and recv_data[1] == 0:  # 只处理第0路音频
                    audio_data = recv_data[8:-1]
                    return audio_data
            return None
        except Exception as e:
            logger.error(f"处理音频数据异常: {e}")
            return None

    def _process_audio_to_baidu(self):
        """将音频数据发送给百度"""
        try:
            while self.is_running:
                audio_data = self._process_audio_data()
                if audio_data:
                    audio_base64 = base64.b64encode(audio_data).decode()
                    self.baidu_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": audio_base64
                    }))

        except Exception as e:
            logger.error(f"发送音频到百度异常: {e}")

    def _play_audio(self):
        """音频播放线程"""
        try:
            # 获取输出设备 - 修复设备选择逻辑
            try:
                devices = sd.query_devices()
                output_device = None

                # 查找默认输出设备
                for i, device in enumerate(devices):
                    if device['max_outputs'] > 0:  # 有输出能力的设备
                        output_device = i
                        break

                if output_device is None:
                    logger.warning("未找到输出设备，使用默认设备")
                    output_device = None
                else:
                    logger.info(f"使用输出设备: {devices[output_device]['name']}")

            except Exception as e:
                logger.warning(f"设备查询失败，使用默认设备: {e}")
                output_device = None

            # 获取音频配置
            output_audio_config = self.baidu_config.get('output_audio', {})
            sample_rate = output_audio_config.get('sample_rate', 24000)
            channels = output_audio_config.get('channels', 1)

            logger.info(
                f"启动音频播放线程，采样率: {sample_rate}, 声道: {channels}, 设备: {output_device}")

            with sd.RawOutputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype='int16',
                blocksize=1024,
                device=output_device
            ) as stream:
                while self.is_running:
                    try:
                        chunk = self.play_buffer.get(timeout=1)
                        if chunk == 'EOF':
                            break
                        stream.write(chunk)
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logger.error(f"音频播放异常: {e}")
                        break

        except Exception as e:
            logger.error(f"音频播放线程异常: {e}")

    def _start_baidu_realtime(self):
        """启动百度实时语音识别"""
        try:
            if not self.access_token:
                logger.error("百度access token未初始化")
                return False

            # 获取百度配置
            streaming_url = self.baidu_config.get('streaming_url')
            model_name = self.baidu_config.get('model_name', 'audio-realtime')

            url = f'{streaming_url}?model={model_name}&access_token={self.access_token}'

            self.baidu_ws = connect(url)
            self.is_running = True

            # 启动音频播放线程
            play_thread = threading.Thread(target=self._play_audio)
            play_thread.daemon = True
            play_thread.start()

            # 启动接收线程
            receive_thread = threading.Thread(target=self._receive_baidu_data)
            receive_thread.daemon = True
            receive_thread.start()

            # 启动音频处理线程
            audio_thread = threading.Thread(
                target=self._process_audio_to_baidu)
            audio_thread.daemon = True
            audio_thread.start()

            # 更新会话配置 - 确保启用音频输出
            session_config = {
                "type": "session.update",
                "session": {
                    "input_audio_transcription": {
                        "model": "default"
                    },
                    "output_audio": {
                        "format": "pcm16",
                        "sample_rate": 24000
                    },
                    "max_output_tokens": "inf",
                    "voice": "default"
                }
            }

            self.baidu_ws.send(json.dumps(session_config))

            logger.info("百度实时语音识别启动成功")
            return True

        except Exception as e:
            logger.error(f"启动百度实时语音识别失败: {e}")
            return False

    def _handle_baidu_response_done(self, data):
        """处理百度response.done消息"""
        try:
            if 'response' in data:
                response = data['response']
                status = response.get('status', '')
                status_details = response.get('status_details', {})

                logger.info(f"百度响应状态: {status}")

                if status == 'completed':
                    # 正常完成的响应
                    if 'output' in response:
                        output = response['output']
                        for item in output:
                            if item.get('type') == 'message' and 'content' in item:
                                content = item['content']
                                for content_item in content:
                                    if content_item.get('type') == 'audio':
                                        # 处理音频内容
                                        transcript = content_item.get(
                                            'transcript', '')
                                        if transcript:
                                            logger.info(
                                                f"百度识别结果: {transcript}")
                                            # 检查是否有音频数据
                                            if 'audio' in content_item:
                                                audio_data = base64.b64decode(
                                                    content_item['audio'])
                                                self.play_buffer.put(
                                                    audio_data)
                                                logger.info(
                                                    f"从content_item中提取音频数据，大小: {len(audio_data)} 字节")
                                            else:
                                                logger.warning(
                                                    "content_item中没有找到音频数据")

                                            # 直接播放百度返回的音频，不使用TTS
                                            self._play_baidu_audio_response(
                                                response)

                elif status == 'incomplete':
                    # 不完整的响应，可能是内容过滤等原因
                    reason = status_details.get('reason', 'unknown')
                    logger.warning(f"百度响应不完整，原因: {reason}")

                    if reason == 'content_filter':
                        logger.info("内容被过滤，使用TTS播放提示音")
                        # 播放提示音告知用户内容被过滤
                        # play_text_async("抱歉，我无法回答这个问题", use_cache=True)
                    else:
                        logger.warning(f"未知的不完整原因: {reason}")

                else:
                    logger.warning(f"未知的响应状态: {status}")

        except Exception as e:
            logger.error(f"处理百度response.done异常: {e}")

    def _play_baidu_audio_response(self, response):
        """播放百度返回的音频响应"""
        try:
            # 检查响应中是否包含音频数据
            if 'output' in response:
                output = response['output']
                for item in output:
                    if item.get('type') == 'message' and 'content' in item:
                        content = item['content']
                        for content_item in content:
                            if content_item.get('type') == 'audio':
                                # 检查是否有音频数据
                                if 'audio' in content_item:
                                    audio_data = base64.b64decode(
                                        content_item['audio'])
                                    self.play_buffer.put(audio_data)
                                    logger.info(
                                        f"从响应中提取音频数据，大小: {len(audio_data)} 字节")
                                else:
                                    logger.warning("响应中没有找到音频数据")

            logger.info("等待百度音频数据播放...")

        except Exception as e:
            logger.error(f"播放百度音频响应异常: {e}")

    def _receive_baidu_data(self):
        """接收百度返回的数据"""
        try:
            while self.is_running:
                data = self.baidu_ws.recv()
                if isinstance(data, str):
                    data = json.loads(data)

                    # 记录所有消息类型，帮助调试
                    msg_type = data.get('type', 'unknown')
                    logger.info(f"收到百度消息类型: {msg_type}")

                    if data['type'] == 'response.audio.delta':
                        # 处理音频输出 - 这是百度返回的实际音频数据
                        audio = base64.b64decode(data['delta'])
                        self.play_buffer.put(audio)
                        logger.info(f"收到百度音频数据，大小: {len(audio)} 字节")
                        data['delta'] = '...'

                    elif data['type'] == 'response.created':
                        # 清空播放缓冲区
                        while True:
                            try:
                                self.play_buffer.get(block=False)
                            except queue.Empty:
                                break
                        logger.info("清空播放缓冲区，准备接收新的音频")

                    elif data['type'] == 'input_audio_buffer.speech_started':
                        self.chatting.set()
                        logger.info("语音开始")

                    elif data['type'] == 'response.done':
                        self.chatting.clear()
                        logger.info("响应完成")
                        # 处理完整的响应，包括音频数据
                        self._handle_baidu_response_done(data)

                    elif data['type'] == 'input_audio_buffer.speech_ended':
                        # 处理语音识别结果
                        self._handle_baidu_recognition_result(data)
                        logger.info("语音结束")

                    elif data['type'] == 'response.audio':
                        # 处理完整的音频响应
                        logger.info("收到完整的音频响应")
                        if 'audio' in data:
                            audio = base64.b64decode(data['audio'])
                            self.play_buffer.put(audio)
                            logger.info(f"收到完整音频数据，大小: {len(audio)} 字节")

                    elif data['type'] == 'response.text':
                        # 处理文本响应
                        logger.info("收到文本响应")
                        if 'text' in data:
                            logger.info(f"文本内容: {data['text']}")

                    elif data['type'] == 'session.created':
                        # 处理会话创建
                        logger.info("会话创建成功")
                        if 'session' in data:
                            session = data['session']
                            logger.info(f"会话ID: {session.get('id')}")

                    elif data['type'] == 'conversation.created':
                        # 处理对话创建
                        logger.info("对话创建成功")
                        if 'conversation' in data:
                            conversation = data['conversation']
                            logger.info(f"对话ID: {conversation.get('id')}")

                    elif data['type'] == 'error':
                        # 处理错误消息
                        logger.error("收到错误消息")
                        if 'error' in data:
                            error = data['error']
                            error_type = error.get('type', 'unknown')
                            error_code = error.get('code', 'unknown')
                            error_message = error.get('message', 'unknown')
                            logger.error(
                                f"错误类型: {error_type}, 代码: {error_code}, 消息: {error_message}")

                    else:
                        # 记录其他类型的消息
                        logger.info(f"收到其他类型消息: {msg_type}")

                    logger.info(json.dumps(data, ensure_ascii=False))

        except ConnectionClosedOK:
            logger.info("百度WebSocket连接已关闭")
        except Exception as e:
            logger.error(f"接收百度数据异常: {e}")

    def _handle_baidu_recognition_result(self, data):
        """处理百度语音识别结果"""
        try:
            if 'result' in data:
                result_text = data['result'].get('text', '')
                if result_text:
                    logger.info(f"百度识别结果: {result_text}")
                    # 不播放思考语气词，因为百度会直接返回音频

        except Exception as e:
            logger.error(f"处理百度识别结果异常: {e}")

    def play_thinking_phrase(self, text_length: int = 0, type="thinking"):
        """根据文字长度播放合适的语气助词（使用缓存）"""
        # 百度实时语音识别不使用TTS播放思考语气词
        # 因为百度会直接返回音频响应
        logger.info("百度实时语音识别模式，跳过TTS思考语气词播放")
        return

    def start_recognition(self):
        """启动百度实时语音识别服务"""
        if not self._init_audio_socket():
            return False

        return self._start_baidu_realtime()

    def stop_recognition(self):
        """停止百度实时语音识别服务"""
        self.is_running = False

        # 发送结束信号给音频播放线程
        self.play_buffer.put('EOF')

        if self.audio_socket:
            self.audio_socket.close()
            self.audio_socket = None

        if self.baidu_ws:
            self.baidu_ws.close()
            self.baidu_ws = None

        logger.info("百度实时语音识别服务已停止")
