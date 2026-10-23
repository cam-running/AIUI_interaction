"""
消息处理核心逻辑模块
"""
from utils.logger import logger
import struct
import json
from typing import Optional, Tuple

from core.socket_client import SocketClient
from strategies.confirm_process import ConfirmProcess
from strategies.aiui_process import AiuiMessageProcess
from handlers.xunfei.intent_handler import IntentHandler
from handlers.xunfei.speech_handler import XunfeiSpeechHandler
from handlers.xunfei.nlp_handler import NLPHandler
from handlers.xunfei.knowledge_handler import KnowledgeHandler


class MessageProcessor:
    """消息处理核心类"""

    def __init__(self, socket_client: SocketClient):
        self.socket_client = socket_client
        self.aiui_type = ""

        # 初始化策略处理器
        self.confirm_process = ConfirmProcess()
        self.aiui_process = AiuiMessageProcess()

        # 初始化业务处理器
        self.intent_handler = IntentHandler()
        self.speech_handler = XunfeiSpeechHandler()  # 使用讯飞AIUI处理器
        self.nlp_handler = NLPHandler()
        self.knowledge_handler = KnowledgeHandler()
        # 把意图类注册到语音处理器
        self.speech_handler.intent_handler = self.intent_handler
        # 设置NLP处理器的意图处理器引用
        self.nlp_handler.intent_handler = self.intent_handler
        # 设置NLP处理器的IAT处理器引用
        self.nlp_handler.iat_handler = self.speech_handler

    def process(self) -> bool:
        """
        处理接收到的消息

        Returns:
            bool: 处理是否成功
        """
        try:
            socket = self.socket_client.get_socket()
            if not socket:
                logger.error("Socket未连接，重新连接...")
                self.socket_client.connected_event.clear()
                self.socket_client.connect()
                return False

            # 设置接收超时
            socket.settimeout(3)

            # 接收消息头
            recv_data = self.socket_client.receive_full_data(7)
            if not recv_data:
                # logger.error("未接收到数据，重新连接...")
                self.socket_client.connected_event.clear()
                self.socket_client.connect()
                return False

            if len(recv_data) < 7:
                logger.error(f"数据不完整: {recv_data}")
                return False

            # 解析消息头
            sync_head, user_id, msg_type, msg_length, msg_id = struct.unpack(
                '<BBBHH', recv_data)

            # 接收消息体
            msg_data = self.socket_client.receive_full_data(msg_length + 1)
            if len(msg_data) < msg_length + 1:
                logger.error(f"消息体数据不完整: {msg_data}")
                return False

            # 解析消息数据
            msg = msg_data[:msg_length]
            check_code = msg_data[-1]  # 校验码

            # 处理消息
            if sync_head == 0xa5 and user_id == 0x01:
                return self._handle_message(msg_type, msg_id, msg)

            return True

        except Exception as e:
            logger.error(f"消息处理异常: {e}")
            return False

    def _handle_message(self, msg_type: int, msg_id: int, msg: bytes) -> bool:
        """
        处理具体消息类型

        Args:
            msg_type: 消息类型
            msg_id: 消息ID
            msg: 消息内容

        Returns:
            bool: 处理结果
        """
        try:
            socket = self.socket_client.get_socket()

            if msg_type == 0x01:
                # 确认消息
                self.confirm_process.process(socket, msg_id)

            elif msg_type == 0x04:
                # AIUI消息
                self.confirm_process.process(socket, msg_id)
                success, result = self.aiui_process.process(socket, msg)

                if success:
                    self.aiui_type = ""
                    data = json.loads(result)
                    self._get_aiui_type(data)

                    # 处理唤醒事件
                    if data.get('content', {}).get('eventType', {}) == 4:
                        logger.info(f"唤醒成功：===={msg_id} 我在 ====")
                        from utils.tts_client import play_text_async
                        play_text_async('我在呢，有什么可以帮您的？', use_cache=True)

                    # 根据AIUI类型处理
                    if self.aiui_type == "iat":
                        self.speech_handler.handle_iat_result(data)
                    elif self.aiui_type == "nlp":
                        self.nlp_handler.handle_nlp_result(data)
                    elif self.aiui_type == "cbm_semantic":
                        self.intent_handler.handle_intent_result(data)
                    elif self.aiui_type == "cbm_knowledge":
                        self.knowledge_handler.handle_knowledge_result(data)
                else:
                    logger.warning("AIUI消息处理失败")

            return True

        except Exception as e:
            logger.error(f"消息类型处理异常: {e}")
            return False

    def _get_aiui_type(self, data: dict) -> None:
        """
        获取AIUI类型

        Args:
            data: AIUI数据
        """
        if 'content' in data:
            content = data['content']
            if 'info' in content:
                info = content['info']
                if 'data' in info and isinstance(info['data'], list) and len(info['data']) > 0:
                    data_item = info['data'][0]
                    if 'params' in data_item:
                        params = data_item['params']
                        sub_value = params.get('sub')
                        if sub_value is not None:
                            self.aiui_type = sub_value
