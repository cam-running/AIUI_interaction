# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   model.PY
# @Time       2025-06-17 10:41

from pydantic import BaseModel, validator
class Any_mp3(BaseModel):
    mp3_writing: str
    _validate_mp3 = validator('mp3_writing', allow_reuse=True)(
        lambda v: v if v and v != "null" else (_ for _ in ()).throw(ValueError("值不能为None、null或空字符串"))
    )

class VolumeRequest(BaseModel):
    volume: int

class FaceOpen(BaseModel):
    status: str
    group_id: str = None

class RobotAi(BaseModel):
    status: str

class Audio(BaseModel):
    status: str

class Commd(BaseModel):
    name: str

class TimberRequest(BaseModel):
    timbre_model: str

class ServiceRequest(BaseModel):
    unitreeip: str

class Update_audio_recognized(BaseModel):
    code: int
    text: str

class Identify_s(BaseModel):
    sta: str

class Yx_indentify_code(BaseModel):
    through_1: int = 10
    through_2: int = 10
    interval_time: int = 5
    interval_code: int = 0
    action_code_1: int = 2006
    action_code_2: int = 2006
    identifications_num: int = 2

class QaCallback(BaseModel):
    question: str = None
    answer: str = None
    time: float = None

# 定义请求体模型：语言模式
class LanguageMode(BaseModel):
    mode: str  # 取值：zh(中文)、yue(粤语)、en(英文)
