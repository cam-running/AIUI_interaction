"""
机器人AI语音识别配置文件
支持环境变量和YAML配置文件
"""
import os
import yaml
from typing import Tuple, Dict, Any
from pathlib import Path
from utils.logger import logger


class Config:
    """配置类"""

    def __init__(self):
        self._config_data = {}
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        # 加载YAML配置
        self._load_yaml_config()

    def _load_yaml_config(self):
        """加载YAML配置文件"""
        # 修复路径：config.yaml在上级目录
        config_file = Path(__file__).parent.parent / "config.yaml"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f) or {}
                logger.info(f"成功加载配置文件: {config_file}")
            except Exception as e:
                logger.info(f"加载YAML配置文件失败: {e}")
                self._config_data = {}
        else:
            logger.warning(f"配置文件不存在: {config_file}")
            self._config_data = {}

    @property
    def SERVER_IP(self) -> str:
        """讯飞套件IP"""
        return self._config_data.get('server', {}).get('ip', '192.168.0.26')

    @property
    def SERVER_PORT(self) -> int:
        """服务器端口"""
        return self._config_data.get('server', {}).get('port', 19199)

    @property
    def SERVER_ADDRESS(self) -> Tuple[str, int]:
        """获取服务器地址"""
        return (self.SERVER_IP, self.SERVER_PORT)

    @property
    def CONNECTION_TIMEOUT(self) -> int:
        """连接超时时间"""
        return self._config_data.get('network', {}).get('connection_timeout', 5)

    @property
    def RECEIVE_TIMEOUT(self) -> int:
        """接收超时时间"""
        return self._config_data.get('network', {}).get('receive_timeout', 3)

    @property
    def PING_INTERVAL(self) -> int:
        """心跳检测间隔"""
        return self._config_data.get('network', {}).get('ping_interval', 10)

    @property
    def RECONNECT_DELAY(self) -> int:
        """重连延迟时间"""
        return self._config_data.get('network', {}).get('reconnect_delay', 5)

    @property
    def machinename(self) -> str:
        """机器人对外称呼"""
        return self._config_data.get('machinename', '小勇')

    @property
    def LOG_LEVEL(self) -> str:
        """日志级别"""
        return self._config_data.get('logging', {}).get('level', 'INFO')

    @property
    def LOG_FILE(self) -> str:
        """日志文件"""
        return self._config_data.get('logging', {}).get('file', 'robot_ai.log')

    @property
    def LOG_FORMAT(self) -> str:
        """日志格式"""
        return self._config_data.get('logging', {}).get('format', '%(asctime)s %(levelname)s:%(message)s')

    @property
    def LOG_DATE_FORMAT(self) -> str:
        """日志日期格式"""
        return self._config_data.get('logging', {}).get('date_format', '%Y-%m-%d %H:%M:%S')

    @property
    def TTS_VOICE(self) -> str:
        """TTS语音"""
        return self._config_data.get('tts', {}).get('voice', 'x4_lingxiaoxuan_oral')

    @property
    def TTS_SPEED(self) -> int:
        """TTS速度"""
        return self._config_data.get('tts', {}).get('speed', 50)

    @property
    def TTS_PITCH(self) -> int:
        """TTS音调"""
        return self._config_data.get('tts', {}).get('pitch', 50)

    @property
    def TTS_VOLUME(self) -> int:
        """TTS音量"""
        return self._config_data.get('tts', {}).get('volume', 50)

    @property
    def XUNFEI_API_KEY(self) -> str:
        """科大讯飞API Key"""
        return self._config_data.get('xunfei', {}).get('api_key', 'your_api_key_here')

    @property
    def XUNFEI_API_SECRET(self) -> str:
        """科大讯飞API Secret"""
        return self._config_data.get('xunfei', {}).get('api_secret', 'your_api_secret_here')

    @property
    def XUNFEI_APP_ID(self) -> str:
        """科大讯飞App ID"""
        return self._config_data.get('xunfei', {}).get('app_id', 'your_app_id_here')

    @property
    def XUNFEI_STREAMING_TTS_URL(self) -> str:
        """科大讯飞流式TTS URL"""
        return self._config_data.get('xunfei', {}).get('streaming_tts_url', 'wss://tts-api.xfyun.cn/v2/tts')

    @property
    def XUNFEI_SCENE(self) -> str:
        """科大讯飞场景"""
        return self._config_data.get('xunfei', {}).get('scene', 'main')

    @property
    def ENVIRONMENT(self) -> str:
        """运行环境"""
        return self._config_data.get('environment', 'development')

    @property
    def DEBUG(self) -> bool:
        """调试模式"""
        return self._config_data.get('debug', False)

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config_data.copy()

    def reload(self):
        """重新加载配置"""
        self._load_config()

    @property
    def pc2_base_url(self) -> str:
        """PC2基础URL"""
        return self._config_data.get('pc2', {}).get('base_url', '')

    @property
    def pc2_time(self) -> int:
        """PC2超时时间"""
        return self._config_data.get('pc2', {}).get('timeout', 30)

    def get_pc2_url(self, endpoint: str) -> str:
        """
        获取PC2 API URL
        :param endpoint: 端点名称 (robot_action/robot_waypoint/robot_cmd_action)
        :return: 完整的API URL
        """
        endpoints = self._config_data.get('pc2', {}).get('endpoints', {})
        return f"{self.pc2_base_url}{endpoints.get(endpoint, '')}"


# 全局配置实例
config = Config()
