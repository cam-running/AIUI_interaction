# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   baidu_ai_pic.PY
# @Time       2025-05-29 20:20

import os
import base64

from aip import AipFace
from loguru import logger

class BaiduAip:
    def __init__(self, app_id: str, api_key: str, secret_key: str, default_group: str = "group5"):
        self.app_id = app_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.default_group = default_group
        self.client = AipFace(self.app_id, self.api_key, self.secret_key)

    def add_group(self, group: str = None):
        if not group:
            group = self.default_group
        r = self.client.groupAdd(group)
        logger.debug(f"创建组结果:{r}")
        return r

    def add_user(self, pic_file: str, user_info: str, user_id: str, group: str = None,
                 other_options: dict = None):
        if not group:
            group = self.default_group
        if not os.path.isfile(pic_file):
            logger.error(f"人脸图片:{pic_file},不存在")
            return
        with open(pic_file, "rb") as f:
            image = base64.b64encode(f.read()).decode()
        options = {"user_info": user_info}
        if other_options:
            options.update(other_options)
        r = self.client.addUser(image, "BASE64", group, user_id, options)
        logger.debug(f"添加用户结果:{r}")
        return r

    def search_user(self, pic_file: str, group_list_str: str = None):
        if not group_list_str:
            group_list_str = self.default_group
        if not os.path.isfile(pic_file):
            logger.error(f"人脸图片:{pic_file},不存在")
            return
        with open(pic_file, "rb") as f:
            image = base64.b64encode(f.read()).decode()
        r = self.client.search(image, "BASE64", group_list_str)
        logger.debug(f"对比结果:{r}")
        return r


if __name__ == "__main__":
    pass
