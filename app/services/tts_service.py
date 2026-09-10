import threading
import wave
from pathlib import Path

import numpy as np
from pythaitts import TTS

try:
    import winsound
except ImportError:  # Raspberry Pi/Linux
    winsound = None


_engine = None
_prepared = False
_engine_lock = threading.Lock()
_output_file = Path(__file__).resolve().parent / "output.wav"


def _get_engine():
    global _engine
    if _engine is None:
        _engine = TTS(pretrained="vachana")
    return _engine


def _prepare_locked():
    global _prepared
    tts = _get_engine()
    if not _prepared:
        # Force the th_f_2 voice to download/load before Login is shown.
        tts.tts(
            "เตรียมระบบเสียง",
            speaker_idx="th_f_2",
            filename=str(_output_file),
        )
        _prepared = True
    return tts


def _play_output_file():
    if winsound is not None:
        winsound.PlaySound(str(_output_file), winsound.SND_FILENAME)
        return
    try:
        import sounddevice as sd
        with wave.open(str(_output_file), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
        dtype_by_width = {1: np.uint8, 2: np.int16, 4: np.int32}
        dtype = dtype_by_width.get(sample_width)
        if dtype is None:
            raise RuntimeError("รูปแบบไฟล์เสียงไม่รองรับ")
        audio = np.frombuffer(frames, dtype=dtype)
        if channels > 1:
            audio = audio.reshape(-1, channels)
        sd.query_devices(kind="output")
        sd.play(audio, sample_rate)
        sd.wait()
    except Exception as error:
        raise RuntimeError("ไม่พบลำโพงหรืออุปกรณ์เสียงที่พร้อมใช้งาน") from error


class ThaiTTSService:
    """VachanaTTS female voice 2, matching the verified standalone example."""

    @staticmethod
    def prepare():
        """Load the model synchronously before the login window is created."""
        with _engine_lock:
            _prepare_locked()

    def prepare_text(self, text: str):
        """Synthesize the personalized welcome before entering Chatbot."""
        with _engine_lock:
            tts = _prepare_locked()
            tts.tts(
                text,
                speaker_idx="th_f_2",
                filename=str(_output_file),
            )

    def play_prepared(self):
        """Play the already-synthesized welcome without generation delay."""
        with _engine_lock:
            _play_output_file()

    def speak(self, text: str):
        with _engine_lock:
            tts = _prepare_locked()
            tts.tts(
                text,
                speaker_idx="th_f_2",
                filename=str(_output_file),
            )
            _play_output_file()
