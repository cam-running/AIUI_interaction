# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   init_logger.PY
# @Time       2025-05-30 23:00

import os
from conf.basic import GlobalConf
from datetime import datetime
from conf.log_message_conf import LoggerInstance
from utils.setting_log import SettingLog, LogConfig


def init_logger(no_console_list: list = None):
    if not no_console_list:
        no_console_list = ["logger_global"]

    log_path = GlobalConf.log_path or os.path.join(GlobalConf.home_path, "logs")
    os.makedirs(log_path, exist_ok=True)
    log_level = "DEBUG"
    current_date = datetime.now().strftime("%Y-%m-%d")
    global_config = LogConfig(
        file_name=f"global_{current_date}.log",
        log_path=log_path,
        log_level=log_level,
        to_console=False,
        format_key="full",
        clear_default=True,
        global_log=False
    )
    global_logger = SettingLog(global_config)
    setattr(LoggerInstance, "logger_global", global_logger)
    logger_list = [_ for _ in LoggerInstance.__dict__.keys()
                  if _.startswith("logger_") and _ != "logger_global"]

    for name in logger_list:
        file_name = name.replace("logger_", "") + ".log"
        to_console = name not in no_console_list
        format_key = "full" if name in no_console_list else "single"

        logger_config = LogConfig(
            file_name=file_name,
            log_path=log_path,
            log_level=log_level,
            to_console=to_console,
            log_type=name,
            format_key=format_key,
            global_log=True,
            clear_default=False
        )
        logger_obj = SettingLog(logger_config)
        setattr(LoggerInstance, name, logger_obj)





if __name__ == "__main__":
    pass
