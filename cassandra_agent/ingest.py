"""Pulls raw PCM audio out of a YouTube video/live URL.

yt-dlp resolves the direct media URL, ffmpeg decodes/resamples it to 16-bit
mono PCM. Both are imported lazily so the rest of the package (and its tests)
don't need them installed just to be imported.
"""

import shutil
import subprocess

from . import config


class YoutubeAudioSource:
    def __init__(self, url: str, chunk_seconds: float = None, sample_rate: int = None):
        self.url = url
        self.chunk_seconds = chunk_seconds or config.AUDIO_CHUNK_SECONDS
        self.sample_rate = sample_rate or config.SAMPLE_RATE
        self._proc = None

    def _resolve_stream_url(self) -> str:
        import yt_dlp

        ydl_opts = {"format": "bestaudio/best", "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
            if info.get("url"):
                return info["url"]
            for fmt in info.get("formats", []):
                if fmt.get("acodec") not in (None, "none") and fmt.get("url"):
                    return fmt["url"]
            raise RuntimeError(f"No audio stream found for {self.url}")

    def __enter__(self) -> "YoutubeAudioSource":
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required on PATH to decode the audio stream")
        stream_url = self._resolve_stream_url()
        cmd = [
            "ffmpeg", "-loglevel", "error",
            "-i", stream_url,
            "-f", "s16le", "-ac", "1", "-ar", str(self.sample_rate),
            "-",
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc.wait()

    def chunks(self):
        """Yields raw PCM byte chunks of ~chunk_seconds each until the stream ends."""
        if self._proc is None:
            raise RuntimeError("YoutubeAudioSource must be used as a context manager")
        bytes_per_chunk = int(self.sample_rate * self.chunk_seconds) * 2  # 16-bit samples
        while True:
            data = self._proc.stdout.read(bytes_per_chunk)
            if not data:
                return
            yield data
