# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   face_v.PY
# @Time       2025-05-29 23:20
import os
import random
import base64
import time
import requests
from flask_cors import CORS
from flask import Flask, request, jsonify
from conf.basic import *
from openpyxl import Workbook, load_workbook
from filelock import FileLock
from init_voice import add_one, all_voice

app = Flask(__name__)
CORS(app, resources={
    r"/add_user": {
        "origins": "*",
        "methods": ["POST"],
        "allow_headers": ["Content-Type"]
    },
    r"/generate_v": {
        "origins": "*",
        "methods": ["PUT"],
        "allow_headers": ["Content-Type"]
    },
    r"/init_vo": {
        "origins": "*",
        "methods": ["POST"],
        "allow_headers": ["Content-Type"]
    }
})

logger = get_logger("face_v")

def add_to_excel(name, group):
    try:
        save_dir = "name_file"
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"data_{group}.xlsx")
        if os.path.exists(filename):
            wb = load_workbook(filename)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                if row[0] == name:
                    return
        else:
            wb = Workbook()
            ws = wb.active
        ws.append([name])
        wb.save(filename)
        logger.info(f"用户{name}已写入data_{group}.xlsx")
        return {"msg": "success", "code": 200}
    except Exception as e:
        logger.error(f"生成Excel文件时出错: {e}")
        return {"error": str(e)}


@app.route('/add_user', methods=['POST'])
def add_user_api():
    index = int(time.time())
    group = request.form.get('group')
    files = request.files.getlist('images')
    speech1 = request.form.get('speech1')
    speech2 = request.form.get('speech2')
    results = []
    counts = count_first_column()
    if counts >= 1000:
        logger.error({"code": 400, "error": f"已达到最大用户数{100}人"})
        return jsonify({"code": 400, "error": f"已达到最大用户数{100}人"}), 400
    if group not in GlobalConf.group_list:
        logger.error(f"组名{group}不在允许的组名列表<group2~group7>中，请联系管理员添加")
        return jsonify({"error": f"组名{group}不在允许的组名列表<group2~group7>中，请联系管理员添加"}), 400
    is_valid = lambda x: (x is None or (hasattr(x, '__len__') and len(x) == 0) or (isinstance(x, str) and x.strip().lower() in ("null", "none")))
    if is_valid(speech1) or is_valid(speech2):
        logger.error(f"请输入语音内容")
        return jsonify({"code": 400, "error": f"请输入语音内容"}), 400
    file = files[0]
    if len(files) == 1:
        if file.filename.endswith('.jpg'):
            name = file.filename[:-4]
            confirm = check_name_exists(name, group)
            if confirm:
                return jsonify({"code": 400, "error": f"用户>{name}<已存在"}), 400
            image = base64.b64encode(file.read()).decode('utf-8')
            file_name = file.filename.rsplit('.', 1)[0]
            user_id = f"user_{group}_{index}"
            # add_spe(user_id,speech1, speech2)
            data = {
                "image": image,
                "file_name": file_name,
                "user_id": user_id,
                "group": group
            }
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(GlobalConf.baidu_gw_url, json=data, headers=headers)
            if response and response.json()["error_code"] == 0:
                add_u_json(group, name, user_id)
                add_to_excel(name, group)
                add_one(user_id, name, speech1, speech2)
            logger.info(f"{name}注册成功，已添加至{group}中")
            return response.json(), response.status_code
        else:
            return jsonify({"code": "400", "error": f"文件{file.filename}不是jpg格式"}), 400
    elif len(files) > 1:
        names = []
        for file in files:
            try:
                if file.filename.endswith('.jpg'):
                    name = file.filename[:-4]
                    names.append(name)
                    add_to_excel(name, group)
                    image = base64.b64encode(file.read()).decode('utf-8')
                    file_name = file.filename.rsplit('.', 1)[0]
                    user_id = f"user_{group}_{index}"
                    data = {
                        "image": image,
                        "file_name": file_name,
                        "user_id": user_id,
                        "group": group
                    }
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    response = requests.post(GlobalConf.baidu_gw_url, json=data, headers=headers)
                    if response and response.json()["error_code"] == 0:
                        add_u_json(group, name, user_id)
                    results.append(response.json())
                    index += 1
                else:
                    return jsonify({"code": "400", "error": f"文件{file.filename}不是jpg格式"}), 400
            except Exception as e:
                logger.error(f"添加用户时出错: {e}")
                results.append({"error": str(e)})
        all_voice(speech1, speech2, f"data_{group}.xlsx")
        return results


@app.route('/generate_v', methods=['put'])
def generate():
    data = request.get_json()
    name = data.get('name')
    user_id = data.get('user_id')
    speech1 = data.get('speech1')
    speech2 = data.get('speech2')
    try:
        add_one(user_id, name, speech1, speech2)
        return jsonify({"msg": f"{name}音频文件已更新", "code": 200}), 200
    except Exception as e:
        logger.error(f"生成语音时出错: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/init_vo', methods=['post'])
def init_voc():
    user_id = 123
    data = request.get_json()
    group = data.get('group')
    all_names = []
    name_list = get_all_user(group)
    xlsx_dir = "chicken_xl"
    if not isinstance(name_list, list) or not name_list:
        return jsonify({"code": 401, "message": "无有效用户数据", "data": []})
    if not os.path.exists(xlsx_dir):
        return jsonify({"code": 404, "message": "目录不存在", "data": []})
    for filename in os.listdir(xlsx_dir):
        if filename.endswith('.xlsx'):
            filepath = os.path.join(xlsx_dir, filename)
            try:
                wb = load_workbook(filepath)
                ws = wb.active
                names = [row[0] for row in ws.iter_rows(values_only=True) if row[0]]
                all_names.extend(names)
            except Exception as e:
                logger.error(f"读取文件{filename}失败: {str(e)}")
                continue
    if len(all_names) >= 2:
        for z in name_list:
            text1, text2 = random.sample(all_names, 2)
            add_one(user_id, z, text1, text2)
        return jsonify({"code": 200, "message": "音频文件已生成"})
    elif len(all_names) == 1:
        text1 = text2 = all_names[0]
        for a in name_list:
            add_one(user_id, a, text1, text2)
        return jsonify({"code": 200, "message": "音频文件已生成"})
    else:
        return jsonify({"code": 401, "message": "未知错误", "data": []})

class SignInManager:
    def __init__(self):
        self.sign_file = GlobalConf.sign_in_file
        self.lock = FileLock(self.sign_file + ".lock")
    def _safe_read(self):
        if not os.path.exists(self.sign_file):
            return {}

        with self.lock:
            if os.path.getsize(self.sign_file) == 0:
                return {}

            try:
                with open(self.sign_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"文件损坏，尝试恢复: {e}")
                return self._recover()

    def _safe_write(self, data: dict):
        with self.lock:
            if os.path.exists(self.sign_file):
                bak_path = self.sign_file + ".bak"
                try:
                    with open(self.sign_file, 'r', encoding='utf-8') as src:
                        with open(bak_path, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                except:
                    logger.warning("无法创建备份，但不影响写入")
            temp_path = self.sign_file + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.sign_file)

    def _recover(self):
        bak = self.sign_file + ".bak"
        if os.path.exists(bak):
            try:
                with open(bak, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info("文件已通过备份恢复")
                return data
            except:
                logger.error("备份也损坏，将重置为空字典")
        self._safe_write({})
        return {}

    def clean_old_sign_in(self, hours_threshold=0.01):
        data = self._safe_read()
        if not data:
            logger.info("签到文件为空，无需清理")
            return

        first_name = next(iter(data))
        first_timestamp = data[first_name]["time"]
        hours_diff = (time.time() - first_timestamp) / 3600

        if hours_diff > hours_threshold:
            self._safe_write({})
            logger.info("签到数据已清空")
        else:
            logger.info("未超过清理时间，无需清理")


if __name__ == '__main__':
    manager = SignInManager()
    manager.clean_old_sign_in()
    app.run(debug=False, host="0.0.0.0", port=5001)




