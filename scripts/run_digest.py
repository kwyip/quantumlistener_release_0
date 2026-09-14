#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.agents.orchestrator import WeeklyEditor
from app.domain.models import Paper
from app.ingestion.arxiv import exact_week_window, fetch_quant_ph_papers
from app.repositories.local import LocalRepository


def load_fixture(run_id: str) -> list[Paper]:
    retrieved = datetime.now(UTC)
    return [
        Paper.model_validate({**item, "ingestion_run_id": run_id, "retrieved_at": retrieved})
        for item in json.loads(Path("data/fixtures/quant-ph-week.json").read_text())
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--aws", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume-from")
    parser.add_argument("--reference", default="2026-09-10T12:00:00+00:00")
    args = parser.parse_args()
    start, end = exact_week_window(datetime.fromisoformat(args.reference))
    papers = (
        load_fixture("fixture-run")
        if args.fixture
        else fetch_quant_ph_papers(start, end, "manual-run")
    )
    report = WeeklyEditor(LocalRepository(), aws=args.aws).run(
        papers, start, end, approve=args.approve, dry_run=args.dry_run, resume_from=args.resume_from
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
