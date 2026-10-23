"""
百度实时语音识别消息处理器

说明：不改动原有讯飞（AIUI）流程，单独提供百度处理器。
该处理器负责启动/停止百度实时语音识别流程，核心音频采集、VAD门控、通道过滤、
以及自回声抑制（在助手播报期间暂停上行音频）等逻辑由 `handlers.baidu.speech_handler.BaiduSpeechHandler` 内部实现。
"""
from utils.logger import logger
import time
from typing import Optional

from handlers.baidu.speech_handler import BaiduSpeechHandler


class BaiduMessageProcessor:
    """百度实时语音识别消息处理器"""

    def __init__(self) -> None:
        self._running: bool = False
        self._handler: Optional[BaiduSpeechHandler] = None

    def start(self) -> bool:
        """启动百度实时语音识别主流程"""
        try:
            logger.info("初始化百度实时语音识别处理器…")
            self._handler = BaiduSpeechHandler()

            logger.info("启动百度实时语音识别…")
            ok = self._handler.start_recognition()
            if not ok:
                logger.error("百度实时语音识别启动失败")
                return False

            self._running = True
            logger.info("百度实时语音识别处理器已启动")
            return True
        except Exception as e:
            logger.error(f"百度处理器启动异常: {e}")
            return False

    def run_forever(self) -> None:
        """保持运行（供主循环调用）"""
        while self._running:
            time.sleep(1)

    def stop(self) -> None:
        """停止百度实时语音识别主流程"""
        self._running = False
        if self._handler:
            try:
                self._handler.stop_recognition()
            except Exception as e:
                logger.error(f"停止百度处理器异常: {e}")
        logger.info("百度实时语音识别处理器已停止")
