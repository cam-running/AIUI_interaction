"""
确认消息处理策略
"""
from utils.logger import logger
from .base_strategy import ProcessStrategy


class ConfirmProcess(ProcessStrategy):
    """确认消息处理类"""

    def process(self, client_socket, msg_id: int) -> bool:
        """
        发送确认消息

        Args:
            client_socket: 客户端socket
            msg_id: 消息ID

        Returns:
            bool: 处理结果
        """
        try:
            temp = bytearray()
            temp.append(0xa5)
            temp.append(0x00)
            temp.append(0x00)
            temp.append(0x00)

            send_data = self.makepacket(msg_id, 0xff, temp)
            client_socket.send(send_data)
            return True
        except Exception as e:
            logger.info(f"发送确认消息失败: {e}")
            return False
