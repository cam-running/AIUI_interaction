'''
Author: zhaoyong 77912776@qq.com
Date: 2025-06-20 14:31:06
LastEditTime: 2025-09-05 13:32:52
LastEditors: zhaoyong 77912776@qq.com
FilePath: \server_tts\tts_audio_control\control_tts_audio_xinwang.py
Description: 头部注释配置模板
'''
# -*- coding: utf-8 -*-
"""
文件: 高级音频控制类
"""
import time
import os
import shutil
import simpleaudio as sa
from pydub import AudioSegment
import threading
import queue
import subprocess
import sys
import platform
import atexit
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# 尝试导入sounddevice
try:
    import sounddevice as sd
    import platform

    system = platform.system().lower()

    if system == "linux":
        sd.default.device = 'pulse'  # 或 'pipewire'
    elif system == "windows":
        sd.default.device = None  # 使用系统默认输出（WASAPI）
    elif system == "darwin":
        sd.default.device = None  # macOS 使用 CoreAudio 默认设备

    import numpy as np
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

from conf.basic import get_logger

logger = get_logger("control_audio_advanced")


class ControlAudio:
    # 类级别的单例播放队列和锁
    _instance = None
    _lock = threading.Lock()
    _play_queue = queue.Queue()
    _play_thread = None
    _queue_lock = threading.Lock()
    _file_lock = None
    _is_playing = False
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ControlAudio, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, logger_main=None):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
            
        # 如果没有传入logger，使用模块级的logger
        self.logger_main = logger_main if logger_main is not None else logger

        self.audio_instance = None
        self.steam_source_obj = None
        self.steam_sink_obj = None
        self._steam_sink_stop = False
        self._steam_sink_status = False

        # 检测操作系统和音频环境
        self.is_ubuntu = platform.system() == 'Linux'
        self.available_players = self._detect_audio_players()

        # 根据环境选择初始化策略
        if self.available_players:
            self.logger_main.info(
                f"检测到可用播放器: {[p[1] for p in self.available_players]}")
        else:
            self.logger_main.warning("未检测到任何可用的音频播放器")

        # 尝试初始化simpleaudio作为备选
        try:
            self.reload_audio()
        except Exception as e:
            self.logger_main.warning(f"simpleaudio初始化失败: {str(e)}")

        self._paused = False
        self._start_time = time.time()
        self._pause_position = 0  # 记录暂停位置
        self._audio_data = None  # 保存音频数据
        self._current_position = 0  # 当前播放的chunk位置

        self._progress_queue = queue.Queue()  # 进度队列
        self.cur_tts_file = None  # 当前播放的tts文件
        self.pause_progress_ts = None  # 暂停进度时间戳
        self.usb_audio_sink = None  # USB Audio设备sink名称
        
        # 初始化文件锁
        self._init_file_lock()
        
        # 启动播放队列处理线程
        self._start_queue_processor()
        
        # 注册退出清理函数
        atexit.register(self._cleanup_on_exit)
        
        self._initialized = True

    def _init_file_lock(self):
        """初始化文件锁"""
        if not HAS_FCNTL:
            self.logger_main.info("Windows环境，跳过文件锁初始化")
            self._file_lock = None
            return
            
        try:
            lock_file_path = "/tmp/audio_control.lock"
            self._file_lock = open(lock_file_path, 'w')
            fcntl.flock(self._file_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.logger_main.info("文件锁初始化成功")
        except (OSError, IOError) as e:
            self.logger_main.warning(f"文件锁初始化失败: {str(e)}")
            self._file_lock = None

    def _start_queue_processor(self):
        """启动播放队列处理线程"""
        with self._queue_lock:
            if self._play_thread is None or not self._play_thread.is_alive():
                self._play_thread = threading.Thread(
                    target=self._process_play_queue,
                    daemon=True,
                    name="AudioPlayQueue"
                )
                self._play_thread.start()
                self.logger_main.info("播放队列处理线程已启动")

    def _process_play_queue(self):
        """处理播放队列的主循环"""
        self.logger_main.info("播放队列处理器开始运行")
        
        while True:
            try:
                # 从队列获取播放任务
                task = self._play_queue.get(timeout=1.0)
                if task is None:  # 收到停止信号
                    break
                    
                self.logger_main.info(f"开始处理播放任务: {task.get('tts_file', 'unknown')}")
                self._is_playing = True
                
                try:
                    # 执行播放任务
                    self._execute_play_task(task)
                except Exception as e:
                    self.logger_main.error(f"播放任务执行失败: {str(e)}")
                finally:
                    self._is_playing = False
                    self._play_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.logger_main.error(f"播放队列处理异常: {str(e)}")
                time.sleep(0.1)
                
        self.logger_main.info("播放队列处理器已停止")

    def _execute_play_task(self, task):
        """执行具体的播放任务"""
        audio = task['audio']
        file_path = task['file_path']
        control_id = task.get('control_id')
        chunk = task.get('chunk', 1024)
        tts_file = os.path.basename(file_path)
        
        # 重置播放状态
        self._steam_sink_stop = False
        self._steam_sink_status = False
        self._current_position = 0
        self._paused = False
        self._pause_position = 0
        self.cur_tts_file = tts_file
        self._start_time = time.time()
        
        try:
            # 使用优先级策略播放
            success = self._play_with_priority_strategy(
                audio, file_path, control_id, tts_file)
            
            if not success:
                self.logger_main.error("所有播放器都失败了")
                raise Exception("没有可用的音频播放器")
                
        except Exception as e:
            self.logger_main.error(f"音频播放失败: {str(e)}")
            raise
        finally:
            self.steam_sink_status = False

    def _detect_audio_players(self):
        """检测可用的音频播放器"""
        players = []

        self.logger_main.info("开始检测可用的音频播放器...")
        self.logger_main.info(f"操作系统: {platform.system()} {platform.release()}")
        self.logger_main.info(f"Python版本: {sys.version}")

        if not self.is_ubuntu:
            # Windows环境，优先使用sounddevice，然后simpleaudio
            self.logger_main.info("检测到Windows环境，开始检测音频播放器...")
            
            # 优先级1: sounddevice (推荐)
            if HAS_SOUNDDEVICE:
                test_result = self._test_sounddevice()
                if test_result:
                    players.append(('sounddevice', 'sounddevice'))
                    self.logger_main.info("Windows环境：sounddevice 可用且测试通过")
                else:
                    self.logger_main.warning("Windows环境：sounddevice 导入成功但测试失败")
            else:
                self.logger_main.info("Windows环境：sounddevice 不可用，请安装: pip install sounddevice")
            
            # 优先级2: simpleaudio (备选)
            try:
                import simpleaudio as sa
                # 测试simpleaudio是否真正可用
                test_result = self._test_simpleaudio()
                if test_result:
                    players.append(('simpleaudio', 'simpleaudio'))
                    self.logger_main.info("Windows环境：simpleaudio 可用且测试通过")
                else:
                    self.logger_main.warning("Windows环境：simpleaudio 导入成功但测试失败")
            except ImportError as e:
                self.logger_main.warning(f"Windows环境：simpleaudio 不可用 - {str(e)}")
            except Exception as e:
                self.logger_main.error(f"Windows环境：simpleaudio 检测异常 - {str(e)}")
            return players

        # Linux环境：按优先级检测，优先使用sounddevice
        # 优先级1: sounddevice (推荐，跨平台兼容性好)
        if HAS_SOUNDDEVICE:
            test_result = self._test_sounddevice()
            if test_result:
                players.append(('sounddevice', 'sounddevice'))
                self.logger_main.info("Linux环境：sounddevice 可用且测试通过")
            else:
                self.logger_main.warning("Linux环境：sounddevice 导入成功但测试失败")
        else:
            self.logger_main.info("Linux环境：sounddevice 不可用，请安装: pip install sounddevice")

        # 优先级2: ALSA (最稳定，直接访问USB Audio硬件)
        if self._check_alsa():
            players.append(('alsa', 'aplay'))
            self.logger_main.info("检测到 ALSA (aplay) - 优先使用USB Audio")

        # 优先级3: PulseAudio (通过USB Audio设备)
        if self._check_pulseaudio():
            players.append(('pulseaudio', 'paplay'))
            self.logger_main.info("检测到 PulseAudio (paplay) - 支持USB Audio")

        # 优先级4: SoX (备选)
        if self._check_sox():
            players.append(('sox', 'play'))
            self.logger_main.info("检测到 SoX (play) - 备选播放器")

        # 优先级5: FFmpeg (备选)
        if shutil.which('ffplay'):
            players.append(('ffmpeg', 'ffplay'))
            self.logger_main.info("检测到 FFmpeg (ffplay) - 备选播放器")

        # 备选: simpleaudio (最后选择)
        try:
            import simpleaudio as sa
            players.append(('simpleaudio', 'simpleaudio'))
            self.logger_main.info("检测到 simpleaudio - 最后备选")
        except ImportError:
            self.logger_main.warning("simpleaudio 不可用")

        self.logger_main.info(
            f"总共检测到 {len(players)} 个可用播放器: {[p[1] for p in players]}")

        # 如果检测到PulseAudio，尝试获取USB Audio设备名称
        if any(p[0] == 'pulseaudio' for p in players):
            self._detect_usb_audio_sink()

        return players

    def _test_sounddevice(self):
        """测试sounddevice是否真正可用"""
        try:
            # 尝试播放一个极短的静音片段
            silence = np.zeros(int(0.1 * 44100), dtype=np.float32)  # 0.1秒静音
            sd.play(silence, samplerate=44100, blocking=True)
            self.logger_main.info("sounddevice测试：播放测试成功")
            return True
        except Exception as e:
            self.logger_main.error(f"sounddevice测试失败: {str(e)}")
            return False

    def _play_with_sounddevice(self, audio, control_id, tts_file):
        """使用sounddevice播放，增加缓冲与降级策略"""
        try:
            # 将pydub的AudioSegment转换为numpy数组
            # 获取音频数据并转换为float32格式
            audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32)

            # 如果是立体声，需要重新整形
            if audio.channels == 2:
                audio_data = audio_data.reshape((-1, 2))
            else:
                audio_data = audio_data.reshape((-1, 1))

            # 归一化到[-1, 1]范围
            if audio.sample_width == 1:  # 8位
                audio_data = audio_data / 128.0 - 1.0
            elif audio.sample_width == 2:  # 16位
                audio_data = audio_data / 32768.0
            elif audio.sample_width == 4:  # 32位
                audio_data = audio_data / 2147483648.0

            self.logger_main.info(f"sounddevice播放: {audio.channels}声道, {audio.frame_rate}Hz, {len(audio_data)}样本")

            # 计算总时长(毫秒)
            total_duration = len(audio)  # pydub的len()返回毫秒

            # 使用sounddevice播放，支持实时停止和暂停
            current_frame = 0
            underflow_count = 0
            last_status_log_ts = 0.0
            status_log_interval = 0.5  # 秒，节流status日志

            def callback(outdata, frames, time, status):
                nonlocal current_frame
                nonlocal underflow_count, last_status_log_ts

                if status:
                    # 节流输出status日志，避免刷屏
                    now_ts = time.inputBufferAdcTime or 0.0
                    if now_ts == 0.0:
                        import time as _t
                        now_ts = _t.time()
                    if now_ts - last_status_log_ts >= status_log_interval:
                        self.logger_main.warning(f"sounddevice状态: {status}")
                        last_status_log_ts = now_ts
                    # 统计 Underflow 次数用于降级判定
                    if 'underflow' in str(status).lower() or 'output underflow' in str(status).lower():
                        underflow_count += 1

                # 检查是否需要停止
                if self._steam_sink_stop:
                    raise sd.CallbackStop()

                # 如果暂停，输出静音
                if self._paused:
                    outdata.fill(0)
                    return

                # 超时保护：检查播放是否超时（排除暂停时间）
                if hasattr(self, '_play_start_time') and hasattr(self, '_play_timeout'):
                    import time as time_module
                    # 计算实际播放时间，排除暂停时间
                    total_elapsed = time_module.time() - self._play_start_time
                    pause_time = getattr(self, '_total_pause_time', 0)
                    actual_play_time = total_elapsed - pause_time

                    if actual_play_time > self._play_timeout:
                        self.logger_main.warning(
                            f"播放超时保护触发: 实际播放时间{actual_play_time:.1f}秒 > {self._play_timeout:.1f}秒 (总时间{total_elapsed:.1f}秒, 暂停时间{pause_time:.1f}秒)")
                        # 设置超时标志，确保结束消息能正确发送
                        self._timeout_triggered = True
                        raise sd.CallbackStop()

                # 检查是否播放完成
                if current_frame >= len(audio_data):
                    raise sd.CallbackStop()

                # 获取当前帧的数据
                end_frame = min(current_frame + frames, len(audio_data))
                if current_frame < len(audio_data):
                    outdata[:end_frame - current_frame] = audio_data[current_frame:end_frame]
                    if end_frame - current_frame < frames:
                        outdata[end_frame - current_frame:] = 0
                    current_frame = end_frame
                else:
                    outdata.fill(0)

            # 预热静音缓冲，减少初始欠载
            warmup_frames = int(audio.frame_rate * 0.05)  # 50ms 预热
            warmup_silence = np.zeros((warmup_frames, audio.channels), dtype=np.float32)

            # 初始参数，优先稳定性（较大块/低延迟折中）
            stream_kwargs_primary = dict(
                samplerate=audio.frame_rate,
                channels=audio.channels,
                dtype=np.float32,
                callback=callback,
                blocksize=1024,
                latency='low'
            )

            # 备选参数，进一步增大块并提高缓冲
            stream_kwargs_backup = dict(
                samplerate=audio.frame_rate,
                channels=audio.channels,
                dtype=np.float32,
                callback=callback,
                blocksize=2048,
                latency='high'
            )

            def _run_stream(stream_kwargs):
                nonlocal current_frame, underflow_count
                current_frame = 0
                underflow_count = 0
                with sd.OutputStream(**stream_kwargs):
                    # 预热
                    try:
                        sd.play(warmup_silence, samplerate=audio.frame_rate, blocking=True)
                    except Exception:
                        pass
                    start_time = time.time()
                    pause_total_time = 0
                    while not self._steam_sink_stop:
                        elapsed_time = (time.time() - start_time - pause_total_time) * 1000
                        current_pos = min(elapsed_time, total_duration)
                        progress_data = {
                            "control_id": control_id,
                            "control_type": "play_progress",
                            "tts_file": tts_file,
                            'progress': int(current_pos)
                        }
                        self._last_progress_ms = int(current_pos)
                        self._progress_queue.put(progress_data)

                        if self._paused:
                            pause_start = time.time()
                            while self._paused and not self._steam_sink_stop:
                                time.sleep(0.01)
                            if self._steam_sink_stop:
                                break
                            pause_total_time += time.time() - pause_start

                        if current_frame >= len(audio_data):
                            break
                        time.sleep(0.01)
                return True

            # 先尝试主配置
            try:
                _run_stream(stream_kwargs_primary)
            except sd.PortAudioError as e:
                self.logger_main.warning(f"sounddevice主配置失败，尝试备选配置: {str(e)}")
                # 检查是否是ALSA相关错误
                if 'alsa' in str(e).lower() or 'pa_linux_alsa' in str(e):
                    self.logger_main.error(f"检测到ALSA错误，sounddevice不可用: {str(e)}")
                    return False
                try:
                    _run_stream(stream_kwargs_backup)
                except Exception as e2:
                    self.logger_main.error(f"sounddevice备选配置仍失败: {str(e2)}")
                    return False
            except Exception as e:
                self.logger_main.error(f"sounddevice播放异常: {str(e)}")
                # 检查是否是ALSA相关错误
                if 'alsa' in str(e).lower() or 'pa_linux_alsa' in str(e):
                    self.logger_main.error(f"检测到ALSA错误，sounddevice不可用: {str(e)}")
                    return False

                # sounddevice失败时的备用逻辑：手动进度跟踪和结束消息发送
                self.logger_main.info("sounddevice失败，使用备用进度跟踪逻辑")
                start_time = time.time()
                pause_total_time = 0

                while not self._steam_sink_stop:
                    # 计算当前播放进度(毫秒)
                    elapsed_time = (time.time() - start_time - pause_total_time) * 1000
                    current_pos = min(elapsed_time, total_duration)

                    # 发送进度信息
                    progress_data = {
                        "control_id": control_id,
                        "control_type": "play_progress",
                        "tts_file": tts_file,
                        'progress': int(current_pos)
                    }
                    self._last_progress_ms = int(current_pos)
                    self._progress_queue.put(progress_data)

                    # 检查暂停状态
                    if self._paused:
                        pause_start = time.time()
                        while self._paused and not self._steam_sink_stop:
                            time.sleep(0.01)  # 更频繁的检查
                        if self._steam_sink_stop:
                            break
                        pause_total_time += time.time() - pause_start

                    # 超时保护：检查播放是否超时
                    if hasattr(self, '_play_start_time') and hasattr(self, '_play_timeout'):
                        elapsed_time = time.time() - self._play_start_time
                        if elapsed_time > self._play_timeout:
                            self.logger_main.warning(
                                f"播放超时保护触发: {elapsed_time:.1f}秒 > {self._play_timeout:.1f}秒")
                            break

                    # 检查是否播放完成
                    if current_frame >= len(audio_data):
                        break

                    time.sleep(0.01)  # 更频繁的检查以提高响应速度

            # 发送播放结束消息 - 修复暂停状态导致的消息丢失问题
            should_send_end_message = True
            final_progress = total_duration

            # 检查是否因超时而结束
            if getattr(self, '_timeout_triggered', False):
                final_progress = int(self._last_progress_ms) if hasattr(self, '_last_progress_ms') else total_duration
                self.logger_main.debug(f"超时保护触发播放结束消息，进度: {final_progress}ms")
            elif hasattr(self, '_play_start_time') and hasattr(self, '_play_timeout'):
                elapsed_time = time.time() - self._play_start_time
                if elapsed_time > self._play_timeout:
                    final_progress = int(self._last_progress_ms) if hasattr(self,
                                                                            '_last_progress_ms') else total_duration
                    self.logger_main.debug(f"超时保护触发播放结束消息，进度: {final_progress}ms")
            elif self._steam_sink_stop:
                # 被主动停止的情况，使用最后记录的进度
                final_progress = int(self._last_progress_ms)
                self.logger_main.debug(f"停止信号触发播放结束消息")
            elif self._paused:
                # 暂停状态结束也要发送结束消息，使用暂停位置的进度
                final_progress = int(self._pause_position) if hasattr(self, '_pause_position') else int(
                    self._last_progress_ms)
                self.logger_main.debug(f"暂停状态结束也发送播放结束消息，进度: {final_progress}ms")
            else:
                # 正常播放完成
                self.logger_main.debug(f"正常播放完成，发送结束消息")

            # 检查是否已经发送过结束消息，防止重复
            if should_send_end_message and not getattr(self, '_end_message_sent', False):
                progress_data = {
                    'control_id': control_id,
                    'control_type': 'play_end',
                    'tts_file': tts_file,
                    'progress': final_progress
                }
                self.logger_main.info(f"发送播放结束消息: {progress_data}")
                self._progress_queue.put(progress_data)
                self._end_message_sent = True  # 标记已发送
            elif getattr(self, '_end_message_sent', False):
                self.logger_main.info(f"跳过重复的播放结束消息发送: {tts_file}")

            return True

        except Exception as e:
            self.logger_main.error(f"sounddevice播放失败: {str(e)}")
            return False

    def _play_with_paplay(self, file_path, control_id, tts_file, audio):
        """使用paplay播放，优先使用USB Audio设备"""
        # PulseAudio设备配置，优先使用USB Audio
        device_options = []

        # 如果检测到了USB Audio设备，优先使用
        if hasattr(self, 'usb_audio_sink') and self.usb_audio_sink:
            device_options.append(
                ['paplay', f'--device={self.usb_audio_sink}', '--verbose', file_path])

        # 添加其他备选配置
        device_options.extend([
            ['paplay', '--device=alsa_output.usb-Generic_USB_Audio-00.analog-stereo',
                '--verbose', file_path],  # 通用USB Audio设备
            ['paplay', '--device=1', '--verbose',
                file_path],  # sink #1 (通常是USB Audio)
            ['paplay', '--verbose', file_path]  # 默认设备
        ])

        for i, cmd in enumerate(device_options):
            try:
                self.logger_main.info(f"尝试paplay配置 {i+1}: {' '.join(cmd)}")
                success = self._play_with_subprocess(
                    cmd, file_path, control_id, tts_file, audio)
                if success:
                    self.logger_main.info(f"paplay配置 {i+1} 播放成功")
                    return True
                else:
                    self.logger_main.warning(f"paplay配置 {i+1} 播放失败，尝试下一个")
            except Exception as e:
                self.logger_main.warning(f"paplay配置 {i+1} 异常: {str(e)}")
                continue

        self.logger_main.error("所有paplay配置都失败了")
        return False

    def _play_with_aplay(self, file_path, control_id, tts_file, audio):
        """使用aplay播放（需要转换为WAV）"""
        try:
            # 确定WAV文件路径
            if file_path.endswith('.wav'):
                wav_path = file_path  # 已经是WAV文件
                temp_file_created = False
            else:
                # 转换MP3为WAV（aplay不支持MP3）
                wav_path = file_path.replace('.mp3', '.wav')
                audio.export(wav_path, format="wav")
                temp_file_created = True

            # 动态检测最优音频设备
            optimal_card = self._detect_optimal_audio_device()

            # 构建设备配置选项，优先使用检测到的最优设备
            device_options = []

            if optimal_card:
                device_options.extend([
                    ['aplay', '-D', f'sysdefault:CARD={optimal_card}', '-v', wav_path],  # 系统默认最优卡
                    ['aplay', '-D', f'plughw:{optimal_card},0', '-v', wav_path],  # 插件层最优卡
                    ['aplay', '-D', f'hw:{optimal_card},0', '-v', wav_path],  # 直接硬件最优卡
                ])

            # 添加固定配置作为备选
            device_options.extend([
                ['aplay', '-D', 'sysdefault:CARD=3', '-v', wav_path],  # 系统默认卡3 (最稳定)
                ['aplay', '-D', 'plughw:3,0', '-v', wav_path],  # USB声卡 card 3 (插件层，支持格式转换)
                ['aplay', '-D', 'hw:3,0', '-v', wav_path],  # USB声卡 card 3 (直接硬件访问)
                ['aplay', '-v', wav_path]  # 系统默认设备（兜底）
            ])

            success = False
            for i, cmd in enumerate(device_options):
                if self._steam_sink_stop:
                    break

                self.logger_main.info(f"尝试aplay配置 {i + 1}: {' '.join(cmd)}")
                try:
                    success = self._play_with_subprocess(
                        cmd, file_path, control_id, tts_file, audio)
                    if success:
                        self.logger_main.info(f"aplay配置 {i + 1} 播放成功")
                        break
                    else:
                        self.logger_main.warning(f"aplay配置 {i + 1} 播放失败，尝试下一个")
                except Exception as e:
                    self.logger_main.warning(f"aplay配置 {i + 1} 异常: {str(e)}")
                    continue

            # 清理临时WAV文件（仅在创建了临时文件时）
            if temp_file_created:
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                except Exception as e:
                    self.logger_main.warning(f"清理临时文件失败: {str(e)}")

            return success
        except Exception as e:
            self.logger_main.error(f'aplay播放失败: {str(e)}')
            return False

    def _test_simpleaudio(self):
        """测试simpleaudio是否真正可用"""
        try:
            import simpleaudio as sa
            # 尝试播放一个极短的静音片段
            play_obj = sa.play_buffer(
                b'\x00\x00\x00\x00',  # 2帧静音
                num_channels=1,
                bytes_per_sample=2,
                sample_rate=44100
            )
            if play_obj is None:
                self.logger_main.warning("simpleaudio测试：play_buffer返回None")
                return False
            
            # 立即停止测试播放
            play_obj.stop()
            self.logger_main.info("simpleaudio测试：播放测试成功")
            return True
        except Exception as e:
            self.logger_main.error(f"simpleaudio测试失败: {str(e)}")
            return False

    def _check_pulseaudio(self):
        """检查PulseAudio可用性"""
        try:
            # 检查paplay命令是否存在
            paplay_path = shutil.which('paplay')
            if not paplay_path:
                self.logger_main.debug("PulseAudio检查：paplay 命令未找到")
                return False

            # 检查pactl命令是否存在
            pactl_path = shutil.which('pactl')
            if not pactl_path:
                self.logger_main.debug("PulseAudio检查：pactl 命令未找到")
                return False

            self.logger_main.debug(
                f"PulseAudio检查：找到 paplay {paplay_path}, pactl {pactl_path}")

            # 检查PulseAudio服务
            result = subprocess.run(['pactl', 'info'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    timeout=3)

            self.logger_main.debug(
                f"PulseAudio检查：pactl info 返回码 {result.returncode}")

            if result.returncode == 0:
                # 检查输出设备
                result = subprocess.run(['pactl', 'list', 'short', 'sinks'],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        timeout=3)

                self.logger_main.debug(
                    f"PulseAudio检查：pactl list sinks 返回码 {result.returncode}")
                if result.stdout:
                    self.logger_main.debug(
                        f"PulseAudio检查：输出设备 {result.stdout.decode('utf-8', errors='ignore')}")

                is_available = result.returncode == 0 and len(
                    result.stdout.strip()) > 0
                self.logger_main.info(
                    f"PulseAudio检查结果：{'可用' if is_available else '不可用'}")
                return is_available
            else:
                if result.stderr:
                    self.logger_main.debug(
                        f"PulseAudio检查：pactl info 错误 {result.stderr.decode('utf-8', errors='ignore')}")
                return False

        except subprocess.TimeoutExpired:
            self.logger_main.warning("PulseAudio检查：执行超时")
            return False
        except Exception as e:
            self.logger_main.warning(f"PulseAudio检查：异常 {str(e)}")
            return False

    def _check_alsa(self):
        """检查ALSA可用性"""
        try:
            # 检查aplay命令是否存在
            aplay_path = shutil.which('aplay')
            if not aplay_path:
                self.logger_main.warning("ALSA检查：aplay 命令未找到")
                return False

            self.logger_main.debug(f"ALSA检查：找到 aplay 路径 {aplay_path}")

            # 执行aplay -l检查音频设备
            result = subprocess.run(['aplay', '-l'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    timeout=3)

            self.logger_main.debug(f"ALSA检查：aplay -l 返回码 {result.returncode}")

            if result.stdout:
                self.logger_main.debug(
                    f"ALSA检查：输出 {result.stdout.decode('utf-8', errors='ignore')}")
            if result.stderr:
                self.logger_main.debug(
                    f"ALSA检查：错误 {result.stderr.decode('utf-8', errors='ignore')}")

            is_available = result.returncode == 0
            self.logger_main.info(
                f"ALSA检查结果：{'可用' if is_available else '不可用'}")
            return is_available

        except subprocess.TimeoutExpired:
            self.logger_main.warning("ALSA检查：aplay -l 执行超时")
            return False
        except Exception as e:
            self.logger_main.warning(f"ALSA检查：异常 {str(e)}")
            return False

    def _check_sox(self):
        """检查SoX可用性"""
        try:
            if not shutil.which('play'):
                return False

            result = subprocess.run(['play', '--version'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    timeout=3)
            return result.returncode == 0
        except:
            return False

    def _detect_usb_audio_sink(self):
        """检测USB Audio设备在PulseAudio中的sink名称"""
        try:
            result = subprocess.run(['pactl', 'list', 'short', 'sinks'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    timeout=3)
            if result.returncode == 0 and result.stdout:
                output = result.stdout.decode('utf-8')
                self.logger_main.debug(f"PulseAudio设备列表:\n{output}")

                # 查找USB Audio相关的sink
                lines = output.strip().split('\n')
                for line in lines:
                    if 'usb' in line.lower() or 'audio' in line.lower():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            sink_name = parts[1]
                            self.logger_main.info(
                                f"找到USB Audio设备: {sink_name}")
                            # 保存为实例变量，供后续使用
                            self.usb_audio_sink = sink_name
                            return sink_name

        except Exception as e:
            self.logger_main.debug(f"检测USB Audio sink失败: {str(e)}")

        return None

    def reload_audio(self):
        """重新加载音频系统"""
        self.close_audio()
        try:
            # simpleaudio不需要显式初始化，直接尝试播放静音片段测试设备
            play_obj = sa.play_buffer(
                b'\x00\x00',  # 静音片段
                num_channels=1,  # 单声道
                bytes_per_sample=2,  # 16位
                sample_rate=44100  # 采样率
            )
            if play_obj is None:
                raise Exception("没有可用的音频输出设备")
            play_obj.stop()  # 立即停止测试播放
        except Exception as e:
            if self.logger_main:
                self.logger_main.error(f"音频系统初始化失败: {str(e)}")
            raise

    def close_audio(self):
        """
        关闭pyaudio.PyAudio()对象
        """
        self.close_steam_source()
        self.close_steam_sink()
        if self.audio_instance is not None:
            self.audio_instance.terminate()
            self.audio_instance = None

    def close_steam_source(self):
        if self.steam_source_obj is not None:
            self.steam_source_obj.stop_stream()
            self.steam_source_obj.close()
            self.steam_source_obj = None

    def close_steam_sink(self):
        if self.steam_sink_obj is not None:
            self.steam_sink_obj.stop_stream()
            self.steam_sink_obj.close()
            self.steam_sink_obj = None

    def run_mp3(self, audio, len_data, file, control_id=None, chunk=1024):
        """非阻塞方式播放MP3 - 使用队列机制"""
        if self.logger_main:
            self.logger_main.info(f"请求播放新音频: {os.path.basename(file)}")

        # 停止当前播放
        self.stop_current_playback()

        # 创建播放任务
        task = {
            'audio': audio,
            'file_path': file,
            'control_id': control_id,
            'chunk': chunk,
            'tts_file': os.path.basename(file)
        }

        # 将任务加入队列
        try:
            self._play_queue.put(task, timeout=5.0)
            if self.logger_main:
                self.logger_main.info(f"播放任务已加入队列: {os.path.basename(file)}")
        except queue.Full:
            if self.logger_main:
                self.logger_main.error("播放队列已满，无法添加新任务")
            raise Exception("播放队列已满")

    def stop_current_playback(self):
        """停止当前播放"""
        if self.logger_main:
            self.logger_main.info("停止当前播放")
        
        # 设置停止标志
        self._steam_sink_stop = True
        
        # 等待一小段时间让播放线程响应
        time.sleep(0.1)
        
        # 清理当前播放资源
        self._force_cleanup_audio_resources()

    def _play_with_priority_strategy(self, audio, file_path, control_id, tts_file):
        """使用优先级策略播放音频"""
        if not self.available_players:
            self.logger_main.error("没有检测到可用的音频播放器")
            return False

        # 重置停止标志，准备开始播放
        self._steam_sink_stop = False
        
        # 记录播放开始信息
        self.logger_main.info(f"开始播放音频: {tts_file}")
        self.logger_main.info(f"音频文件大小: {len(audio.raw_data)} 字节")
        self.logger_main.info(f"音频时长: {len(audio)} 毫秒")
        self.logger_main.info(f"音频格式: {audio.channels}声道, {audio.frame_rate}Hz, {audio.sample_width}字节/样本")

        for player_type, player_cmd in self.available_players:
            if self._steam_sink_stop:
                self.logger_main.info("收到停止信号，终止播放尝试")
                break

            try:
                self.logger_main.info(f"尝试使用 {player_type} ({player_cmd}) 播放")

                if player_type == 'sounddevice':
                    success = self._play_with_sounddevice(
                        audio, control_id, tts_file)
                elif player_type == 'pulseaudio':
                    success = self._play_with_paplay(
                        file_path, control_id, tts_file, audio)
                elif player_type == 'alsa':
                    success = self._play_with_aplay(
                        file_path, control_id, tts_file, audio)
                elif player_type == 'sox':
                    success = self._play_with_sox(
                        file_path, control_id, tts_file, audio)
                elif player_type == 'ffmpeg':
                    success = self._play_with_ffplay(
                        file_path, control_id, tts_file, audio)
                elif player_type == 'simpleaudio':
                    success = self._play_with_simpleaudio(
                        audio, control_id, tts_file)
                else:
                    continue

                if success:
                    self.logger_main.info(f"成功使用 {player_type} 播放音频")
                    return True
                else:
                    self.logger_main.warning(f"{player_type} 播放失败，尝试下一个播放器")

            except Exception as e:
                self.logger_main.error(f"{player_type} 播放异常: {str(e)}")
                continue

        self.logger_main.error("所有播放器都失败了")
        return False

    def _play_with_simpleaudio(self, audio, control_id, tts_file):
        """使用simpleaudio播放"""
        try:
            # 使用simpleaudio播放
            play_obj = sa.play_buffer(
                audio.raw_data,
                num_channels=audio.channels,
                bytes_per_sample=audio.sample_width,
                sample_rate=audio.frame_rate
            )

            # 计算总时长(毫秒)
            total_duration = len(audio)  # pydub的len()返回毫秒

            while play_obj.is_playing():
                if self._steam_sink_stop:
                    play_obj.stop()
                    break

                # 计算当前播放进度(毫秒)
                elapsed_time = (time.time() - self._start_time) * 1000
                current_pos = min(elapsed_time, total_duration)

                progress_data = {
                    "control_id": control_id,
                    "control_type": "play_progress",
                    "tts_file": tts_file,
                    'progress': int(current_pos)
                }
                self._progress_queue.put(progress_data)

                # 检查暂停状态
                if self._paused:
                    play_obj.stop()
                    self._current_position = current_pos
                    while self._paused and not self._steam_sink_stop:
                        time.sleep(0.1)
                    if self._steam_sink_stop:
                        break
                    # 恢复播放
                    bytes_per_frame = audio.channels * audio.sample_width
                    start_byte = int(self._current_position *
                                     audio.frame_rate * bytes_per_frame // 1000)
                    # 确保切片位置对齐到帧边界
                    start_byte = (start_byte // bytes_per_frame) * \
                        bytes_per_frame
                    play_obj = sa.play_buffer(
                        audio.raw_data[start_byte:],
                        num_channels=audio.channels,
                        bytes_per_sample=audio.sample_width,
                        sample_rate=audio.frame_rate
                    )

                time.sleep(0.05)  # 降低CPU使用率

            # 发送播放结束消息
            if not self._paused and not self._steam_sink_stop:
                progress_data = {
                    'control_id': control_id,
                    'control_type': 'play_end',
                    'tts_file': tts_file,
                    'progress': total_duration
                }
                self.logger_main.debug(f"发送播放结束消息:{progress_data}")
                self._progress_queue.put(progress_data)

            return True

        except Exception as e:
            self.logger_main.error(f"simpleaudio播放失败: {str(e)}")
            return False

    def _play_with_sox(self, file_path, control_id, tts_file, audio):
        """使用SoX play命令播放"""
        try:
            cmd = ['play', '-V1', file_path]
            return self._play_with_subprocess(cmd, file_path, control_id, tts_file, audio)
        except Exception as e:
            self.logger_main.error(f'SoX播放失败: {str(e)}')
            return False

    def _play_with_ffplay(self, file_path, control_id, tts_file, audio):
        """使用ffplay播放"""
        try:
            cmd = ['ffplay', '-nodisp', '-autoexit', file_path]
            return self._play_with_subprocess(cmd, file_path, control_id, tts_file, audio)
        except Exception as e:
            self.logger_main.error(f'ffplay播放失败: {str(e)}')
            return False

    def _play_with_subprocess(self, cmd, file_path, control_id, tts_file, audio):
        """通用subprocess播放方法"""
        max_retries = 2
        retry_delay = 0.5
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    self.logger_main.info(f'重试播放 (第{attempt}次): {" ".join(cmd)}')
                    time.sleep(retry_delay)
                else:
                    self.logger_main.info(f'执行命令: {" ".join(cmd)}')

                # 检查文件是否存在
                if not os.path.exists(file_path):
                    self.logger_main.error(f"音频文件不存在: {file_path}")
                    return False

                # 检查文件权限
                if not os.access(file_path, os.R_OK):
                    self.logger_main.error(f"音频文件无读取权限: {file_path}")
                    return False

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid if self.is_ubuntu else None
                )

                # 获取音频时长用于进度计算
                total_duration = len(audio)
                start_time = time.time()
                pause_total_time = 0  # 暂停的总时间

                # 监控播放进度
                while process.poll() is None:
                    if self._steam_sink_stop:
                        # 终止进程
                        try:
                            if self.is_ubuntu:
                                os.killpg(os.getpgid(process.pid), 15)  # SIGTERM
                            else:
                                process.terminate()
                            process.wait(timeout=1)
                        except:
                            try:
                                if self.is_ubuntu:
                                    os.killpg(os.getpgid(process.pid), 9)  # SIGKILL
                                else:
                                    process.kill()
                            except:
                                pass
                        if self.logger_main:
                            self.logger_main.info("subprocess播放进程已被终止")
                        return False

                    # 处理暂停状态
                    if self._paused:
                        pause_start = time.time()
                        # 暂停进程（发送SIGSTOP信号）
                        try:
                            if self.is_ubuntu:
                                os.killpg(os.getpgid(process.pid), 19)  # SIGSTOP
                            if self.logger_main:
                                self.logger_main.info("subprocess播放进程已暂停")
                        except:
                            pass

                        # 等待恢复
                        while self._paused and not self._steam_sink_stop:
                            time.sleep(0.1)

                        # 恢复进程（发送SIGCONT信号）
                        if not self._steam_sink_stop:
                            try:
                                if self.is_ubuntu:
                                    os.killpg(os.getpgid(process.pid), 18)  # SIGCONT
                                if self.logger_main:
                                    self.logger_main.info("subprocess播放进程已恢复")
                            except:
                                pass
                            # 累计暂停时间
                            pause_total_time += time.time() - pause_start

                    # 计算播放进度（减去暂停时间）
                    elapsed_time = (time.time() - start_time -
                                    pause_total_time) * 1000
                    current_pos = min(elapsed_time, total_duration)

                    # 发送进度信息
                    progress_data = {
                        'control_id': control_id,
                        'control_type': 'play_progress',
                        'tts_file': tts_file,
                        'progress': int(current_pos)
                    }
                    self._progress_queue.put(progress_data)

                    time.sleep(0.1)

                # 检查进程退出状态
                exit_code = process.returncode
                if exit_code == 0:
                    # 发送播放完成消息
                    progress_data = {
                        'control_id': control_id,
                        'control_type': 'play_end',
                        'tts_file': tts_file,
                        'progress': total_duration
                    }
                    self.logger_main.debug(f"发送播放结束消息:{progress_data}")
                    self._progress_queue.put(progress_data)
                    return True
                else:
                    stdout, stderr = process.communicate()
                    self.logger_main.error(
                        f'播放进程退出码: {exit_code}, stderr: {stderr.decode()}')
                    
                    # 如果是重试次数未用完，继续重试
                    if attempt < max_retries:
                        self.logger_main.warning(f"播放失败，将在{retry_delay}秒后重试")
                        continue
                    else:
                        return False

            except subprocess.TimeoutExpired:
                self.logger_main.error(f"播放进程超时: {cmd[0]}")
                try:
                    process.kill()
                except:
                    pass
                if attempt < max_retries:
                    continue
                else:
                    return False
                    
            except FileNotFoundError:
                self.logger_main.error(f"播放命令未找到: {cmd[0]}")
                return False
                
            except PermissionError:
                self.logger_main.error(f"播放命令权限不足: {cmd[0]}")
                return False
                
            except Exception as e:
                self.logger_main.error(f'subprocess播放异常: {str(e)}')
                if attempt < max_retries:
                    continue
                else:
                    return False
        
        return False

    def _force_cleanup_audio_resources(self):
        """强制清理所有音频资源"""
        self._steam_sink_stop = True
        
        # 清理音频流
        if self.steam_sink_obj:
            try:
                if hasattr(self.steam_sink_obj, 'is_active') and self.steam_sink_obj.is_active():
                    self.steam_sink_obj.stop_stream()
                self.steam_sink_obj.close()
            except Exception as e:
                self.logger_main.debug(f"清理音频流失败: {str(e)}")
            finally:
                self.steam_sink_obj = None
        
        # 清理音频实例
        if self.audio_instance:
            try:
                self.audio_instance.terminate()
            except Exception as e:
                self.logger_main.debug(f"清理音频实例失败: {str(e)}")
            finally:
                self.audio_instance = None
        
        # 重置状态
        self._steam_sink_status = False
        self._paused = False
        self._pause_position = 0
        self._current_position = 0
        self.cur_tts_file = None

    def _cleanup_on_exit(self):
        """程序退出时的清理工作"""
        self.logger_main.info("开始清理音频资源...")
        
        # 停止播放队列
        try:
            self._play_queue.put(None)  # 发送停止信号
            if self._play_thread and self._play_thread.is_alive():
                self._play_thread.join(timeout=2.0)
        except Exception as e:
            self.logger_main.warning(f"停止播放队列失败: {str(e)}")
        
        # 清理音频资源
        try:
            self._force_cleanup_audio_resources()
        except Exception as e:
            self.logger_main.warning(f"清理音频资源失败: {str(e)}")
        
        # 释放文件锁
        try:
            if self._file_lock and HAS_FCNTL:
                fcntl.flock(self._file_lock.fileno(), fcntl.LOCK_UN)
                self._file_lock.close()
        except Exception as e:
            self.logger_main.warning(f"释放文件锁失败: {str(e)}")
        
        self.logger_main.info("音频资源清理完成")

    def close_mp3(self):
        """立即停止MP3播放并清理资源"""
        if self.logger_main:
            self.logger_main.info("开始清理音频播放资源")

        # 使用统一的资源清理方法
        self._force_cleanup_audio_resources()

        if self.logger_main:
            self.logger_main.info("音频播放资源清理完成")

    def pause_mp3(self):
        """暂停当前MP3播放"""
        if self._play_thread and self._play_thread.is_alive() and not self._paused:
            try:
                self._paused = True
                # 使用time.time()计算的位置替代pyaudio的get_time()
                self._pause_position = int(
                    (time.time() - self._start_time) * 1000)
                if self.logger_main:
                    self.logger_main.info(
                        f"MP3播放已暂停于位置: {self._pause_position}ms")
            except Exception as e:
                self._paused = False
                if self.logger_main:
                    self.logger_main.error(f"暂停播放失败: {str(e)}")

    def resume_mp3(self):
        """恢复MP3播放"""
        if self._paused and self._play_thread and self._play_thread.is_alive():
            max_retries = 3
            retry_delay = 0.2

            for attempt in range(max_retries):
                try:
                    time.sleep(retry_delay)
                    self._paused = False
                    if self.logger_main:
                        self.logger_main.info(f"MP3播放已恢复(第{attempt + 1}次尝试)")
                    return
                except Exception as e:
                    if attempt == max_retries - 1:
                        self._paused = True
                        if self.logger_main:
                            self.logger_main.error(f"恢复播放失败(最终尝试): {str(e)}")
                        raise
                    else:
                        if self.logger_main:
                            self.logger_main.warning(
                                f"恢复播放失败(第{attempt + 1}次尝试), 将重试: {str(e)}")
                        time.sleep(retry_delay * 2)

    @property
    def steam_sink_stop(self):
        return self._steam_sink_stop

    @steam_sink_stop.setter
    def steam_sink_stop(self, status):
        self._steam_sink_stop = status

    @property
    def steam_sink_status(self):
        return self._steam_sink_status

    @steam_sink_status.setter
    def steam_sink_status(self, status):
        self._steam_sink_status = status

    @property
    def progress_queue(self):
        return self._progress_queue

    @property
    def paused(self):
        return self._paused

    @property
    def is_playing(self):
        """检查是否正在播放"""
        return self._is_playing

    @property
    def queue_size(self):
        """获取播放队列大小"""
        return self._play_queue.qsize()

    def clear_queue(self):
        """清空播放队列"""
        try:
            while not self._play_queue.empty():
                try:
                    self._play_queue.get_nowait()
                    self._play_queue.task_done()
                except queue.Empty:
                    break
            if self.logger_main:
                self.logger_main.info("播放队列已清空")
        except Exception as e:
            if self.logger_main:
                self.logger_main.error(f"清空播放队列失败: {str(e)}")

    def wait_for_queue_empty(self, timeout=10.0):
        """等待播放队列为空"""
        try:
            self._play_queue.join()
            return True
        except Exception as e:
            if self.logger_main:
                self.logger_main.error(f"等待队列为空失败: {str(e)}")
            return False
