import os

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

SAMPLE_RATE = int(os.environ.get("SAMPLE_RATE", "16000"))
AUDIO_CHUNK_SECONDS = float(os.environ.get("AUDIO_CHUNK_SECONDS", "5"))
TRANSCRIPT_WINDOW_SECONDS = float(os.environ.get("TRANSCRIPT_WINDOW_SECONDS", "25"))
MAX_FLAGGED_CLAIMS_MEMORY = int(os.environ.get("MAX_FLAGGED_CLAIMS_MEMORY", "50"))
EVIDENCE_RESULTS = int(os.environ.get("EVIDENCE_RESULTS", "5"))
