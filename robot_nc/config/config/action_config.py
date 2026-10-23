'''
Author: zhaoyong 77912776@qq.com
Date: 2025-08-24 13:52:33
LastEditTime: 2025-08-24 14:25:50
LastEditors: zhaoyong 77912776@qq.com
FilePath: \robot_ai\config\config\action_config.py
Description: 头部注释配置模板
'''
"""
动作配置管理模块
统一加载和管理 action.yaml 配置文件
"""
import yaml
import os
from pathlib import Path
from utils.logger import logger
from typing import Dict, Any


class ActionConfig:
    """动作配置管理类"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActionConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self):
        """加载配置文件"""
        try:
            # 获取配置文件路径
            config_path = Path(__file__).parent.parent / "action.yaml"

            if not config_path.exists():
                logger.error(f"配置文件不存在: {config_path}")
                self._config = {}
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

            logger.info("动作配置文件加载成功")

        except Exception as e:
            logger.error(f"加载动作配置文件失败: {e}")
            self._config = {}

    def get_actions(self) -> Dict[str, str]:
        """获取动作常量"""
        return self._config.get('actions', {})

    def get_action_dict(self) -> Dict[str, int]:
        """获取动作指令字典"""
        return self._config.get('action_dict', {})

    def get_point_dict(self) -> Dict[str, str]:
        """获取点位字典"""
        return self._config.get('point_dict', {})

    def get_action_value(self, action_name: str) -> int:
        """获取动作对应的数值"""
        action_dict = self.get_action_dict()
        return action_dict.get(action_name)

    def get_point_value(self, point_name: str) -> str:
        """获取点位对应的值"""
        point_dict = self.get_point_dict()
        return point_dict.get(point_name)

    def reload_config(self):
        """重新加载配置文件"""
        self._config = None
        self._load_config()
        logger.info("动作配置文件重新加载完成")


# 全局配置实例
action_config = ActionConfig()

# 为了保持向后兼容，提供直接的访问方式


def get_action_dict() -> Dict[str, int]:
    """获取动作指令字典（向后兼容）"""
    return action_config.get_action_dict()


def get_point_dict() -> Dict[str, str]:
    """获取点位字典（向后兼容）"""
    return action_config.get_point_dict()


def get_actions() -> Dict[str, str]:
    """获取动作常量（向后兼容）"""
    return action_config.get_actions()
