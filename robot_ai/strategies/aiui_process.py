"""
AIUI消息处理策略
"""
import zlib
from utils.logger import logger
from .base_strategy import ProcessStrategy


class AiuiMessageProcess(ProcessStrategy):
    """AIUI消息处理类"""

    def process(self, client_socket, data: bytes) -> tuple[bool, bytes]:
        """
        处理AIUI消息（解压缩）

        Args:
            client_socket: 客户端socket（未使用）
            data: 压缩的数据

        Returns:
            tuple[bool, bytes]: (成功标志, 解压后的数据)
        """
        if not data:
            return False, b''

        try:
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            output = decompressor.decompress(data)
            output += decompressor.flush()
            return True, output
        except zlib.error as e:
            logger.info(f"AIUI消息解压失败: {e}")
            return False, b''
