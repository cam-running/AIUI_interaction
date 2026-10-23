"""
网络工具模块
"""
import subprocess
from utils.logger import logger
from typing import Optional


def ping_host(host: str) -> bool:
    """
    检测主机连通性

    Args:
        host: 目标主机IP

    Returns:
        bool: 是否可达
    """
    try:
        response = subprocess.run(
            ["ping", "-c", "1", host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return response.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.error(f"Ping检测失败: {e}")
        return False


def check_network_connectivity(host: str) -> Optional[str]:
    """
    检查网络连接状态

    Args:
        host: 目标主机

    Returns:
        str: 连接状态描述，失败时返回None
    """
    if ping_host(host):
        return f"网络连接正常: {host}"
    else:
        return None
