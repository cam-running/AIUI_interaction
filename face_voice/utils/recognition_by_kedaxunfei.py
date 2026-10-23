# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   recognition_by_kedaxunfei.PY
# @Time       2025-05-30 20:40

from ws4py.client.threadedclient import WebSocketClient
import base64
import hashlib
import json
import time
import uuid
import requests


class ApiClient(WebSocketClient):
    def __init__(self, logger, message, save_file, *args, **kwargs):
        self.message = message
        self.save_file = save_file
        self.end_flag = False
        self.logger = logger
        super().__init__(*args, **kwargs)

    def send(self, data, binary=False):
        try:
            super().send(data, binary)
        except Exception as e:
            self.logger.error(f"发送数据失败: {e}")

    def opened(self):
        pass

    def close(self, code=1000, reason=''):
        try:
            if self.sock and self.sock.fileno() != -1:
                WebSocketClient.close(self, code=code, reason=reason)
        except Exception as e:
            self.logger.warning(f"尝试关闭连接时发生错误: {e}")
        finally:
            self.sock.close()

    def closed(self, code, reason=None):
        if code == 1000:
            self.logger.info("tts连接正常关闭")
        else:
            self.logger.error(f"连接异常关闭，code：{code}，reason：{reason}")

    def received_message(self, m):
        s = json.loads(str(m))
        if s['action'] == "started":
            self.send(self.message.encode("utf-8"))
            self.send(bytes("--end--".encode("utf-8")))

        elif s['action'] == "result":
            data = s['data']
            if data['sub'] == "tts":
                self.logger.debug(f"tts文字:{self.message} " + base64.b64decode(data['content']).decode())
                mp3_url = base64.b64decode(data['content']).decode()
                response = requests.get(mp3_url, stream=True)
                if response.status_code == 200:
                    with open(self.save_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                    self.logger.debug(f"文件已成功下载到 {self.save_file}")
                    self.end_flag = True
                else:
                    self.logger.error(f"下载失败，状态码：{response.status_code}")

        else:
            self.logger.warning(f"未支持的情况:{s}")


def make_tts_kedaxunfei(logger, app_id, api_key, vcn, tts_message, save_file):
    base_url = "ws://wsapi.xfyun.cn/v1/aiui"
    param_tts = """{{
                "auth_id": "ydtts000000000000000000000000000",
                "data_type": "text",
                "vcn": \"""" + vcn + """\",
                "scene": "IFLYTEK.tts",
                "tts_res_type": "url",
                "context": "{{\\\"sdk_support\\\":[\\\"tts\\\"]}}",
                "sn":"jiangsuyidong-00:00:00:00:00:00"
            }}"""
    run_time = int(time.time())
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    auth_id = hashlib.md5(":".join([mac[e:e + 2] for e in range(0, 11, 2)]).encode("utf-8")).hexdigest()
    param = param_tts.format(auth_id).encode(encoding="utf-8")
    param_base64 = base64.b64encode(param).decode()
    check_sum_pre = f"{api_key}{run_time}{param_base64}"
    check_sum = hashlib.md5(check_sum_pre.encode("utf-8")).hexdigest()
    run_url = f"{base_url}?appid={app_id}&checksum={check_sum}&param={param_base64}&curtime={run_time}&signtype=md5"
    try:
        ws = ApiClient(logger=logger, message=tts_message, save_file=save_file, url=run_url, protocols=['chat'],
                       headers=[("Origin", "https://wsapi.xfyun.cn")])
        ws.connect()
        ws.run_forever()
        end_flag = ws.end_flag
    except BrokenPipeError as error_message:
        logger.warning(f"tts下载失败:{error_message}")
        end_flag = False
    except Exception as error_message:
        logger.warning(f"tts下载异常:{error_message}")
        end_flag = False
    return end_flag


if __name__ == "__main__":
    pass
