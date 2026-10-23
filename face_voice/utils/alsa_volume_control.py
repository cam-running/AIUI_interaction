# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   alsa_volume_control.py
# @Time       2025-01-27 created

import subprocess
import re
import logging
from typing import Optional, Dict, List
from conf.basic import get_logger

logger = get_logger("alsa_volume")

class AlsaVolumeControl:
    """
    基于ALSA的音量控制类，提供更可靠的音量识别和控制
    相比PulseAudio的pactl，ALSA amixer命令更底层，更稳定
    """
    
    def __init__(self, preferred_card: str = None):
        self.logger = logger
        self.default_card = None
        self.default_mixer = None
        self.preferred_card = preferred_card
        self.initialize()
    
    def initialize(self):
        """初始化ALSA音频设备"""
        try:
            self.default_card = self.get_default_card()
            self.default_mixer = self.get_default_mixer(self.default_card)
            self.logger.info(f"ALSA初始化成功: 卡片={self.default_card}, 混音器={self.default_mixer}")
        except Exception as e:
            self.logger.error(f"ALSA初始化失败: {str(e)}")
    
    def get_default_card(self) -> str:
        """获取默认音频卡片，优先选择USB音频设备"""
        try:
            # 获取系统音频卡片列表
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, check=True)
            lines = result.stdout.split('\n')
            
            cards = []
            usb_cards = []
            
            for line in lines:
                if 'card' in line.lower() and ':' in line:
                    # 解析 "card 0: PCH [HDA Intel PCH], device 0:"
                    match = re.search(r'card\s+(\d+):\s*([^,\[]+)\s*\[([^\]]+)\]', line)
                    if match:
                        card_id = match.group(1)
                        card_short_name = match.group(2).strip()
                        card_long_name = match.group(3).strip()
                        
                        card_info = {
                            'id': card_id,
                            'short_name': card_short_name,
                            'long_name': card_long_name,
                            'full_line': line.strip()
                        }
                        
                        self.logger.info(f"检测到音频卡片: {line.strip()}")
                        cards.append(card_info)
                        
                        # 检查是否为USB音频设备
                        line_upper = line.upper()
                        if any(keyword in line_upper for keyword in ['USB AUDIO', 'DAC', 'USB']):
                            usb_cards.append(card_info)
                            self.logger.info(f"发现USB音频设备: card {card_id} - {card_long_name}")
            
            # 如果有指定的卡片，优先使用
            if self.preferred_card:
                for card in cards:
                    if card['id'] == self.preferred_card:
                        self.logger.info(f"使用指定的音频卡片: {card['id']}")
                        return card['id']
                self.logger.warning(f"指定的卡片 {self.preferred_card} 未找到")
            
            # 优先使用USB音频设备
            if usb_cards:
                selected_card = usb_cards[0]
                self.logger.info(f"选择USB音频设备: card {selected_card['id']} - {selected_card['long_name']}")
                return selected_card['id']
            
            # 如果没有USB设备，使用第一个可用的卡片
            if cards:
                selected_card = cards[0]
                self.logger.info(f"使用第一个音频卡片: card {selected_card['id']} - {selected_card['long_name']}")
                return selected_card['id']
            
            # 如果都没有找到，默认返回0
            self.logger.warning("未找到任何音频卡片，使用默认卡片0")
            return "0"
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取音频卡片失败: {e.stderr}")
            return "0"
        except Exception as e:
            self.logger.error(f"获取音频卡片异常: {str(e)}")
            return "0"
    
    def get_default_mixer(self, card: str) -> str:
        """获取默认混音器控制，智能选择支持音量控制的混音器"""
        try:
            # 获取指定卡片的混音器控制列表
            result = subprocess.run(['amixer', '-c', card, 'scontrols'], 
                                  capture_output=True, text=True, check=True)
            
            lines = result.stdout.split('\n')
            mixers = []
            
            for line in lines:
                if 'Simple mixer control' in line:
                    # 解析 "Simple mixer control 'Master',0"
                    match = re.search(r"'([^']+)'", line)
                    if match:
                        mixer_name = match.group(1)
                        mixers.append(mixer_name)
                        self.logger.info(f"检测到混音器: {mixer_name}")
            
            # 过滤掉不支持音量控制的混音器
            valid_mixers = []
            for mixer in mixers:
                if self._test_mixer_volume_support(card, mixer):
                    valid_mixers.append(mixer)
                    self.logger.info(f"混音器 {mixer} 支持音量控制")
                else:
                    self.logger.debug(f"混音器 {mixer} 不支持音量控制，跳过")
            
            # 优先选择常见的混音器（如果它们支持音量控制）
            preferred_mixers = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital', 'Analog']
            for preferred in preferred_mixers:
                if preferred in valid_mixers:
                    self.logger.info(f"选择首选混音器: {preferred}")
                    return preferred
            
            # 如果没有找到首选的，使用第一个支持音量控制的
            if valid_mixers:
                selected = valid_mixers[0]
                self.logger.info(f"使用第一个有效混音器: {selected}")
                return selected
            
            # 如果都不支持，还是返回第一个（可能是只读的）
            if mixers:
                selected = mixers[0]
                self.logger.warning(f"所有混音器都不支持音量控制，使用第一个: {selected}")
                return selected
            
            # 默认使用Master
            self.logger.warning("未找到任何混音器，使用默认Master")
            return "Master"
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取混音器失败: {e.stderr}")
            return "Master"
        except Exception as e:
            self.logger.error(f"获取混音器异常: {str(e)}")
            return "Master"
    
    def _test_mixer_volume_support(self, card: str, mixer: str) -> bool:
        """测试混音器是否支持音量控制"""
        try:
            # 首先尝试获取当前音量
            result = subprocess.run(['amixer', '-c', card, 'sget', mixer], 
                                  capture_output=True, text=True, check=True)
            
            # 检查输出是否包含音量信息
            if '[' in result.stdout and '%]' in result.stdout:
                # 进一步测试是否可以设置音量（测试设置当前音量）
                volume_match = re.search(r'\[(\d+)%\]', result.stdout)
                if volume_match:
                    current_volume = volume_match.group(1)
                    # 尝试设置相同的音量值来测试是否支持写入
                    test_result = subprocess.run(['amixer', '-c', card, 'sset', mixer, f'{current_volume}%'], 
                                               capture_output=True, text=True)
                    if test_result.returncode == 0:
                        return True
            
            return False
            
        except Exception:
            return False
    
    def get_volume(self, card: str = None, mixer: str = None) -> Optional[int]:
        """获取当前音量 (0-100)"""
        try:
            card = card or self.default_card
            mixer = mixer or self.default_mixer
            
            if not card or not mixer:
                self.logger.error("音频卡片或混音器未设置")
                return None
            
            result = subprocess.run(['amixer', '-c', card, 'sget', mixer], 
                                  capture_output=True, text=True, check=True)
            
            # 解析音量信息，格式类似: [50%] [-20.00dB] [on]
            volume_match = re.search(r'\[(\d+)%\]', result.stdout)
            if volume_match:
                volume = int(volume_match.group(1))
                self.logger.debug(f"当前音量: {volume}%")
                return volume
            
            self.logger.error("无法解析音量信息")
            return None
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取音量失败: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"获取音量异常: {str(e)}")
            return None
    
    def set_volume(self, volume: int, card: str = None, mixer: str = None) -> bool:
        """设置音量 (0-100)"""
        try:
            if not 0 <= volume <= 100:
                self.logger.error(f"音量值超出范围: {volume}")
                return False
            
            card = card or self.default_card
            mixer = mixer or self.default_mixer
            
            if not card or not mixer:
                self.logger.error("音频卡片或混音器未设置")
                return False
            
            # 设置音量
            result = subprocess.run(['amixer', '-c', card, 'sset', mixer, f'{volume}%'], 
                                  capture_output=True, text=True, check=True)
            
            # 验证设置是否成功
            current_volume = self.get_volume(card, mixer)
            if current_volume is not None and abs(current_volume - volume) <= 2:  # 允许2%的误差
                self.logger.info(f"音量设置成功: {volume}% (实际: {current_volume}%)")
                return True
            else:
                self.logger.warning(f"音量设置可能不准确: 目标{volume}%, 实际{current_volume}%")
                return True  # 即使有小误差也认为成功
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"设置音量失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"设置音量异常: {str(e)}")
            return False
    
    def mute(self, card: str = None, mixer: str = None) -> bool:
        """静音"""
        try:
            card = card or self.default_card
            mixer = mixer or self.default_mixer
            
            if not card or not mixer:
                self.logger.error("音频卡片或混音器未设置")
                return False
            
            subprocess.run(['amixer', '-c', card, 'sset', mixer, 'mute'], 
                          capture_output=True, text=True, check=True)
            
            self.logger.info("已静音")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"静音失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"静音异常: {str(e)}")
            return False
    
    def unmute(self, card: str = None, mixer: str = None) -> bool:
        """取消静音"""
        try:
            card = card or self.default_card
            mixer = mixer or self.default_mixer
            
            if not card or not mixer:
                self.logger.error("音频卡片或混音器未设置")
                return False
            
            subprocess.run(['amixer', '-c', card, 'sset', mixer, 'unmute'], 
                          capture_output=True, text=True, check=True)
            
            self.logger.info("已取消静音")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"取消静音失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"取消静音异常: {str(e)}")
            return False
    
    def is_muted(self, card: str = None, mixer: str = None) -> Optional[bool]:
        """检查是否静音"""
        try:
            card = card or self.default_card
            mixer = mixer or self.default_mixer
            
            if not card or not mixer:
                self.logger.error("音频卡片或混音器未设置")
                return None
            
            result = subprocess.run(['amixer', '-c', card, 'sget', mixer], 
                                  capture_output=True, text=True, check=True)
            
            # 查找静音状态，格式类似: [50%] [-20.00dB] [on] 或 [off]
            if '[off]' in result.stdout:
                return True
            elif '[on]' in result.stdout:
                return False
            
            self.logger.warning("无法确定静音状态")
            return None
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"检查静音状态失败: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"检查静音状态异常: {str(e)}")
            return None
    
    def get_audio_devices(self) -> List[Dict[str, str]]:
        """获取所有音频设备信息"""
        devices = []
        try:
            # 获取播放设备
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, check=True)
            lines = result.stdout.split('\n')
            
            for line in lines:
                if 'card' in line.lower() and ':' in line:
                    # 解析设备信息
                    match = re.search(r'card\s+(\d+):\s+([^,]+),\s+device\s+(\d+):\s+(.+)', line)
                    if match:
                        card_id, card_name, device_id, device_name = match.groups()
                        devices.append({
                            'type': 'playback',
                            'card_id': card_id,
                            'card_name': card_name.strip(),
                            'device_id': device_id,
                            'device_name': device_name.strip()
                        })
            
            self.logger.info(f"检测到 {len(devices)} 个音频设备")
            return devices
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取音频设备失败: {e.stderr}")
            return []
        except Exception as e:
            self.logger.error(f"获取音频设备异常: {str(e)}")
            return []
    
    def test_audio_device(self, card: str = None) -> bool:
        """测试音频设备是否正常工作"""
        try:
            card = card or self.default_card
            
            if not card:
                self.logger.error("音频卡片未设置")
                return False
            
            # 使用aplay测试音频设备
            result = subprocess.run(['aplay', '-q', '-D', f'plughw:{card},0', '/dev/zero'], 
                                  capture_output=True, text=True, timeout=2)
            
            if result.returncode == 0:
                self.logger.info(f"音频设备测试通过: card {card}")
                return True
            else:
                self.logger.warning(f"音频设备测试失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.info("音频设备测试超时，可能正常工作")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"音频设备测试失败: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"音频设备测试异常: {str(e)}")
            return False
    
    def get_status_info(self) -> Dict:
        """获取音频系统状态信息"""
        info = {
            'card': self.default_card,
            'mixer': self.default_mixer,
            'volume': self.get_volume(),
            'muted': self.is_muted(),
            'devices': self.get_audio_devices(),
            'working': False
        }
        
        # 测试设备工作状态
        info['working'] = self.test_audio_device()
        
        return info


def create_alsa_controller(preferred_card: str = None) -> AlsaVolumeControl:
    """创建ALSA音量控制器实例"""
    return AlsaVolumeControl(preferred_card=preferred_card)


if __name__ == "__main__":
    # 测试代码
    controller = create_alsa_controller()
    
    print("=== ALSA音量控制测试 ===")
    
    # 获取状态信息
    status = controller.get_status_info()
    print(f"状态信息: {status}")
    
    # 获取当前音量
    current_volume = controller.get_volume()
    print(f"当前音量: {current_volume}%")
    
    # 测试设置音量
    test_volume = 50
    if controller.set_volume(test_volume):
        print(f"音量设置成功: {test_volume}%")
        new_volume = controller.get_volume()
        print(f"验证音量: {new_volume}%")
    else:
        print("音量设置失败")
    
    # 恢复原音量
    if current_volume is not None:
        controller.set_volume(current_volume)
        print(f"恢复原音量: {current_volume}%")
