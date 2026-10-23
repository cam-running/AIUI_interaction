'''
Author: zhaoyong 77912776@qq.com
Date: 2025-08-23 14:34:11
LastEditTime: 2025-08-27 15:06:43
LastEditors: zhaoyong 77912776@qq.com
FilePath: \robot_ai\handlers\speech_handler.py
Description: 头部注释配置模板
'''
"""
语音识别处理模块 - 工厂类
"""
from utils.logger import logger
from utils.load_config import load_config
from handlers.baidu.speech_handler import BaiduSpeechHandler
from handlers.xunfei.speech_handler import XunfeiSpeechHandler


class SpeechHandlerFactory:
    """语音识别处理器工厂类"""

    @staticmethod
    def create_handler():
        """
        根据配置创建相应的语音识别处理器

        Returns:
            BaiduSpeechHandler or XunfeiSpeechHandler: 语音识别处理器实例
        """
        try:
            # 加载配置
            config = load_config()
            speech_config = config.get('speech_recognition', {})
            service_type = speech_config.get('service', 'xunfei_aiui')

            logger.info(f"创建语音识别处理器，服务类型: {service_type}")

            if service_type == 'baidu_realtime':
                return BaiduSpeechHandler()
            elif service_type == 'xunfei_aiui':
                return XunfeiSpeechHandler()
            else:
                logger.error(f"不支持的语音识别服务类型: {service_type}")
                raise ValueError(f"不支持的语音识别服务类型: {service_type}")

        except Exception as e:
            logger.error(f"创建语音识别处理器失败: {e}")
            raise


# 为了保持向后兼容，保留原有的SpeechHandler类名
class SpeechHandler:
    """语音识别处理类 - 兼容性包装器"""

    def __init__(self):
        self.handler = SpeechHandlerFactory.create_handler()

    def __getattr__(self, name):
        """代理所有方法调用到实际的处理器"""
        return getattr(self.handler, name)
