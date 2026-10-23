# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   synchronous.PY
# @Time       2025-06-26 14:11
import os
import time
from conf.basic import GlobalConf
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter

def write_names_to_excel(names_list, groupid):
    # 构建上级目录下的 name_file 文件夹路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # 获取utils的上级目录
    target_dir = os.path.join(parent_dir, "name_file")
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    file_name = os.path.join(target_dir, f"data_{groupid}.xlsx")
    if os.path.isfile(file_name):
        # 文件存在，加载文件
        workbook = load_workbook(file_name)
        sheet = workbook.active
        # 找到第一列最后一个有数据的行
        last_row = sheet.max_row + 1
    else:
        # 文件不存在，创建新的工作表
        workbook = Workbook()  # 修改这里：使用Workbook()而不是load_workbook()
        sheet = workbook.active
        last_row = 1

    # 写入数据到第一列
    for index, name in enumerate(names_list, start=last_row):
        sheet[f"{get_column_letter(1)}{index}"] = name

    workbook.save(file_name)

def check_and_backup_group(input_group, loger):
    try:
        timestamp = time.strftime("%Y%m%d%H%M%S")
        current_dir = os.path.dirname(__file__)
        config_dir = os.path.dirname(current_dir)
        sign_in_path = os.path.join(config_dir, "sign_in.txt")
        backup_path = os.path.join(config_dir, f"sign_in_{timestamp}.txt")
        if input_group != GlobalConf.baidu_groups and os.path.exists(sign_in_path):
            with open(sign_in_path, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            with open(sign_in_path, 'w', encoding='utf-8') as f:
                f.write('')
        loger.info(f"备份并清空已签到文件")
    except Exception as e:
        loger.error(f"备份并清空已签到文件失败：{e}")
