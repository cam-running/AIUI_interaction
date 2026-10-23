# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   listen_action.PY
# @Time       2025-05-30 23:05

import threading
import subprocess
import time

from conf.basic import GlobalConf


def loading_action(logger):
    logger.info("加载动作监听")

    while 1:
        if GlobalConf.server_queue.empty():
            time.sleep(0.1)
            continue
        server_data = GlobalConf.server_queue.get(timeout=1)
        logger.info(f"接收到的数据:{server_data}")
        name = server_data.get("name")
        data_list = server_data.get("data")
        num = server_data.get("num")
        if not name or not num:
            logger.warning(f"数据错误:{server_data}")
            continue
        if data_list and not isinstance(data_list, list):
            logger.warning(f"数据错误:{server_data}")
            continue
        data_str = " ".join(data_list)
        command = f"/home/unitree/catkin_ws/arm_cmd_control/arm_cmd_control eth0 {name} {data_str}"
        logger.info(f"执行命令:{command}")
        GlobalConf.action_num = num
        try:
            GlobalConf.action_status = True
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            ret = result.stdout.strip()
            logger.info(f"命令输出:{ret}")
        except Exception as error_message:
            logger.error(f"执行命令失败:{error_message}")
        finally:
            GlobalConf.action_status = False

        time.sleep(0.4)


def run_action(logger):
    action_thread = threading.Thread(target=loading_action, args=(logger,), name="Thread")
    action_thread.start()


if __name__ == "__main__":
    pass
