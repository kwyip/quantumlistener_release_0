from __future__ import annotations

import json
import os
from pathlib import Path


class LocalRepository:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.getenv("QUANTUMLISTENER_DATA", ".quantumlistener"))
        self.root.mkdir(parents=True, exist_ok=True)

    def _read(self, name: str, default):
        path = self.root / name
        return json.loads(path.read_text()) if path.exists() else default

    def _atomic(self, name: str, payload) -> None:
        target = self.root / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, default=str))
        temporary.replace(target)

    def save_papers(self, papers: list[dict]) -> None:
        existing = {(p["arxiv_id"], p["version"]): p for p in self._read("papers.json", [])}
        existing.update({(p["arxiv_id"], p["version"]): p for p in papers})
        self._atomic("papers.json", list(existing.values()))

    def save_run(self, run: dict) -> None:
        runs = self._read("runs.json", {})
        runs[run["run_id"]] = run
        self._atomic("runs.json", runs)

    def save_draft(self, episode: dict) -> None:
        drafts = self._read("drafts.json", {})
        drafts[episode["week"]] = episode
        self._atomic("drafts.json", drafts)

    def approve(self, week: str) -> dict:
        drafts = self._read("drafts.json", {})
        if week not in drafts:
            raise KeyError(week)
        drafts[week]["status"] = "approved"
        self._atomic("drafts.json", drafts)
        return drafts[week]

    def publish_atomic(self, episode: dict) -> None:
        if episode.get("status") != "published":
            raise ValueError("episode must be published")
        episodes = self._read("episodes.json", {})
        episodes[episode["week"]] = episode
        publication = {"current": episode["week"], "episodes": episodes}
        self._atomic("publication.json", publication)

    def current(self):
        state = self._read("publication.json", {})
        return state.get("episodes", {}).get(state.get("current"))

    def episodes(self):
        return list(self._read("publication.json", {}).get("episodes", {}).values())

    def papers(self):
        return self._read("papers.json", [])

    def run(self, run_id: str):
        return self._read("runs.json", {}).get(run_id)
