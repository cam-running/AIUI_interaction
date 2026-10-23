'''
Author: zhaoyong 77912776@qq.com
Date: 2025-08-16 16:55:13
LastEditTime: 2025-08-16 18:31:31
LastEditors: zhaoyong 77912776@qq.com
FilePath: \robot_ai\strategies\vision\qwenv.py
Description: 头部注释配置模板
'''
import os
import dashscope
from utils.logger import logger


# 处理base64图片
def process_base64_image(base64_pic: str = '', question: str = '描述下你看到了什么'):
    # 示例参照
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "text": "你是一个具身智能机器人，你具备详尽观察和描述环境的能力，能够准确捕捉场景中的人物、物体、颜色、动作，以及它们的空间位置和相互关系。描述内容必须从\"我面前的是\"开始，以第一人称视角表达，语句完整流畅，并保留必要的逗号和句号。禁止出现\"图中\"、\"图片中\"等类似表达，不使用markdown、列表、代码块、引号，并且不得出现多余的换行。回复字数在20~40个字符"}
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "image": ""},
                {"text": "描述下你看到了什么"}]
        }]
    if base64_pic:
        pic_content = "data:image/jpeg;base64," + base64_pic
        messages[1]["content"][0]["image"] = pic_content
    messages[1]["content"][1]["text"] = question
    try:
        from config.config.settings import config
        baolian_api_key = config._config_data.get(
            'baolian_api_key', 'sk-1dcf9fc95ee54c3bbb2a3fdc9ebaa49f')
        baolian_model = config._config_data.get(
            'baolian_model', 'qwen-vl-max-latest')

        dashscope.api_key = baolian_api_key

        # 发送图片到模型
        response = dashscope.MultiModalConversation.call(
            model=baolian_model,
            messages=messages
        )
        # 解析响应（描述内容）
        result = response.output.choices[0].message.content[0]["text"]
        return result
    except Exception as e:
        logger.info(e)


def qwen_nlp(question: str = '描述下你看到了什么'):
    # 示例参照
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "text": "你是一个具身智能机器人，快速理解意图，并用口语化的方式作出回答，语气自然、语速适中，回答简洁明了，适合语音播放，不使用markdown、列表、代码块、引号，并且不得出现多余的换行。回复字数在20~40个字符"}
            ]
        },
        {
            "role": "user",
            "content": "你是谁？"
        }]
    messages[1]["content"] = question
    try:
        from config.config.settings import config
        baolian_api_key = config._config_data.get(
            'baolian_api_key', 'sk-1dcf9fc95ee54c3bbb2a3fdc9ebaa49f')
        baolian_nlp_model = config._config_data.get(
            'baolian_nlp_model', 'qwen-plus-latest')

        dashscope.api_key = baolian_api_key

        # 发送图片到模型
        response = dashscope.Generation.call(
            model=baolian_nlp_model,
            messages=messages
        )
        if response and response.get("output") and response["output"].get("text"):
            result = response["output"]["text"]
            return result
        else:
            return "抱歉，我当前无法处理这个问题，请再说一遍"

    except Exception as e:
        logger.info(f"千问NLP处理异常: {e}")
        return "抱歉，处理出现异常"


if __name__ == '__main__':
    pass
