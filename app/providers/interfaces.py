from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ModelProvider(Protocol):
    def complete_json(self, system: str, prompt: str) -> dict: ...


class TextToSpeech(Protocol):
    def synthesize(self, text: str, destination: Path, *, ssml: bool = False) -> Path: ...


class ObjectStorage(Protocol):
    def upload(self, key: str, source: Path, *, public: bool = False) -> str: ...


class PaperRepository(Protocol):
    def save_papers(self, papers: list[dict]) -> None: ...


class EpisodeRepository(Protocol):
    def save_draft(self, episode: dict) -> None: ...
    def publish_atomic(self, episode: dict) -> None: ...


class JobQueue(Protocol):
    def enqueue(self, payload: dict) -> str: ...


class Scheduler(Protocol):
    def schedule_weekly(self, expression: str) -> str: ...


class SecretsProvider(Protocol):
    def get(self, name: str) -> str: ...


class TelemetryProvider(Protocol):
    def record(self, event: str, attributes: dict) -> None: ...
