import os
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from app.config import settings


class WhisperSTTService:
    SAMPLE_RATE = 16000

    def __init__(self):
        self.directory = Path(__file__).resolve().parent / "STT"
        self.executable = self.directory / "whisper-cli.exe"
        self.model = self.directory / "ggml-small.bin"

    def transcribe(self) -> str:
        try:
            import sounddevice as sd
        except ImportError as error:
            raise RuntimeError("ยังไม่ได้ติดตั้ง sounddevice กรุณาติดตั้ง requirements.txt") from error
        if not self.executable.exists() or not self.model.exists():
            raise RuntimeError("ไม่พบ whisper.cpp หรือโมเดลภาษา")
        frames = int(settings.whisper_record_seconds * self.SAMPLE_RATE)
        audio = sd.rec(frames, samplerate=self.SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()
        pcm = np.clip(audio[:, 0] * 32767, -32768, 32767).astype(np.int16)
        temp_dir = tempfile.mkdtemp(prefix="face_ai_stt_")
        wav_path = Path(temp_dir) / "input.wav"
        output_prefix = Path(temp_dir) / "result"
        try:
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.SAMPLE_RATE)
                wav_file.writeframes(pcm.tobytes())
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            result = subprocess.run(
                [
                    str(self.executable), "-m", str(self.model), "-f", str(wav_path),
                    "-l", "th", "-otxt", "-of", str(output_prefix), "-nt",
                ],
                cwd=str(self.directory), capture_output=True, text=True, timeout=120,
                creationflags=flags,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Whisper ไม่สามารถถอดเสียงได้")
            text_path = output_prefix.with_suffix(".txt")
            transcript = text_path.read_text(encoding="utf-8-sig").strip()
            if not transcript:
                raise RuntimeError("ไม่ได้ยินเสียงพูด กรุณาลองใหม่")
            return transcript
        finally:
            for path in Path(temp_dir).glob("*"):
                try:
                    path.unlink()
                except OSError:
                    pass
            try:
                Path(temp_dir).rmdir()
            except OSError:
                pass
