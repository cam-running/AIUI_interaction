"""
AIOT 配置管理模块
统一加载和管理 aiot.yaml 配置文件
"""
import yaml
import os
from pathlib import Path
from utils.logger import logger
from typing import Dict, Any


class AiotConfig:
    """AIOT 配置管理类"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AiotConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self):
        """加载配置文件"""
        try:
            # 获取配置文件路径
            config_path = Path(__file__).parent.parent / "aiot.yaml"

            if not config_path.exists():
                logger.error(f"AIOT配置文件不存在: {config_path}")
                self._config = {}
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

            logger.info("AIOT配置文件加载成功")

        except Exception as e:
            logger.error(f"加载AIOT配置文件失败: {e}")
            self._config = {}

    def get_machine_id(self) -> str:
        """获取机器ID"""
        return self._config.get('machine', {}).get('machine-id', '')

    def get_machine_name(self) -> str:
        """获取机器名称"""
        return self._config.get('machine', {}).get('machine-name', '')

    def get_aiot_platform_config(self) -> Dict[str, Any]:
        """获取AIOT平台配置"""
        return self._config.get('aiot_platform', {})

    def get_aiot_host(self) -> str:
        """获取AIOT平台地址"""
        return self._config.get('aiot_platform', {}).get('host', '')

    def get_aiot_app_id(self) -> str:
        """获取AIOT应用ID"""
        return self._config.get('aiot_platform', {}).get('app_id', '')

    def get_aiot_app_secret(self) -> str:
        """获取AIOT应用密钥"""
        return self._config.get('aiot_platform', {}).get('app_secret', '')

    def get_aiot_union_id(self) -> str:
        """获取AIOT联合ID"""
        return self._config.get('aiot_platform', {}).get('union_id', '')

    def get_scenes(self) -> Dict[str, str]:
        """获取场景配置"""
        return self._config.get('scenes', {})

    def get_devices(self) -> Dict[str, Dict[str, Any]]:
        """获取设备配置"""
        return self._config.get('devices', {})

    def get_device_config(self, device_name: str) -> Dict[str, Any]:
        """获取指定设备的配置"""
        return self._config.get('devices', {}).get(device_name, {})

    def reload_config(self):
        """重新加载配置文件"""
        self._config = None
        self._load_config()
        logger.info("AIOT配置文件重新加载完成")


# 全局配置实例
aiot_config = AiotConfig()

# 为了保持向后兼容，提供直接的访问方式


def get_machine_id() -> str:
    """获取机器ID（向后兼容）"""
    return aiot_config.get_machine_id()


def get_machine_name() -> str:
    """获取机器名称（向后兼容）"""
    return aiot_config.get_machine_name()


def get_aiot_platform_config() -> Dict[str, Any]:
    """获取AIOT平台配置（向后兼容）"""
    return aiot_config.get_aiot_platform_config()


def get_aiot_host() -> str:
    """获取AIOT平台地址（向后兼容）"""
    return aiot_config.get_aiot_host()


def get_aiot_app_id() -> str:
    """获取AIOT应用ID（向后兼容）"""
    return aiot_config.get_aiot_app_id()


def get_aiot_app_secret() -> str:
    """获取AIOT应用密钥（向后兼容）"""
    return aiot_config.get_aiot_app_secret()


def get_aiot_union_id() -> str:
    """获取AIOT联合ID（向后兼容）"""
    return aiot_config.get_aiot_union_id()


def get_scenes() -> Dict[str, str]:
    """获取场景配置（向后兼容）"""
    return aiot_config.get_scenes()


def get_devices() -> Dict[str, Dict[str, Any]]:
    """获取设备配置（向后兼容）"""
    return aiot_config.get_devices()


def get_device_config(device_name: str) -> Dict[str, Any]:
    """获取指定设备的配置（向后兼容）"""
    return aiot_config.get_device_config(device_name)
