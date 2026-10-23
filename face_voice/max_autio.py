'''
Author: zhaoyong 77912776@qq.com
Date: 2025-06-16 08:43:38
LastEditTime: 2025-06-23 14:29:43
LastEditors: zhaoyong 77912776@qq.com
FilePath: \face_voice_0\max_autio.py
Description: 头部注释配置模板
'''
# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   max_autio.py
# @Time       Updated for ALSA support

import sys
import subprocess
import re
from conf.basic import GlobalConf, get_logger

logger = get_logger("max_autio")

# 尝试导入ALSA控制器，如果失败则使用传统方法
try:
    from utils.alsa_volume_control import create_alsa_controller
    ALSA_AVAILABLE = True
    logger.info("ALSA音量控制模块加载成功")
except ImportError as e:
    ALSA_AVAILABLE = False
    logger.warning(f"ALSA音量控制模块不可用，将使用PulseAudio: {e}")

def get_default_sink():
    """获取默认音频输出设备（PulseAudio）"""
    try:
        result = subprocess.run(['pactl', 'get-default-sink'], stdout=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"获取默认输出设备失败: {e}")
        return None

def get_sink_volume(sink_name):
    """获取音频设备音量（PulseAudio）"""
    try:
        result = subprocess.run(['pactl', 'get-sink-volume', sink_name], stdout=subprocess.PIPE, text=True)
        match = re.search(r'/\s*(\d+)%', result.stdout)
        if match:
            return int(match.group(1))
    except Exception as e:
        logger.error(f"获取音量失败: {e}")
    return None

def set_sink_volume(sink_name, volume_percent):
    """设置音频设备音量（PulseAudio）"""
    try:
        subprocess.run(['pactl', 'set-sink-volume', sink_name, f'{volume_percent}%'])
        logger.info(f"PulseAudio音量设置为: {volume_percent}%")
        return True
    except Exception as e:
        logger.error(f"设置音量失败: {e}")
        return False

def main():
    """
    设置系统音量，支持ALSA和PulseAudio两种方式
    支持命令行参数：python3 max_autio.py [volume_level]
    """
    try:
        # 获取目标音量
        target_volume = GlobalConf.volume_num
        
        # 如果有命令行参数，使用命令行提供的音量值
        if len(sys.argv) > 1:
            try:
                target_volume = int(sys.argv[1])
                if not 0 <= target_volume <= 100:
                    logger.error(f"音量值超出范围: {target_volume}, 必须在0-100之间")
                    return
            except ValueError:
                logger.error(f"无效的音量值: {sys.argv[1]}")
                return
        
        logger.info(f"目标音量: {target_volume}%")
        
        # 尝试使用ALSA音量控制
        if ALSA_AVAILABLE:
            try:
                logger.info("使用ALSA音量控制")
                controller = create_alsa_controller()
                
                # 获取当前音量
                current_volume = controller.get_volume()
                if current_volume is not None:
                    logger.info(f"当前音量: {current_volume}%")
                
                # 设置音量
                if controller.set_volume(target_volume):
                    # 验证设置结果
                    new_volume = controller.get_volume()
                    if new_volume is not None:
                        logger.info(f"ALSA音量设置成功: {target_volume}% -> {new_volume}%")
                    else:
                        logger.warning("ALSA音量设置后无法验证")
                    return
                else:
                    logger.error(f"ALSA音量设置失败: {target_volume}%")
                    
            except Exception as e:
                logger.error(f"ALSA音量控制异常: {str(e)}")
                logger.info("回退到PulseAudio音量控制")
        
        # 回退到PulseAudio音量控制
        logger.info("使用PulseAudio音量控制")
        sink = get_default_sink()
        if not sink:
            logger.error("未能找到默认输出设备")
            return
        
        # 获取当前音量
        current_volume = get_sink_volume(sink)
        if current_volume is not None:
            logger.info(f"当前音量: {current_volume}%")
            
            # 设置音量
            if set_sink_volume(sink, target_volume):
                # 验证设置结果
                new_volume = get_sink_volume(sink)
                if new_volume is not None:
                    logger.info(f"PulseAudio音量设置成功: {target_volume}% -> {new_volume}%")
                else:
                    logger.warning("PulseAudio音量设置后无法验证")
            else:
                logger.error(f"PulseAudio音量设置失败: {target_volume}%")
        else:
            logger.error("无法获取当前音量信息")
    
    except Exception as e:
        logger.error(f"音量控制异常: {str(e)}")

if __name__ == "__main__":
    main()
