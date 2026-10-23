from abc import ABC, abstractmethod



"""
文件:base_strategy.py
功能：定义策略接口
"""
__Author__ = "xueYang"

class ActionStrategy(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def execute(self,skill: str):
        pass
