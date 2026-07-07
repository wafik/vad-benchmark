"""VAD benchmark — measures Silero VAD's effect on Indonesian STT.

A thin wrapper around ``whisper-cli`` that mirrors how ``ai4db`` uses it
internally (Silero VAD delegated to whisper.cpp via ``--vad --vad-model``),
paired with a FastAPI dashboard for configurable end-to-end comparison.
"""
__version__ = "0.1.0"