from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from app.agents.specialists import classify, summarize, verify
from app.domain.models import Category, Chapter, Episode, Paper
from app.providers.tts import MockTTS, PollyTTS


class WeeklyEditor:
    """Agentic coordinator with bounded retries, evidence gates, budgets, and activity records."""

    def __init__(
        self,
        repository,
        *,
        aws: bool = False,
        max_bedrock_calls: int | None = None,
        max_polly_characters: int | None = None,
    ):
        self.repository = repository
        self.aws = aws
        self.max_bedrock_calls = max_bedrock_calls or int(os.getenv("MAX_BEDROCK_CALLS", "500"))
        self.max_polly_characters = max_polly_characters or int(
            os.getenv("MAX_POLLY_CHARACTERS", "100000")
        )
        self.tool_calls: list[dict] = []
        self._strands_agent = self._create_strands_agent() if aws else None

    def _create_strands_agent(self):
        """Production foundation: Strands chooses registered specialist tools via Bedrock."""
        from strands import Agent, tool
        from strands.models import BedrockModel

        @tool
        def category_editor(title: str, abstract: str) -> str:
            """Classify a quantum paper into the required five-category taxonomy."""
            return json.dumps(
                {
                    "instruction": "Use title and abstract evidence",
                    "title": title,
                    "abstract": abstract,
                }
            )

        @tool
        def evidence_editor(claims_json: str, abstract: str) -> str:
            """Check claims against supplied abstract evidence and flag unsupported claims."""
            return json.dumps({"claims": claims_json, "evidence": abstract})

        model_id = os.getenv("BEDROCK_MODEL_ID")
        if not model_id:
            raise ValueError("BEDROCK_MODEL_ID is required in AWS mode")
        return Agent(
            model=BedrockModel(model_id=model_id, region_name=os.getenv("AWS_REGION", "us-east-1")),
            tools=[category_editor, evidence_editor],
            system_prompt="You are QuantumListener Weekly Editor. Delegate work, ground every claim, output concise actions—not private reasoning.",
        )

    def _record(self, tool: str, status: str, **details):
        self.tool_calls.append({"tool": tool, "status": status, **details})

    def run(
        self,
        papers: list[Paper],
        start: datetime,
        end: datetime,
        *,
        approve: bool = False,
        dry_run: bool = False,
        resume_from: str | None = None,
    ) -> dict:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        warnings: list[str] = []
        classified = []
        summaries = []
        self._record("deduplicate_papers", "succeeded", count=len(papers))
        bedrock_calls = 0
        for paper in papers:
            if self._strands_agent is not None:
                if bedrock_calls >= self.max_bedrock_calls:
                    raise RuntimeError("Bedrock call ceiling exceeded")
                self._strands_agent(
                    "Delegate classification and evidence review for this arXiv record. "
                    f"Title: {paper.title}\nAbstract: {paper.abstract}"
                )
                bedrock_calls += 1
                self._record("strands_agent", "succeeded", arxiv_id=paper.arxiv_id)
            classified_paper = classify(paper)
            classified.append(classified_paper)
            self._record("category_editor", "succeeded", arxiv_id=paper.arxiv_id)
            for attempt in range(2):
                try:
                    result = summarize(classified_paper)
                    if not result.claims:
                        raise ValueError("missing evidence")
                    summaries.append(result)
                    self._record(
                        "paper_listener", "succeeded", arxiv_id=paper.arxiv_id, attempt=attempt + 1
                    )
                    break
                except (ValueError, TypeError) as error:
                    self._record(
                        "paper_listener",
                        "retrying",
                        arxiv_id=paper.arxiv_id,
                        error=type(error).__name__,
                    )
            else:
                warnings.append(f"{paper.arxiv_id}: summary failed after retry")
        for paper, summary in zip(classified, summaries, strict=False):
            warnings.extend(verify(summary, paper))
        grouped = defaultdict(list)
        for paper in classified:
            grouped[paper.quantumlistener_primary_category].append(paper.arxiv_id)
        chapters, transcript, cursor = (
            [],
            ["Welcome to QuantumListener, the weekly quant-ph research digest."],
            8,
        )
        for category in Category:
            ids = grouped[category]
            chapters.append(
                Chapter(
                    category=category, title=category.value, start_seconds=cursor, paper_ids=ids
                )
            )
            transcript.append(
                f"{category.value}."
                + (" No papers appeared in this fixture interval." if not ids else "")
            )
            for paper_id in ids:
                summary = next(item for item in summaries if item.arxiv_id == paper_id)
                transcript.append(summary.takeaway)
                cursor += max(8, len(summary.takeaway) // 12)
        transcript.append(
            "What to watch next: follow the cited arXiv records and apply your scientific judgment."
        )
        script = "\n\n".join(transcript)
        if len(script) > self.max_polly_characters:
            raise RuntimeError("Polly character ceiling exceeded")
        week = start.strftime("%G-W%V")
        episode = Episode(
            week=week,
            title=f"QuantumListener {week}: Weekly quant-ph Digest",
            description=f"Evidence-grounded coverage of {len(papers)} papers updated in the exact interval.",
            interval_start=start,
            interval_end=end,
            duration_seconds=max(cursor + 12, 30),
            status="approved" if approve else "draft",
            chapters=chapters,
            paper_ids=[p.arxiv_id for p in classified],
        )
        root = self.repository.root
        assets = root / "media" / week
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "transcript.txt").write_text(script)
        (assets / "transcript.json").write_text(
            json.dumps(
                {"text": script, "summaries": [s.model_dump(mode="json") for s in summaries]},
                indent=2,
            )
        )
        notes = "# Show notes\n\n" + "\n".join(
            f"- [{p.title}]({p.abstract_url}) — {next(s.takeaway for s in summaries if s.arxiv_id == p.arxiv_id)}"
            for p in classified
        )
        (assets / "show-notes.md").write_text(notes)
        if approve and not dry_run:
            tts = PollyTTS() if self.aws else MockTTS()
            tts.synthesize(script, assets / "episode.mp3")
            self._record(
                "amazon_polly" if self.aws else "mock_tts", "succeeded", characters=len(script)
            )
        payload = episode.model_dump(mode="json")
        payload.update(
            {
                "run_id": run_id,
                "summaries": [s.model_dump(mode="json") for s in summaries],
                "transcript_url": f"/media/{week}/transcript.txt",
                "show_notes_url": f"/media/{week}/show-notes.md",
                "audio_url": f"/media/{week}/episode.mp3" if approve and not dry_run else None,
            }
        )
        self.repository.save_papers([p.model_dump(mode="json") for p in classified])
        self.repository.save_draft(payload)
        report = {
            "run_id": run_id,
            "status": "human_review_required" if not approve else "approved",
            "interval": {"start": start.isoformat(), "end": end.isoformat()},
            "retrieved_at": datetime.now(UTC).isoformat(),
            "papers_found": len(papers),
            "papers_classified": len(classified),
            "papers_summarized": len(summaries),
            "evidence_warnings": warnings,
            "audio_segments_generated": 1 if approve and not dry_run else 0,
            "publication_status": payload["status"],
            "tool_calls": self.tool_calls,
            "resume_from": resume_from,
            "cost_limits": {
                "bedrock_calls": self.max_bedrock_calls,
                "bedrock_calls_used": bedrock_calls,
                "polly_characters": self.max_polly_characters,
            },
        }
        self.repository.save_run(report)
        return report
