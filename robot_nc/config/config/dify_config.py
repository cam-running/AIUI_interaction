"""
Dify 配置管理模块
统一加载和管理 dify.yaml 配置文件
"""
import threading
import time

import yaml
import os
from pathlib import Path
from utils.logger import logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化处理器"""

    def __init__(self, config_instance):
        self.config_instance = config_instance
        self.last_modified = 0

    def on_modified(self, event):
        if event.src_path.endswith('dify.yaml'):
            now = time.time()
            # 0.5 秒内的重复事件忽略
            if now - self.last_modified < 0.5:
                return
            self.last_modified = now
            logger.info("检测到配置文件修改，开始重载配置")
            self.config_instance.reload_config()


class DifyConfig:
    """Dify 配置管理类"""

    _instance = None
    _config = None
    _observer = None
    _observer_thread = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DifyConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()
            self._init_default_model()
            self._start_file_watcher()

    def _start_file_watcher(self):
        """启动文件监听器"""
        try:
            config_path = Path(__file__).parent.parent / "dify.yaml"
            config_dir = config_path.parent

            self._observer = Observer()
            event_handler = ConfigFileHandler(self)
            self._observer.schedule(event_handler, str(config_dir), recursive=False)

            # 在后台线程中启动监听器
            self._observer_thread = threading.Thread(target=self._observer.start)
            self._observer_thread.daemon = True
            self._observer_thread.start()

            logger.info("配置文件监听器已启动")

        except Exception as e:
            logger.error(f"启动文件监听器失败: {e}")

    def stop_file_watcher(self):
        """停止文件监听器"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("配置文件监听器已停止")

    def _load_config(self):
        """加载配置文件"""
        try:
            # 获取配置文件路径
            config_path = Path(__file__).parent.parent / "dify.yaml"

            if not config_path.exists():
                logger.error(f"Dify配置文件不存在: {config_path}")
                self._config = {}
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

            logger.info("Dify配置文件加载成功")

        except Exception as e:
            logger.error(f"加载Dify配置文件失败: {e}")
            self._config = {}

    def _init_default_model(self):
        """恢复默认模型"""
        # 首次加载时将current_model改为xunfei
        try:# 获取配置文件路径
            config_path = Path(__file__).parent.parent / "dify.yaml"
            if self._config.get('models', {}).get('current_model') != 'xunfei':
                self._config['models']['current_model'] = 'xunfei'
                logger.info("首次加载，将current_model设置为xunfei")
                # 同时更新配置文件
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(self._config, f, default_flow_style=False, allow_unicode=True)
                logger.info("配置文件已更新")
        except Exception as e:
            logger.error(f"恢复默认模型失败: {e}")

    def reload_config(self):
        """重载配置文件"""
        logger.info("开始重载Dify配置文件")
        self._load_config()
        logger.info("Dify配置文件重载完成")

    def set_current_model(self, model_name: str) -> bool:
        """设置当前使用的模型"""
        try:
            # 检查模型是否存在于配置中
            if model_name not in self._config.get('models', {}):
                logger.error(f"模型 {model_name} 不存在于配置中")
                return False

            # 获取配置文件路径
            config_path = Path(__file__).parent.parent / "dify.yaml"

            if not config_path.exists():
                logger.error(f"Dify配置文件不存在: {config_path}")
                return False

            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            # 修改current_model
            config_data['models']['current_model'] = model_name

            # 写回配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config_data, f, default_flow_style=False, allow_unicode=True)

            # 更新内存中的配置
            self._config['models']['current_model'] = model_name

            logger.info(f"成功将当前模型设置为: {model_name}")
            return True

        except Exception as e:
            logger.error(f"设置当前模型失败: {e}")
            return False

    def get_available_models(self) -> list:
        """获取可用的模型列表"""
        models_config = self._config.get('models', {})
        available_models = []

        # 排除非模型配置项
        exclude_keys = ['switch', 'api-key', 'url', 'current_model']
        for key in models_config.keys():
            if key not in exclude_keys:
                available_models.append(key)

        return available_models

    def get_user(self) -> str:
        """获取用户信息"""
        return self._config.get('user', '')

    def get_vision_switch(self) -> bool:
        """获取视觉开关状态"""
        return self._config.get('vision', {}).get('switch', False)

    def get_recognize_api_key(self) -> str:
        """获取识别API密钥"""
        return self._config.get('vision', {}).get('recognize-api-key', '')

    def get_recognize_url(self) -> str:
        """获取识别URL"""
        return self._config.get('vision', {}).get('recognize-url', '')

    def get_models_switch(self) -> bool:
        """获取模型开关状态"""
        return self._config.get('models', {}).get('switch', False)

    def get_models_api_key(self) -> str:
        """获取模型API密钥"""
        return self._config.get('models', {}).get('api-key', '')

    def get_models_url(self) -> str:
        """获取模型URL"""
        return self._config.get('models', {}).get('url', '')

    def get_model_dify_type(self,model_name) -> str:
        """获取模型类型"""
        return self._config.get('models', {}).get(model_name, {}).get('dify_type', '')

    def get_current_mode(self) -> str:
        """获取模型类型"""
        return self._config.get('models', {}).get('current_model','')

difyconfig = DifyConfig()