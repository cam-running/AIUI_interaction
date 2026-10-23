"""
Author: zhaoyong 77912776@qq.com
Date: 2025-08-23 14:37:39
LastEditTime: 2025-08-23 20:43:45
LastEditors: zhaoyong 77912776@qq.com
FilePath: robot_ai/utils/pc2_requests.py
Description: PC2网络请求模块 - 异步版本
"""
import time
import aiohttp
import asyncio
import threading
from utils.logger import logger

# 延迟加载配置，避免循环导入


def _get_config():
    from config.config.settings import config
    return config


def _get_api_urls():
    config = _get_config()
    return config.get_config().get('qa_callback_url'), config.get_pc2_url('led')


API_QA_CALLBACK_URL, API_LED_URL = _get_api_urls()

# 防重复调用机制
_last_qa_request = {"time": 0, "content": ""}
_last_led_request = {"time": 0, "mode": "", "color": ""}
_REQUEST_INTERVAL = 0.5  # 请求间隔（秒）


async def _send_qa_task_async(result):
    """将结果异步发送到外部接口--欣网前端"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_access_token"
    }

    logger.info(f"开始识别内容 result: {result}")

    # 组织 payload
    payload = {}
    if result.get("question"):
        payload = {
            "question": result["question"],
            "time": time.time(),
        }
    elif result.get("result"):
        payload = {
            "answer": result["result"],
            "time": time.time(),
        }

    logger.info(f"准备发送识别结果到 QA callBack 接口: {payload}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_QA_CALLBACK_URL, json=payload, headers=headers, timeout=5) as response:
                if response.status == 200:
                    logger.info("结果已成功发送到 QA callBack 接口")
                    return True
                else:
                    text = await response.text()
                    logger.error(f"接口返回错误状态码: {response.status}, 响应内容: {text}")
                    return False
    except Exception as e:
        logger.error(f"QA callBack 接口请求失败: {e}")
        return False


async def _send_led_color_task_async(mode, color):
    """异步改变灯带颜色"""
    payload = {"mode": mode, "color": color}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_LED_URL, json=payload, timeout=5) as response:
                if response.status == 200:
                    logger.info("灯带颜色设置成功")
                    return True
                else:
                    text = await response.text()
                    logger.error(
                        f"灯带颜色设置失败，状态码: {response.status}, 响应: {text}")
                    return False
    except aiohttp.ClientConnectionError:
        logger.error("LED 接口调用失败，连接错误")
        return False
    except Exception as e:
        logger.error(f"LED 接口调用失败: {e}")
        return False


def _send_qa_task(self, result):
    """同步包装器，用于兼容现有代码"""
    global _last_qa_request

    # 防重复调用检查
    current_time = time.time()
    content_hash = str(result)

    # 如果内容相同且时间间隔太短，跳过请求
    if (_last_qa_request["content"] == content_hash and
            current_time - _last_qa_request["time"] < _REQUEST_INTERVAL):
        logger.debug(f"跳过重复的QA请求: {result}")
        return True

    # 更新最后请求记录
    _last_qa_request["time"] = current_time
    _last_qa_request["content"] = content_hash

    def run_async():
        asyncio.run(_send_qa_task_async(result))

    # 在后台线程中运行异步函数，不阻塞主流程
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    return True


def _send_led_color_task(self, mode, color):
    """同步包装器，用于兼容现有代码"""
    global _last_led_request

    # 防重复调用检查
    current_time = time.time()

    # 如果参数相同且时间间隔太短，跳过请求
    if (_last_led_request["mode"] == mode and
        _last_led_request["color"] == color and
            current_time - _last_led_request["time"] < _REQUEST_INTERVAL):
        logger.debug(f"跳过重复的LED请求: mode={mode}, color={color}")
        return True

    # 更新最后请求记录
    _last_led_request["time"] = current_time
    _last_led_request["mode"] = mode
    _last_led_request["color"] = color

    def run_async():
        asyncio.run(_send_led_color_task_async(mode, color))

    # 在后台线程中运行异步函数，不阻塞主流程
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    return True
