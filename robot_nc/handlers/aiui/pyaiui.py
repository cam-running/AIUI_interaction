'''
Author: zhaoyong 77912776@qq.com
Date: 2025-07-02 06:34:52
LastEditTime: 2025-07-19 12:24:11
LastEditors: zhaoyong 77912776@qq.com
FilePath: \robot_ai\src\aiui\pyaiui.py
Description: aiui的python调用c++接口类
'''
#!/usr/bin python3
# coding=utf-8
import ctypes
import os
from .pyAIUIConstant import AIUIConstant
import abc
import sys
import platform
from pathlib import Path

AIUI_DLL = None
# 当前脚本路径
script_path = Path(__file__).resolve()

# 项目根目录（向上两级：src/aiui -> src -> 根目录）
BASE_DIR = script_path.parent.parent.parent

if platform.system() == "Windows":
    AIUI_DLL = ctypes.windll.LoadLibrary(
        str(BASE_DIR / "config" / "aiui" / "x64" / "aiui.dll"))
else:
    AIUI_DLL = ctypes.cdll.LoadLibrary(
        str(BASE_DIR / "config" / "aiui" / "arm" / "libaiui.so"))


def aiui_get_version():
    if AIUI_DLL is None:
        return "AIUI DLL not loaded"

    if not hasattr(AIUI_DLL, 'aiui_get_version'):
        return "aiui_get_version function not found in DLL"

    _f = AIUI_DLL.aiui_get_version
    _f.restype = ctypes.c_char_p
    s = _f()
    return str(s, encoding="utf-8")


class IDataBundle:
    aiui_db = None

    def __init__(self, aiui_db: ctypes.c_void_p):
        self.aiui_db = aiui_db

        if AIUI_DLL is not None and hasattr(AIUI_DLL, 'aiui_db_int'):
            self.aiui_db_int = AIUI_DLL.aiui_db_int
            self.aiui_db_int.restype = ctypes.c_int
            self.aiui_db_int.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
        else:
            self.aiui_db_int = None

        if AIUI_DLL is not None and hasattr(AIUI_DLL, 'aiui_db_long'):
            self.aiui_db_long = AIUI_DLL.aiui_db_long
            self.aiui_db_long.restype = ctypes.c_long
            self.aiui_db_long.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
        else:
            self.aiui_db_long = None

        if AIUI_DLL is not None and hasattr(AIUI_DLL, 'aiui_db_string'):
            self.aiui_db_string = AIUI_DLL.aiui_db_string
            self.aiui_db_string.restype = ctypes.c_char_p
            self.aiui_db_string.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        else:
            self.aiui_db_string = None

        if AIUI_DLL is not None and hasattr(AIUI_DLL, 'aiui_db_binary'):
            self.aiui_db_binary = AIUI_DLL.aiui_db_binary
            self.aiui_db_binary.restype = ctypes.c_void_p
            self.aiui_db_binary.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
        else:
            self.aiui_db_binary = None

    def getInt(self, key: str, defaultVal: int):
        if self.aiui_db_int is None:
            return defaultVal
        return int(self.aiui_db_int(self.aiui_db, ctypes.c_char_p(key.encode("utf-8")),
                                    ctypes.pointer(ctypes.c_int(defaultVal))))

    def getLong(self, key: str, defaultVal: int):
        if self.aiui_db_long is None:
            return defaultVal
        return int(self.aiui_db_long(self.aiui_db, ctypes.c_char_p(key.encode("utf-8")),
                                     ctypes.pointer(ctypes.c_long(defaultVal))))

    def getString(self, key: str, defaultVal: str):
        if self.aiui_db_string is None:
            return defaultVal
        s = self.aiui_db_string(self.aiui_db, ctypes.c_char_p(key.encode("utf-8")),
                                ctypes.c_char_p(defaultVal.encode("utf-8")))
        return str(s, encoding="utf-8")

    def getBinary(self, key: str):
        if self.aiui_db_binary is None:
            return b""
        datalen = ctypes.c_int(0)

        s = self.aiui_db_binary(self.aiui_db, ctypes.c_char_p(
            key.encode("utf-8")), ctypes.pointer(datalen))

        ArrayType = ctypes.c_char * datalen.value
        pa = ctypes.cast(s, ctypes.POINTER(ArrayType))

        return bytes(pa.contents)

    def getBinaryAsStr(self, key: str):
        """获取二进制数据并转换为字符串，修复JSON截断问题"""
        try:
            if self.aiui_db_binary is None:
                return ""

            datalen = ctypes.c_int(0)
            binary = self.aiui_db_binary(self.aiui_db, ctypes.c_char_p(
                key.encode('utf-8')), ctypes.pointer(datalen))

            if datalen.value <= 0:
                return ""

            # 移除-1操作，避免截断JSON
            arrayType = ctypes.c_char * datalen.value
            pointArray = ctypes.cast(binary, ctypes.POINTER(arrayType))

            # 获取字节数据并转换为字符串
            raw_bytes = bytes(pointArray.contents)

            # 处理可能的空字节终止符
            if raw_bytes and raw_bytes[-1] == 0:
                raw_bytes = raw_bytes[:-1]

            return str(raw_bytes, encoding='utf-8')
        except Exception as e:
            # logger.info(f"getBinaryAsStr error: {e}")
            return ""


class IAIUIEvent:
    aiui_event = None

    def __init__(self, aiui_event):
        self.aiui_event = aiui_event

        if AIUI_DLL is not None:
            self.aiui_event_type = AIUI_DLL.aiui_event_type
            self.aiui_event_type.restype = ctypes.c_int
            self.aiui_event_type.argtypes = [ctypes.c_void_p]

            self.aiui_event_arg1 = AIUI_DLL.aiui_event_arg1
            self.aiui_event_arg1.restype = ctypes.c_int
            self.aiui_event_arg1.argtypes = [ctypes.c_void_p]

            self.aiui_event_arg2 = AIUI_DLL.aiui_event_arg2
            self.aiui_event_arg2.restype = ctypes.c_int
            self.aiui_event_arg2.argtypes = [ctypes.c_void_p]

            self.aiui_event_info = AIUI_DLL.aiui_event_info
            self.aiui_event_info.restype = ctypes.c_char_p
            self.aiui_event_info.argtypes = [ctypes.c_void_p]

            self.aiui_event_databundle = AIUI_DLL.aiui_event_databundle
            self.aiui_event_databundle.restype = ctypes.c_void_p
            self.aiui_event_databundle.argtypes = [ctypes.c_void_p]

    def getEventType(self) -> int:
        return self.aiui_event_type(self.aiui_event)

    def getArg1(self) -> int:
        return self.aiui_event_arg1(self.aiui_event)

    def getArg2(self) -> int:
        return self.aiui_event_arg2(self.aiui_event)

    def getInfo(self) -> str:
        s = self.aiui_event_info(self.aiui_event)
        return str(s, encoding="utf-8")

    def getData(self) -> IDataBundle:
        db = self.aiui_event_databundle(self.aiui_event)
        return IDataBundle(db)


class Buffer:
    aiui_buf = None

    def __init__(self, aiui_buf):
        self.aiui_buf = aiui_buf

    @staticmethod
    def create(dataBytearray: bytes):
        if AIUI_DLL is None:
            return None

        _f = AIUI_DLL.aiui_create_buffer_from_data
        _f.restype = ctypes.c_void_p
        _f.argtypes = [ctypes.c_char_p, ctypes.c_size_t]

        return Buffer(_f(ctypes.c_char_p(dataBytearray), ctypes.c_size_t(len(dataBytearray))))


class IAIUIMessage:
    aiui_msg = None

    def __init__(self, aiui_msg):
        self.aiui_msg = aiui_msg

    @staticmethod
    def create(msgType: AIUIConstant, arg1=0, arg2=0, params="", data=Buffer(None)):
        if AIUI_DLL is None:
            return None

        _f = AIUI_DLL.aiui_msg_create
        _f.restype = ctypes.c_void_p
        _f.argtypes = [ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p]

        return IAIUIMessage(
            _f(ctypes.c_int(msgType.value), ctypes.c_int(arg1), ctypes.c_int(arg2),
               ctypes.c_char_p(params.encode("utf-8")), data.aiui_buf)
        )

    def destroy(self):
        if AIUI_DLL is None:
            return None

        _f = AIUI_DLL.aiui_msg_destroy
        _f.argtypes = [ctypes.c_void_p]

        return _f(self.aiui_msg)


class AIUIEventListener:
    @abc.abstractmethod
    def onEvent(self, ev: IAIUIEvent):
        pass


def eventCallback(obj: AIUIEventListener):
    def wrapper(ev: ctypes.c_void_p, data: ctypes.c_void_p):
        obj.onEvent(IAIUIEvent(ev))

    return wrapper


class IAIUIAgent:
    aiui_agent = None
    ListenerWarpper = None
    AIUIListenerCallback = None

    def __init__(self, aiui_agent):
        self.aiui_agent = aiui_agent

        if AIUI_DLL is not None:
            self.aiui_agent_send_message = AIUI_DLL.aiui_agent_send_message
            self.aiui_agent_send_message.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p]

            self.aiui_agent_destroy = AIUI_DLL.aiui_agent_destroy
            self.aiui_agent_destroy.argtypes = [ctypes.c_void_p]
        else:
            self.aiui_agent_send_message = None
            self.aiui_agent_destroy = None

    def sendMessage(self, msg: IAIUIMessage):
        if self.aiui_agent_send_message is not None:
            return self.aiui_agent_send_message(self.aiui_agent, msg.aiui_msg)
        return None

    def destroy(self):
        if self.aiui_agent_destroy is not None:
            self.aiui_agent_destroy(self.aiui_agent)
        self.AIUIListenerCallback = None
        self.ListenerWarpper = None
        self.aiui_agent = None

    @staticmethod
    def createAgent(params: str, listener):
        if AIUI_DLL is None:
            return None

        _f = AIUI_DLL.aiui_agent_create
        _f.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]
        _f.restype = ctypes.c_void_p

        agent = IAIUIAgent(None)
        agent.ListenerWarpper = eventCallback(listener)
        agent.AIUIListenerCallback = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p)(agent.ListenerWarpper)
        agent.aiui_agent = _f(ctypes.c_char_p(
            params.encode('utf-8')), agent.AIUIListenerCallback, None)

        return agent


class AIUISetting:
    @staticmethod
    def setSystemInfo(key: str, val: str):
        if AIUI_DLL is None:
            return None

        _f = AIUI_DLL.aiui_set_system_info
        _f.argtypes = [ctypes.c_char_p, ctypes.c_char_p]

        return _f(ctypes.c_char_p(key.encode("utf-8")), ctypes.c_char_p(val.encode("utf-8")))

    @staticmethod
    def setMscDir(szDir: str):
        if AIUI_DLL is None:
            return False

        _f = AIUI_DLL.aiui_set_msc_dir
        _f.restype = ctypes.c_bool
        _f.argtypes = [ctypes.c_char_p]

        return _f(ctypes.c_char_p(szDir.encode('utf-8')))
