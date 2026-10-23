"""
统一日志工具模块
使用loguru实现按天生成日志文件，统一项目日志格式
"""
import sys
from pathlib import Path
from loguru import logger
from config.config.settings import config

# 全局logger实例
_global_logger = None


def setup_logger(name='robot_ai', log_dir='logs'):
    """
    设置统一的日志记录器

    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录

    Returns:
        logger: 配置好的日志记录器
    """
    global _global_logger

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 移除默认的处理器
    logger.remove()

    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.LOG_LEVEL,
        colorize=True
    )

    # 添加文件处理器（按天轮转）
    log_file = log_path / f"{name}.log"
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level=config.LOG_LEVEL,
        rotation="00:00",  # 每天午夜轮转
        retention="30 days",  # 保留30天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
        enqueue=True  # 异步写入
    )

    _global_logger = logger
    return logger


def get_logger(name=None):
    """
    获取日志记录器

    Args:
        name: 模块名称，如果为None则使用调用模块的名称

    Returns:
        logger: 日志记录器
    """
    if name is None:
        # 获取调用模块的名称
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'robot_ai')

    # 如果还没有初始化，先初始化
    if _global_logger is None:
        setup_logger()

    # 返回绑定模块名的logger
    return _global_logger.bind(name=name)


# 初始化根日志记录器
setup_logger('robot_ai', 'logs')

# 导出统一的logger接口 - 直接导出loguru的logger
__all__ = ['setup_logger', 'get_logger', 'logger']
