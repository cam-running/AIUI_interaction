# -*- coding: utf-8 -*-
# @Author     zyb
# @FileName   main_client.py
# @Time       2025-09-11 15:26
import os
import cv2
import json
import time
import queue
import shutil
import requests
import websocket
import threading
import numpy as np
from datetime import datetime
from openpyxl import load_workbook
from utils.baidu_ai_pic import BaiduAip
from utils.temp_audio import generate_audio
from utils.audio_playback import play_face_v
from version import __version__, __build_date__
from conf.basic import GlobalConf, get_user_time
from middlewares.init_logger import init_logger, LoggerInstance

frame_queue = queue.Queue(maxsize=1)


def ws_frame_receiver(ws_url="ws://192.168.0.10:34550/ws"):
    def on_message(ws, message):
        if isinstance(message, bytes):
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except:
                    pass
            frame_queue.put(message)

    def on_error(ws, error):
        print(f"WebSocket 错误: {error}")

    def on_close(ws, close_status_code, close_msg):
        print("WebSocket 关闭")

    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()


def get_latest_frame():
    try:
        frame_bytes = frame_queue.get(timeout=1)
    except queue.Empty:
        return None
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return frame


def face(logger):
    face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    while True:
        frame = get_latest_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_detector.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            x, y, w, h = faces[0]
            face_img = frame[y:y + h, x:x + w]
            _, buffer = cv2.imencode('.jpg', face_img)
            face_bytes = buffer.tobytes()
            if not GlobalConf.sink_status and not GlobalConf.identify_status:
                GlobalConf.face_queue.put({"face": face_bytes})
        time.sleep(0.05)

def send_identify(logger, face_file, instance, wait_name):
    try:
        result = instance.search_user(face_file)
        if GlobalConf.clear_tmp and os.path.isfile(face_file):
            os.remove(face_file)
        if not result.get("result"):
            return
        user_name = result["result"]["user_list"][0].get("user_info")
        if not user_name:
            return
        score = result["result"]["user_list"][0].get("score")
        if not score:
            return
        if GlobalConf.baidu_score - 10 < score < GlobalConf.baidu_score:
            if wait_name == user_name:
                logger.info(f"最相似的照片是: {user_name},值: {score},虽然未达到预估值,但是连续2次识别为同一人")
                return {"name": user_name}
            else:
                logger.info(f"最相似的照片是: {user_name},值: {score},但是未达到预估值,等待连续人脸")
                return {"name": "-", "wait": user_name}
        if score < GlobalConf.baidu_score:
            logger.info(f"最相似的照片是: {user_name},值: {score},忽略本次,播放正视摄像头")
            return {"name": "-"}
    except Exception as error_message:
        logger.warning(f"本次解析人脸识别错误:{error_message}")
        return
    logger.info(f"最相似的照片是: {user_name}, 识别系数: {score},可以使用")
    return {"name": user_name}

def identify(logger):
    instance = BaiduAip(GlobalConf.baidu_app_id, GlobalConf.baidu_api_key, GlobalConf.baidu_secret_key,
                        GlobalConf.baidu_groups)
    last_name = ""
    last_time = 0
    wait_name = ""
    while 1:
        if GlobalConf.face_queue.empty():
            continue

        data = GlobalConf.face_queue.get(timeout=1)
        if not isinstance(data, dict) or not data.get("face"):
            logger.error(f"数据错误:{data}")
            continue
        if GlobalConf.sink_status:
            logger.debug("正在播放语音不识别")
            time.sleep(0.5)
            continue
        face_data = data.get("face")
        GlobalConf.identify_status = True
        try:
            time_int = int(time.time() * 1000)
            face_pic_file = os.path.join(GlobalConf.tmp_path, f"{time_int}.jpg")
            with open(face_pic_file, "wb") as file:
                file.write(face_data)
            result = send_identify(logger, face_pic_file, instance, wait_name)
        except Exception as error_message:
            logger.error(f"识别异常:{error_message}")
            result = None
        finally:
            GlobalConf.identify_status = False
        if not result:
            last_time = 0
            last_name = ""
            continue
        name = result.get("name")
        if not name:
            last_time = 0
            last_name = ""
            continue
        wait_name = result.get("wait", "")
        if wait_name:
            continue
        time_num = time.time()
        if name == last_name and last_time != 0:
            t = time_num - last_time
            if t < GlobalConf.sleep_time:
                logger.debug(f"{name}出境时间:{t}秒，小于{GlobalConf.sleep_time}秒，忽略本次")
                continue
        else:
            last_name = name
            last_time = time_num
        logger.info(f"发送:{result}")
        GlobalConf.identify_queue.put(result)

def voice(logger):
    file_type = "wav"
    no_person_count = 0
    fail_last_time = 0
    while True:
        if GlobalConf.identify_queue.empty():
            time.sleep(0.05)
            continue
        try:
            data = GlobalConf.identify_queue.get(timeout=1)
        except Exception as e:
            logger.error(f"获取队列数据失败: {str(e)}")
            continue
        if not isinstance(data, dict):
            logger.error(f"数据错误: {data}")
            continue
        logger.success(f"获取到数据: {data}")
        name = data.get("name")
        if not name:
            continue
        time_int = int(time.time())
        current_time = round(time.time(), 2)
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if name == "-":
            logger.info(f"当前无人，未识别计数: {no_person_count}")
            if current_time - fail_last_time < GlobalConf.interval_time:
                logger.info(f"间隔时间不足{GlobalConf.interval_time}秒，重新识别,间隔时间：{current_time - fail_last_time}")
                continue
            if no_person_count >= 1:
                logger.info(f"最后一次识别, 间隔时间：{current_time - fail_last_time}")
                file_mp3 = os.path.join(GlobalConf.voice_path, "fail.wav")
                logger.warning("连续未识别，播放失败提示")
                fail_last_time = current_time
                GlobalConf.action_queue.put(
                    {"action": 1, "action_code": GlobalConf.interval_code, "reason": "fail1_action"})
                no_person_count = 0
            else:
                logger.info(f"第{no_person_count}次识别,间隔时间：{current_time - fail_last_time}")
                file_mp3 = os.path.join(GlobalConf.voice_path, "show.wav")
                logger.info("检测到无人，播放提示音")
                fail_last_time = current_time
                GlobalConf.action_queue.put({"action": 1, "action_code": GlobalConf.interval_code, "reason": "fail2_action"})
                no_person_count += 1
        else:
            last_play_time, is_completed = get_user_time(name)
            no_person_count = 0
            if GlobalConf.identify_sta == "realtime":
                logger.info("~~~~~~~~~~~~切换为实时音频模式~~~~~~~~~~~~")
                if current_time - last_play_time < GlobalConf.through_1:
                    logger.info(
                        f"间隔时间不足{GlobalConf.through_1}秒，重新识别,间隔时间：{current_time - last_play_time}")
                    continue
                temp_audio_path = os.path.join(GlobalConf.tmp_path, f"{name}.{file_type}")
                generate_audio(name)
                if name not in GlobalConf.exist_data:
                    file_mp3 = temp_audio_path
                    GlobalConf.exist_data[name] = {"time": time_int, "num": 1}
                    logger.info(f"第一次识别{name}，音频生成并保存: {file_mp3}")
                    logger.info("将第一次识别动作放入队列_realtime")
                    GlobalConf.action_queue.put(
                        {"action": 1, "action_code": GlobalConf.action_code_1, "reason": "realtime_1"})
                    GlobalConf.attendance_queue.put(
                        {"attendance": 1, "name": name, "time": str(current_timestamp), "num": 1})
                elif GlobalConf.exist_data[name]["num"] < GlobalConf.identifications_num:
                    file_mp3 = temp_audio_path
                    GlobalConf.exist_data[name]["num"] += 1
                    logger.info(f"第二次识别{name}，音频生成并保存: {file_mp3}")
                    logger.info("将第二次识别动作放入队列_realtime")
                    GlobalConf.action_queue.put(
                        {"action": 1, "action_code": GlobalConf.action_code_2, "reason": "realtime_2"})
                    GlobalConf.attendance_queue.put(
                        {"attendance": 1, "name": name, "time": str(current_timestamp), "num": GlobalConf.exist_data[name]["num"]})
                else:
                    logger.info(f"{name}已播放过{GlobalConf.identifications_num}次音频，不再播放")
                    continue
            elif GlobalConf.identify_sta == "online":
                logger.info("============切换为在线音频模式============")
                if current_time - last_play_time < GlobalConf.through_1:
                    logger.info(
                        f"间隔时间不足{GlobalConf.through_1}秒，重新识别,间隔时间：{current_time - last_play_time}")
                    continue
                if name not in GlobalConf.exist_data:
                    file_mp3 = os.path.join(GlobalConf.voice_path, f"{name}_1.{file_type}")
                    GlobalConf.exist_data[name] = {"time": time_int, "num": 1}
                    logger.info("将第一次识别动作放入队列_online")
                    GlobalConf.action_queue.put({"action": 1, "action_code": GlobalConf.action_code_1, "reason": "online_1"})
                    GlobalConf.attendance_queue.put(
                        {"attendance": 1, "name": name, "time": str(current_timestamp), "num": 1})
                elif GlobalConf.exist_data[name]["num"] < GlobalConf.identifications_num:
                    file_mp3 = os.path.join(GlobalConf.voice_path, f"{name}_2.{file_type}")
                    GlobalConf.exist_data[name]["num"] += 1
                    logger.info("将第二次识别动作放入队列_online")
                    GlobalConf.action_queue.put({"action": 1, "action_code": GlobalConf.action_code_2, "reason": "online_2"})
                    print("数据已经放入QA接口")
                    GlobalConf.attendance_queue.put(
                        {"attendance": 1, "name": name, "time": str(current_timestamp), "num": GlobalConf.exist_data[name]["num"]})
                else:
                    logger.info(f"{name}已播放过{GlobalConf.identifications_num}次音频，不再播放")
                    continue
                if not os.path.isfile(file_mp3):
                    temp_audio_patho = os.path.join(GlobalConf.tmp_path, f"{name}.{file_type}")
                    generate_audio(name)
                    file_mp3 = temp_audio_patho
                    logger.error(f"语音文件不存在: {file_mp3},使用在线生成")
            GlobalConf.show_queue.put({"name": name})
            logger.info("准备将动作数据放入队列")
            logger.info("动作数据已放入队列")
            GlobalConf.exist_data[name]["time"] = time_int
            try:
                with open(GlobalConf.sign_in_file, 'w', encoding="utf-8") as file:
                    json.dump(GlobalConf.exist_data, file, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"保存签到记录失败: {e}")
        if os.path.isfile(file_mp3):
            logger.info("播放音频中，不在识别")
            play_face_v(file_mp3)
            logger.info(f"播放音频: {file_mp3}")
        else:
            logger.warning(f"音频文件不存在: {file_mp3}")

def action(logger):
    while 1:
        if GlobalConf.action_queue.empty():
            time.sleep(0.05)
            continue
        data = GlobalConf.action_queue.get(timeout=1)
        if not isinstance(data, dict):
            logger.error(f"动作数据错误:{data}")
            continue
        action_type = data.get("action")
        if action_type == 1:
            try:
                action_code = data.get("action_code")
                if int(action_code) == 0:
                    pass
                else:
                    logger.info(f"已发送动作请求，动作编码< {action_code} >")
                    requests.post(GlobalConf.action_url, json={"data": action_code})
                    logger.info(f"{action_code}动作编码已发送")
            except Exception as e:
                logger.error(f"发送动作请求失败: {e}")

def attendance_func(logger):
    while 1:
        if GlobalConf.attendance_queue.empty():
            time.sleep(0.05)
            continue
        data = GlobalConf.attendance_queue.get(timeout=1)
        if not isinstance(data, dict):
            logger.error(f"数据错误:{data}")
            continue
        attendance_sta = data.get("attendance")
        if attendance_sta == 1:
            try:
                name = data.get("name")
                number = data.get("num")
                times = data.get("time")
                logger.info(f"发送识别数据，姓名：{name}，第{number}次，时间：{times}")
                requests.post(GlobalConf.attendance_url, json={"name": name, "num": number, "time": times})
                logger.info(f"识别数据已发送")
            except Exception as e:
                logger.error(f"发送识别数据失败: {e}")

def load_old_data(logger):
    if not os.path.isfile(GlobalConf.sign_in_file):
        return
    exist_data = {}
    try:
        with open(GlobalConf.sign_in_file, 'r', encoding="utf-8") as file:
            exist_data = json.load(file)
    except Exception as e:
        logger.error(f"加载历史签到数据失败: {e}")
    logger.info(f"存在历史签到人员: {list(exist_data.keys())}")
    GlobalConf.exist_data = exist_data

def show_result(logger):
    all_num = len(GlobalConf.all_users)
    while 1:
        time.sleep(1)
        if GlobalConf.show_queue.empty():
            continue
        data = GlobalConf.show_queue.get(timeout=1)
        if not isinstance(data, dict):
            logger.error(f"数据错误:{data}")
            continue
        name = data.get("name")
        if not name:
            continue
        exist_num = len(GlobalConf.exist_data)
        no_num = all_num - exist_num
        if GlobalConf.exist_data[name]["num"] == 1:
            logger.success(
                f"{name} 初次签到，共有{all_num}人参加,已有{exist_num}人完成签到，还有{no_num}人未来签到")
        else:
            logger.success(
                f"{name} 已完成签到，共有{all_num}人参加,已有{exist_num}人完成签到，还有{no_num}人未来签到")

def main():
    init_logger(["logger_main"])

    if not os.path.isfile(GlobalConf.excel_file):
        LoggerInstance.logger_main.error(f"Excel文件缺失: {GlobalConf.excel_file},请从<upload_xlsx>接口上传该文件")
        LoggerInstance.logger_main.error("程序终止运行")
        return

    if os.path.isdir(GlobalConf.tmp_path):
        shutil.rmtree(GlobalConf.tmp_path)
        time.sleep(0.5)
        os.mkdir(GlobalConf.tmp_path)
    else:
        os.mkdir(GlobalConf.tmp_path)
    logger = LoggerInstance.logger_main

    logger.info("语音文件确认开始")
    load_old_data(logger)
    wb = load_workbook(filename=GlobalConf.excel_file)
    sheet = wb.active
    GlobalConf.all_users = [row[0].value for row in sheet.iter_rows(min_row=1) if row[0].value]
    # 启动线程
    ws_thread = threading.Thread(target=ws_frame_receiver, name="WSReceiver", daemon=True)
    face_thread = threading.Thread(target=face, args=(logger,), name="FaceThread")
    identify_thread = threading.Thread(target=identify, args=(logger,), name="IdentifyThread")
    voice_thread = threading.Thread(target=voice, args=(logger,), name="VoiceThread")
    action_thread = threading.Thread(target=action, args=(logger,), name="ActionThread")
    attendance_thread = threading.Thread(target=attendance_func, args=(logger,), name="AttendanceThread")
    show_result_thread = threading.Thread(target=show_result, args=(LoggerInstance.logger_print,), name="ShowThread")
    ws_thread.start()
    face_thread.start()
    identify_thread.start()
    voice_thread.start()
    action_thread.start()
    attendance_thread.start()
    show_result_thread.start()
    all_num = len(GlobalConf.all_users)
    LoggerInstance.logger_print.success(f"版本: {__version__}")
    LoggerInstance.logger_print.success(f"构建日期: {__build_date__}")
    LoggerInstance.logger_print.success(f"程序开始运行,共有{all_num}人")

    while 1:
        time.sleep(7)


if __name__ == "__main__":
    main()
