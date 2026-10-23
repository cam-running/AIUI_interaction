"""
机器人AI语音识别主程序入口
Author: zhaoyong 77912776@qq.com
Date: 2025-08-19
LastEditTime: 2025-08-24
"""

import time
from datetime import datetime
import signal
from typing import Optional
from utils.load_config import load_config
from utils.logger import setup_logger, logger
from handlers.aiui.EventListener import EventListener
from handlers.aiui.AIui_node import AIUINode
from handlers.baidu.speech_handler import BaiduSpeechHandler
from handlers.speech_handler import SpeechHandler
from core.message_processor import MessageProcessor
from core.socket_client import SocketClient
from utils.init_system import initialize_robot_system
import sys


class RobotAI:
    """机器人AI主类"""

    def __init__(self):
        self.run = True
        self.socket_client: Optional[SocketClient] = None
        self.message_processor: Optional[MessageProcessor] = None
        self.speech_handler: Optional[SpeechHandler] = None
        self.baidu_handler: Optional[BaiduSpeechHandler] = None
        self.xunfei_linux_node: Optional[AIUINode] = None

        signal.signal(signal.SIGINT, self._stop_handler)

        setup_logger('robot_ai', 'logs')
        self.config = load_config()

        self.speech_config = self.config.get('speech_recognition', {})
        self.service_type = self.speech_config.get('service', 'xunfei_aiui')
        self.is_xunfei_linux = self.service_type == 'xunfei_linux'

        self._init_components()

    def _stop_handler(self, signum, frame):
        """信号处理函数"""
        logger.info(f"收到信号 {signum}，正在停止...")
        self.run = False

    def _init_components(self):
        """初始化语音识别组件"""
        logger.info("正在初始化机器人AI语音识别组件...")
        try:
            if self.service_type == 'baidu_realtime':
                self._init_baidu()
            elif self.is_xunfei_linux:
                self._init_xunfei_linux()
            else:
                self._init_xunfei_aiui()
            logger.info("机器人AI语音识别初始化完成")
        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            raise

    def _init_baidu(self):
        """初始化百度语音识别"""
        logger.info("使用百度实时语音识别服务")
        self.baidu_handler = BaiduSpeechHandler()
        if not self.baidu_handler.start_recognition():
            raise RuntimeError("百度实时语音识别启动失败")
        logger.info("百度实时语音识别启动成功")

    def _init_xunfei_linux(self):
        """初始化讯飞 Linux SDK"""
        logger.info("使用讯飞 Linux SDK 语音识别服务")
        event_listener = EventListener(skills_dict={}, debug=False)
        self.xunfei_linux_node = AIUINode(event_listener, debug=False)
        # 导入 IntentHandler 并传入 aiui_node 实例
        from handlers.xunfei.intent_handler import IntentHandler
        intent_handler = IntentHandler(aiui_node=self.xunfei_linux_node)

        # 将 intent_handler 绑定到 event_listener
        event_listener.intent_handler = intent_handler
        # 可选：将 intent_handler 保存到实例变量，方便后续调用
        self.intent_handler = intent_handler
        logger.info("讯飞 Linux SDK 初始化成功")

    def _init_xunfei_aiui(self):
        """初始化讯飞 AIUI"""
        logger.info("使用讯飞 AIUI 语音识别服务")
        self.speech_handler = SpeechHandler()
        self.socket_client = SocketClient()
        self.message_processor = MessageProcessor(self.socket_client)

    def start(self):
        """启动系统"""
        logger.info("机器人AI语音识别启动")
        try:
            if self.service_type == 'baidu_realtime':
                self._run_baidu()
            elif self.is_xunfei_linux:
                self._run_xunfei_linux()
            else:
                self._run_xunfei_aiui()
        except Exception as e:
            logger.error(f"系统运行异常: {e}")
        finally:
            self.stop()

    def _run_baidu(self):
        logger.info("百度实时语音识别服务运行中...")
        while self.run:
            time.sleep(1)

    def _run_xunfei_linux(self):
        logger.info("讯飞 Linux SDK 服务运行中...")
        if self.xunfei_linux_node:
            self.xunfei_linux_node.start(spin=True)

    def _run_xunfei_aiui(self):
        logger.info("讯飞 AIUI 服务运行中...")
        while self.run and self.message_processor:
            self.message_processor.process()

    def stop(self):
        """停止系统"""
        logger.info("正在停止机器人AI语音识别...")
        try:
            if self.baidu_handler and self.service_type == 'baidu_realtime':
                self.baidu_handler.stop_recognition()

            if self.xunfei_linux_node and self.is_xunfei_linux:
                self.xunfei_linux_node.shutdown()

            if self.socket_client:
                self.socket_client.close()

            logger.info("机器人AI语音识别已停止")
        except Exception as e:
            logger.error(f"停止过程中出现异常: {e}")


def main():
    """主函数"""
    logger.info("=== 机器人AI主程序启动 ===")
    logger.info(f"启动时间: {datetime.now()}")

    try:
        # 先进行系统级初始化（音频/组件等）
        initialize_robot_system()
        robot = RobotAI()
        robot.start()
        logger.info("机器人AI主程序正常退出")
        return 0
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号，程序退出")
        return 0
    except Exception as e:
        import traceback
        logger.error(f"程序启动失败: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
