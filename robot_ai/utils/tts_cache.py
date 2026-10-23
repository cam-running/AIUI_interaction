"""
TTS音频缓存管理器模块
提供音频数据的本地缓存功能，避免重复调用TTS API
"""
import threading
import time
import hashlib
import pickle
from pathlib import Path
from utils.logger import logger


class TTSCache:
    """TTS音频缓存管理器"""

    def __init__(self, cache_file: str = "tts_cache/tts_cache.pkl"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_data = self._load_cache_data()
        self._lock = threading.Lock()

    def _load_cache_data(self):
        """加载缓存数据"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.info(f"[缓存] 加载缓存数据失败: {e}")
        return {}

    def _save_cache_data(self):
        """保存缓存数据"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache_data, f)
        except Exception as e:
            logger.info(f"[缓存] 保存缓存数据失败: {e}")

    def _get_cache_key(self, text: str, voice: str = None) -> str:
        """生成缓存键"""
        if voice is None:
            from config.config.settings import config
            voice = config.TTS_VOICE
        # 使用文本内容和语音参数的哈希作为缓存键
        cache_data = f"{text.strip()}_{voice}"
        return hashlib.md5(cache_data.encode('utf-8')).hexdigest()

    def get_cached_audio(self, text: str, voice: str = None) -> bytes:
        """获取缓存的音频数据"""
        with self._lock:
            cache_key = self._get_cache_key(text, voice)
            if cache_key in self.cache_data:
                cache_info = self.cache_data[cache_key]
                audio_data = cache_info.get('audio_data')
                if audio_data:
                    logger.info(f"[缓存] 命中缓存: {text[:20]}...")
                    return audio_data
                else:
                    # 删除损坏的缓存记录
                    del self.cache_data[cache_key]
                    self._save_cache_data()

        return None

    def save_audio_cache(self, text: str, audio_data: bytes, voice: str = None):
        """保存音频数据到缓存"""
        with self._lock:
            cache_key = self._get_cache_key(text, voice)

            try:
                # 更新缓存数据
                if voice is None:
                    from config.config.settings import config
                    voice = config.TTS_VOICE
                self.cache_data[cache_key] = {
                    'text': text,
                    'voice': voice,
                    'audio_data': audio_data,
                    'size': len(audio_data),
                    'created_time': time.time()
                }

                self._save_cache_data()
                logger.info(
                    f"[缓存] 已缓存: {text[:20]}... (大小: {len(audio_data)} bytes)")

            except Exception as e:
                logger.info(f"[缓存] 保存缓存失败: {e}")

    def clear_cache(self, max_age_days: int = 30):
        """清理过期缓存"""
        with self._lock:
            current_time = time.time()
            expired_keys = []

            for cache_key, cache_info in self.cache_data.items():
                age_days = (current_time -
                            cache_info['created_time']) / (24 * 3600)
                if age_days > max_age_days:
                    expired_keys.append(cache_key)

            for cache_key in expired_keys:
                del self.cache_data[cache_key]

            if expired_keys:
                self._save_cache_data()
                logger.info(f"[缓存] 清理了 {len(expired_keys)} 个过期缓存")

    def get_cache_stats(self):
        """获取缓存统计信息"""
        with self._lock:
            total_size = sum(info['size']
                             for info in self.cache_data.values())
            return {
                'total_entries': len(self.cache_data),
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024)
            }

    def clear_all_cache(self):
        """清空所有缓存"""
        with self._lock:
            self.cache_data.clear()
            self._save_cache_data()
            logger.info("[缓存] 已清空所有缓存")

    def get_cache_info(self, text: str, voice: str = None):
        """获取指定文本的缓存信息"""
        with self._lock:
            cache_key = self._get_cache_key(text, voice)
            if cache_key in self.cache_data:
                cache_info = self.cache_data[cache_key].copy()
                # 不返回音频数据，只返回元信息
                cache_info.pop('audio_data', None)
                return cache_info
        return None


# 全局缓存实例
_tts_cache = TTSCache()


def get_cache_instance():
    """获取缓存实例"""
    return _tts_cache


def get_cached_audio(text: str, voice: str = None) -> bytes:
    """获取缓存的音频数据"""
    return _tts_cache.get_cached_audio(text, voice)


def save_audio_cache(text: str, audio_data: bytes, voice: str = None):
    """保存音频数据到缓存"""
    _tts_cache.save_audio_cache(text, audio_data, voice)


def clear_cache(max_age_days: int = 30):
    """清理过期缓存"""
    _tts_cache.clear_cache(max_age_days)


def get_cache_stats():
    """获取缓存统计信息"""
    return _tts_cache.get_cache_stats()


def clear_all_cache():
    """清空所有缓存"""
    _tts_cache.clear_all_cache()


def get_cache_info(text: str, voice: str = None):
    """获取指定文本的缓存信息"""
    return _tts_cache.get_cache_info(text, voice)
