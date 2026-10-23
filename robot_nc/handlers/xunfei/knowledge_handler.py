"""
知识库处理器模块
"""
from utils.logger import logger
import json
from typing import Dict, Any, Optional
from utils.logger import logger


class KnowledgeHandler:
    """知识库处理器类"""

    def __init__(self):
        """初始化知识库处理器"""
        self.logger = logger.bind(name=__name__)

    def handle_knowledge_result(self, data: Dict[str, Any]) -> bool:
        """
        处理知识库检索结果

        Args:
            data: AIUI知识库数据

        Returns:
            bool: 处理结果
        """
        try:
            self.logger.info("开始处理知识库检索结果")

            # 提取知识库内容
            knowledge_content = self._extract_knowledge_content(data)

            if knowledge_content:
                self.logger.info(f"知识库检索到内容: {knowledge_content[:100]}...")

                # 这里可以添加TTS播放逻辑
                # 暂时只记录日志，后续可以集成TTS播放
                self.logger.info(f"知识库内容: {knowledge_content}")

                return True
            else:
                self.logger.warning("知识库检索结果为空")
                return False

        except Exception as e:
            self.logger.error(f"处理知识库结果异常: {e}")
            return False

    def _extract_knowledge_content(self, data: Dict[str, Any]) -> Optional[str]:
        """
        从AIUI数据中提取知识库内容

        Args:
            data: AIUI数据

        Returns:
            Optional[str]: 提取的知识库内容
        """
        try:
            # 解析AIUI数据结构
            if 'content' not in data:
                self.logger.warning("数据中缺少content字段")
                return None

            content = data['content']

            # 检查是否有知识库结果
            if 'info' not in content:
                self.logger.warning("content中缺少info字段")
                return None

            info = content['info']

            # 检查是否有数据
            if 'data' not in info or not isinstance(info['data'], list):
                self.logger.warning("info中缺少data字段或格式不正确")
                return None

            data_list = info['data']
            if not data_list:
                self.logger.warning("data列表为空")
                return None

            # 获取第一个结果
            first_result = data_list[0]

            # 检查结果类型
            if 'type' not in first_result:
                self.logger.warning("结果中缺少type字段")
                return None

            result_type = first_result['type']

            if result_type == 'text':
                # 文本类型结果
                if 'content' in first_result:
                    return first_result['content']
                else:
                    self.logger.warning("文本结果中缺少content字段")
                    return None

            elif result_type == 'json':
                # JSON类型结果
                if 'content' in first_result:
                    try:
                        json_content = json.loads(first_result['content'])
                        return self._extract_from_json_content(json_content)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON解析失败: {e}")
                        return None
                else:
                    self.logger.warning("JSON结果中缺少content字段")
                    return None

            else:
                self.logger.warning(f"未知的结果类型: {result_type}")
                return None

        except Exception as e:
            self.logger.error(f"提取知识库内容异常: {e}")
            return None

    def _extract_from_json_content(self, json_content: Dict[str, Any]) -> Optional[str]:
        """
        从JSON内容中提取知识库文本

        Args:
            json_content: JSON内容

        Returns:
            Optional[str]: 提取的文本内容
        """
        try:
            # 检查是否有nested字段（知识库结果通常在这里）
            if 'nested' in json_content:
                nested = json_content['nested']

                if isinstance(nested, list) and len(nested) > 0:
                    # 取第一个最相关的结果
                    first_result = nested[0]

                    if isinstance(first_result, dict):
                        # 检查score阈值
                        score = first_result.get("score", 0.0)
                        self.logger.info(f"知识库检索score: {score}")

                        if score > 0.5:
                            # 提取内容
                            knowledge_content = first_result.get("content", "")
                            knowledge_detail = first_result.get("detail", "")
                            knowledge_summary = first_result.get("summary", "")
                            knowledge_title = first_result.get("title", "")

                            # 优先使用detail，其次summary，最后content
                            if knowledge_detail and len(knowledge_detail.strip()) > 10:
                                return knowledge_detail
                            elif knowledge_summary and len(knowledge_summary.strip()) > 10:
                                return knowledge_summary
                            else:
                                return knowledge_content
                        else:
                            self.logger.info(
                                f"知识库检索score({score:.3f}) <= 0.5，跳过知识库内容")
                            return None
                    else:
                        self.logger.warning("知识库结果格式不正确")
                        return None
                else:
                    self.logger.warning("知识库nested结果为空")
                    return None
            else:
                self.logger.warning("JSON内容中缺少nested字段")
                return None

        except Exception as e:
            self.logger.error(f"从JSON内容提取文本异常: {e}")
            return None
