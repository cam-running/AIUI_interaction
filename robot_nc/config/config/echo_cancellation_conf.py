# -*- coding: utf-8 -*-
"""
回声消除配置文件
管理自我声音检测和回声消除的相关参数
"""


class EchoCancellationConf:
    """回声消除配置类"""

    # 基础配置
    ENABLE_ECHO_CANCELLATION = True  # 是否启用回声消除
    ENABLE_INTERRUPT_DURING_PLAYBACK = True  # 播放中是否允许打断

    # 音频处理参数
    SAMPLE_RATE = 16000  # 采样率
    FRAME_SIZE = 1024    # 帧大小
    OVERLAP_RATIO = 0.5  # 重叠比率

    # 阈值参数
    ENERGY_THRESHOLD = 500.0        # 基础能量阈值
    USER_VOICE_ENERGY_MULTIPLIER = 2.0  # 用户语音能量倍数
    CORRELATION_THRESHOLD = 0.7     # 相关性阈值

    # 时间窗口参数
    TIME_WINDOW = 3.0               # 指纹比较时间窗口（秒）
    TTS_FADE_OUT_DURATION = 3.0     # TTS结束后的淡出时间（秒）- 延长到3秒防止声音泄漏
    TTS_REFERENCE_WINDOW = 3.0      # TTS参考时间窗口（秒）- 延长到3秒

    # 频谱分析参数
    FFT_SIZE = 512      # FFT大小
    MEL_FILTERS = 13    # Mel滤波器数量

    # 缓存参数
    MAX_TTS_FINGERPRINTS = 100      # 最大TTS指纹缓存数量
    MAX_RECORDING_BUFFER = 1000     # 最大录音缓冲区大小

    # 用户语音检测参数
    VOICE_DETECTION = {
        'energy_multiplier': 2.0,           # 能量倍数阈值
        'spectral_diff_threshold': 0.5,     # 频谱差异阈值
        'energy_diff_threshold': 0.3,       # 能量差异阈值（30%）
        'low_freq_weight': 0.7,             # 低频权重
        'recent_tts_check_count': 3,        # 检查最近TTS指纹数量
    }

    # TTS音频平衡过滤参数
    TTS_FILTERING = {
        'strict_mode': False,               # 关闭严格模式 - 允许用户打断
        'variant_detection_window': 1.0,    # 适中的TTS变种检测时间窗口
        'energy_attenuation_range': (0.2, 0.7),  # 适中的能量衰减范围
        'variant_similarity_threshold': 0.6,     # 适中的变种相似度阈值
        'frequency_correlation_threshold': 0.5,   # 适中的频率相关性阈值
        'definite_voice_energy_multiplier': 2.5,  # 适中的确定用户语音的能量倍数
        'max_similarity_with_tts': 0.4,           # 适中的与TTS的最大允许相似度
        'min_spectral_variation': 0.7,            # 适中的最小频谱变化要求
        'min_spectral_range': 2.2,                # 适中的最小频谱动态范围要求
    }

    # 调试和日志配置
    DEBUG_MODE = False              # 调试模式
    LOG_DETECTION_DETAILS = False   # 记录检测详情
    LOG_AUDIO_FINGERPRINTS = False  # 记录音频指纹

    # 性能优化配置
    CLEANUP_INTERVAL = 1.0          # 清理间隔（秒）
    PROCESSING_TIMEOUT = 0.1        # 处理超时（秒）

    @classmethod
    def get_user_voice_energy_threshold(cls):
        """获取用户语音能量阈值"""
        return cls.ENERGY_THRESHOLD * cls.USER_VOICE_ENERGY_MULTIPLIER

    @classmethod
    def is_debug_enabled(cls):
        """检查是否启用调试模式"""
        return cls.DEBUG_MODE

    @classmethod
    def should_log_detection_details(cls):
        """是否应该记录检测详情"""
        return cls.LOG_DETECTION_DETAILS or cls.DEBUG_MODE

    @classmethod
    def should_log_audio_fingerprints(cls):
        """是否应该记录音频指纹"""
        return cls.LOG_AUDIO_FINGERPRINTS or cls.DEBUG_MODE

    @classmethod
    def get_voice_detection_config(cls):
        """获取语音检测配置"""
        return cls.VOICE_DETECTION.copy()

    @classmethod
    def update_config(cls, **kwargs):
        """动态更新配置"""
        for key, value in kwargs.items():
            if hasattr(cls, key.upper()):
                setattr(cls, key.upper(), value)
            elif key in cls.VOICE_DETECTION:
                cls.VOICE_DETECTION[key] = value

    @classmethod
    def get_all_config(cls):
        """获取所有配置"""
        config = {}
        for attr_name in dir(cls):
            if not attr_name.startswith('_') and not callable(getattr(cls, attr_name)):
                config[attr_name] = getattr(cls, attr_name)
        return config

    @classmethod
    def validate_config(cls):
        """验证配置参数的合理性"""
        errors = []

        # 检查阈值参数
        if cls.ENERGY_THRESHOLD <= 0:
            errors.append("ENERGY_THRESHOLD必须大于0")

        if cls.CORRELATION_THRESHOLD < 0 or cls.CORRELATION_THRESHOLD > 1:
            errors.append("CORRELATION_THRESHOLD必须在0-1之间")

        # 检查时间窗口参数
        if cls.TIME_WINDOW <= 0:
            errors.append("TIME_WINDOW必须大于0")

        if cls.TTS_FADE_OUT_DURATION < 0:
            errors.append("TTS_FADE_OUT_DURATION不能为负数")

        # 检查频谱参数
        if cls.FFT_SIZE <= 0 or (cls.FFT_SIZE & (cls.FFT_SIZE - 1)) != 0:
            errors.append("FFT_SIZE必须是2的幂次方")

        if cls.MEL_FILTERS <= 0:
            errors.append("MEL_FILTERS必须大于0")

        # 检查缓存参数
        if cls.MAX_TTS_FINGERPRINTS <= 0:
            errors.append("MAX_TTS_FINGERPRINTS必须大于0")

        if cls.MAX_RECORDING_BUFFER <= 0:
            errors.append("MAX_RECORDING_BUFFER必须大于0")

        return errors


# 提供全局配置实例
echo_config = EchoCancellationConf()
