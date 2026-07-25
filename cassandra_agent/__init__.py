"""Cassandra Live — autonomous debate fact-checking agent.

Pipeline: YouTube/stream audio -> speech-to-text -> claim extraction (Gemma)
-> web evidence retrieval (SerpApi) -> verdict judging (Gemma) -> live web overlay.
"""
