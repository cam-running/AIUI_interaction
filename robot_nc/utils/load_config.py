from utils.logger import logger

import yaml
from typing import Dict, Any, Optional

# 配置常量
CONFIG_PATH = 'config/config.yaml'

# 加载配置


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}


def get_pc2_url(endpoint: str) -> str:
    """
    获取PC2 API URL
    :param endpoint: 端点名称 (robot_action/robot_waypoint/robot_cmd_action)
    :return: 完整的API URL
    """
    config = load_config()
    pc2_config = config.get('pc2', {})
    return f"{pc2_config.get('base_url', '')}{pc2_config.get('endpoints', {}).get(endpoint, '')}"


def get_pc2_timeout() -> int:
    """获取PC2 API超时时间"""
    config = load_config()
    return config.get('pc2', {}).get('timeout', 30)
