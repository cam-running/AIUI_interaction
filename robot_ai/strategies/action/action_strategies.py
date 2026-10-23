import re
from utils.logger import logger
import threading

import requests

from config.config.settings import config
from .base_strategy import ActionStrategy

from config.config.action_config import get_action_dict, get_point_dict

"""
文件:action_strategies.py
功能: 定义具体的策略类
"""
__Author__ = "xueYang"


# 使用全局配置实例，无需重复加载
API_ACTION_URL = config.get_pc2_url('robot_action')
API_WAYPOINT_URL = config.get_pc2_url('robot_waypoint')
API_CMD_URL = config.get_pc2_url('robot_cmd_action')
API_TTS_URL = config.get_config().get('music_url')

class RealTimeActionStrategy(ActionStrategy):

    def execute(self, skill: str):
        """执行实时交互动作"""
        logger.info(f"执行动作:{skill}")
        thread = threading.Thread(
            target=self._execute_real_time_action,
            args=(skill,),
            daemon=True
        )
        thread.start()

    def _execute_real_time_action(self, skill: str):
        """实际执行实时交互动作的方法"""
        # 这里实现具体的实时交互逻辑
        try:
            logger.info(f"执行动作:{skill}")
            action_dict = get_action_dict()
            logger.info(f"动作字典: {action_dict}")
            param = action_dict.get(skill)
            logger.info(f"获取到的动作参数: {param}")
            logger.info(
                "========================API接口===========================: %s", API_ACTION_URL)
            # if skill
            if param is not None:
                if re.fullmatch(r'PLAY_MUSIC', skill):
                    logger.info(f"检测到音乐播放指令: {skill}")
                    print(f"检测到音乐播放指令: {skill}")
                    self.send_tts_request("play", "dodge.mp3")

                if re.fullmatch(r'STOP_MUSIC', skill):
                    logger.info(f"检测到音乐停止指令: {skill}")
                    self.send_tts_request("stop", "dodge.mp3")

                try:
                    response = requests.post(API_ACTION_URL, json={"data": param}, timeout=5)
                    logger.info(f"API响应状态: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"请求执行动作失败: {str(e)}")
            else:
                logger.error(f"未找到动作 {skill} 对应的参数")
        except Exception as e:
            logger.error(f"执行动作时发生错误: {str(e)}")

    def send_tts_request(self, control_type: str, tts_file: str):
        payload = {"control_type": control_type, "tts_file": tts_file}
        try:
            response = requests.post(API_TTS_URL, json=payload, timeout=5)
            if response.status_code == 200:
                logger.info(f"TTS请求成功: {control_type}, 文件: {tts_file}")
            else:
                logger.warning(f"TTS请求返回异常状态码: {response.status_code}, 文件: {tts_file}")
        except requests.exceptions.RequestException as e:
            logger.error(f"TTS请求失败: {str(e)}, 文件: {tts_file}")


class NaviWayPointStrategy(ActionStrategy):
    def execute(self, skill: str):
        """执行点控动作"""
        logger.info(f"执行点控:{skill}")
        thread = threading.Thread(
            target=self._execute_navigation,
            args=(skill,),
            daemon=True
        )
        thread.start()

    def _execute_navigation(self, skill: str):
        """实际执行点位动作的方法"""
        # 这里实现具体的点控逻辑
        try:
            logger.info(f"执行点控:{skill}")
            param = get_point_dict().get(skill)
            requests.post(API_WAYPOINT_URL, json={"data": param})

        except requests.exceptions.RequestException as e:
            logger.error(f"请求API失败: {str(e)}")


class CMDActionStrategy(ActionStrategy):
    def execute(self, skill: str):
        """执行CMD动作"""
        logger.info(f"执行CMD动作:{skill}")
        thread = threading.Thread(
            target=self._execute_cmd_action,
            args=(skill,),
            daemon=True
        )
        thread.start()

    def _execute_cmd_action(self, skill: str):
        try:
            logger.info(f"执行CMD动作:{skill}")
            param = skill
            #判断 skill 值为ZWJS时,发送参数为17;JSWRJZQ 时，发送参数为18
            if skill == "ZWJS":
                param = "17"
            elif skill == "JSWRJZQ":
                param = "18"
            requests.post(API_CMD_URL, json={"data": param})
        except requests.exceptions.RequestException as e:
            logger.error(f"请求API失败: {str(e)}")

# class AiotSceneStrategy(ActionStrategy):
#     def execute(self, skill: str):
#         """执行AIOT场景动作"""
#         logger.info(f"执行AIOT场景动作:{skill}")
#         thread = threading.Thread(
#             target=aiot_controller.execute_scene,
#             args=(skill,),
#             daemon=True
#         )
#         thread.start()
#
# class AiotDeviceStrategy(ActionStrategy):
#     def execute(self, skills: str):
#         """执行AIOT设备控制动作"""
#         state = skills.split("_", 1)[0]
#         device_name = skills.split("_", 1)[1]
#         logger.info(f"执行设备控制:{device_name} 状态:{state}")
#
#         thread = threading.Thread(
#             target=aiot_controller.control_device_power,
#             args=(device_name, state),
#             daemon=True
#         )
#         thread.start()
