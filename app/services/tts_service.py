import threading
import winsound
from pathlib import Path

from pythaitts import TTS


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
            winsound.PlaySound(
                str(_output_file),
                winsound.SND_FILENAME,
            )

    def speak(self, text: str):
        with _engine_lock:
            tts = _prepare_locked()
            tts.tts(
                text,
                speaker_idx="th_f_2",
                filename=str(_output_file),
            )
            winsound.PlaySound(
                str(_output_file),
                winsound.SND_FILENAME,
            )
