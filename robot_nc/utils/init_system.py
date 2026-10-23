"""
系统初始化模块
负责机器人AI系统的初始化工作
"""
import platform
import subprocess
from utils.logger import logger
import time
import asyncio
from typing import Optional
from core.socket_client import SocketClient
from core.xunfei.message_processor import XunfeiMessageProcessor
from core.baidu.message_processor import BaiduMessageProcessor
from handlers.speech_handler import SpeechHandler
from utils.logger import setup_logger
from utils.time_sync import sync_system_time
from utils.load_config import load_config


class SystemInitializer:
    """系统初始化器"""

    def __init__(self):
        self.config = None
        self.speech_config = None
        self.service_type = None

    def initialize_system(self):
        """初始化整个系统"""
        try:
            # 设置日志
            setup_logger()
            logger.info("开始系统初始化...")

            # 加载配置
            self._load_configuration()

            # 初始化音频系统
            # self._init_audio_system()

            # 初始化组件
            components = self._init_components()

            logger.info("系统初始化完成")
            return components

        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            raise

    def _load_configuration(self):
        """加载配置"""
        try:
            self.config = load_config()
            self.speech_config = self.config.get('speech_recognition', {})
            self.service_type = self.speech_config.get(
                'service', 'xunfei_aiui')
            logger.info(f"配置加载完成，使用服务类型: {self.service_type}")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            raise

    def _init_audio_system(self):
        """初始化音频系统"""
        try:
            if platform.system() == "Linux":
                logger.info("检测到Linux系统，正在初始化音频系统...")

                try:
                    # 杀掉当前 PulseAudio 进程
                    logger.info("正在关闭PulseAudio进程...")
                    subprocess.run(
                        ["pulseaudio", "--kill"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    time.sleep(1)

                    # 检查是否仍有进程占用声卡
                    result = subprocess.run(
                        ["fuser", "-v", "/dev/snd/*"],
                        capture_output=True,
                        text=True
                    )
                    if result.stdout.strip():
                        logger.warning("检测到音频设备仍被占用:\n" + result.stdout)
                    else:
                        logger.info("音频设备已释放，可由ALSA独占使用")

                    # 重启 PulseAudio
                    logger.info("正在重新启动PulseAudio...")
                    subprocess.run(
                        ["pulseaudio", "--start"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    logger.info("PulseAudio已重新启动")

                except subprocess.TimeoutExpired:
                    logger.warning("PulseAudio操作超时，继续执行")
                except FileNotFoundError:
                    logger.warning("未找到 pulseaudio 命令，请确认已安装 PulseAudio")
                except Exception as e:
                    logger.error(f"音频系统初始化异常: {e}")
                    raise
            else:
                logger.info(f"当前系统: {platform.system()}，跳过音频系统初始化")

        except Exception as e:
            logger.error(f"音频系统初始化失败: {e}")
            raise


    def _init_components(self):
        """初始化组件"""
        try:
            logger.info("正在初始化机器人AI语音识别组件...")

            components = {
                'socket_client': None,
                'xunfei_processor': None,
                'speech_handler': None,
                'baidu_processor': None
            }

            # 根据配置选择语音识别服务
            if self.service_type == 'baidu_realtime':
                logger.info("使用百度实时语音识别服务")
                # 使用百度消息处理器
                components['baidu_processor'] = BaiduMessageProcessor()
                if components['baidu_processor'].start():
                    logger.info("百度实时语音识别启动成功")
                else:
                    logger.error("百度实时语音识别启动失败")
                    raise Exception("百度实时语音识别启动失败")
            elif self.service_type == 'xunfei_aiui':
                logger.info("使用讯飞AIUI语音识别服务")
                # 初始化语音处理器（工厂模式）
                components['speech_handler'] = SpeechHandler()
                # 初始化Socket客户端（用于讯飞AIUI）
                components['socket_client'] = SocketClient()
                # 初始化消息处理器
                components['xunfei_processor'] = XunfeiMessageProcessor(
                    components['socket_client'])

            logger.info("机器人AI语音识别组件初始化完成")
            return components

        except Exception as e:
            logger.error(f"组件初始化失败: {e}")
            raise

    async def sync_time(self):
        """同步系统时间"""
        try:
            logger.info("正在同步系统时间...")
            # 在事件循环中运行同步函数
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, sync_system_time)
            if result:
                logger.info("系统时间同步成功")
            else:
                logger.warning("系统时间同步失败，继续运行")
        except Exception as e:
            logger.error(f"时间同步异常: {e}")


def initialize_robot_system():
    """初始化机器人系统的便捷函数"""
    initializer = SystemInitializer()
    return initializer.initialize_system()
