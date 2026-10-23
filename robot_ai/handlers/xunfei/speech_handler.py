"""
讯飞AIUI语音识别处理模块
"""
import json5
import requests

from utils.logger import logger
import json
import random
import threading
from strategies.vision.qwenv import process_base64_image

from utils.pc2_requests import _send_qa_task, _send_led_color_task
from utils.tts_client import play_text_async, is_playing
from utils.logger import logger
from handlers.xunfei.intent_handler import IntentHandler


class XunfeiSpeechHandler:
    """讯飞AIUI语音识别处理类"""

    def __init__(self):
        # 根据文字长度分类的语气助词列表
        self.short_thinking_phrases = [
            "嗯", "呃", "哦"
        ]

        self.medium_thinking_phrases = [
            "嗯…"
        ]

        self.long_thinking_phrases = [
            "嗯…", "呃…", "哦…", "那个", "这个"
        ]
        
        self.std_thinking_phrases = [
            "我想一下","你好呀"
        ]

        # 添加IntentHandler引用
        self.intent_handler = None
        self.iat_txt = ""

    def play_thinking_phrase(self, text_length: int = 0, type="thinking"):
        """根据文字长度播放合适的语气助词（使用缓存）"""
        if text_length < 3:
            return
        elif 3 <= text_length < 7:
            phrase = random.choice(self.medium_thinking_phrases)
        elif 7 <= text_length < 15:
            phrase = random.choice(self.medium_thinking_phrases)
        elif 15 <= text_length:
            phrase = random.choice(self.std_thinking_phrases)
        else:
            return

        logger.info(f"播放语气助词: {phrase}")
        play_text_async(phrase, use_cache=True)
        logger.info(f"{type}文本({text_length}字)，播放语气助词: {phrase}")

    def handle_iat_result(self, data: dict) -> None:
        """
        处理讯飞AIUI语音识别结果

        Args:
            data: 语音识别数据
        """
        try:

            # 异步调用 _send_led_color_task，添加异常处理
            try:

                led_thread = threading.Thread(
                    target=_send_led_color_task,
                    args=(self, "DEFAULT", "GREEN"),
                    daemon=True
                )
                led_thread.start()
            except Exception as e:
                logger.debug(f"[LED] LED控制失败，不影响语音识别: {e}")

            # logger.info('IAT数据', json.dumps(data, ensure_ascii=False, indent=2))
            # 使用get_recognition_text方法提取文本
            result_string = self.get_recognition_text(data)
            self.iat_txt = result_string
            # 获取状态信息
            sn_value = data.get('content', {}).get(
                'result', {}).get('text', {}).get('sn')
            ls_value = data.get('content', {}).get(
                'result', {}).get('text', {}).get('ls')

            # 确定状态值
            if sn_value == 1:
                status_value = 0
            elif ls_value is True:
                status_value = 2
            else:
                status_value = 1

            # 输出识别结果
            if result_string or status_value == 2:
                logger.info(f"讯飞识别到IAT结果是: {result_string}")

                # 异步调用 _send_qa_task，添加异常处理
                try:
                    qa_thread = threading.Thread(
                        target=_send_qa_task,
                        args=(self, {"question": result_string}),
                        daemon=True
                    )
                    qa_thread.start()
                except Exception as e:
                    logger.debug(f"[QA] QA请求失败，不影响语音识别: {e}")

                # 使用改进的播放逻辑
                logger.info(f"开始播放语气词")
                self.play_thinking_phrase(len(result_string), type="thinking")

        except Exception as e:
            logger.error(f"讯飞语音识别处理异常: {e}")

    def get_recognition_text(self, data: dict) -> str:
        """
        获取讯飞识别文本

        Args:
            data: 语音识别数据

        Returns:
            str: 识别文本
        """
        try:
            words = []
            ws_list = data.get('content', {}).get(
                'result', {}).get('text', {}).get('ws', [])

            for item in ws_list:
                cw_list = item.get('cw', [])
                for cw in cw_list:
                    words.append(cw.get('w', ''))

            return ''.join(words)
        except Exception as e:
            logger.error(f"获取讯飞识别文本异常: {e}")
            return ""
