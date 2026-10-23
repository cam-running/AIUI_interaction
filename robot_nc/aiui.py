import _thread as thread
import base64
import datetime
import hashlib
import hmac
import json
import traceback
from urllib.parse import urlparse
import time
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websocket

# 修改应用应用配置和文件地址后直接执行即可

# 请求地址
url = "wss://aiui.xf-yun.com/v3/aiint/sos"

# 应用配置
appid = "f016fce3"
api_key = "fcb58dc79de9b0568d2287bd8184e291"
api_secret = "YTFiN2NkOGVjNTVjY2QyMTlmMTViOTBh"

sn = "test-sn"

# 场景
scene = "test_box"

vcn = "x5_lingxiaoyue_flow"

# 请求类型用来设置文本请求还是音频请求，text/audio
data_type = 'text'

# 音频请求需要先设置audio_path
# 当前音频格式默认pcm 16k 16bit，修改音频格式需要修改audioReq中的payload中音频相关参数
# data_type = 'audio'

# 音频请求上传的音频文件路径
text_msg = ""
audio_path = "weather.pcm"

# 文本请求输入的文本
question = "介绍下苏超？"
question = "你好，今天天气怎么样，介绍下苏超"

# 下面两个参数配合音频采样率设置，16k 16bit的音频： 每 40毫秒 发送 1280字节
# 每帧音频数据大小，单位字节
frame_size = 1280
# 每帧音频发送间隔
sleep_inetrval = 0.04


class AIUIV3WsClient(object):
    # 初始化
    def __init__(self):
        self.handshake = self.assemble_auth_url(url)

    # 生成握手url
    def assemble_auth_url(self, base_url):
        host = urlparse(base_url).netloc
        path = urlparse(base_url).path
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + path + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        print(signature_origin)
        signature_sha = hmac.new(api_secret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(
            signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

        print('get authorization_origin:', authorization_origin)
        authorization = base64.b64encode(
            authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "host": host,
            "date": date,
            "authorization": authorization,
        }
        # 拼接鉴权参数，生成url
        url = base_url + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url

    def on_open(self, ws):
        # 连接建立成功后开始发送数据
        print("### ws connect open")
        thread.start_new_thread(self.run, ())

    def run(self):
        if data_type == "text":
            self.text_req()
        if data_type == "audio":
            self.audio_req()

    def text_req(self):
        # 文本请求status固定为3，interact_mode固定为oneshot
        aiui_data = {
            "header": {
                "appid": appid,
                "sn": sn,
                "stmid": "text-1",
                "status": 3,
                "scene": scene,
                "msc.lat": 19.65309164062,
                "msc.lng": 109.259056086,
                "os_sys": "android",
                "interact_mode":"oneshot"
            },
            "parameter": {
                "nlp": {
                    "nlp": {
                        "compress": "raw",
                        "format": "json",
                        "encoding": "utf8"
                    },
                    "new_session": True,
                },
                # 合成参数
                "tts": {
                    # 发音人
                    "vcn": vcn,
                    "tts": {
                        "channels": 1,
                        "bit_depth": 16,
                        "sample_rate": 16000,
                        "encoding": "raw"
                    }
                }
            },
            "payload": {
                "text": {
                    "compress": "raw",
                    "format": "plain",
                    "text": base64.b64encode(question.encode('utf-8')).decode('utf-8'),
                    "encoding": "utf8",
                    "status": 3
                }
            }
        }
        data = json.dumps(aiui_data)
        print('text request data:', data)
        self.ws.send(data)

    def audio_req(self):
        f = open(audio_path, 'rb')
        try:
            f.seek(0, 2)
            eof = f.tell()
            f.seek(0, 0)

            first = True
            status = 0
            while True:
                d = f.read(frame_size)
                if not d:
                    break

                if f.tell() >= eof:
                    # 尾帧
                    status = 2
                elif not first:
                    # 中间帧
                    status = 1

                req = self.genAudioReq(d, status)
                first = False
                self.ws.send(req)
                # 发送间隔
                time.sleep(sleep_inetrval)
        finally:
            f.close()

    def genAudioReq(self, data, status):
        # 构造pcm音频请求参数
        aiui_data = {
            "header": {
                "appid": appid,
                "sn": sn,
                "stmid": "audio-1",
                "status": status,
                "scene": scene,
                "interact_mode": "continuous"
            },
            "parameter": {
                "nlp": {
                    "nlp": {
                        "compress": "raw",
                        "format": "json",
                        "encoding": "utf8"
                    },
                    "new_session": True
                },
                # 合成参数
                "tts": {
                    # 发音人
                    "vcn": vcn,
                    "tts": {
                        "channels": 1,
                        "bit_depth": 16,
                        "sample_rate": 16000,
                        "encoding": "raw"
                    }
                }
            },
            "payload": {
                "audio": {
                    "encoding": "raw",
                    "sample_rate": 16000,
                    "channels": 1,
                    "bit_depth": 16,
                    "status": status,
                    "audio": base64.b64encode(data).decode(),
                }
            }
        }
        return json.dumps(aiui_data)

    # 收到websocket消息的处理
    def on_message(self, ws, message):
        try:
            data = json.loads(message)

            # print('原始结果:', message)
            header = data['header']
            code = header['code']
            # 结果解析
            if code != 0:
                print('请求错误：', code, json.dumps(data, ensure_ascii=False))
                ws.close()
            sid = header.get('sid', "sid")
            payload = data.get('payload', {})
            parameter = data.get('parameter', {})
            if 'event' in payload:
                # 事件结果
                event_json = payload['event']
                event_text_bs64 = event_json['text']
                event_text = base64.b64decode(event_text_bs64).decode('utf-8')
                print("事件，", event_text)
            if 'iat' in payload:
                # 识别结果
                iat_json = payload['iat']
                iat_text_bs64 = iat_json['text']
                iat_text = base64.b64decode(iat_text_bs64).decode('utf-8')
                print("识别结果，seq：", iat_json['seq'], "，status：",
                      iat_json['status'], "，", self.parse_iat_result(iat_text))
            if 'cbm_tidy' in payload:
                # 语义规整结果（历史改写），意图拆分
                cbm_tidy_json = payload['cbm_tidy']
                cbm_tidy_text_bs64 = cbm_tidy_json['text']
                cbm_tidy_text = base64.b64decode(
                    cbm_tidy_text_bs64).decode('utf-8')
                cbm_tidy_json = json.loads(cbm_tidy_text)
                print("语义规整结果：")
                intents = cbm_tidy_json['intent']
                for intent in intents:
                    print("  intent index：",
                          intent['index'], "，意图语料：", intent['value'])
            if 'cbm_intent_domain' in payload:
                # 意图拆分后的落域结果
                cbm_intent_domain_json = payload['cbm_intent_domain']
                cbm_intent_domain_text_bs64 = cbm_intent_domain_json['text']
                cbm_intent_domain_text = base64.b64decode(
                    cbm_intent_domain_text_bs64).decode('utf-8')
                index = self.get_intent_index(parameter, "cbm_intent_domain")
                print("intent index：", index, "，落域结果：", cbm_intent_domain_text)
            if 'cbm_semantic' in payload:
                # 技能结果
                cbm_semantic_json = payload['cbm_semantic']
                cbm_semantic_text_bs64 = cbm_semantic_json['text']
                cbm_semantic_text = base64.b64decode(
                    cbm_semantic_text_bs64).decode('utf-8')
                cbm_semantic_json = json.loads(cbm_semantic_text)
                index = self.get_intent_index(parameter, "cbm_semantic")
                if cbm_semantic_json['rc'] != 0:
                    print("intent index：", index, "，技能结果：说法：",
                          cbm_semantic_json['text'], "，", cbm_semantic_text)
                else:
                    print("intent index：", index, "，技能结果：说法：",
                          cbm_semantic_json['text'], "，命中技能：", cbm_semantic_json['category'], "，回复：", cbm_semantic_json['answer']['text'])
            if 'nlp' in payload:
                # 语义结果，经过大模型润色的最终结果
                nlp_json = payload['nlp']
                nlp_text_bs64 = nlp_json['text']
                nlp_text = base64.b64decode(nlp_text_bs64).decode('utf-8')
                print("语义结果 seq：", nlp_json['seq'], "，status：",
                      nlp_json['status'], "，nlp.text: ", nlp_text)
            if 'tts' in payload:
                # 将结果保存到文件，文件后缀名需要根据tts参数中的encoding来决定
                audioData = payload['tts']['audio']
                if audioData != None:
                    audioBytes = base64.b64decode(audioData)
                    print("tts结果: ", len(audioBytes), " 字节")
                    with open(sid + "." + self.get_suffix(payload['tts']['encoding']), 'ab') as file:
                        file.write(audioBytes)

            if 'status' in header and header['status'] == 2:
                # 接收最后一帧结果，关闭连接
                ws.close()
        except Exception as e:
            traceback.print_exc()
            pass

    def parse_iat_result(self, iat_res):
        iat_text = ""
        iat_res_json = json.loads(iat_res)
        for cw in iat_res_json['text']['ws']:
            for cw_item in cw["cw"]:
                iat_text += cw_item['w']

        return iat_text

    def get_intent_index(self, parameter, key):
        if key in parameter:
            return parameter[key]['loc']['intent']

        return "-"

    def get_suffix(self, encoding):
        if encoding == 'raw':
            return 'pcm'
        if encoding == 'lame':
            return 'mp3'

        return 'unknow'

    def on_error(self, ws, error):
        print("### connection error: ", str(error))
        ws.close()

    def on_close(self, ws, close_status_code, close_msg):
        print("### connection is closed ###, cloce code:", close_status_code)

    def start(self):
        self.ws = websocket.WebSocketApp(
            self.handshake,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.ws.run_forever()


if __name__ == "__main__":

    client = AIUIV3WsClient()
    client.start()
