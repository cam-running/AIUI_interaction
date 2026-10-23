# core/aiui/audio_segment.py
from dataclasses import dataclass
import time


@dataclass
class AudioSegment:
    pcm: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2   # int16
    start_ts_ms: int = 0
    end_ts_ms: int = 0


class VadSegmentCollector:
    """
    Upstream contract (as you stated):
      1 = start (WITH audio)
      2 = continue (WITH audio)
      3 = end (WITH audio, last frame)
    """

    STATE_IDLE = 0
    STATE_IN_SEG = 1
    STATE_TAIL = 2

    def __init__(self, sample_rate=16000, max_ms=15000, min_ms=800, tail_ms=0, logger=None):
        self.sample_rate = int(sample_rate)
        self.max_ms = int(max_ms)
        self.min_ms = int(min_ms)
        self.tail_ms = int(tail_ms)
        self._logger = logger

        self._state = self.STATE_IDLE
        self._buf = bytearray()
        self._start_ts_ms = 0

        # tail control
        self._tail_target_ms = 0

    def reset(self):
        self._state = self.STATE_IDLE
        self._buf = bytearray()
        self._start_ts_ms = 0
        self._tail_target_ms = 0

    def feed(self, vad_status: int, pcm: bytes, ts_ms: int = 0):
        now = time.time()
        now_ms = int(ts_ms or (now * 1000))
        vad_status = int(vad_status or 0)
        pcm = pcm or b""

        # ---- Tail phase: keep appending until reach fixed target, then flush ----
        if self._state == self.STATE_TAIL:
            if pcm:
                self._buf.extend(pcm)
            if self._duration_ms() >= self._tail_target_ms:
                return self._flush(now_ms)
            return None

        # ---- Start ----
        if vad_status == 1:
            # If we were already inside a segment, that's an upstream violation or
            # we lost an "end". Choose: flush previous if long enough, then start new.
            if self._state == self.STATE_IN_SEG and self._buf:
                prev_dur = self._duration_ms()
                if self._logger:
                    self._logger.warning(f"[VAD] got status=1 while in_seg, force flush prev_dur={prev_dur}ms")

                seg = None
                if prev_dur >= self.min_ms:
                    seg = self._flush(now_ms)
                else:
                    self.reset()

                # start new segment immediately
                self._state = self.STATE_IN_SEG
                self._start_ts_ms = now_ms
                if pcm:
                    self._buf.extend(pcm)
                return seg

            # normal start
            self.reset()
            self._state = self.STATE_IN_SEG
            self._start_ts_ms = now_ms
            if pcm:
                self._buf.extend(pcm)
            return None

        # ---- Continue ----
        if vad_status == 2:
            # If we missed start, tolerate: treat as start
            if self._state == self.STATE_IDLE:
                if self._logger:
                    self._logger.warning("[VAD] got status=2 while idle, treat as start")
                self._state = self.STATE_IN_SEG
                self._start_ts_ms = now_ms

            if pcm:
                self._buf.extend(pcm)

            if self._duration_ms() >= self.max_ms:
                # force flush to bound latency
                return self._flush(now_ms)

            return None

        # ---- End ----
        if vad_status == 3:
            if self._state == self.STATE_IDLE or not self._buf:
                # No active segment: ignore
                if self._logger:
                    self._logger.warning("[VAD] got status=3 while idle/empty, ignore")
                self.reset()
                return None

            if pcm:
                self._buf.extend(pcm)

            dur = self._duration_ms()
            if dur < self.min_ms:
                # too short: drop
                if self._logger:
                    self._logger.info(f"[VAD] drop too-short segment dur={dur}ms")
                self.reset()
                return None

            if self.tail_ms > 0:
                # enter tail with a fixed target length
                self._state = self.STATE_TAIL
                self._tail_target_ms = dur + self.tail_ms
                return None

            return self._flush(now_ms)

        # ---- Unknown status ----
        if self._logger:
            self._logger.warning(f"[VAD] unknown vad_status={vad_status}, ignore")
        return None

    def _duration_ms(self) -> int:
        samples = len(self._buf) // 2
        return int(samples * 1000 / self.sample_rate)

    def _flush(self, end_ts_ms: int):
        seg = AudioSegment(
            pcm=bytes(self._buf),
            sample_rate=self.sample_rate,
            channels=1,
            sample_width=2,
            start_ts_ms=int(self._start_ts_ms or 0),
            end_ts_ms=int(end_ts_ms or 0),
        )
        self.reset()
        return seg
