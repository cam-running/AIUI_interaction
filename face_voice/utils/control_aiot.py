# -*- coding: utf-8 -*-
from conf.log_message_conf import LoggerInstance
import traceback
import urllib.parse
import requests
import time
import random
import hmac
import hashlib
import base64
import sys
import os
import aiohttp
import asyncio
from loguru import logger

# 获取 conf项目目录
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

"""
功能: 与物联中控平台交互服务
"""
__Author__ = "torjean(陶)"

###########################
#注意：物联平台沟通账号，及配置场景
###########################
class ControlConf:
    # 江苏移动业务账号
    aiot_unionId = "18505105276"
    # aiot_unionId = "13951742810"

    # 测试环境配置
    # aiot_platform_host= "http://iot.test.tstar-tech.com:6001"
    # app_id= "DXJSul8kAD4o0vLm"
    # app_secret= "NExpWCKDl7vXb4ElFfqktsFr+Go5tiem"

    # 正式环境配置
    aiot_platform_host = "http://iot.tstar-tech.com:6001"
    aiot_appid = "NVOPaEwo8S61ytrZ"
    aiot_appSecret = "/uUMzm79BK0RPzI8VBgomSRjngXb5/sH"


# 获取系统id并存储
def save_machine_id():
    os_machine_id_file = '/etc/machine-id'
    machine_id_file = os.path.join(project_root, "machine-id")
    try:
        if os.path.exists(os_machine_id_file):
            with open(os_machine_id_file, 'r') as f:
                machine_id = f.read().strip()
            with open(machine_id_file, 'w') as f:
                f.write(machine_id)
        else:
            machine_id = ''.join(random.choices('0123456789abcdef', k=32))
            with open(machine_id_file, 'w') as f:
                f.write(machine_id)
        return machine_id
    except Exception as e:
        print(e)
        machine_id = ''.join(random.choices('0123456789abcdef', k=32))
        with open(machine_id_file, 'w') as f:
            f.write(machine_id)
        return machine_id


# 获取项目存储机器id
def get_machine_id():
    machine_id_file = os.path.join(project_root, "machine-id")
    try:
        if os.path.exists(machine_id_file):
            with open(machine_id_file, 'r') as f:
                machine_id = f.read().strip()
            if machine_id == '':
                return save_machine_id()
            else:
                return machine_id
        else:
            return save_machine_id()
    except Exception as e:
        print(f"Error: {e}")
        return save_machine_id()


# 物联交互相关类
class ControlAIotPlatform:
    # (展箱)场景
    scenes_id = {
        # 明灯id
        "scene_001": '500',
        # 灭灯id
        "scene_002": '501'
    }
    # (展箱)设备具体信息
    resource_info = {
        "livingroom_downlight": {
            'devName': '客厅筒灯',
            'productId': 'RSD00003',
            'deviceId': 'ATARZ4A3000124587C00D2DC',
            'resourceId': 'power1',
            'open': "1",
            'close': "2",
        },
        "rail_light": {
            'devName': '客厅轨道灯',
            'productId': 'U7GE5C7X',
            'deviceId': '0001200d1cc089fffecaf196',
            'resourceId': 'power1',
            'open': True,
            'close': False,
        },
        "light_strip": {
            'devName': '灯带',
            'productId': 'KXYP79V2',
            'deviceId': '0001200d90395efffe80c4ee',
            'resourceId': 'power1',
            'open': True,
            'close': False,
        },
        "ceiling_light": {
            'devName': '吸顶灯',
            'productId': 'KXYP79V2',
            'deviceId': '0001200d90395efffe80c4ee',
            'resourceId': 'power2',
            'open': True,
            'close': False,
        },
        "the_curtains": {
            'devName': '窗帘',
            'productId': 'RSD00005',
            'deviceId': 'ATARWSA40001B8D61AA720B0',
            'resourceId': "work1.work1",
            'open': '1',
            'close': '2',
        }
    }

    def __init__(self, comm_instance=None):
        self.logger = logger
        self.comm_instance = comm_instance
        # 机器id作为userId
        self.machine_id = get_machine_id()
        # 用户密钥
        self.user_secretkey = None
        # access-token
        self.access_token = None
        # refresh-token
        self.refresh_token = None
        self.connect()

    # 一、连接物联平台中控系统,获取用户密钥
    def _get_platform_user_secretkey(self):
        current_timestamp = int(time.time())
        try:
            url = ControlConf.aiot_platform_host + '/cloud-api/app/active'
            to_encode_str = (ControlConf.aiot_appid + str(
                current_timestamp) + ControlConf.aiot_unionId + self.machine_id).encode('utf-8')
            # Base64解码appSecretKey
            decode_app_secret = base64.b64decode(ControlConf.aiot_appSecret)
            # hmac_sha256签名
            hmac_encode_sign = hmac.new(
                decode_app_secret, to_encode_str, hashlib.sha256)
            # Base64编码
            base64_encode_sign = base64.b64encode(
                hmac_encode_sign.digest()).decode('utf-8')

            response = requests.post(url, json={
                "appId": ControlConf.aiot_appid,
                "timestamp": current_timestamp,
                "unionId": ControlConf.aiot_unionId,
                "userId": self.machine_id,
                "sign": base64_encode_sign
            }, timeout=3)
            response_json = response.json()
            # logger.info("1.1 获取用户密钥userSecretKey:", response_json)
            if response_json['code'] == 0:
                return True, response_json['data']['userSecret']
            else:
                logger.info("响应失败:", response_json['msg'])
                return False, response_json['msg']
        except Exception as e:
            print(e)
            return False, e

    # 二、连接物联平台中控系统,获取access-token
    def _get_access_token(self):
        url = ControlConf.aiot_platform_host + '/cloud-api/oauth2/token'

        try:
            authorization = self._generate_authorization()
            request_headers = {
                'Authorization': authorization,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            password = self._generate_password()
            requests_data = {
                "grant_type": 'hmac_sign',
                "username": ControlConf.aiot_appid + '.' + self.machine_id,
                "password": password,
                # 权限
                "scope": 'cloud_write'
            }
            try:
                # print(1111111,request_headers)
                # print(2222222,requests_data)
                encoded_data = urllib.parse.urlencode(requests_data)
                response = requests.post(
                    url, headers=request_headers, data=encoded_data, timeout=3)
                response_json = response.json()
                # logger.info("1.2 获取access-token:", response_json)
                if response_json['code'] == 0:
                    return True, response_json['data']
                else:
                    logger.info("响应失败:", response_json['msg'])
                    return False, response_json['msg']
            except requests.exceptions.RequestException as e:
                print("请求失败:", e)
        except Exception as e:
            traceback.print_exc()
            print(e)

    # 生成初始Authorization
    def _generate_authorization(self):
        try:
            ########## 测试案例###########
            # md5_hex_app_secret = hashlib.md5("/uUMzm79BK0RPzI8VBgomSRjngXb5/sH".encode('utf-8')).hexdigest()
            # authorization = 'Basic ' + base64.b64encode(
            #     ("NVOPaEwo8S61ytrZ" + ':' + md5_hex_app_secret).encode('utf-8')).decode('utf-8')
            ############################
            # md5 appSecret
            md5_hex_app_secret = hashlib.md5(
                ControlConf.aiot_appSecret.encode('utf-8')).hexdigest()
            # 生成Authorization
            authorization = 'Basic ' + base64.b64encode(
                (ControlConf.aiot_appid + ':' + md5_hex_app_secret).encode('utf-8')).decode('utf-8')
            return authorization
        except Exception as e:
            print(e)
            return None

    # 生成password
    def _generate_password(self):
        try:
            appid = ControlConf.aiot_appid
            userid = self.machine_id
            secure_mode = 'hmac_sign'
            timestamp = int(time.time())
            to_encode_str = (appid + secure_mode +
                             str(timestamp) + userid).encode('utf-8')
            # Base64解码userSecretKey
            decoded_user_secret = base64.b64decode(self.user_secretkey)
            # hmac_sha256签名
            hmac_encode_sign = hmac.new(
                decoded_user_secret, to_encode_str, hashlib.sha256)
            # Base64编码
            base64_encode_sign = base64.b64encode(
                hmac_encode_sign.digest()).decode('utf-8')
            # URL 编码
            url_encoded_sign = urllib.parse.quote(base64_encode_sign, safe='')
            password = f'appId={appid}&secureMode={secure_mode}&timestamp={timestamp}&userId={userid}&sign={url_encoded_sign}'
            return password
        except Exception as e:
            print(e)
            traceback.print_exc()
            return None

    # 刷新access-token
    def refresh_access_token(self):
        """
            如果后续接口返回401，则调用该接口刷新access-token
        """
        url = ControlConf.aiot_platform_host + '/cloud-api/oauth2/token'
        try:
            authorization = self._generate_authorization()
            request_headers = {
                'Authorization': authorization,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            requests_data = {
                "grant_type": 'refresh_token',
                "refresh_token": self.refresh_token
            }
            try:
                # print(1111111,request_headers)
                # print(2222222,requests_data)
                encoded_data = urllib.parse.urlencode(requests_data)
                response = requests.post(
                    url, headers=request_headers, data=encoded_data, timeout=3)
                response_json = response.json()
                logger.info("1.3 刷新access-token:", response_json)
                if response_json['code'] == 0:
                    self.access_token = response_json['data']['access_token']
                    self.refresh_token = response_json['data']['refresh_token']
                    return True, ''
                else:
                    logger.info("响应失败:", response_json['msg'])
                    return False, response_json['msg']
            except requests.exceptions.RequestException as e:
                print("请求失败:", e)
        except Exception as e:
            traceback.print_exc()
            print(e)

    # 连接物联平台中控系统,获取access-token
    def connect(self):
        # 一、获取用户密钥

        connect_flag, user_secret = self._get_platform_user_secretkey()
        if connect_flag is False:
            self.logger.error("1.1、获取用户密钥userSecretKey失败: %s" % user_secret)
            return
        else:
            # logger.info("1.1 成功获取用户密钥userSecretKey:%s" % str(user_secret))
            self.logger.info("1.1、成功获取用户密钥userSecretKey: %s" %
                             str(user_secret))
            self.user_secretkey = user_secret
            # self.logger.info("一、获取用户密钥userSecretKey:%s"%self.user_secretkey)
        # 二、获取access-token和refresh-token
        connect_flag, access_token_data = self._get_access_token()
        if connect_flag is False:
            # self.logger.error("二、获取access-token失败:%s"%access_token_data)
            return
        else:
            # logger.info("1.2 成功获取access-token:%s" % str(access_token_data))
            self.logger.info("1.2 成功获取access-token: %s" %
                             str(access_token_data))
            self.access_token = access_token_data['access_token']
            self.refresh_token = access_token_data['refresh_token']
            # self.logger.info("二、获取refresh-token:%s"%self.refresh_token)

    # 获取设备列表
    def get_device_list(self):
        url = ControlConf.aiot_platform_host + '/cloud-api/device/list'
        try:
            authorization = "Bearer " + self.access_token
            request_headers = {
                'Authorization': authorization,
            }
            response = requests.get(url, headers=request_headers, timeout=3)
            response_json = response.json()
            logger.info("2.1 获取设备列表:", response_json)
            if response_json['code'] == 0:
                return True, response_json['data']
            elif response_json['code'] == 401:
                # 如果返回401，则刷新access-token
                self.refresh_access_token()
                return False, "token过期,已刷新，重新调用"
            else:
                logger.info("响应失败:", response_json['msg'])
                return False, response_json['msg']
        except requests.exceptions.RequestException as e:
            print("请求失败:", e)

    # 获取产品资源
    def get_product_resource(self, product_id=''):
        url = ControlConf.aiot_platform_host + '/cloud-api/product/resource'
        try:
            authorization = "Bearer " + self.access_token
            request_headers = {
                'Authorization': authorization,
            }
            params = {
                "productId": product_id
            }
            response = requests.get(
                url, headers=request_headers, params=params, timeout=3)
            response_json = response.json()
            logger.info("2.2 获取产品资源:", response_json)
            if response_json['code'] == 0:
                return True, response_json['data']
            elif response_json['code'] == 401:
                # 如果返回401，则刷新access-token
                self.refresh_access_token()
                return False, "token过期,已刷新，重新调用"
            else:
                logger.info("响应失败:", response_json['msg'])
                return False, response_json['msg']
        except requests.exceptions.RequestException as e:
            print("请求失败:", e)

    # 控制设备
    def control_device(self, control_detailed_data, device_id='', product_id=''):
        """
            控制设备
            :param device_id: 设备id
            :param product_id: 产品id
            :param control_detailed_data: 控制数据
                示例：[{"resourceId":"property.power1","value":1},{"resourceId":"property.power2","value":1}]
            :return: True,''
        """
        url = ControlConf.aiot_platform_host + '/cloud-api/device/control'
        authorization = "Bearer " + self.access_token
        headers = {
            'Authorization': authorization,
            'Content-Type': 'application/json',
        }
        requests_data = {
            "productId": product_id,
            "deviceId": device_id,
            "data": control_detailed_data
        }

        def _send_request():
            response = requests.post(
                url, headers=headers, json=requests_data, timeout=3)
            return response.json()

        try:
            response_json = _send_request()
            logger.info("2.3 控制设备:", response_json)
            if response_json['code'] == 401:
                # 如果返回401，则刷新access-token
                self.refresh_access_token()
                logger.info("token过期,已刷新，重试中")
                response_json = _send_request()
            if response_json['code'] == 0:
                return True, response_json
            else:
                print("响应失败:", response_json['msg'])
                return False, response_json
        except requests.exceptions.RequestException as e:
            print("请求失败:", e)

    # 场景列表
    def get_scene_list(self):
        """
            :return: True,[{'acId': '338', 'name': '离家模式'}, {'acId': '389', 'name': '回家模式'}]
        """
        url = ControlConf.aiot_platform_host + '/cloud-api/scene/list'
        try:
            authorization = "Bearer " + self.access_token
            requests_headers = {
                'Authorization': authorization,
            }
            response = requests.get(url, headers=requests_headers, timeout=3)
            response_json = response.json()
            logger.info("2.4 场景列表为:", response_json)
            if response_json['code'] == 0:
                return True, response_json['data']
            elif response_json['code'] == 401:
                # 如果返回401，则刷新access-token
                self.refresh_access_token()
                return False, "token过期,已刷新，重新调用"
            else:
                logger.info("响应失败:", response_json['msg'])
                return False, response_json['msg']
        except Exception as e:
            print("请求失败:", e)
            return False, e

    # 对外接口,场景执行
    def execute_scene(self, acid_name=''):
        """
            :param acid_name: 场景名字
            :return: True,''
        """
        if self.scenes_id.get(acid_name, '') == '':
            return False, "场景不存在"
        acid = self.scenes_id.get(acid_name, '')
        url = ControlConf.aiot_platform_host + '/cloud-api/scene/control'
        authorization = "Bearer " + self.access_token
        headers = {
            'Authorization': authorization,
            "Content-Type": "application/json",
        }
        data = {"acId": acid}

        def send_request():
            _response_json = requests.post(
                url, headers=headers, json=data, timeout=3)
            return _response_json.json()

        try:
            response_json = send_request()
            # logger.info("2.5 执行场景:", response_json)
            if response_json['code'] == 401:
                # 如果返回401，则刷新access-token
                self.refresh_access_token()
                # return False, "token过期,已刷新，重新调用"
                logger.info("token过期，已刷新，重试中...")
                response = send_request()
                response_json = response.json()
            if response_json['code'] == 0:
                return True, response_json['data']
            else:
                print("响应失败:", response_json['msg'])
                return False, response_json['msg']
        except Exception as e:
            print("请求失败:", e)
            return False, e

    # 对外接口,控制设备开关
    def control_device_power(self, device_name='', state=''):
        """
        对外接口,控制设备开关
        :param device_name: 设备名称
        :param state: 开关状态
        :return: True,''
        """
        try:
            dev_dict = self.resource_info.get(device_name, '')
            print("-----------%s-%s-----------" % (state, device_name))
            if dev_dict == '' or state not in ['open', 'close']:
                return False, "设备名称或状态不存在"
            else:
                # 控制数据
                control_detailed_data = [
                    {"resourceId": dev_dict['resourceId'],
                     "value": dev_dict[state]}
                ]
                res, res_data = self.control_device(device_id=dev_dict['deviceId'], product_id=dev_dict['productId'],
                                                    control_detailed_data=control_detailed_data)
                return res, res_data
        except Exception as e:
            print(e)
            return False, e

    def main(self, stop_event):
        try:
            print("！！！！！！！！！！！可以控制家具！！！！！！！！！！！")
        except Exception as e:
            self.logger.error(f"与物联平台中控系统交互出错: {e}")


aiot_controller = ControlAIotPlatform()

if __name__ == "__main__":
    # print(aiot_controller.resource_info)
    # 获取设备列表
    # aiot_controller.get_device_list()
    # 获取具体
    # res, resdata = aiot_controller.get_product_resource("RSD00005")
    # if res is True:
    #     print("获取资源RSD00003成功！",resdata)
    # else:
    #     print("获取资源RSD00003失败！",resdata)
    # aiot_controller.get_scene_list()
    aiot_controller.execute_scene('scene_001')
    # 控制设备先写死测试
    # {
    #       'productId': 'KXYP79V2',
    #       'deviceId': '0001200d90395efffe80c4ee',
    #       'deviceName': '卧室灯带',
    #       'place': '卧室',
    #       'resourceId': 'power2',
    #       'connected': True
    #     }
    # control_data = [
    #     # {"resourceId": "power2", "value": False},
    #     # {"resourceId": "power1", "value": False},
    #     # 窗帘
    #     {"resourceId": "work1.work1", "value": "2"}
    # ]
    # res, resdata = aiot_controller.control_device(device_id='ATARWSA40001B8D61AA720B0', product_id='RSD00005',
    #                                               control_detailed_data=control_data)
    # if res is True:
    #     print("客厅筒灯！",resdata)
    # else:
    #     print("客厅筒灯！",resdata)