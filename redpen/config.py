import os

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4")
# Claim-spotting is the hot path (it runs continuously); judging runs only once
# per claim. Allowing a smaller model for spotting keeps the loop real-time.
CLAIM_MODEL = os.environ.get("CLAIM_MODEL", OLLAMA_MODEL)
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", OLLAMA_MODEL)
# Keeps the model resident between calls — without this every call pays the
# full model load, which measured ~31s on the hackathon machine.
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")

SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

SAMPLE_RATE = int(os.environ.get("SAMPLE_RATE", "16000"))
AUDIO_CHUNK_SECONDS = float(os.environ.get("AUDIO_CHUNK_SECONDS", "5"))
TRANSCRIPT_WINDOW_SECONDS = float(os.environ.get("TRANSCRIPT_WINDOW_SECONDS", "25"))
MAX_FLAGGED_CLAIMS_MEMORY = int(os.environ.get("MAX_FLAGGED_CLAIMS_MEMORY", "50"))
EVIDENCE_RESULTS = int(os.environ.get("EVIDENCE_RESULTS", "5"))

# Don't wake Gemma for every Whisper segment — wait until enough *new* speech
# has accumulated to be worth a claim-spotting pass.
CLAIM_SCAN_MIN_CHARS = int(os.environ.get("CLAIM_SCAN_MIN_CHARS", "180"))
REPLAY_SPEED = float(os.environ.get("REPLAY_SPEED", "1.0"))

# Prefetch mode. A recorded video's transcript exists upfront, so the agent can
# analyse it far faster than playback and hold each result until the playhead
# reaches it — the same idea as prefetching, applied to inference. These are the
# offsets, in video seconds, from when a claim is spoken to when its card and
# then its verdict are surfaced.
FETCH_PAGES = os.environ.get("FETCH_PAGES", "1") not in ("0", "false", "False")
PAGE_FETCH_LIMIT = int(os.environ.get("PAGE_FETCH_LIMIT", "4"))
PAGE_FETCH_TIMEOUT = float(os.environ.get("PAGE_FETCH_TIMEOUT", "6"))
PAGE_MAX_BYTES = int(os.environ.get("PAGE_MAX_BYTES", str(1_500_000)))
PAGE_EXTRACT_CHARS = int(os.environ.get("PAGE_EXTRACT_CHARS", "1200"))

REVEAL_CLAIM_DELAY = float(os.environ.get("REVEAL_CLAIM_DELAY", "0"))
REVEAL_VERDICT_DELAY = float(os.environ.get("REVEAL_VERDICT_DELAY", "7.0"))
