"""
时间同步工具模块
"""
import subprocess
from utils.logger import logger
import platform
import time
from typing import Optional


class TimeSync:
    """时间同步类"""

    def __init__(self):
        self.ntp_servers = [
            "ntp.aliyun.com",
            "ntp1.aliyun.com",
            "ntp2.aliyun.com",
            "time.windows.com",
            "pool.ntp.org"
        ]

    def sync_time(self) -> bool:
        """
        同步系统时间

        Returns:
            bool: 同步是否成功
        """
        try:
            logger.info("开始同步系统时间...")

            # 检测操作系统
            system = platform.system()

            if system == "Linux":
                return self._sync_linux()
            elif system == "Windows":
                return self._sync_windows()
            else:
                logger.warning(f"不支持的操作系统: {system}")
                return False

        except Exception as e:
            logger.error(f"时间同步失败: {e}")
            return False

    def _sync_linux(self) -> bool:
        """Linux系统时间同步"""
        for server in self.ntp_servers:
            try:
                logger.info(f"尝试从 {server} 同步时间...")

                # 使用echo命令自动输入密码
                cmd = f'echo "12345678" | sudo -S ntpdate {server}'
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    logger.info(f"时间同步成功: {result.stdout.strip()}")
                    return True
                else:
                    logger.warning(
                        f"从 {server} 同步失败: {result.stderr.strip()}")

            except subprocess.TimeoutExpired:
                logger.warning(f"从 {server} 同步超时")
            except subprocess.CalledProcessError as e:
                logger.warning(f"从 {server} 同步失败: {e}")
            except FileNotFoundError:
                logger.error("未找到ntpdate命令，请安装ntpdate工具")
                return False
            except Exception as e:
                logger.warning(f"从 {server} 同步异常: {e}")

        logger.error("所有NTP服务器同步失败")
        return False

    def _sync_windows(self) -> bool:
        """Windows系统时间同步"""
        try:
            logger.info("Windows系统时间同步...")

            # 使用w32tm命令同步时间
            result = subprocess.run(
                ["w32tm", "/resync"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("Windows时间同步成功")
                return True
            else:
                logger.warning(f"Windows时间同步失败: {result.stderr.strip()}")
                return False

        except subprocess.TimeoutExpired:
            logger.warning("Windows时间同步超时")
            return False
        except subprocess.CalledProcessError as e:
            logger.warning(f"Windows时间同步失败: {e}")
            return False
        except Exception as e:
            logger.error(f"Windows时间同步异常: {e}")
            return False

    def get_current_time(self) -> str:
        """
        获取当前系统时间

        Returns:
            str: 格式化的当前时间
        """
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def check_time_drift(self) -> Optional[float]:
        """
        检查时间偏差（需要网络连接）

        Returns:
            Optional[float]: 时间偏差（秒），失败返回None
        """
        try:
            import requests
            import datetime

            # 获取网络时间
            response = requests.get(
                "http://worldtimeapi.org/api/timezone/Asia/Shanghai", timeout=5)
            if response.status_code == 200:
                data = response.json()
                network_time = datetime.datetime.fromisoformat(
                    data['datetime'].replace('Z', '+00:00'))

                # 获取本地时间
                local_time = datetime.datetime.now()

                # 计算时间差
                time_diff = abs((network_time - local_time).total_seconds())
                return time_diff

        except Exception as e:
            logger.debug(f"检查时间偏差失败: {e}")
            return None


def sync_system_time() -> bool:
    """
    同步系统时间的便捷函数

    Returns:
        bool: 同步是否成功
    """
    time_sync = TimeSync()
    return time_sync.sync_time()
