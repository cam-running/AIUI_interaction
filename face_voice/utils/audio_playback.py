# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   audio_playback.PY
# @Time       2025-06-12 08:47
import os
import queue
import shutil
import platform
import threading
import subprocess
from pathlib import Path
import simpleaudio as sa
from conf.basic import GlobalConf
from fastapi import HTTPException
from conf.basic import get_logger

logger = get_logger("audio_playback")

def ensure_alsa_volume():
    """确保音量设置正确（优先使用ALSA，回退到其他方式）"""
    try:
        from conf.basic import GlobalConf
        target_volume = GlobalConf.volume_num

        # 尝试使用ALSA
        try:
            from utils.alsa_volume_control import create_alsa_controller
            controller = create_alsa_controller()
            current_volume = controller.get_volume()

            if current_volume is None:
                logger.warning("ALSA无法获取当前音量")
            elif abs(current_volume - target_volume) > 5:  # 如果音量差异超过5%
                logger.info(f"ALSA调整音量: {current_volume}% -> {target_volume}%")
                if controller.set_volume(target_volume):
                    return True
                else:
                    logger.warning("ALSA音量设置失败")
            else:
                return True  # 音量已经合适

        except ImportError:
            logger.info("ALSA模块不可用，跳过音量检查")
        except Exception as e:
            logger.warning(f"ALSA音量检查异常: {str(e)}")

        # 如果ALSA不可用或失败，这里可以添加其他音量控制方式
        logger.info("音量检查完成（可能使用了回退方案）")
        return True

    except Exception as e:
        logger.warning(f"音量检查失败: {str(e)}")
        return False




class ControlAudio:
    def __init__(self):
        # 检测操作系统和音频环境
        self.is_ubuntu = platform.system() == 'Linux'
        self.available_players = self._detect_audio_players()

        if self.available_players:
            logger.warning(f"检测到可用播放器: {[p[1] for p in self.available_players]}")
        else:
            logger.warning("未检测到任何可用的音频播放器")

        # 播放状态变量
        self._play_thread = None

    def _detect_audio_players(self):
        players = []
        if not self.is_ubuntu:
            # Windows环境，优先使用simpleaudio
            try:
                import simpleaudio as sa
                players.append(('simpleaudio', 'simpleaudio'))
            except ImportError:
                pass
            return players

        # 优先级1: PulseAudio
        if self._check_pulseaudio():
            players.append(('pulseaudio', 'paplay'))

        # 优先级2: ALSA
        if self._check_alsa():
            players.append(('alsa', 'aplay'))

        # 优先级3: SoX
        if self._check_sox():
            players.append(('sox', 'play'))

        try:
            import simpleaudio as sa
            players.append(('simpleaudio', 'simpleaudio'))
        except ImportError:
            pass

        return players

    def _check_pulseaudio(self):
        """检查PulseAudio可用性"""
        try:
            return shutil.which('paplay') is not None
        except:
            return False

    def _check_alsa(self):
        """检查ALSA可用性"""
        try:
            return shutil.which('aplay') is not None
        except:
            return False

    def _check_sox(self):
        """检查SoX可用性"""
        try:
            return shutil.which('play') is not None
        except:
            return False

    def play_mp3(self, audio, file_path):
        """非阻塞方式播放MP3"""
        logger.info(f"开始播放音频: {os.path.basename(file_path)}")

        if self._play_thread is not None and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)
            self._play_thread = None

        # 创建新的播放线程
        self._play_thread = threading.Thread(
            target=self._play_mp3_blocking,
            args=(audio, file_path),
            daemon=True
        )
        self._play_thread.start()
        logger.info("播放线程已启动")

    def _play_mp3_blocking(self, audio, file_path):
        """实际的阻塞播放方法"""
        try:
            success = self._play_with_priority_strategy(audio, file_path)

            if not success:
                logger.error("所有播放器都失败了")
        except Exception as e:
            logger.error(f"音频播放失败: {str(e)}")

    def _play_with_priority_strategy(self, audio, file_path):
        """使用优先级策略播放音频"""
        if not self.available_players:
            logger.info("没有检测到可用的音频播放器")
            return False

        for player_type, player_cmd in self.available_players:
            try:
                logger.info(f"尝试使用 {player_type} ({player_cmd}) 播放")

                if player_type == 'pulseaudio':
                    success = self._play_with_paplay(file_path, audio)
                elif player_type == 'alsa':
                    success = self._play_with_aplay(file_path, audio)
                elif player_type == 'sox':
                    success = self._play_with_sox(file_path, audio)
                elif player_type == 'simpleaudio':
                    success = self._play_with_simpleaudio(audio)
                else:
                    continue
                if success:
                    logger.info(f"成功使用 {player_type} 播放音频")
                    return True
            except Exception as e:
                logger.error(f"{player_type} 播放异常: {str(e)}")
                continue

        return False

    def _play_with_simpleaudio(self, audio):
        """使用simpleaudio播放"""
        try:
            # 使用simpleaudio播放
            play_obj = sa.play_buffer(
                audio.raw_data,
                num_channels=audio.channels,
                bytes_per_sample=audio.sample_width,
                sample_rate=audio.frame_rate
            )
            play_obj.wait_done()
            return True

        except Exception as e:
            logger.error(f"simpleaudio播放失败: {str(e)}")
            return False

    def _play_with_paplay(self, file_path, audio):
        """使用paplay播放"""
        try:
            cmd = ['paplay', file_path]
            process = subprocess.Popen(cmd)
            process.wait()
            return process.returncode == 0
        except Exception as e:
            logger.error(f'paplay播放失败: {str(e)}')
            return False

    def _play_with_aplay(self, file_path, audio):
        """使用aplay播放"""
        try:
            # 转换MP3为WAV（aplay不支持MP3）
            file_path_str = str(file_path)  # 先转换为字符串
            wav_path = file_path_str.replace('.mp3', '.wav')
            audio.export(wav_path, format="wav")
            cmd = ['aplay', wav_path]
            process = subprocess.Popen(cmd)
            process.wait()
            if os.path.exists(wav_path):
                os.remove(wav_path)
            return process.returncode == 0
        except Exception as e:
            logger.error(f'aplay播放失败: {str(e)}')
            return False

    def _play_with_sox(self, file_path, audio):
        try:
            cmd = ['play', file_path]
            process = subprocess.Popen(cmd)
            process.wait()
            return process.returncode == 0
        except Exception as e:
            logger.error(f'SoX播放失败: {str(e)}')
            return False



def play_audio(filename):
    """使用新的高级音频控制类播放音频"""
    from utils.control_audio_advanced import ControlAudio
    from pydub import AudioSegment
    
    # 创建高级音频控制实例（单例模式）
    c = ControlAudio()
    
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    mp3_dir = parent_dir / "conf" / "mp3"
    mp3_path = mp3_dir / f"{filename}.wav" if not filename.endswith('.wav') else mp3_dir / filename
    logger.info(f"mp3_path: {mp3_path}")
    if not mp3_path.exists():
        raise HTTPException(status_code=404, detail=f"音频文件 {filename} 不存在")
    
    try:
        # 使用pydub加载音频文件
        audio = AudioSegment.from_file(mp3_path, format="wav")
        
        # 使用新的高级播放方法
        c.run_mp3(audio, len(audio.raw_data), str(mp3_path))
        
        logger.info(f"开始播放音频: {filename}")
        return {"status": "success", "message": f"开始播放 {filename}"}
        
    except Exception as e:
        logger.error(f"播放失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"播放失败: {str(e)}")




audio_play_queue = queue.Queue()
is_audio_playing = False
current_process = None

def audio_play_worker():
    """音频播放线程"""
    global is_audio_playing, current_process
    while True:
        try:
            audio_file = audio_play_queue.get(timeout=1)
            if audio_file:
                # 在实际播放前设置全局状态为播放中
                GlobalConf.sink_status = True
                is_audio_playing = True
                logger.info(f"开始播放音频: {audio_file}")

                try:
                    play_audio_file(audio_file)  # 实际播放函数
                    logger.info(f"音频播放完成: {audio_file}")
                except Exception as e:
                    logger.error(f"播放音频失败: {str(e)}")
                finally:
                    # 无论播放成功或失败，都重置状态
                    is_audio_playing = False
                    current_process = None
                    GlobalConf.sink_status = False  # 播放完成后释放全局锁
                    audio_play_queue.task_done()
                    logger.info("音频播放完成，继续识别")
        except queue.Empty:
            continue


def play_audio_file(file_path):
    """实际播放音频文件的函数"""
    global current_process
    try:
        current_process = subprocess.Popen(
            ["play", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        current_process.wait()  # 阻塞直到播放完成
    except Exception as e:
        # 清理可能残留的进程
        if current_process:
            try:
                current_process.terminate()
            except:
                pass
        current_process = None
        raise e


def play_face_v(file_path):
    """将音频加入播放队列"""
    global current_process
    if not file_path.endswith('.wav'):
        raise HTTPException(status_code=400, detail="只支持WAV格式音频文件")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"音频文件不存在: {file_path}")
    if current_process and is_audio_playing:
        logger.warning(f"已有音频在播放，新请求将排队等待: {file_path}")

    # 将音频文件加入播放队列
    audio_play_queue.put(file_path)
    logger.info(f"已将音频加入播放队列: {file_path}")
    return {"status": "queued", "message": f"音频已加入播放队列: {file_path}"}


audio_thread = threading.Thread(target=audio_play_worker, daemon=True)
audio_thread.start()

