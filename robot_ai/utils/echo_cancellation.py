# -*- coding: utf-8 -*-
"""
自我声音检测和回声消除模块
防止系统在播放TTS时误触发语音识别
"""
import threading
import time
import numpy as np
from typing import Optional, Callable, Dict, List, Tuple
from utils.logger import logger
import hashlib
import json
from collections import deque
from dataclasses import dataclass
import struct
from config.config.echo_cancellation_conf import EchoCancellationConf


@dataclass
class AudioFingerprint:
    """音频指纹数据结构"""
    fingerprint: str
    timestamp: float
    duration: float
    energy: float
    spectral_features: List[float]


class EchoCancellationEngine:
    """回声消除引擎"""

    def __init__(self):
        self.is_enabled = EchoCancellationConf.ENABLE_ECHO_CANCELLATION
        self.is_playing_tts = False
        self._current_playing_status = False  # 添加这个属性初始化
        self.tts_audio_fingerprints: deque = deque(
            maxlen=EchoCancellationConf.MAX_TTS_FINGERPRINTS)
        self.recording_buffer: deque = deque(
            maxlen=EchoCancellationConf.MAX_RECORDING_BUFFER)

        # 配置参数
        self.sample_rate = EchoCancellationConf.SAMPLE_RATE
        self.frame_size = EchoCancellationConf.FRAME_SIZE
        self.overlap_ratio = EchoCancellationConf.OVERLAP_RATIO
        self.energy_threshold = EchoCancellationConf.ENERGY_THRESHOLD
        self.correlation_threshold = EchoCancellationConf.CORRELATION_THRESHOLD
        self.time_window = EchoCancellationConf.TIME_WINDOW

        # 状态管理
        self._lock = threading.RLock()
        self.last_tts_end_time = 0
        self.tts_fade_out_duration = EchoCancellationConf.TTS_FADE_OUT_DURATION

        # 频谱分析参数
        self.fft_size = EchoCancellationConf.FFT_SIZE
        self.mel_filters = EchoCancellationConf.MEL_FILTERS

        # 用户语音检测配置
        self.voice_detection_config = EchoCancellationConf.get_voice_detection_config()

        # TTS过滤配置
        self.tts_filtering_config = EchoCancellationConf.TTS_FILTERING.copy()

        # 统计信息
        self.stats = {
            'total_processed': 0,
            'echo_detected': 0,
            'false_positives': 0,
            'processing_time_avg': 0.0,
            'user_interrupts_detected': 0
        }

        logger.info("🔇 回声消除引擎已初始化")

        # 验证配置
        config_errors = EchoCancellationConf.validate_config()
        if config_errors:
            logger.warning(f"⚠️ 配置验证发现问题: {config_errors}")
        else:
            logger.info("✅ 回声消除配置验证通过")

    def set_tts_playing_status(self, is_playing: bool, audio_data: Optional[bytes] = None):
        """设置TTS播放状态并记录音频指纹"""
        with self._lock:
            # 避免重复设置相同状态
            if hasattr(self, '_current_playing_status') and self._current_playing_status == is_playing:
                return

            self._current_playing_status = is_playing
            self.is_playing_tts = is_playing
            current_time = time.time()

            if is_playing:
                # 记录TTS开始时间
                self._tts_start_time = current_time

                if audio_data:
                    # 生成TTS音频指纹
                    fingerprint = self._generate_audio_fingerprint(
                        audio_data, current_time)
                    if fingerprint:
                        self.tts_audio_fingerprints.append(fingerprint)
                        logger.debug(
                            f"🎵 记录TTS音频指纹: {fingerprint.fingerprint[:16]}...")
            else:
                self.last_tts_end_time = current_time
                # logger.debug("🔇 TTS播放结束，开始淡出期")

    def is_echo_audio(self, audio_data: bytes) -> bool:
        """检测音频是否为回声（自我声音）"""
        if not self.is_enabled or not audio_data:
            return False

        start_time = time.time()

        try:
            with self._lock:
                current_time = time.time()

                # 如果正在播放TTS，采用更严格的过滤策略
                if self.is_playing_tts:
                    # 检查TTS播放是否刚刚开始，给音频指纹建立一些时间
                    tts_start_time = getattr(self, '_tts_start_time', 0)
                    if current_time - tts_start_time < 1.2:  # TTS开始1.2秒内，延长过滤时间
                        # 直接认为是回声，给系统时间建立指纹，防止误触发打断
                        self.stats['echo_detected'] += 1
                        # logger.debug("🚨 TTS刚开始播放，预防性过滤音频")
                        return True

                    # 生成当前音频的指纹进行分析
                    current_fingerprint = self._generate_audio_fingerprint(
                        audio_data, current_time)
                    if not current_fingerprint:
                        # 无法生成指纹时默认认为是回声
                        self.stats['echo_detected'] += 1
                        # logger.debug("🚨 无法生成音频指纹，默认过滤")
                        return True

                    # TTS播放期间，采用更严格的过滤策略
                    # 只有非常明显的用户语音才允许通过
                    if self._is_very_strong_user_voice(current_fingerprint):
                        # 进一步检查与TTS的差异，使用更严格的标准
                        if self._has_extreme_difference_from_tts(current_fingerprint):
                            # logger.debug("🎤 检测到非常强烈的用户语音特征且与TTS有极大差异，允许通过")
                            return False
                        else:
                            # 即使能量很强，但与TTS差异不够大，仍然过滤
                            self.stats['echo_detected'] += 1
                            logger.debug("🚨 强用户语音但与TTS差异不够，仍然过滤")
                            return True

                    # 其他情况全部过滤，防止回声
                    self.stats['echo_detected'] += 1
                    # logger.debug("🚨 TTS播放期间严格过滤音频，防止回声")
                    return True

                # 检查是否在TTS结束后的淡出期内
                if current_time - self.last_tts_end_time < self.tts_fade_out_duration:
                    # 在TTS淡出期内，采用更宽松的过滤策略
                    # 生成当前音频的指纹进行分析
                    current_fingerprint = self._generate_audio_fingerprint(
                        audio_data, current_time)
                    if not current_fingerprint:
                        # 无法生成指纹时默认过滤
                        self.stats['echo_detected'] += 1
                        # logger.debug("🚨 TTS淡出期内无法生成音频指纹，默认过滤")
                        return True

                    # 在淡出期内，允许明显的用户语音通过
                    if self._has_obvious_voice_characteristics(current_fingerprint):
                        # 检查与TTS的差异，但使用更宽松的标准
                        if self._has_basic_difference_from_tts(current_fingerprint):
                            # logger.debug("🎤 TTS淡出期内检测到明显用户语音，允许通过")
                            return False

                    # 其他情况仍然过滤，但记录更详细的信息
                    self.stats['echo_detected'] += 1
                    logger.debug(
                        f"🚨 TTS淡出期内过滤音频（距离TTS结束 {current_time - self.last_tts_end_time:.1f}s）")
                    return True

                # 生成当前音频的指纹
                current_fingerprint = self._generate_audio_fingerprint(
                    audio_data, current_time)
                if not current_fingerprint:
                    return False

                # 与最近的TTS指纹进行比较
                is_echo = self._compare_with_tts_fingerprints(
                    current_fingerprint)

                if is_echo:
                    self.stats['echo_detected'] += 1

                # 更新统计信息
                self.stats['total_processed'] += 1

                processing_time = time.time() - start_time
                self.stats['processing_time_avg'] = (
                    self.stats['processing_time_avg'] * (self.stats['total_processed'] - 1) +
                    processing_time
                ) / self.stats['total_processed']

                return is_echo

        except Exception as e:
            logger.error(f"❌ 回声检测失败: {e}")
            # 出错时默认不认为是回声，避免影响正常功能
            return False

    def _generate_audio_fingerprint(self, audio_data: bytes, timestamp: float) -> Optional[AudioFingerprint]:
        """生成音频指纹"""
        try:
            # 转换为numpy数组
            samples = np.frombuffer(
                audio_data, dtype=np.int16).astype(np.float32)
            if len(samples) == 0:
                return None

            # 计算能量
            energy = float(np.mean(samples ** 2))
            if energy < self.energy_threshold:
                return None

            # 计算频谱特征
            spectral_features = self._extract_spectral_features(samples)

            # 生成更详细的指纹哈希 - 包含更多特征
            feature_str = f"{energy:.2f}_{len(samples)}_{np.mean(spectral_features):.4f}_{np.std(spectral_features):.4f}"
            fingerprint = hashlib.md5(feature_str.encode()).hexdigest()

            duration = len(samples) / self.sample_rate

            # 记录更详细的调试信息
            if EchoCancellationConf.should_log_audio_fingerprints():
                logger.debug(
                    f"🎵 生成音频指纹: 能量={energy:.1f}, 时长={duration:.3f}s, 特征均值={np.mean(spectral_features):.3f}")

            return AudioFingerprint(
                fingerprint=fingerprint,
                timestamp=timestamp,
                duration=duration,
                energy=energy,
                spectral_features=spectral_features
            )

        except Exception as e:
            logger.error(f"❌ 生成音频指纹失败: {e}")
            return None

    def _extract_spectral_features(self, samples: np.ndarray) -> List[float]:
        """提取频谱特征"""
        try:
            # 确保样本长度足够进行FFT
            if len(samples) < self.fft_size:
                # 零填充
                padded_samples = np.zeros(self.fft_size)
                padded_samples[:len(samples)] = samples
                samples = padded_samples

            # 应用窗函数
            windowed = samples[:self.fft_size] * np.hanning(self.fft_size)

            # FFT变换
            fft_result = np.fft.fft(windowed)
            magnitude_spectrum = np.abs(fft_result[:self.fft_size//2])

            # 计算mel频率特征
            mel_features = self._compute_mel_features(magnitude_spectrum)

            return mel_features.tolist()

        except Exception as e:
            logger.error(f"❌ 提取频谱特征失败: {e}")
            return [0.0] * self.mel_filters

    def _compute_mel_features(self, magnitude_spectrum: np.ndarray) -> np.ndarray:
        """计算Mel频率特征"""
        try:
            # 简化的Mel滤波器组
            mel_filters = np.linspace(
                0, len(magnitude_spectrum), self.mel_filters + 2)
            mel_features = np.zeros(self.mel_filters)

            for i in range(self.mel_filters):
                start_idx = int(mel_filters[i])
                end_idx = int(mel_filters[i + 2])
                if end_idx > start_idx:
                    mel_features[i] = np.mean(
                        magnitude_spectrum[start_idx:end_idx])

            # 对数变换
            mel_features = np.log(mel_features + 1e-10)

            return mel_features

        except Exception as e:
            logger.error(f"❌ 计算Mel特征失败: {e}")
            return np.zeros(self.mel_filters)

    def _compare_with_tts_fingerprints(self, current_fingerprint: AudioFingerprint) -> bool:
        """与TTS指纹进行比较"""
        try:
            current_time = current_fingerprint.timestamp

            for tts_fingerprint in self.tts_audio_fingerprints:
                # 检查时间窗口
                time_diff = current_time - tts_fingerprint.timestamp
                if time_diff > self.time_window:
                    continue

                # 比较指纹哈希
                if current_fingerprint.fingerprint == tts_fingerprint.fingerprint:
                    return True

                # 比较能量和频谱特征
                if self._is_similar_audio(current_fingerprint, tts_fingerprint):
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ 指纹比较失败: {e}")
            return False

    def _is_similar_audio(self, fp1: AudioFingerprint, fp2: AudioFingerprint) -> bool:
        """判断两个音频指纹是否相似"""
        try:
            # 能量相似性检查
            energy_ratio = min(fp1.energy, fp2.energy) / \
                max(fp1.energy, fp2.energy)
            if energy_ratio < 0.5:
                return False

            # 频谱特征相似性检查
            if len(fp1.spectral_features) != len(fp2.spectral_features):
                return False

            # 计算余弦相似度
            features1 = np.array(fp1.spectral_features)
            features2 = np.array(fp2.spectral_features)

            norm1 = np.linalg.norm(features1)
            norm2 = np.linalg.norm(features2)

            if norm1 == 0 or norm2 == 0:
                return False

            cosine_similarity = np.dot(features1, features2) / (norm1 * norm2)

            return cosine_similarity > self.correlation_threshold

        except Exception as e:
            logger.error(f"❌ 音频相似性计算失败: {e}")
            return False

    def _is_likely_user_voice(self, fingerprint: AudioFingerprint) -> bool:
        """判断是否可能是用户语音（用于打断检测）"""
        try:
            # 1. 能量阈值检查 - 用户语音通常有足够的能量
            user_voice_threshold = self.energy_threshold * \
                self.voice_detection_config['energy_multiplier']
            if fingerprint.energy < user_voice_threshold:
                return False

            # 2. 频谱特征分析 - 人声有特定的频谱特征
            features = np.array(fingerprint.spectral_features)

            # 检查频谱分布是否符合人声特征
            # 人声通常在中低频有较强的能量
            if len(features) >= 8:
                low_freq_energy = np.mean(features[:4])    # 低频部分
                mid_freq_energy = np.mean(features[4:8])   # 中频部分
                high_freq_energy = np.mean(features[8:]) if len(
                    features) > 8 else 0  # 高频部分

                # 人声特征：中低频能量较强，高频相对较弱
                low_freq_weight = self.voice_detection_config['low_freq_weight']
                if mid_freq_energy > low_freq_energy * low_freq_weight and mid_freq_energy > high_freq_energy:
                    # 3. 与最近TTS音频的差异检查
                    if self._has_significant_difference_from_tts(fingerprint):
                        self.stats['user_interrupts_detected'] += 1
                        return True

            return False

        except Exception as e:
            logger.error(f"❌ 用户语音判断失败: {e}")
            return False

    def _has_significant_difference_from_tts(self, fingerprint: AudioFingerprint) -> bool:
        """检查与TTS音频是否有显著差异"""
        try:
            if not self.tts_audio_fingerprints:
                return True  # 没有TTS参考，认为是用户语音

            current_time = fingerprint.timestamp
            tts_reference_window = EchoCancellationConf.TTS_REFERENCE_WINDOW

            # 找到最近的TTS指纹进行比较
            recent_tts_fingerprints = [
                fp for fp in self.tts_audio_fingerprints
                if current_time - fp.timestamp < tts_reference_window
            ]

            if not recent_tts_fingerprints:
                return True  # 没有最近的TTS参考

            # 与最近的TTS指纹比较
            check_count = self.voice_detection_config['recent_tts_check_count']
            energy_diff_threshold = self.voice_detection_config['energy_diff_threshold']
            spectral_diff_threshold = self.voice_detection_config['spectral_diff_threshold']

            for tts_fp in recent_tts_fingerprints[-check_count:]:
                # 能量差异检查
                energy_diff = abs(fingerprint.energy - tts_fp.energy) / \
                    max(fingerprint.energy, tts_fp.energy)
                if energy_diff > energy_diff_threshold:
                    continue

                # 频谱特征差异检查
                if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                    features1 = np.array(fingerprint.spectral_features)
                    features2 = np.array(tts_fp.spectral_features)

                    # 计算频谱差异
                    spectral_diff = np.mean(np.abs(features1 - features2))
                    if spectral_diff < spectral_diff_threshold:
                        return False  # 频谱过于相似，可能是回声

            return True  # 与TTS有显著差异，可能是用户语音

        except Exception as e:
            logger.error(f"❌ TTS差异检查失败: {e}")
            return True  # 出错时倾向于认为是用户语音

    def _update_processing_time(self, processing_time: float):
        """更新处理时间统计"""
        if self.stats['total_processed'] > 0:
            alpha = 0.1  # 平滑因子
            self.stats['processing_time_avg'] = (
                alpha * processing_time +
                (1 - alpha) * self.stats['processing_time_avg']
            )
        else:
            self.stats['processing_time_avg'] = processing_time

    def cleanup_old_fingerprints(self):
        """清理过期的指纹"""
        try:
            with self._lock:
                current_time = time.time()

                # 清理过期的TTS指纹
                while (self.tts_audio_fingerprints and
                       current_time - self.tts_audio_fingerprints[0].timestamp > self.time_window):
                    self.tts_audio_fingerprints.popleft()

        except Exception as e:
            logger.error(f"❌ 清理指纹失败: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            total = self.stats['total_processed']
            return {
                'total_processed': total,
                'echo_detected': self.stats['echo_detected'],
                'user_interrupts_detected': self.stats['user_interrupts_detected'],
                'echo_detection_rate': self.stats['echo_detected'] / max(total, 1),
                'interrupt_success_rate': self.stats['user_interrupts_detected'] / max(total, 1),
                'processing_time_avg_ms': self.stats['processing_time_avg'] * 1000,
                'fingerprints_stored': len(self.tts_audio_fingerprints),
                'config': {
                    'is_enabled': self.is_enabled,
                    'interrupt_during_playback': EchoCancellationConf.ENABLE_INTERRUPT_DURING_PLAYBACK,
                    'energy_threshold': self.energy_threshold,
                    'user_voice_threshold': self.energy_threshold * self.voice_detection_config['energy_multiplier']
                }
            }

    def enable(self):
        """启用回声消除"""
        self.is_enabled = True
        logger.info("✅ 回声消除已启用")

    def disable(self):
        """禁用回声消除"""
        self.is_enabled = False
        logger.info("❌ 回声消除已禁用")

    def _is_tts_variant_audio(self, fingerprint: AudioFingerprint) -> bool:
        """检测是否为TTS音频的变种（经过扬声器-麦克风传输后的音频）"""
        try:
            if not self.tts_audio_fingerprints:
                return False

            current_time = fingerprint.timestamp
            detection_window = self.tts_filtering_config['variant_detection_window']

            # 检查最近的TTS指纹
            recent_tts_fingerprints = [
                fp for fp in self.tts_audio_fingerprints
                if current_time - fp.timestamp < detection_window
            ]

            if not recent_tts_fingerprints:
                return False

            energy_range = self.tts_filtering_config['energy_attenuation_range']
            similarity_threshold = self.tts_filtering_config['variant_similarity_threshold']
            correlation_threshold = self.tts_filtering_config['frequency_correlation_threshold']

            # 检查所有最近的TTS指纹，而不仅仅是最后几个
            for tts_fp in recent_tts_fingerprints:
                # 1. 时间相关性检查 - 播放开始后短时间内的音频很可能是回声
                time_diff = current_time - tts_fp.timestamp
                if time_diff < 1.0:  # 1秒内

                    # 2. 能量衰减检查 - 扬声器播放的音频通过麦克风录制会有能量衰减
                    if tts_fp.energy > 0:  # 避免除零
                        energy_ratio = fingerprint.energy / tts_fp.energy
                        if energy_range[0] <= energy_ratio <= energy_range[1]:

                            # 3. 频谱形状相似性检查
                            if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                                features1 = np.array(
                                    fingerprint.spectral_features)
                                features2 = np.array(tts_fp.spectral_features)

                                # 归一化频谱特征以消除能量差异的影响
                                if np.linalg.norm(features1) > 0 and np.linalg.norm(features2) > 0:
                                    features1_norm = features1 / \
                                        np.linalg.norm(features1)
                                    features2_norm = features2 / \
                                        np.linalg.norm(features2)

                                    # 计算归一化后的相似度
                                    similarity = np.dot(
                                        features1_norm, features2_norm)

                                    # 如果归一化后的相似度高，很可能是TTS音频的变种
                                    if similarity > similarity_threshold:
                                        if EchoCancellationConf.should_log_detection_details():
                                            logger.debug(
                                                f"🚨 TTS变种检测: 时间差={time_diff:.3f}s, 能量比={energy_ratio:.3f}, 相似度={similarity:.3f}")
                                        return True

                # 4. 频率分布相关性检查
                if self._has_similar_frequency_distribution(fingerprint, tts_fp, correlation_threshold):
                    if EchoCancellationConf.should_log_detection_details():
                        logger.debug(f"🚨 TTS变种检测: 频率分布相似，时间差={time_diff:.3f}s")
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ TTS变种检测失败: {e}")
            return False

    def _has_similar_frequency_distribution(self, fp1: AudioFingerprint, fp2: AudioFingerprint, threshold: float = 0.5) -> bool:
        """检查两个音频指纹是否有相似的频率分布"""
        try:
            if len(fp1.spectral_features) != len(fp2.spectral_features):
                return False

            features1 = np.array(fp1.spectral_features)
            features2 = np.array(fp2.spectral_features)

            # 计算频率分布的相关系数
            if len(features1) > 1:
                correlation = np.corrcoef(features1, features2)[0, 1]
                return not np.isnan(correlation) and correlation > threshold

            return False

        except Exception as e:
            logger.error(f"❌ 频率分布比较失败: {e}")
            return False

    def _is_definitely_user_voice(self, fingerprint: AudioFingerprint) -> bool:
        """严格判断是否为确定的用户语音（用于播放中的打断检测）"""
        try:
            # 1. 更高的能量阈值 - 用户打断时通常会更大声
            energy_multiplier = self.tts_filtering_config['definite_voice_energy_multiplier']
            high_energy_threshold = self.energy_threshold * \
                self.voice_detection_config['energy_multiplier'] * \
                energy_multiplier
            if fingerprint.energy < high_energy_threshold:
                return False

            # 2. 严格的频谱特征分析
            features = np.array(fingerprint.spectral_features)

            if len(features) >= 8:
                low_freq_energy = np.mean(features[:4])    # 低频部分
                mid_freq_energy = np.mean(features[4:8])   # 中频部分
                high_freq_energy = np.mean(features[8:]) if len(
                    features) > 8 else 0  # 高频部分

                # 人声特征检查 - 更严格的标准
                # 中频能量应该明显高于低频和高频
                if not (mid_freq_energy > low_freq_energy * 0.8 and
                        mid_freq_energy > high_freq_energy * 1.2):
                    return False

                # 3. 检查频谱的动态范围 - 人声通常有较大的动态范围
                min_spectral_range = self.tts_filtering_config['min_spectral_range']
                spectral_range = np.max(features) - np.min(features)
                if spectral_range < min_spectral_range:
                    return False

            # 4. 与所有TTS音频的差异检查 - 必须与所有TTS音频都有显著差异
            if not self._has_significant_difference_from_all_tts(fingerprint):
                return False

            # 5. 检查音频的复杂度 - 人声通常比TTS更复杂
            if not self._has_sufficient_complexity(fingerprint):
                return False

            # 所有检查都通过，认为是确定的用户语音
            self.stats['user_interrupts_detected'] += 1
            return True

        except Exception as e:
            logger.error(f"❌ 确定用户语音判断失败: {e}")
            return False

    def _has_significant_difference_from_all_tts(self, fingerprint: AudioFingerprint) -> bool:
        """检查与所有TTS音频是否都有显著差异"""
        try:
            if not self.tts_audio_fingerprints:
                return True

            current_time = fingerprint.timestamp
            max_similarity = self.tts_filtering_config['max_similarity_with_tts']

            # 检查所有最近的TTS指纹
            recent_tts_fingerprints = [
                fp for fp in self.tts_audio_fingerprints
                if current_time - fp.timestamp < 3.0  # 3秒内的所有TTS
            ]

            if not recent_tts_fingerprints:
                return True

            # 必须与所有TTS音频都有显著差异
            for tts_fp in recent_tts_fingerprints:
                # 能量差异检查 - 更严格
                energy_ratio = min(fingerprint.energy, tts_fp.energy) / \
                    max(fingerprint.energy, tts_fp.energy)
                if energy_ratio > 0.7:  # 能量过于相似
                    return False

                # 频谱相似度检查 - 更严格
                if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                    features1 = np.array(fingerprint.spectral_features)
                    features2 = np.array(tts_fp.spectral_features)

                    if np.linalg.norm(features1) > 0 and np.linalg.norm(features2) > 0:
                        # 归一化比较
                        features1_norm = features1 / np.linalg.norm(features1)
                        features2_norm = features2 / np.linalg.norm(features2)
                        similarity = np.dot(features1_norm, features2_norm)

                        if similarity > max_similarity:  # 相似度过高
                            return False

            return True

        except Exception as e:
            logger.error(f"❌ 全TTS差异检查失败: {e}")
            return False

    def _has_sufficient_complexity(self, fingerprint: AudioFingerprint) -> bool:
        """检查音频是否有足够的复杂度（人声特征）"""
        try:
            features = np.array(fingerprint.spectral_features)
            min_variation = self.tts_filtering_config['min_spectral_variation']

            # 1. 频谱变化检查 - 人声通常有更多的频谱变化
            if len(features) > 1:
                spectral_variation = np.std(features)
                if spectral_variation < min_variation:
                    return False

            # 2. 频谱分布检查 - 人声应该有特定的频率分布
            if len(features) >= 6:
                # 检查是否有明显的共振峰特征
                # 人声通常在某些频段有能量集中
                max_energy_idx = np.argmax(features)
                if max_energy_idx < 2 or max_energy_idx > len(features) - 2:
                    # 能量峰值在边缘，可能不是人声
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ 复杂度检查失败: {e}")
            return False

    def _is_likely_user_voice_relaxed(self, fingerprint: AudioFingerprint) -> bool:
        """宽松判断是否为用户语音（用于非严格模式的打断检测）"""
        try:
            # 1. 极严格的能量阈值 - 避免嘈杂环境误判
            user_voice_threshold = self.energy_threshold * 5.0  # 大幅提高阈值
            if fingerprint.energy < user_voice_threshold:
                return False

            # 2. 如果音频能量足够，需要极严格的检查
            moderate_energy_threshold = self.energy_threshold * 20.0  # 极大幅提高阈值
            if fingerprint.energy > moderate_energy_threshold:
                # 能量足够时，需要通过更严格的差异检查
                if self._has_strict_difference_from_tts(fingerprint):
                    logger.debug(
                        f"🎤 高能量({fingerprint.energy:.1f})，通过严格差异检查，认为是用户语音")
                    return True
                else:
                    logger.debug(
                        f"🚫 高能量({fingerprint.energy:.1f})，但未通过严格差异检查，可能是噪音")
                    return False

            # 3. 基本的频谱特征检查（更宽松）
            features = np.array(fingerprint.spectral_features)

            if len(features) >= 4:  # 降低要求
                # 检查是否有人声的基本特征
                if len(features) >= 6:
                    mid_freq_energy = np.mean(features[2:5])  # 中频部分
                    total_energy = np.mean(features)

                    # 中频能量占比检查（更宽松）
                    if mid_freq_energy > total_energy * 0.3:  # 从0.5降低到0.3
                        # 简单的与TTS差异检查
                        if self._has_basic_difference_from_tts(fingerprint):
                            return True

            # 4. 如果音频足够大声，需要极严格的检查
            high_energy_threshold = self.energy_threshold * 50.0  # 提高到50.0，极严格
            if fingerprint.energy > high_energy_threshold:
                # 即使能量很高，也要检查与TTS的差异，并且需要更严格的条件
                if self._has_strict_difference_from_tts(fingerprint):
                    logger.debug(
                        f"🎤 极高能量({fingerprint.energy:.1f})且通过严格差异检查，认为是用户语音")
                    return True
                else:
                    logger.debug(
                        f"🚫 极高能量({fingerprint.energy:.1f})，但未通过严格差异检查，可能是强噪音")
                    return False

            # 5. 时间窗口检查 - 距离TTS较远时更容易认为是用户语音
            if self.tts_audio_fingerprints:
                last_tts_time = max(
                    fp.timestamp for fp in self.tts_audio_fingerprints)
                time_since_last_tts = fingerprint.timestamp - last_tts_time
                if time_since_last_tts > 1.5:  # 从1.0提高到1.5秒
                    logger.debug(
                        f"🎤 距离最后TTS较远({time_since_last_tts:.1f}s)，认为是用户语音")
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ 宽松用户语音判断失败: {e}")
            # 出错时倾向于认为是用户语音，允许打断
            return True

    def _has_basic_difference_from_tts(self, fingerprint: AudioFingerprint) -> bool:
        """基本的与TTS差异检查（更宽松）"""
        try:
            if not self.tts_audio_fingerprints:
                return True  # 没有TTS参考，认为是用户语音

            current_time = fingerprint.timestamp

            # 检查是否在TTS播放期间
            if self.is_playing_tts:
                # TTS播放期间采用更严格的标准
                # 只检查最近0.3秒内的TTS，缩短时间窗口
                recent_tts_fingerprints = [
                    fp for fp in self.tts_audio_fingerprints
                    if current_time - fp.timestamp < 0.3
                ]

                if not recent_tts_fingerprints:
                    return True  # 没有最近的TTS参考

                # 与最近的TTS指纹比较（TTS播放期间更严格的标准）
                for tts_fp in recent_tts_fingerprints[-1:]:  # 只检查最近1个
                    # 能量差异检查（TTS播放期间更严格）
                    energy_ratio = min(fingerprint.energy, tts_fp.energy) / \
                        max(fingerprint.energy, tts_fp.energy)
                    if energy_ratio > 0.6:  # TTS播放期间需要更大的能量差异
                        logger.debug(
                            f"🚨 TTS播放期间能量过于相似({energy_ratio:.2f})，可能是回声")
                        return False

                    # 频谱特征差异检查（TTS播放期间更严格）
                    if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                        features1 = np.array(fingerprint.spectral_features)
                        features2 = np.array(tts_fp.spectral_features)

                        # 计算简单的欧氏距离
                        distance = np.linalg.norm(features1 - features2)
                        if distance < 0.8:  # TTS播放期间需要更大的频谱差异
                            logger.debug(
                                f"🚨 TTS播放期间频谱距离过小({distance:.2f})，可能是回声")
                            return False

                        # 检查相关性
                        if np.linalg.norm(features1) > 0 and np.linalg.norm(features2) > 0:
                            features1_norm = features1 / \
                                np.linalg.norm(features1)
                            features2_norm = features2 / \
                                np.linalg.norm(features2)
                            correlation = np.dot(
                                features1_norm, features2_norm)
                            if correlation > 0.5:  # TTS播放期间相关性要求更严格
                                logger.debug(
                                    f"🚨 TTS播放期间频谱相关性过高({correlation:.2f})，可能是回声")
                                return False

                return True  # 通过TTS播放期间的严格检查
            else:
                # 非TTS播放期间采用原来的宽松标准
                # 只检查最近0.5秒内的TTS，缩短时间窗口
                recent_tts_fingerprints = [
                    fp for fp in self.tts_audio_fingerprints
                    if current_time - fp.timestamp < 0.5
                ]

                if not recent_tts_fingerprints:
                    return True  # 没有最近的TTS参考

                # 与最近的TTS指纹比较（非常宽松的标准）
                for tts_fp in recent_tts_fingerprints[-1:]:  # 只检查最近1个
                    # 能量差异检查（更宽松）
                    energy_ratio = min(fingerprint.energy, tts_fp.energy) / \
                        max(fingerprint.energy, tts_fp.energy)
                    if energy_ratio > 0.8:  # 从0.5提高到0.8，需要更相似才认为可疑

                        # 频谱特征差异检查（更宽松）
                        if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                            features1 = np.array(fingerprint.spectral_features)
                            features2 = np.array(tts_fp.spectral_features)

                            # 计算简单的欧氏距离
                            distance = np.linalg.norm(features1 - features2)
                            if distance < 0.5:  # 从1.0降低到0.5，需要更相似才认为是回声
                                logger.debug(f"🚨 频谱距离过小({distance:.2f})，可能是回声")
                                return False

                return True  # 通过基本检查，认为是用户语音

        except Exception as e:
            logger.error(f"❌ 基本TTS差异检查失败: {e}")
            return True  # 出错时倾向于认为是用户语音

    def _has_strict_difference_from_tts(self, fingerprint: AudioFingerprint) -> bool:
        """严格的与TTS差异检查（用于高能量音频）"""
        try:
            if not self.tts_audio_fingerprints:
                return True  # 没有TTS参考，认为是用户语音

            current_time = fingerprint.timestamp

            # 检查最近1秒内的TTS，时间窗口更严格
            recent_tts_fingerprints = [
                fp for fp in self.tts_audio_fingerprints
                if current_time - fp.timestamp < 1.0
            ]

            if not recent_tts_fingerprints:
                return True  # 没有最近的TTS参考

            # 与最近的TTS指纹比较（非常严格的标准）
            for tts_fp in recent_tts_fingerprints:
                # 1. 时间相关性检查 - 如果在TTS播放后很短时间内出现，更可能是回声
                time_diff = current_time - tts_fp.timestamp
                if time_diff < 0.3:  # 300ms内
                    logger.debug(f"🚫 时间过近({time_diff:.2f}s)，可能是回声")
                    return False

                # 2. 能量差异检查（非常严格）
                energy_ratio = min(fingerprint.energy, tts_fp.energy) / \
                    max(fingerprint.energy, tts_fp.energy)
                if energy_ratio > 0.9:  # 需要能量差异很大才认为不是回声
                    logger.debug(f"🚫 能量过于相似({energy_ratio:.2f})，可能是回声")
                    return False

                # 3. 频谱特征差异检查（非常严格）
                if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                    features1 = np.array(fingerprint.spectral_features)
                    features2 = np.array(tts_fp.spectral_features)

                    # 计算欧氏距离和相关性
                    distance = np.linalg.norm(features1 - features2)
                    if distance < 0.3:  # 需要频谱差异很大
                        logger.debug(f"🚫 频谱过于相似({distance:.2f})，可能是回声")
                        return False

                    # 检查相关性
                    if np.linalg.norm(features1) > 0 and np.linalg.norm(features2) > 0:
                        features1_norm = features1 / np.linalg.norm(features1)
                        features2_norm = features2 / np.linalg.norm(features2)
                        correlation = np.dot(features1_norm, features2_norm)
                        if correlation > 0.7:  # 相关性过高
                            logger.debug(f"🚫 频谱相关性过高({correlation:.2f})，可能是回声")
                            return False

            return True  # 通过严格检查，认为是用户语音

        except Exception as e:
            logger.error(f"❌ 严格TTS差异检查失败: {e}")
            return False  # 出错时倾向于认为是回声，减少误判

    def _is_definitely_echo(self, fingerprint: AudioFingerprint) -> bool:
        """确定判断是否为回声（用于非严格模式）"""
        try:
            if not self.tts_audio_fingerprints:
                return False  # 没有TTS参考，不能确定是回声

            current_time = fingerprint.timestamp

            # 检查最近的TTS指纹
            recent_tts_fingerprints = [
                fp for fp in self.tts_audio_fingerprints
                if current_time - fp.timestamp < 1.5  # 1.5秒内的TTS
            ]

            if not recent_tts_fingerprints:
                return False  # 没有最近的TTS参考

            for tts_fp in recent_tts_fingerprints:
                # 1. 时间相关性检查 - 如果在TTS播放后很短时间内出现
                time_diff = current_time - tts_fp.timestamp
                if time_diff < 0.3:  # 300ms内

                    # 2. 能量衰减检查 - 符合扬声器到麦克风的衰减特征
                    energy_ratio = fingerprint.energy / tts_fp.energy
                    if 0.1 <= energy_ratio <= 0.7:  # 能量衰减10%-70%

                        # 3. 频谱相似性检查 - 高度相似
                        if len(fingerprint.spectral_features) == len(tts_fp.spectral_features):
                            features1 = np.array(fingerprint.spectral_features)
                            features2 = np.array(tts_fp.spectral_features)

                            if np.linalg.norm(features1) > 0 and np.linalg.norm(features2) > 0:
                                # 归一化比较
                                features1_norm = features1 / \
                                    np.linalg.norm(features1)
                                features2_norm = features2 / \
                                    np.linalg.norm(features2)
                                similarity = np.dot(
                                    features1_norm, features2_norm)

                                # 如果相似度很高，几乎确定是回声
                                if similarity > 0.8:
                                    return True

                # 4. 完全匹配检查
                if fingerprint.fingerprint == tts_fp.fingerprint:
                    return True

            return False  # 不能确定是回声

        except Exception as e:
            logger.error(f"❌ 确定回声判断失败: {e}")
            return False  # 出错时不确定是回声

    def _trigger_interrupt(self):
        """已移除：不再触发打断信号，语音正常播放进行消音"""
        try:
            # 防止重复触发
            current_time = time.time()
            if hasattr(self, '_last_trigger_time') and current_time - self._last_trigger_time < 0.5:
                logger.debug("🔇 打断信号防抖：跳过重复触发")
                return

            self._last_trigger_time = current_time

            # 不再创建待验证的打断请求，只进行消音处理
            logger.debug("🔇 回声消除检测到音频，进行消音处理但不打断播放")

        except Exception as e:
            logger.error(f"❌ 消音处理失败: {e}")
            import traceback
            logger.error(f"消音处理异常详情: {traceback.format_exc()}")

    def _is_very_strong_user_voice(self, fingerprint: AudioFingerprint) -> bool:
        """
        检测是否为非常强的用户语音
        用于在TTS播放期间让明显的用户语音通过，触发VAD和IAT
        """
        try:
            # 1. 适中的能量阈值 - 让更多用户语音通过
            high_energy_threshold = self.energy_threshold * 3.0  # 降低到3倍基础阈值
            if fingerprint.energy < high_energy_threshold:
                return False

            # 2. 检查是否有明显的人声特征
            if not self._has_obvious_voice_characteristics(fingerprint):
                return False

            # 3. 与TTS音频有足够差异
            if not self._has_significant_difference_from_tts(fingerprint):
                return False

            # logger.debug(f"🔊 检测到强用户语音，能量: {fingerprint.energy:.1f}")
            return True

        except Exception as e:
            logger.error(f"❌ 强用户语音检测失败: {e}")
            return False

    def _has_extreme_difference_from_tts(self, fingerprint: AudioFingerprint) -> bool:
        """检查与TTS音频是否有极大差异"""
        try:
            if not self.tts_audio_fingerprints:
                return True

            current_time = fingerprint.timestamp

            # 检查最近的TTS指纹
            recent_tts_fingerprints = [
                fp for fp in self.tts_audio_fingerprints
                if current_time - fp.timestamp < 3.0  # 3秒内的TTS，延长检查时间
            ]

            if not recent_tts_fingerprints:
                return True

            # 必须与所有TTS音频都有极大的能量差异
            for tts_fp in recent_tts_fingerprints:
                energy_ratio = min(fingerprint.energy, tts_fp.energy) / \
                    max(fingerprint.energy, tts_fp.energy)
                if energy_ratio > 0.3:  # 能量差异阈值降低到0.3，更严格
                    return False

            # 进一步检查频谱特征差异
            for tts_fp in recent_tts_fingerprints:
                if self._has_similar_frequency_distribution(fingerprint, tts_fp, threshold=0.6):
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ 极大TTS差异检查失败: {e}")
            return False

    def _has_obvious_voice_characteristics(self, fingerprint: AudioFingerprint) -> bool:
        """检查是否有明显的人声特征"""
        try:
            features = np.array(fingerprint.spectral_features)

            if len(features) < 6:
                return False

            # 简单但有效的人声检查
            low_freq = np.mean(features[:2])    # 低频
            mid_freq = np.mean(features[2:5])   # 中频
            high_freq = np.mean(features[5:])   # 高频

            # 放宽人声检测条件
            # 1. 中频能量较强（主要条件）
            if mid_freq > low_freq * 0.6 and mid_freq > high_freq * 0.6:
                return True

            # 2. 或者能量分布相对均匀（人声特征）
            total_energy = low_freq + mid_freq + high_freq
            if total_energy > 0:
                mid_ratio = mid_freq / total_energy
                if 0.25 < mid_ratio < 0.6:  # 中频占比合理范围
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ 明显人声特征检测失败: {e}")
            return False

    # 已移除：_is_very_likely_user_voice_during_tts 方法（不再需要TTS期间的打断检测）

    def _has_strong_voice_characteristics(self, fingerprint: AudioFingerprint) -> bool:
        """检查是否具有强烈的人声特征"""
        try:
            features = np.array(fingerprint.spectral_features)

            if len(features) < 8:
                return False

            # 更严格的频谱分布检查
            low_freq = np.mean(features[:2])    # 低频
            mid_freq = np.mean(features[2:6])   # 中频
            high_freq = np.mean(features[6:])   # 高频

            # 中频能量必须明显强于低频和高频（人声特征）
            if mid_freq < low_freq * 1.2 or mid_freq < high_freq * 1.5:
                return False

            # 检查频谱的平滑度 - 人声通常有特定的共振峰
            spectral_variance = np.var(features)
            if spectral_variance < 0.1:  # 频谱过于平滑可能是TTS
                return False

            return True

        except Exception as e:
            logger.error(f"❌ 强人声特征检测失败: {e}")
            return False

    def _has_high_spectral_complexity(self, fingerprint: AudioFingerprint) -> bool:
        """检查是否具有高频谱复杂度"""
        try:
            features = np.array(fingerprint.spectral_features)

            if len(features) < 4:
                return False

            # 计算频谱的熵（复杂度指标）
            normalized_features = features / \
                np.sum(features) if np.sum(features) > 0 else features
            entropy = -np.sum(normalized_features *
                              np.log(normalized_features + 1e-10))

            # 人声通常有较高的熵值
            min_entropy = 2.0  # 根据实际情况调整
            if entropy < min_entropy:
                return False

            return True

        except Exception as e:
            logger.error(f"❌ 频谱复杂度检测失败: {e}")
            return False

    def _is_possibly_user_voice_during_tts(self, fingerprint: AudioFingerprint) -> bool:
        """
        在TTS播放期间判断是否可能是用户语音
        使用更宽松的标准，主要用于创建待验证的打断请求
        """
        try:
            # 1. 基本能量检查 - 需要足够的能量
            min_energy_threshold = self.energy_threshold * 2.0  # 降低能量要求
            if fingerprint.energy < min_energy_threshold:
                return False

            # 2. 与TTS音频的基本差异检查
            if not self._has_basic_difference_from_tts(fingerprint):
                return False

            # 3. 检查是否有人声特征
            if not self._has_voice_characteristics(fingerprint):
                return False

            return True

        except Exception as e:
            logger.error(f"❌ TTS期间用户语音检测失败: {e}")
            return False

    def _has_voice_characteristics(self, fingerprint: AudioFingerprint) -> bool:
        """检查音频是否具有人声特征"""
        try:
            features = np.array(fingerprint.spectral_features)

            if len(features) < 4:
                return False

            # 检查频谱分布 - 人声通常在中频有较强能量
            if len(features) >= 8:
                low_freq = np.mean(features[:3])
                mid_freq = np.mean(features[3:7])
                high_freq = np.mean(features[7:]) if len(features) > 7 else 0

                # 中频能量应该相对较强
                if mid_freq < low_freq * 0.5:
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ 人声特征检测失败: {e}")
            return False

    # 已移除：_create_pending_interrupt_request 方法（不再需要创建待验证的打断请求）


class SelfVoiceDetector:
    """自我声音检测器"""

    def __init__(self):
        self.echo_engine = EchoCancellationEngine()
        self.voice_callbacks: Dict[str, Callable] = {}
        self._lock = threading.RLock()

        # 定期清理线程
        self._cleanup_thread = threading.Thread(
            target=self._periodic_cleanup, daemon=True)
        self._stop_cleanup = threading.Event()
        self._cleanup_thread.start()

        logger.info("🎯 自我声音检测器已初始化")

    def register_voice_callback(self, name: str, callback: Callable):
        """注册声音检测回调"""
        with self._lock:
            self.voice_callbacks[name] = callback
            logger.info(f"📝 注册声音检测回调: {name}")

    def unregister_voice_callback(self, name: str):
        """注销声音检测回调"""
        with self._lock:
            if name in self.voice_callbacks:
                del self.voice_callbacks[name]
                logger.info(f"🗑️ 注销声音检测回调: {name}")

    def set_tts_playing(self, is_playing: bool, audio_data: Optional[bytes] = None):
        """设置TTS播放状态"""
        self.echo_engine.set_tts_playing_status(is_playing, audio_data)

        # 通知回调
        with self._lock:
            for name, callback in self.voice_callbacks.items():
                try:
                    callback('tts_status_changed', {
                        'is_playing': is_playing,
                        'timestamp': time.time()
                    })
                except Exception as e:
                    logger.error(f"❌ 声音检测回调 {name} 执行失败: {e}")

    def should_ignore_audio(self, audio_data: bytes) -> bool:
        """判断是否应该忽略音频（回声检测）"""
        return self.echo_engine.is_echo_audio(audio_data)

    def process_recording_audio(self, audio_data: bytes) -> bool:
        """处理录音音频，返回是否应该继续处理"""
        if self.should_ignore_audio(audio_data):
            # logger.debug("🚫 检测到自我声音，忽略音频数据")
            return False
        return True

    def _periodic_cleanup(self):
        """定期清理过期数据"""
        while not self._stop_cleanup.is_set():
            try:
                self.echo_engine.cleanup_old_fingerprints()
                time.sleep(0.1)  # 每秒清理一次
            except Exception as e:
                logger.error(f"❌ 定期清理失败: {e}")
                time.sleep(1.0)  # 出错时等待更长时间

    def get_detection_stats(self) -> Dict:
        """获取检测统计信息"""
        return self.echo_engine.get_stats()

    def enable_echo_cancellation(self):
        """启用回声消除"""
        self.echo_engine.enable()

    def disable_echo_cancellation(self):
        """禁用回声消除"""
        self.echo_engine.disable()

    def shutdown(self):
        """关闭检测器"""
        logger.info("🔄 关闭自我声音检测器...")
        self._stop_cleanup.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2.0)
        logger.info("✅ 自我声音检测器已关闭")


# 全局实例
_self_voice_detector: Optional[SelfVoiceDetector] = None
_detector_lock = threading.Lock()


def get_self_voice_detector() -> SelfVoiceDetector:
    """获取全局自我声音检测器实例"""
    global _self_voice_detector

    with _detector_lock:
        if _self_voice_detector is None:
            _self_voice_detector = SelfVoiceDetector()
        return _self_voice_detector


def cleanup_self_voice_detector():
    """清理全局检测器实例"""
    global _self_voice_detector

    with _detector_lock:
        if _self_voice_detector is not None:
            _self_voice_detector.shutdown()
            _self_voice_detector = None
