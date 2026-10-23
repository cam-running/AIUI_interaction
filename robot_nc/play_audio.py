"""
TTS缓存音频完整性测试脚本
验证缓存中的音频数据是否完整、格式正确、可正常播放
"""
import pickle
import wave
import io
import subprocess
import sys
import os
from pathlib import Path
from utils.logger import logger
# 导入你的缓存模块
from utils.tts_cache import get_cache_instance, get_cached_audio

# ====================== 配置项 ======================
CACHE_FILE_PATH = "tts_cache/tts_cache.pkl"  # 缓存文件路径
SOUND_CARD = "plughw:2,0"  # 声卡设备（根据aplay -l调整）
TEST_PLAY = True  # 是否播放音频验证（True/False）
TARGET_TEXT = None  # 指定测试的文本（None则测试所有）
# ====================================================

class TTSCacheTester:
    def __init__(self, cache_file: str, sound_card: str, test_play: bool = True):
        self.cache_file = Path(cache_file)
        self.sound_card = sound_card
        self.test_play = test_play
        self.cache = get_cache_instance()  # 获取你的缓存实例
        self.stats = {
            "total_records": 0,
            "valid_records": 0,
            "corrupted_records": 0,
            "invalid_format": [],
            "empty_audio": [],
            "playback_failed": [],
        }

    def _validate_pcm_format(self, audio_data: bytes) -> bool:
        """
        验证PCM音频格式是否符合要求（16kHz/16bit/单声道）
        :param audio_data: 原始PCM字节数据
        :return: 是否有效
        """
        if not audio_data:
            return False
        
        # 1. 检查字节数是否为 2 的倍数（16bit = 2字节/采样点）
        if len(audio_data) % 2 != 0:
            logger.warning(f"音频字节数 {len(audio_data)} 不是2的倍数（16bit要求）")
            return False
        
        # 2. 验证时长合理性（至少0.1秒，避免空数据）
        bytes_per_second = 16000 * 1 * 2  # 16kHz * 单声道 * 16bit
        duration = len(audio_data) / bytes_per_second
        if duration < 0.1:
            logger.warning(f"音频时长过短: {duration:.2f}秒（字节数：{len(audio_data)}）")
            return False
        
        return True

    def _save_pcm_to_wav(self, audio_data: bytes, wav_path: str):
        """将PCM数据保存为WAV文件（便于验证格式）"""
        with wave.open(wav_path, 'wb') as wf:
            wf.setnchannels(1)  # 单声道
            wf.setsampwidth(2)  # 16bit
            wf.setframerate(16000)  # 16kHz
            wf.writeframes(audio_data)

    def _play_pcm_audio(self, audio_data: bytes, text: str) -> bool:
        """播放PCM音频，返回是否播放成功"""
        if not self.test_play:
            return True
        
        # 创建临时PCM文件
        temp_pcm = "/tmp/tts_test_temp.pcm"
        try:
            with open(temp_pcm, 'wb') as f:
                f.write(audio_data)
            
            # 使用aplay播放
            play_cmd = [
                "aplay",
                "-f", "S16_LE",   # 16bit小端
                "-r", "16000",    # 采样率
                "-c", "1",        # 单声道
                "-D", self.sound_card,
                temp_pcm
            ]
            result = subprocess.run(play_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"播放失败: {text[:20]}... 错误: {result.stderr}")
                return False
            
            logger.info(f"✅ 播放成功: {text[:20]}...")
            return True
        
        except Exception as e:
            logger.error(f"播放异常: {text[:20]}... 错误: {str(e)}")
            return False
        finally:
            # 清理临时文件
            if os.path.exists(temp_pcm):
                os.remove(temp_pcm)

    def _test_single_record(self, cache_key: str, cache_info: dict):
        """测试单条缓存记录"""
        self.stats["total_records"] += 1
        text = cache_info.get("text", "")
        audio_data = cache_info.get("audio_data", b"")
        voice = cache_info.get("voice", "")
        size = cache_info.get("size", 0)

        logger.info(f"\n--- 测试记录: {text[:30]}... (key: {cache_key[:10]}...) ---")
        logger.info(f"语音: {voice}, 缓存大小: {size} bytes")

        # 1. 检查音频是否为空
        if not audio_data or size == 0:
            logger.error(f"❌ 音频数据为空")
            self.stats["corrupted_records"] += 1
            self.stats["empty_audio"].append(text[:30] + "...")
            return

        # 2. 验证PCM格式
        if not self._validate_pcm_format(audio_data):
            logger.error(f"❌ PCM格式无效")
            self.stats["corrupted_records"] += 1
            self.stats["invalid_format"].append(text[:30] + "...")
            return

        # 3. 播放验证（可选）
        play_success = self._play_pcm_audio(audio_data, text)
        if not play_success:
            self.stats["playback_failed"].append(text[:30] + "...")

        # 4. 所有检查通过
        self.stats["valid_records"] += 1
        logger.info(f"✅ 所有校验通过: {text[:20]}...")

    def run_full_test(self, target_text: str = None):
        """运行完整测试"""
        # 1. 验证缓存文件是否存在
        if not self.cache_file.exists():
            logger.error(f"❌ 缓存文件不存在: {self.cache_file}")
            return

        # 2. 加载缓存数据（双重验证：直接加载 + 通过缓存实例）
        try:
            # 直接加载pickle文件验证格式
            with open(self.cache_file, 'rb') as f:
                raw_cache = pickle.load(f)
            logger.info(f"✅ 缓存文件格式正常，共 {len(raw_cache)} 条记录")

            # 通过缓存实例获取数据（验证接口可用性）
            cache_data = self.cache.cache_data
            if len(cache_data) != len(raw_cache):
                logger.warning(f"⚠️ 缓存实例数据与文件不一致: 实例{len(cache_data)}条 vs 文件{len(raw_cache)}条")

        except Exception as e:
            logger.error(f"❌ 加载缓存文件失败: {str(e)}")
            return

        # 3. 测试指定记录或所有记录
        test_records = {}
        if target_text:
            # 查找目标文本的缓存记录
            for key, info in cache_data.items():
                if target_text in info.get("text", ""):
                    test_records[key] = info
            if not test_records:
                logger.error(f"❌ 未找到目标文本: {target_text}")
                return
        else:
            test_records = cache_data

        # 4. 逐个测试记录
        logger.info(f"\n开始测试 {len(test_records)} 条缓存记录...")
        for cache_key, cache_info in test_records.items():
            self._test_single_record(cache_key, cache_info)

        # 5. 生成测试报告
        self._generate_report()

    def _generate_report(self):
        """生成测试报告"""
        logger.info("\n" + "="*50)
        logger.info("📊 TTS缓存完整性测试报告")
        logger.info("="*50)
        logger.info(f"总记录数: {self.stats['total_records']}")
        logger.info(f"有效记录数: {self.stats['valid_records']}")
        logger.info(f"损坏记录数: {self.stats['corrupted_records']}")
        
        if self.stats["invalid_format"]:
            logger.error(f"\n❌ 格式无效的记录:")
            for text in self.stats["invalid_format"]:
                logger.error(f"  - {text}")
        
        if self.stats["empty_audio"]:
            logger.error(f"\n❌ 音频为空的记录:")
            for text in self.stats["empty_audio"]:
                logger.error(f"  - {text}")
        
        if self.stats["playback_failed"]:
            logger.error(f"\n❌ 播放失败的记录:")
            for text in self.stats["playback_failed"]:
                logger.error(f"  - {text}")
        
        success_rate = (self.stats["valid_records"] / self.stats["total_records"]) * 100 if self.stats["total_records"] > 0 else 0
        logger.info(f"\n✅ 缓存健康率: {success_rate:.1f}%")

def main():
    """主函数"""
    # 初始化日志（如果未初始化）
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    # 创建测试器并运行
    tester = TTSCacheTester(
        cache_file=CACHE_FILE_PATH,
        sound_card=SOUND_CARD,
        test_play=TEST_PLAY
    )
    
    tester.run_full_test(target_text=TARGET_TEXT)

if __name__ == "__main__":
    main()
