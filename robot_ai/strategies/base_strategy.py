"""
基础策略类
"""
from utils.logger import logger
from abc import abstractmethod, ABC
from typing import Union, Tuple


class ProcessStrategy(ABC):
    """处理策略基类"""

    def makepacket(self, sid: int, msg_type: int, content: Union[str, bytes]) -> bytearray:
        """
        构建消息包

        Args:
            sid: 会话ID
            msg_type: 消息类型
            content: 消息内容

        Returns:
            bytearray: 完整的消息包
        """
        if isinstance(content, str):
            content = content.encode('utf-8')

        size = len(content)
        temp = bytearray()
        temp.append(0xa5)  # 同步头
        temp.append(0x01)  # 用户ID
        temp.append(msg_type)  # 消息类型
        temp.append(size & 0xff)  # 长度低字节
        temp.append((size >> 8) & 0xff)  # 长度高字节
        temp.append(sid & 0xff)  # 会话ID低字节
        temp.append((sid >> 8) & 0xff)  # 会话ID高字节
        temp.extend(content)  # 消息内容
        temp.append(self.checkcode(temp))  # 校验码

        return temp

    def checkcode(self, data: bytearray) -> int:
        """
        计算校验码

        Args:
            data: 数据字节数组

        Returns:
            int: 校验码
        """
        total = sum(data)
        checkcode = (~total + 1) & 0xFF
        return checkcode

    @abstractmethod
    def process(self, client_socket, data) -> Union[bool, Tuple[bool, bytes]]:
        """
        处理消息的抽象方法

        Args:
            client_socket: 客户端socket
            data: 要处理的数据

        Returns:
            Union[bool, Tuple[bool, bytes]]: 处理结果
        """
        pass
