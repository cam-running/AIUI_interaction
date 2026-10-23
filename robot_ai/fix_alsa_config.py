'''
Author: zhaoyong 77912776@qq.com
Date: 2025-08-24 15:45:57
LastEditTime: 2025-08-24 16:02:32
LastEditors: zhaoyong 77912776@qq.com
FilePath: \robot_ai\fix_alsa_config.py
Description: 头部注释配置模板
'''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALSA配置优化脚本
解决Ubuntu环境中的ALSA音频问题
"""

import os
import platform
import subprocess
import shutil
from utils.logger import setup_logger, logger


def check_alsa_config():
    """检查ALSA配置"""
    logger.info("🔍 检查ALSA配置...")

    try:
        # 检查ALSA版本
        result = subprocess.run(['aplay', '--version'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"📋 ALSA版本: {result.stdout.strip()}")
        else:
            logger.warning("⚠️ 无法获取ALSA版本信息")
    except Exception as e:
        logger.error(f"❌ 检查ALSA版本失败: {e}")


def check_audio_devices():
    """检查音频设备"""
    logger.info("🎵 检查音频设备...")

    try:
        # 列出音频设备
        result = subprocess.run(['aplay', '-l'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("📋 音频播放设备:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"    {line}")
        else:
            logger.warning("⚠️ 无法获取音频设备列表")
    except Exception as e:
        logger.error(f"❌ 检查音频设备失败: {e}")


def create_alsa_config():
    """创建优化的ALSA配置"""
    logger.info("⚙️ 创建优化的ALSA配置...")

    # ALSA配置文件路径 - 应该在用户主目录
    if platform.system().lower() == 'linux':
        config_path = os.path.expanduser("~/.asoundrc")
    else:
        logger.info("📋 非Linux系统，跳过ALSA配置")
        return False

    # 优化的ALSA配置 - 专门针对音色清晰度优化
    alsa_config = """# ALSA配置文件 - 自动生成
# 用于修复音频设备配置问题，解决电流声和音色不清晰问题

# 默认PCM设备配置 - 使用优化的缓冲区设置，提高音色清晰度
pcm.!default {
    type plug
    slave.pcm {
        type hw
        card 0
        device 0
        rate 16000
        channels 1
        format S16_LE
        buffer_size 1024
        period_size 512
    }
}

# 默认控制设备配置
ctl.!default {
    type hw
    card 0
}

# 高清晰度PCM设备 - 专门用于TTS播放，确保音色清晰
pcm.high_quality {
    type plug
    slave.pcm {
        type hw
        card 0
        device 0
        rate 16000
        channels 1
        format S16_LE
        buffer_size 512
        period_size 256
    }
}

# 低延迟PCM设备 - 用于TTS播放
pcm.lowlatency {
    type plug
    slave.pcm {
        type hw
        card 0
        device 0
        rate 16000
        channels 1
        format S16_LE
        buffer_size 1024
        period_size 512
    }
}

# 稳定PCM设备 - 用于避免电流声
pcm.stable {
    type plug
    slave.pcm {
        type hw
        card 0
        device 0
        rate 16000
        channels 1
        format S16_LE
        buffer_size 2048
        period_size 1024
    }
}

# 无电流声PCM设备 - 专门用于避免电流声
pcm.no_current_noise {
    type plug
    slave.pcm {
        type hw
        card 0
        device 0
        rate 16000
        channels 1
        format S16_LE
        buffer_size 1024
        period_size 512
    }
}

# 简单PCM设备
pcm.simple {
    type plug
    slave.pcm "hw:0,0"
}

# 禁用不存在的设备以避免ALSA错误
pcm.front {
    type null
}

pcm.rear {
    type null
}

pcm.center_lfe {
    type null
}

pcm.side {
    type null
}

pcm.surround21 {
    type null
}

pcm.surround40 {
    type null
}

pcm.surround41 {
    type null
}

pcm.surround50 {
    type null
}

pcm.surround51 {
    type null
}

pcm.surround71 {
    type null
}

pcm.iec958 {
    type null
}

pcm.spdif {
    type null
}

pcm.hdmi {
    type null
}

pcm.modem {
    type null
}

pcm.phoneline {
    type null
}

# 禁用OSS设备
pcm.dsp {
    type null
}

# 禁用USB音频设备错误
pcm.usb_stream {
    type null
}
"""

    try:
        # 备份现有配置
        if os.path.exists(config_path):
            backup_path = config_path + ".backup"
            shutil.copy2(config_path, backup_path)
            logger.info(f"📋 已备份现有配置到: {backup_path}")

        # 写入新配置
        with open(config_path, 'w') as f:
            f.write(alsa_config)

        logger.info(f"✅ ALSA配置文件已创建: {config_path}")

        # 设置文件权限
        os.chmod(config_path, 0o644)
        logger.info("✅ 已设置配置文件权限")

        return True
    except Exception as e:
        logger.error(f"❌ 创建ALSA配置文件失败: {e}")
        return False


def create_simple_alsa_config():
    """创建简单的ALSA配置"""
    logger.info("⚙️ 创建简单的ALSA配置...")

    # ALSA配置文件路径
    if platform.system().lower() == 'linux':
        config_path = os.path.expanduser("~/.asoundrc")
    else:
        logger.info("📋 非Linux系统，跳过ALSA配置")
        return False

    # 简单的ALSA配置
    simple_config = """# 简单ALSA配置文件
# 用于修复音频设备配置问题

# 默认PCM设备
pcm.!default {
    type plug
    slave.pcm "hw:0,0"
}

# 默认控制设备
ctl.!default {
    type hw
    card 0
}
"""

    try:
        # 备份现有配置
        if os.path.exists(config_path):
            backup_path = config_path + ".backup"
            shutil.copy2(config_path, backup_path)
            logger.info(f"📋 已备份现有配置到: {backup_path}")

        # 写入新配置
        with open(config_path, 'w') as f:
            f.write(simple_config)

        logger.info(f"✅ 简单ALSA配置文件已创建: {config_path}")
        logger.info("✅ 配置文件已简化，避免复杂配置导致的错误")

        # 设置文件权限
        os.chmod(config_path, 0o644)
        logger.info("✅ 已设置配置文件权限")

        return True
    except Exception as e:
        logger.error(f"❌ 创建ALSA配置文件失败: {e}")
        return False


def remove_alsa_config():
    """移除ALSA配置文件"""
    logger.info("🗑️ 移除ALSA配置文件...")

    if platform.system().lower() != 'linux':
        logger.info("📋 非Linux系统，跳过ALSA配置移除")
        return False

    config_path = os.path.expanduser("~/.asoundrc")

    try:
        if os.path.exists(config_path):
            # 备份现有配置
            backup_path = config_path + ".backup"
            shutil.copy2(config_path, backup_path)
            logger.info(f"📋 已备份现有配置到: {backup_path}")

            # 移除配置文件
            os.remove(config_path)
            logger.info(f"✅ 已移除ALSA配置文件: {config_path}")
            logger.info("💡 系统将使用默认ALSA配置")
            return True
        else:
            logger.info("📋 ALSA配置文件不存在")
            return False
    except Exception as e:
        logger.error(f"❌ 移除ALSA配置文件失败: {e}")
        return False


def check_pulseaudio():
    """检查PulseAudio状态"""
    logger.info("🔊 检查PulseAudio状态...")

    try:
        # 检查PulseAudio是否运行
        result = subprocess.run(['pulseaudio', '--check'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("✅ PulseAudio正在运行")
        else:
            logger.warning("⚠️ PulseAudio未运行，尝试启动...")
            subprocess.run(['pulseaudio', '--start'],
                           capture_output=True, text=True, timeout=10)
    except Exception as e:
        logger.error(f"❌ 检查PulseAudio失败: {e}")


def reload_alsa():
    """重新加载ALSA配置"""
    logger.info("🔄 重新加载ALSA配置...")

    try:
        # 重启ALSA服务
        subprocess.run(['sudo', 'systemctl', 'restart', 'alsa-utils'],
                       capture_output=True, text=True, timeout=10)
        logger.info("✅ ALSA服务已重启")
    except Exception as e:
        logger.warning(f"⚠️ 重启ALSA服务失败: {e}")
        logger.info("💡 请手动重启音频服务或重新登录")


def optimize_audio_settings():
    """优化音频设置"""
    logger.info("🎛️ 优化音频设置...")

    if platform.system().lower() != 'linux':
        logger.info("📋 非Linux系统，跳过音频优化")
        return

    # 首先尝试移除现有配置
    if remove_alsa_config():
        logger.info("✅ 已移除有问题的ALSA配置")

    # 创建简单的ALSA配置
    if create_simple_alsa_config():
        logger.info("✅ 简单ALSA配置创建完成")
    else:
        logger.warning("⚠️ 无法创建ALSA配置，将使用系统默认配置")

    # 重新加载ALSA配置
    reload_alsa()

    # 检查PulseAudio
    check_pulseaudio()

    # 检查音频设备
    check_audio_devices()


def main():
    """主函数"""
    setup_logger('fix_alsa', 'logs')
    logger.info("🚀 开始ALSA配置优化...")

    # 检查系统
    logger.info(f"📋 操作系统: {platform.system()} {platform.release()}")

    # 检查ALSA配置
    check_alsa_config()

    # 优化音频设置
    optimize_audio_settings()

    logger.info("✅ ALSA配置优化完成")
    logger.info("💡 建议重启音频服务或重新登录以应用配置")
    logger.info("💡 如果仍有问题，请运行: sudo systemctl restart pulseaudio")


if __name__ == "__main__":
    main()
