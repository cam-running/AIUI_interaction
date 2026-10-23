# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   control_audio.PY
# @Time       2025-05-30 27:20

import pyaudio
import wave
from pydub import AudioSegment

class ControlAudio:
    def __init__(self, logger_main=None, logger_source=None, logger_sink=None):

        self.logger_main = logger_main
        if logger_source:
            self.logger_source = logger_source
        else:
            self.logger_source = logger_main
        if logger_sink:
            self.logger_sink = logger_sink
        else:
            self.logger_sink = logger_main

        self.audio_instance = None
        self.steam_source_obj = None
        self.steam_sink_obj = None
        self._steam_sink_stop = False
        self._steam_sink_status = False
        self.reload_audio()

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

    def close_audio(self):
        self.close_steam_source()
        self.close_steam_sink()
        if self.audio_instance is not None:
            self.audio_instance.terminate()
            self.audio_instance = None

    def reload_audio(self):
        self.close_audio()
        self.audio_instance = pyaudio.PyAudio()

    def get_devices(self, source_key: str = None, sink_key: str = None) -> dict:
        if self.audio_instance is None:
            return {}
        info = self.audio_instance.get_host_api_info_by_index(0)
        device_count = info.get('deviceCount')
        source_index = None
        sink_index = None
        source_data = {}
        sink_data = {}
        for i in range(device_count):
            info = self.audio_instance.get_device_info_by_host_api_device_index(0, i)
            device_name = info.get('name')
            max_input_channels = info.get('maxInputChannels')
            max_output_channels = info.get('maxOutputChannels')
            if self.logger_main:
                self.logger_main.info(
                    f"当前读取到的设备为:{device_name},max_input_channels={max_input_channels},max_output_channels={max_output_channels}")
            if max_input_channels:

                if source_key is not None and source_key in device_name:
                    source_index = i
                source_data[device_name] = {"index": i, "channels": max_input_channels}
            if max_output_channels:

                if sink_key is not None and sink_key in device_name:
                    sink_index = i
                sink_data[device_name] = {"index": i, "channels": max_output_channels}
        return {
            "source_index": source_index,
            "sink_index": sink_index,
            "source_data": source_data,
            "sink_data": sink_data
        }

    def load_wav(self, play_file, chunk=1024, skip: int = 0, output_device_index=None):
        self.close_steam_sink()
        now_num = 0

        wf = wave.open(play_file, 'rb')
        self.steam_sink_obj = self.audio_instance.open(
            format=self.audio_instance.get_format_from_width(wf.getsampwidth()), channels=wf.getnchannels(),
            rate=wf.getframerate(), output=True, frames_per_buffer=chunk,
            output_device_index=output_device_index)

        data = wf.readframes(chunk)

        while data:
            if self.steam_sink_stop:
                break
            if not skip or skip < now_num:

                self.steam_sink_obj.write(data)

            data = wf.readframes(chunk)
            now_num += 1

        self.steam_sink_obj.stop_stream()
        self.steam_sink_obj.close()
        wf.close()

    @staticmethod
    def get_mp3_data(play_file):
        audio = AudioSegment.from_mp3(play_file)
        return audio

    def load_mp3(self, play_file, chunk=1024, skip: int = 0, output_device_index=None):

        self.close_steam_sink()

        audio = AudioSegment.from_mp3(play_file)

        self.logger_main.debug(f"load音频文件:{play_file}")

        self.steam_sink_obj = self.audio_instance.open(
            format=self.audio_instance.get_format_from_width(audio.sample_width),
            channels=audio.channels,
            rate=audio.frame_rate, frames_per_buffer=chunk,
            output=True, output_device_index=output_device_index)

        for i in range(0, len(audio.raw_data), chunk):
            if self.steam_sink_stop:
                break
            chunk_data = audio.raw_data[i:i + chunk]

            self.steam_sink_obj.write(chunk_data)

        self.steam_sink_obj.stop_stream()
        self.steam_sink_obj.close()

    def run_sink(self, play_file, chunk=1024, skip: int = 0, output_device_index=None):

        self.steam_sink_status = True
        try:
            if play_file.endswith(".mp3"):
                self.load_mp3(play_file, chunk, skip, output_device_index)
            elif play_file.endswith(".wav"):
                self.load_wav(play_file, chunk, skip, output_device_index)
            else:
                if self.logger_main:
                    self.logger_main.error(f"暂不支持的格式:{play_file}")

        except Exception as error_message:
            err = str(error_message)
            if self.logger_main:
                self.logger_main.error(f"播放失败:{err}")
            else:
                print(err)
        self.steam_sink_status = False

    def steam_sink_open(self, audio, chunk=1024, output_device_index=None):
        self.steam_sink_obj = self.audio_instance.open(
            format=self.audio_instance.get_format_from_width(audio.sample_width),
            channels=audio.channels,
            rate=audio.frame_rate, frames_per_buffer=chunk,
            output=True, output_device_index=output_device_index)

    def run_mp3(self, audio, len_data, chunk=1024, output_device_index=None):
        self.steam_sink_status = True
        if self.steam_sink_obj is None:
            self.steam_sink_open(audio, chunk, output_device_index)
        for i in range(0, len_data, chunk):
            if self.steam_sink_stop:
                break
            chunk_data = audio.raw_data[i:i + chunk]
            self.steam_sink_obj.write(chunk_data)
        self.steam_sink_status = False


if __name__ == "__main__":
    from loguru import logger
    c = ControlAudio(logger)
    logger.info("11")
    c.run_sink("D:\\face_voice\\voice\\测试_1.mp3")
