'''
Author: zhaoyong 77912776@qq.com
Date: 2025-08-14 22:19:23
LastEditTime: 2025-08-24 14:21:05
LastEditors: zhaoyong 77912776@qq.com
FilePath: \robot_ai\core\socket_client.py
Description: 头部注释配置模板
'''
"""
Socket客户端连接管理模块
"""
import time
from utils.logger import logger
import struct
from socket import socket, AF_INET, SOCK_STREAM, timeout
from threading import Thread, Event
from typing import Optional, Tuple
from utils.network import ping_host
from config.config.settings import config


class SocketClient:
    """Socket客户端连接管理类"""

    def __init__(self):
        self.client_socket: Optional[socket] = None
        self.server_address = config.SERVER_ADDRESS
        self.connected_event = Event()
        self.stop_event = Event()
        self.connect()
        self.start_ping_check()

    def connect(self) -> None:
        """建立连接"""
        while not self.stop_event.is_set():
            try:
                if self.client_socket:
                    self.client_socket.close()

                self.client_socket = socket(AF_INET, SOCK_STREAM)
                self.client_socket.settimeout(config.CONNECTION_TIMEOUT)
                self.client_socket.connect(self.server_address)

                logger.info(f"已连接到讯飞套件: {self.server_address}")
                self.client_socket.settimeout(None)  # 连接成功后取消超时
                self.connected_event.set()
                break

            except (ConnectionError, OSError, timeout) as e:
                logger.error(
                    f"讯飞套件 {self.server_address} 连接失败: {e}. {config.RECONNECT_DELAY}秒后重试...")
                # 摄像头连接失败播放提示音
                from utils.tts_client import play_text_async
                play_text_async('讯飞套件连接失败，请检查讯飞套件是否正常', use_cache=True)
                self.connected_event.clear()
                time.sleep(config.RECONNECT_DELAY)

    def receive_full_data(self, expected_length: int) -> Optional[bytes]:
        """
        接收完整数据

        Args:
            expected_length: 期望接收的数据长度

        Returns:
            Optional[bytes]: 接收到的数据，失败时返回None
        """
        received_data = bytearray()
        while len(received_data) < expected_length:
            try:
                chunk = self.client_socket.recv(
                    expected_length - len(received_data))
                if not chunk:
                    return None
                received_data.extend(chunk)
            except timeout:
                return None
        return bytes(received_data)

    def start_ping_check(self) -> None:
        """启动心跳检测"""
        Thread(target=self.ping_check, daemon=True).start()

    def ping_check(self) -> None:
        """心跳检测循环"""
        while not self.stop_event.is_set():
            try:
                if not ping_host(self.server_address[0]):
                    logger.error(
                        f"Ping检测失败: {self.server_address[0]}. 重新连接...")
                    self.connected_event.clear()
                    self.connect()
            except Exception as e:
                logger.error(f"心跳检测异常: {e}")
            time.sleep(config.PING_INTERVAL)

    def close(self) -> None:
        """关闭连接"""
        self.stop_event.set()
        if self.client_socket:
            self.client_socket.close()
        logger.info("Socket连接已关闭")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected_event.is_set()

    def get_socket(self) -> Optional[socket]:
        """获取socket对象"""
        return self.client_socket if self.is_connected() else None
