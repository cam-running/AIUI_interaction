# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   log_message_conf.PY
# @Time       2025-05-28 21:20

from conf.basic import GlobalConf


class InitLogConfig:
    def __init__(self, file_name, log_path=GlobalConf.log_path, other_conf=None):
        self.file_name = file_name
        self.log_path = log_path
        if other_conf:
            self.log_level = other_conf.get("log_level", "DEBUG")
            self.log_type = other_conf.get("log_type", "")
            self.to_console = other_conf.get("to_console", True)
            self.rotation_size = other_conf.get("rotation_size", "10 MB")
            self.retention_date = other_conf.get("retention_date", "10 days")
            # full or single
            self.format_key = other_conf.get("format_key", "full")
            self.clear_default = other_conf.get("clear_default", False)


class LoggerInstance:
    logger_main = None
    logger_print = None
    logger_service = None
    logger_global = None


if __name__ == "__main__":
    pass
