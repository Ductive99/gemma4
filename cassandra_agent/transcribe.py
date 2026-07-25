"""Speech-to-text over PCM audio chunks, producing timestamped transcript segments.

Uses faster-whisper (CTranslate2-based, runs on-device/CPU) so the whole
pipeline can stay local except for the evidence search step. Imported lazily
so importing this module doesn't require the model library to be installed.
"""

import numpy as np

from . import config
from .events import TranscriptSegment


class Transcriber:
    def __init__(self, model_size: str = None, device: str = None, compute_type: str = None):
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            model_size or config.WHISPER_MODEL_SIZE,
            device=device or config.WHISPER_DEVICE,
            compute_type=compute_type or config.WHISPER_COMPUTE_TYPE,
        )
        self._offset_seconds = 0.0

    def transcribe_chunk(self, pcm_bytes: bytes, sample_rate: int = None) -> list[TranscriptSegment]:
        """Transcribes one chunk of 16-bit mono PCM audio, returning absolute-timestamped segments."""
        sample_rate = sample_rate or config.SAMPLE_RATE
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        raw_segments, _info = self._model.transcribe(audio, vad_filter=True)
        results = []
        for seg in raw_segments:
            text = seg.text.strip()
            if not text:
                continue
            results.append(TranscriptSegment(
                start=self._offset_seconds + seg.start,
                end=self._offset_seconds + seg.end,
                text=text,
            ))

        self._offset_seconds += len(pcm_bytes) / 2 / sample_rate
        return results
