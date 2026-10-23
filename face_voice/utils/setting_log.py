# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   setting_log.PY
# @Time       2025-05-29 20:30

import os
import sys
from datetime import datetime
from loguru import _file_sink, logger
from loguru._file_sink import FileDateFormatter
from conf.log_message_conf import LoggerInstance

class GlobalConf:
    log_path = None
    home_path = os.path.expanduser("~")



class LogConfig:
    def __init__(self, file_name=None, log_path=None, log_level="DEBUG",
                 to_console=False, log_type=None, format_key="full",
                 rotation_size="10 MB", retention_date="30 days",
                 clear_default=False, global_log=False):
        self.file_name = file_name
        self.log_path = log_path or os.path.join(GlobalConf.home_path, "logs")
        self.log_level = log_level.upper()
        self.to_console = to_console
        self.log_type = log_type
        self.format_key = format_key
        self.rotation_size = rotation_size
        self.retention_date = retention_date
        self.clear_default = clear_default
        self.global_log = global_log


class SettingLog:

    def __init__(self, config_class=None):
        self.config = config_class or LogConfig()
        self.handle_id_list = []
        self.global_handle_id = None
        self.set_flag = False
        self.log_full_path = ""
        self.format_dict = {
            "full": "<light-cyan>{time:YYYY-MM-DD HH:mm:ss,SSS}</light-cyan> <light-red>|</light-red> "
                    "<level>{level: <8}</level> <light-red>|</light-red> "
                    "<level>{message}</level> <light-red>|</light-red> "
                    "<light-magenta>{name}-{line}</light-magenta>",
            "single": "<light-cyan>{time:YYYY-MM-DD HH:mm:ss.f}</light-cyan> | "
                      "<level>{level: <8}</level>| <level>{message}</level>"
        }
        self.use_format = self.format_dict.get(self.config.format_key, "full")
        if self.config.log_path and not os.path.isdir(self.config.log_path):
            os.makedirs(self.config.log_path, exist_ok=True)
        if self.config.clear_default:
            logger.remove(handler_id=None)
        self._setup_logger()
        self.config = config_class or LogConfig()
        self.global_logger = LoggerInstance.logger_global

    def _setup_logger(self):
        if self.config.file_name:
            self.log_full_path = os.path.join(self.config.log_path, self.config.file_name)
            file_handler_id = logger.add(
                self.log_full_path,
                filter=self._get_log_filter(),
                rotation=self.config.rotation_size,
                retention=self.config.retention_date,
                level=self.config.log_level,
                format=self.use_format,
                enqueue=True,
                encoding="utf-8"
            )
            self.handle_id_list.append(file_handler_id)
        if self.config.to_console:
            console_handler_id = logger.add(
                sys.stdout,
                filter=self._get_log_filter(),
                level=self.config.log_level,
                format=self.use_format,
                enqueue=True,
                colorize=True
            )
            self.handle_id_list.append(console_handler_id)
        if self.config.global_log and LoggerInstance.logger_global:
            global_log_path = os.path.join(GlobalConf.log_path or GlobalConf.home_path, f"global.log")
            self.global_handle_id = logger.add(
                global_log_path,
                filter=self._get_log_filter(include_type=False),
                rotation=self.config.rotation_size,
                retention=self.config.retention_date,
                level=self.config.log_level,
                format=self.use_format,
                enqueue=True,
                encoding="utf-8"
            )
        self.set_flag = True

    def _get_log_filter(self, include_type=True):
        log_type = self.config.log_type
        def filter_func(record):
            if not log_type or not include_type:
                return True
            return record["extra"].get("type") == log_type
        return filter_func

    def _log_message(self, level, message):
        if not self.set_flag:
            self._setup_logger()
        log_method = getattr(logger, level)
        if self.config.log_type:
            log_method = logger.bind(type=self.config.log_type).opt(depth=2)
            log_method = getattr(log_method, level)
        log_method(message)

    def debug(self, message):
        self._log_message("debug", message)

    def info(self, message):
        self._log_message("info", message)

    def success(self, message):
        self._log_message("success", message)

    def warning(self, message):
        self._log_message("warning", message)

    def error(self, message):
        self._log_message("error", message)

    def critical(self, message):
        self._log_message("critical", message)

    def del_logger(self):
        for handle_id in self.handle_id_list:
            logger.remove(handle_id)
        if self.global_handle_id:
            logger.remove(self.global_handle_id)
        self.handle_id_list = []
        self.global_handle_id = None
        self.set_flag = False



def _generate_rename_path(root, ext, creation_time):
    creation_datetime = datetime.fromtimestamp(creation_time)
    date = FileDateFormatter(creation_datetime)
    counter = 1
    renamed_path = "{}{}_{:%Y%m%d_%H%M%S_%f}_{}{}".format(root, ext, date, counter, ext)
    while os.path.exists(renamed_path):
        counter += 1
        renamed_path = "{}{}_{:%Y%m%d_%H%M%S_%f}_{}{}".format(root, ext, date, counter, ext)

    return renamed_path


setattr(_file_sink, "generate_rename_path", _generate_rename_path)

if __name__ == "__main__":
    pass
