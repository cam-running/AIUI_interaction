# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   log_uvicorn_conf.PY
# @Time       2025-05-28 22:20

import os
from conf.basic import GlobalConf

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "[%(asctime)s] [%(levelname)s] [%(message)s]",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": "[%(asctime)s] [%(levelname)s] [%(status_code)s] [%(message)s]",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access_file": {
            "formatter": "access",
            "class": "logging.handlers.RotatingFileHandler",
            'filename': os.path.join(GlobalConf.log_path, "request.log"),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 20,
            'encoding': 'utf-8',
        },
        "default_file": {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': "default",
            'filename': os.path.join(GlobalConf.log_path, "run.log"),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 20,
            'encoding': 'utf-8',
        }
    },
    "loggers": {
        "uvicorn": {"handlers": ["default", "default_file"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access", "access_file"], "level": "INFO",
                           "propagate": False},
    },
}

if __name__ == "__main__":
    pass
